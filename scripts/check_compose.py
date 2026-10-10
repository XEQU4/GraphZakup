"""Validate the single Compose file using synthetic, collection-off environments."""

import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"


def render(*, overrides=None, project="iz2-config-check"):
    # Never inherit source credentials, profiles or collection flags from .env.
    variable_names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", COMPOSE_FILE.read_text(encoding="utf-8")))
    environment = {key: value for key, value in os.environ.items()
                   if key not in variable_names and not key.startswith("COMPOSE_")}
    values = {
        "SECRET_KEY": "synthetic-compose-check-only-never-use-in-deployment",
        "DB_PASSWORD": "synthetic-compose-password",
    }
    values.update(overrides or {})
    with TemporaryDirectory() as directory:
        env_path = Path(directory) / "synthetic.env"
        env_path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
        command = ["docker", "compose", "--env-file", str(env_path)]
        if project:
            command.extend(["-p", project])
        command.extend(["config", "--format", "json"])
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=30, check=False)
    if result.returncode:
        raise RuntimeError("Synthetic Compose normalization failed; check Docker Compose installation/version.")
    return json.loads(result.stdout)


def check_common(configuration, *, provider="template", timeout=90, output_tokens=1024):
    services = configuration["services"]
    provider_options = [{key: value for key, value in services[name]["environment"].items()
                         if key.startswith("AI_")} for name in ("web", "worker", "ai-worker", "beat")]
    assert all(options == provider_options[0] for options in provider_options), "Producer/worker AI options differ"
    assert provider_options[0]["AI_PROVIDER"] == provider
    assert provider_options[0]["AI_TIMEOUT_SECONDS"] == str(timeout)
    assert provider_options[0]["AI_MAX_OUTPUT_TOKENS"] == str(output_tokens)
    assert provider_options[0]["AI_ALLOW_PAID"] == "false"
    assert "ollama-init" not in services["worker"]["depends_on"], "Ingestion waits for a model download"
    for name in ("web", "worker", "ai-worker", "beat"):
        for flag in ("ENABLE_SCHEDULED_IMPORT", "ENABLE_SCHEDULED_KGD", "ENABLE_KGD_CHECKS", "ENABLE_BACKGROUND_AI"):
            assert services[name]["environment"][flag] == "false", f"Collection/generation enabled: {name}:{flag}"
    assert services["web"]["ports"][0]["host_ip"] == "127.0.0.1", "Web bypasses the public edge"
    for name in ("db", "redis", "ollama", "ollama-gpu"):
        if name in services:
            assert not services[name].get("ports"), f"Unexpected published {name} port"
    for name, service in services.items():
        assert int(service["mem_limit"]) > 0 and float(service["cpus"]) > 0, f"Missing bounds: {name}"
        assert service["logging"]["options"]["max-size"] and service["logging"]["options"]["max-file"]
    assert services["web"]["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=64m,mode=1777"]


def check_model(configuration, runtime):
    services = configuration["services"]
    other = "ollama" if runtime == "ollama-gpu" else "ollama-gpu"
    assert runtime in services and other not in services
    assert "ollama-init" in services["ai-worker"]["depends_on"]
    assert runtime in services["ollama-init"]["depends_on"]
    assert services["ollama-init"]["environment"]["OLLAMA_HOST"] == f"http://{runtime}:11434"
    assert services["web"]["environment"]["AI_OLLAMA_BASE_URL"] == f"http://{runtime}:11434"
    if runtime == "ollama-gpu":
        assert services[runtime]["deploy"]["resources"]["reservations"]["devices"][0]["count"] == 1
    else:
        assert not services[runtime].get("deploy"), "CPU runtime requires a GPU"


def check_https(configuration):
    services = configuration["services"]
    web, proxy = services["web"], services["proxy"]
    assert proxy["tmpfs"] == ["/tmp:size=16m,mode=1777"]
    for flag in ("TRUST_PROXY_SSL_HEADER", "SECURE_SSL_REDIRECT", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE"):
        assert web["environment"][flag] == proxy["environment"][flag] == "true"
    assert web["environment"]["AUTH_TRUSTED_PROXY_CIDRS"] == proxy["networks"]["edge"]["ipv4_address"] + "/32"
    assert web["networks"]["edge"]["ipv4_address"] != proxy["networks"]["edge"]["ipv4_address"]
    assert proxy["entrypoint"] == ["/bin/sh", "/etc/caddy/start-proxy.sh"]


def main():
    base = render(project=None)
    check_common(base)
    assert base["name"] == "governmentprocurementgraph", "Legacy volume namespace changed"
    assert not {"ollama", "ollama-gpu", "ollama-init", "proxy"}.intersection(base["services"])
    for volume in ("postgres17_data", "redis_data"):
        assert base["volumes"][volume]["name"] == "governmentprocurementgraph_" + volume
    ai_values = {"AI_PROVIDER": "ollama", "AI_MODEL": "qwen3:4b", "AI_TIMEOUT_SECONDS": "180",
                 "AI_MAX_OUTPUT_TOKENS": "2048"}
    https_values = {
        "SITE_DOMAIN": "iz2.example.test", "ACME_EMAIL": "operator@example.test",
        "ALLOWED_HOSTS": "iz2.example.test,localhost,127.0.0.1",
        "CSRF_TRUSTED_ORIGINS": "https://iz2.example.test", "TRUST_PROXY_SSL_HEADER": "true",
        "SECURE_SSL_REDIRECT": "true", "SESSION_COOKIE_SECURE": "true", "CSRF_COOKIE_SECURE": "true",
        "AUTH_TRUSTED_PROXY_CIDRS": "172.30.254.2/32",
    }
    count = 1
    for https in (False, True):
        for profile, runtime in (("local-ai", "ollama"), ("local-ai-gpu", "ollama-gpu")):
            configuration = render(overrides={
                **ai_values, **(https_values if https else {}),
                "COMPOSE_PROFILES": profile + (",https" if https else ""),
                "DOCKER_OLLAMA_BASE_URL": f"http://{runtime}:11434",
                "AI_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            })
            check_common(configuration, provider="ollama", timeout=180, output_tokens=2048)
            check_model(configuration, runtime)
            if https:
                check_https(configuration)
            count += 1
    server = render(overrides={**https_values, "COMPOSE_PROFILES": "https"})
    check_common(server)
    check_https(server)
    override = render(overrides={**ai_values, "COMPOSE_PROFILES": "local-ai",
                                "AI_TIMEOUT_SECONDS": "150", "AI_MAX_OUTPUT_TOKENS": "1536",
                                "WEB_BIND_ADDRESS": "0.0.0.0"})
    check_common(override, provider="ollama", timeout=150, output_tokens=1536)
    check_model(override, "ollama")
    # This normalizes without required-variable interpolation; the proxy's own
    # startup guard rejects incomplete HTTPS settings before Caddy can listen.
    incomplete_https = render(overrides={"COMPOSE_PROFILES": "https"})
    assert incomplete_https["services"]["proxy"]["environment"]["SITE_DOMAIN"] == ""
    print(f"{count + 3} synthetic Compose configurations passed: one file, safe defaults, CPU/GPU, HTTPS and coherent jobs.")


if __name__ == "__main__":
    main()
