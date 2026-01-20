#!/usr/bin/env python3
"""
SessionStart hook for Cloudflare Engineer plugin.

Detects Cloudflare Worker projects and announces plugin capabilities.
Uses fingerprint caching to avoid repeated analysis.

Exit codes:
  0 = success (always - SessionStart hooks should not block)
"""

import json
import os
import sys
import hashlib
from pathlib import Path


def get_project_fingerprint(project_root: Path) -> str:
    """Generate fingerprint from key config files."""
    files_to_hash = [
        "wrangler.toml",
        "wrangler.jsonc",
        "wrangler.json",
        "package.json",
    ]

    content_parts = []
    for filename in files_to_hash:
        filepath = project_root / filename
        if filepath.exists():
            try:
                content_parts.append(f"{filename}:{filepath.stat().st_mtime}")
            except OSError:
                pass

    if not content_parts:
        return ""

    return hashlib.md5("|".join(content_parts).encode()).hexdigest()[:12]


def get_cache_path(project_root: Path) -> Path:
    """Get path to fingerprint cache file."""
    cache_dir = project_root / ".claude"
    return cache_dir / ".cf-session-cache"


def is_cached(project_root: Path, fingerprint: str) -> bool:
    """Check if this fingerprint was already processed."""
    cache_path = get_cache_path(project_root)
    if not cache_path.exists():
        return False

    try:
        cached = cache_path.read_text().strip()
        return cached == fingerprint
    except OSError:
        return False


def update_cache(project_root: Path, fingerprint: str) -> None:
    """Update fingerprint cache."""
    cache_path = get_cache_path(project_root)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(fingerprint)
    except OSError:
        pass  # Cache update failure is non-fatal


def detect_cf_project(project_root: Path) -> dict:
    """Detect Cloudflare project characteristics."""
    result = {
        "is_cf_project": False,
        "config_file": None,
        "has_d1": False,
        "has_r2": False,
        "has_kv": False,
        "has_queues": False,
        "has_do": False,
        "has_ai": False,
        "has_vectorize": False,
        "has_workflows": False,
        "worker_count": 0,
        "is_monorepo": False,
    }

    # Check for wrangler config
    for config_name in ["wrangler.toml", "wrangler.jsonc", "wrangler.json"]:
        config_path = project_root / config_name
        if config_path.exists():
            result["is_cf_project"] = True
            result["config_file"] = config_name

            try:
                content = config_path.read_text()
                content_lower = content.lower()

                # Detect bindings
                result["has_d1"] = "d1_database" in content_lower or '"d1"' in content_lower
                result["has_r2"] = "r2_bucket" in content_lower or '"r2"' in content_lower
                result["has_kv"] = "kv_namespace" in content_lower
                result["has_queues"] = "queues" in content_lower
                result["has_do"] = "durable_object" in content_lower
                result["has_ai"] = "[ai]" in content_lower or '"ai"' in content_lower
                result["has_vectorize"] = "vectorize" in content_lower
                result["has_workflows"] = "workflow" in content_lower
            except OSError:
                pass

            break

    # Check for monorepo (multiple wrangler configs in subdirs)
    if result["is_cf_project"]:
        worker_dirs = list(project_root.glob("**/wrangler.toml"))
        worker_dirs += list(project_root.glob("**/wrangler.jsonc"))
        # Filter out node_modules
        worker_dirs = [d for d in worker_dirs if "node_modules" not in str(d)]
        result["worker_count"] = len(set(d.parent for d in worker_dirs))
        result["is_monorepo"] = result["worker_count"] > 1

    return result


def format_capabilities_message(detection: dict) -> str:
    """Format short capabilities announcement."""
    if not detection["is_cf_project"]:
        return ""

    lines = ["🔶 **Cloudflare Engineer plugin active**"]

    # Build binding summary
    bindings = []
    if detection["has_d1"]:
        bindings.append("D1")
    if detection["has_r2"]:
        bindings.append("R2")
    if detection["has_kv"]:
        bindings.append("KV")
    if detection["has_queues"]:
        bindings.append("Queues")
    if detection["has_do"]:
        bindings.append("Durable Objects")
    if detection["has_ai"]:
        bindings.append("Workers AI")
    if detection["has_vectorize"]:
        bindings.append("Vectorize")
    if detection["has_workflows"]:
        bindings.append("Workflows")

    if bindings:
        lines.append(f"   Detected: {', '.join(bindings)}")

    if detection["is_monorepo"]:
        lines.append(f"   Monorepo: {detection['worker_count']} workers")

    # Suggest cf-audit for comprehensive analysis
    lines.append("   Run `/cf-audit` for architecture review and cost analysis")

    return "\n".join(lines)


def main():
    """Main entry point."""
    # Get working directory from environment or use current
    cwd = os.environ.get("PWD", os.getcwd())
    project_root = Path(cwd)

    # Generate fingerprint
    fingerprint = get_project_fingerprint(project_root)

    # Skip if no CF project indicators
    if not fingerprint:
        sys.exit(0)

    # Check cache to avoid repeated announcements
    if is_cached(project_root, fingerprint):
        sys.exit(0)

    # Detect project characteristics
    detection = detect_cf_project(project_root)

    if not detection["is_cf_project"]:
        sys.exit(0)

    # Update cache
    update_cache(project_root, fingerprint)

    # Output capabilities message
    message = format_capabilities_message(detection)
    if message:
        print(message)

    sys.exit(0)


if __name__ == "__main__":
    main()
