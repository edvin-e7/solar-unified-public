"""AutoApplicator — apply approved improvements (git commit + version bump)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from services import atomic_fs

REPO_ROOT = Path(__file__).parent.parent.parent


class AutoApplicator:
    """Executor role: apply improvements to code (git commit + version bump)."""

    name = "auto_applicator"

    def apply_improvement(
        self, improvement: dict[str, Any], verification: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply an improvement if verified by consensus.

        Args:
            improvement: {target, enhancement, ...}
            verification: {verified: bool, consensus: float, ...}

        Returns:
            {
                "applied": bool,
                "commit": str (commit hash) or None,
                "reason": str
            }
        """
        if not verification.get("verified"):
            return {
                "applied": False,
                "commit": None,
                "reason": f"Not verified (consensus {verification.get('consensus', 0):.0%} < 0.75)",
            }

        target_path = REPO_ROOT / improvement.get("target", "")
        if not target_path.exists():
            return {
                "applied": False,
                "commit": None,
                "reason": f"Target file not found: {improvement.get('target')}",
            }

        # Only auto-apply prompt refinements (safe)
        imp_type = improvement.get("type", "")
        if imp_type not in ("prompt_refinement", "config_change"):
            return {
                "applied": False,
                "commit": None,
                "reason": f"Type '{imp_type}' requires manual review",
            }

        # For prompts: bump version in frontmatter
        if improvement.get("target", "").endswith(".md"):
            try:
                result = self._bump_prompt_version(target_path, improvement)
                if result["success"]:
                    commit_hash = self._commit_change(target_path, improvement)
                    return {
                        "applied": True,
                        "commit": commit_hash,
                        "reason": f"Applied: {improvement.get('enhancement', '')[:50]}...",
                    }
                else:
                    return {"applied": False, "commit": None, "reason": result["error"]}
            except Exception as e:
                from error_logger import log_error
                log_error(
                    "executor-auto-applicator-apply",
                    e,
                    context={"target": str(target_path), "improvement_type": improvement.get("type")},
                )
                return {"applied": False, "commit": None, "reason": f"Failed: {e}"}

        return {
            "applied": False,
            "commit": None,
            "reason": "Only prompt files auto-applied currently",
        }

    def _bump_prompt_version(
        self, path: Path, improvement: dict[str, Any]
    ) -> dict[str, Any]:
        """Bump version in prompt frontmatter, update enhancement note."""
        try:
            content = path.read_text(encoding="utf-8")

            # Extract frontmatter
            match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
            if not match:
                return {"success": False, "error": "No frontmatter found"}

            frontmatter_str = match.group(1)
            body = match.group(2)

            # Parse version
            version_match = re.search(r"^version:\s*(.+?)$", frontmatter_str, re.MULTILINE)
            if not version_match:
                return {"success": False, "error": "No version in frontmatter"}

            old_version = version_match.group(1).strip()
            try:
                major, minor = map(int, old_version.split("."))
                new_version = f"{major}.{minor + 1}"
            except (ValueError, IndexError):
                new_version = f"{old_version}.1"

            # Update frontmatter
            new_frontmatter = re.sub(
                rf"^version:\s*{re.escape(old_version)}$",
                f"version: {new_version}",
                frontmatter_str,
                flags=re.MULTILINE,
            )

            # Prepend enhancement note to body
            enhancement_note = f"<!-- Auto-improved v{old_version}→{new_version}: {improvement.get('enhancement', '')[:80]}... -->\n"
            new_content = f"---\n{new_frontmatter}\n---\n\n{enhancement_note}{body}"

            atomic_fs.write_text_atomic(path, new_content)
            return {"success": True, "old_version": old_version, "new_version": new_version}
        except Exception as e:
            from error_logger import log_error
            log_error(
                "executor-auto-applicator-bump-version",
                e,
                context={"path": str(path)},
            )
            return {"success": False, "error": str(e)}

    def _commit_change(self, path: Path, improvement: dict[str, Any]) -> str | None:
        """Commit change to git."""
        try:
            rel_path = path.relative_to(REPO_ROOT)
            enhancement = improvement.get("enhancement", "")[:60]

            subprocess.run(
                ["git", "add", str(rel_path)],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )

            commit_msg = f"Auto-improve: {rel_path} ({enhancement}...)"

            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            # Extract commit hash from output
            match = re.search(r"\[main ([a-f0-9]+)\]", result.stdout)
            return match.group(1) if match else None

        except subprocess.CalledProcessError as e:
            raise Exception(f"Git commit failed: {e.stderr}")
