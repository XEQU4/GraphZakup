"""Source archives include maintained UI/deployment inputs without local output."""
from pathlib import Path
import tempfile
from unittest import TestCase

from scripts.capture_baseline import source_paths


class SourceInventoryTests(TestCase):
    def test_source_inventory_covers_frontend_and_deployment_without_generated_data(self):
        included = {
            "apps/core/views.py", "frontend/src/App.tsx", "frontend/package-lock.json",
            "frontend/vite.config.ts", "deploy/Caddyfile", "ARTICLE_CONTEXT.md",
            ".env.example", "static/js/api-docs.js", "test.py",
        }
        excluded = {
            "frontend/node_modules/package/index.js", "frontend/coverage/index.html",
            "frontend/.vite/cache.json", "frontend/.cache/transform.js",
            "frontend/tsconfig.app.tsbuildinfo", "frontend/.env.local",
            "static/frontend/assets/index.js", "apps/core/__pycache__/views.pyc",
            "deploy/server.key", "deploy/server.pem", "deploy/source.dump",
            "next-app/src/app/page.tsx", "artifacts/report.json", ".env",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in included | excluded:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic inventory fixture", encoding="utf-8")
            result = [path.relative_to(root).as_posix() for path in source_paths(root)]
        self.assertEqual(result, sorted(included))

    def test_generated_dependency_trees_are_pruned_before_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("frontend/node_modules", "frontend/coverage", "static/frontend"):
                (root / name).mkdir(parents=True)
            (root / "frontend/src").mkdir()
            (root / "frontend/src/main.tsx").write_text("synthetic fixture", encoding="utf-8")
            visited = []
            import os
            from unittest.mock import patch
            original_walk = os.walk

            def traced_walk(*args, **kwargs):
                for current, directories, files in original_walk(*args, **kwargs):
                    visited.append(Path(current).relative_to(root).as_posix())
                    yield current, directories, files

            with patch("scripts.capture_baseline.os.walk", traced_walk):
                source_paths(root)
        self.assertIn("frontend/src", visited)
        self.assertNotIn("frontend/node_modules", visited)
        self.assertNotIn("frontend/coverage", visited)
        self.assertNotIn("static/frontend", visited)
