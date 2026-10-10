"""Create a private, collection-off Compose environment without replacing .env."""

import argparse
import os
from pathlib import Path
import re
import secrets

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def private_output_path(path: Path) -> Path:
    root = PROJECT_ROOT.resolve()
    candidate = Path(os.path.abspath(path))
    resolved = candidate.resolve()
    if candidate == root / ".env" or resolved == root / ".env":
        raise ValueError("Keep the native .env unchanged; choose .env.docker or another private file.")
    private_root_env = (
        candidate.parent == root
        and re.fullmatch(r"\.env\.[A-Za-z0-9][A-Za-z0-9._-]*", candidate.name)
        and candidate.name.lower() != ".env.example"
        and resolved == candidate
    )
    # Validate the resolved target against the real repository, not a symlinked
    # artifacts directory. O_EXCL below also refuses an existing leaf symlink.
    private_artifact = (
        candidate.is_relative_to(root / "artifacts")
        and resolved.is_relative_to(root / "artifacts")
        and resolved != root / "artifacts"
    )
    if not (private_root_env or private_artifact):
        raise ValueError("Output must be a root .env.* file (except .env.example) or an ignored artifacts child.")
    return candidate


def prepare(path: Path, project: str, *, ai="template", domain="", acme_email="") -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project):
        raise ValueError("Project must use lowercase letters, digits, underscores or hyphens.")
    if ai not in {"template", "cpu", "gpu"}:
        raise ValueError("AI runtime must be template, cpu or gpu.")
    domain = domain.lower()
    if bool(domain) != bool(acme_email):
        raise ValueError("HTTPS requires both --domain and --acme-email.")
    if domain and (len(domain) > 253 or not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", domain
    )):
        raise ValueError("Domain must be a plain DNS hostname without a scheme, path or port.")
    if acme_email and not re.fullmatch(r"[A-Za-z0-9.!_+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", acme_email):
        raise ValueError("ACME email must be a plain email address.")
    root = PROJECT_ROOT.resolve()
    path = private_output_path(path)
    content = (root / ".env.example").read_text(encoding="utf-8")
    replacements = {
        "SECRET_KEY": secrets.token_urlsafe(50),
        "DB_PASSWORD": secrets.token_urlsafe(36),
        "COMPOSE_PROJECT_NAME": project,
        # The Docker CPU model rehearsal exceeded the native 90-second budget.
        "AI_TIMEOUT_SECONDS": "180",
        "AI_MAX_OUTPUT_TOKENS": "2048",
        "AI_PROVIDER": "template" if ai == "template" else "ollama",
        "AI_MODEL": "" if ai == "template" else "qwen3:4b",
        "DOCKER_OLLAMA_BASE_URL": "http://ollama-gpu:11434" if ai == "gpu" else "http://ollama:11434",
        "COMPOSE_PROFILES": ",".join(
            (["local-ai-gpu" if ai == "gpu" else "local-ai"] if ai != "template" else [])
            + (["https"] if domain else [])
        ),
    }
    if domain:
        replacements.update({
            "SITE_DOMAIN": domain,
            "ACME_EMAIL": acme_email,
            "ALLOWED_HOSTS": f"{domain},localhost,127.0.0.1",
            "CSRF_TRUSTED_ORIGINS": f"https://{domain}",
            "TRUST_PROXY_SSL_HEADER": "true",
            "SECURE_SSL_REDIRECT": "true",
            "SESSION_COOKIE_SECURE": "true",
            "CSRF_COOKIE_SECURE": "true",
            "AUTH_TRUSTED_PROXY_CIDRS": "172.30.254.2/32",
        })
    for key, value in replacements.items():
        content = re.sub(rf"(?m)^{key}=.*$", f"{key}={value}", content)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env.docker"))
    parser.add_argument("--project", required=True, help="New project namespace; preserve it for later runs.")
    parser.add_argument("--ai", choices=("template", "cpu", "gpu"), default="template",
                        help="Optional local model runtime. GPU requires the NVIDIA Container Toolkit.")
    parser.add_argument("--domain", default="", help="Enable the HTTPS profile for this DNS hostname.")
    parser.add_argument("--acme-email", default="", help="Certificate contact, required with --domain.")
    args = parser.parse_args()
    try:
        prepare(args.output, args.project, ai=args.ai, domain=args.domain, acme_email=args.acme_email)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Environment not created: {exc}\n")
    print(f"Created {args.output}. Secrets were generated locally; collection and paid AI remain disabled.")


if __name__ == "__main__":
    main()
