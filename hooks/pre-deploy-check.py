#!/usr/bin/env python3
"""
Pre-Deploy Check Hook for Cloudflare Engineer Plugin

This hook intercepts `wrangler deploy` commands and validates the wrangler
configuration for security, resilience, cost, and PERFORMANCE issues before
allowing deployment.

Includes Performance Budgeter for bundle size limits:
- Free tier: 1MB compressed
- Standard tier: 10MB compressed

Exit codes:
- 0: Allow deployment
- 2: Block deployment (critical issues found)
"""

import json
import os
import re
import sys
from pathlib import Path
import subprocess


def debug_log(message: str) -> None:
    """Log debug messages to temp file."""
    try:
        with open("/tmp/cf-pre-deploy-check.log", "a") as f:
            f.write(f"{message}\n")
    except:
        pass


def is_wrangler_deploy(command: str) -> bool:
    """Check if command is a wrangler deploy command."""
    # Match various forms of wrangler deploy
    patterns = [
        r"\bwrangler\s+deploy\b",
        r"\bnpx\s+wrangler\s+deploy\b",
        r"\bpnpm\s+.*wrangler\s+deploy\b",
        r"\byarn\s+.*wrangler\s+deploy\b",
    ]
    for pattern in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def find_wrangler_config(working_dir: str) -> str | None:
    """Find wrangler.toml or wrangler.jsonc in working directory."""
    for filename in ["wrangler.jsonc", "wrangler.toml", "wrangler.json"]:
        path = Path(working_dir) / filename
        if path.exists():
            return str(path)
    return None


def parse_jsonc(content: str) -> dict:
    """Parse JSONC (JSON with comments) content."""
    # Process character by character to handle comments correctly
    result = []
    i = 0
    n = len(content)
    in_string = False
    escape = False

    while i < n:
        char = content[i]

        if escape:
            result.append(char)
            escape = False
            i += 1
            continue

        if char == "\\" and in_string:
            result.append(char)
            escape = True
            i += 1
            continue

        if char == '"':
            result.append(char)
            in_string = not in_string
            i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        # Not in string - check for comments
        if char == "/" and i + 1 < n:
            next_char = content[i + 1]
            if next_char == "/":
                # Single-line comment - skip to end of line
                while i < n and content[i] != "\n":
                    i += 1
                continue
            elif next_char == "*":
                # Multi-line comment - skip to */
                i += 2
                while i < n - 1:
                    if content[i] == "*" and content[i + 1] == "/":
                        i += 2
                        break
                    i += 1
                continue

        result.append(char)
        i += 1

    content = "".join(result)

    # Remove trailing commas (multiple passes for nested structures)
    for _ in range(5):
        content = re.sub(r",\s*([}\]])", r"\1", content)

    return json.loads(content)


def parse_toml_simple(content: str) -> dict:
    """Simple TOML parser for wrangler configs."""
    # This is a simplified parser - for production, use tomllib
    result = {}
    current_section = result

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Section header
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            # Handle nested sections like [vars]
            if "." in section_name:
                parts = section_name.split(".")
                current_section = result
                for part in parts:
                    if part not in current_section:
                        current_section[part] = {}
                    current_section = current_section[part]
            else:
                if section_name not in result:
                    result[section_name] = {}
                current_section = result[section_name]
            continue

        # Key-value pair
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            current_section[key] = value

    return result


def load_wrangler_config(config_path: str) -> dict | None:
    """Load and parse wrangler config file."""
    try:
        with open(config_path, "r") as f:
            content = f.read()

        if config_path.endswith(".toml"):
            return parse_toml_simple(content)
        else:
            return parse_jsonc(content)
    except Exception as e:
        debug_log(f"Failed to parse config: {e}")
        return None


def check_secrets_in_vars(config: dict) -> list[dict]:
    """Check for secrets exposed in vars."""
    issues = []
    vars_section = config.get("vars", {})

    secret_patterns = [
        r"API_KEY",
        r"SECRET",
        r"PASSWORD",
        r"TOKEN",
        r"PRIVATE",
        r"CREDENTIAL",
    ]

    for key, value in vars_section.items():
        for pattern in secret_patterns:
            if re.search(pattern, key, re.IGNORECASE):
                # Check if value looks like an actual secret (not a placeholder)
                if value and len(str(value)) > 8 and not value.startswith("${"):
                    issues.append({
                        "id": "SEC001",
                        "severity": "CRITICAL",
                        "message": f"Potential secret in plaintext: vars.{key}",
                        "fix": f"Use: wrangler secret put {key}",
                    })

    return issues


def check_observability(config: dict) -> list[dict]:
    """Check for missing observability config."""
    issues = []

    observability = config.get("observability", {})
    logs = observability.get("logs", {})

    if not logs.get("enabled"):
        issues.append({
            "id": "PERF004",
            "severity": "LOW",
            "message": "Observability logs not enabled",
            "fix": 'Add: "observability": { "logs": { "enabled": true } }',
        })

    return issues


def check_smart_placement(config: dict) -> list[dict]:
    """Check for missing Smart Placement."""
    issues = []

    placement = config.get("placement", {})
    if placement.get("mode") != "smart":
        issues.append({
            "id": "PERF001",
            "severity": "LOW",
            "message": "Smart Placement not enabled",
            "fix": 'Add: "placement": { "mode": "smart" }',
        })

    return issues


def check_bundle_size(working_dir: str, config: dict) -> list[dict]:
    """Check estimated bundle size against tier limits (Performance Budgeter)."""
    issues = []

    # Try to find the main entry file
    main_entry = config.get("main", "src/index.ts")
    entry_path = Path(working_dir) / main_entry

    # Check if dist/src directory exists for size estimation
    src_dir = Path(working_dir) / "src"
    dist_dir = Path(working_dir) / "dist"

    estimated_size_kb = 0

    # Try to estimate bundle size from source
    for check_dir in [dist_dir, src_dir]:
        if check_dir.exists():
            try:
                # Sum up all .js, .ts, .mjs files
                total_size = 0
                for ext in ["*.js", "*.ts", "*.mjs", "*.json"]:
                    for f in check_dir.rglob(ext):
                        if "node_modules" not in str(f):
                            total_size += f.stat().st_size
                estimated_size_kb = total_size / 1024
                break
            except Exception:
                pass

    # Check node_modules for heavy dependencies
    node_modules = Path(working_dir) / "node_modules"
    heavy_deps = []
    if node_modules.exists():
        # Known heavy packages that inflate bundle size
        heavy_packages = {
            "moment": 300,  # ~300KB
            "lodash": 500,  # ~500KB if not tree-shaken
            "aws-sdk": 2000,  # ~2MB
            "@aws-sdk": 1000,  # ~1MB per service
            "sharp": 5000,  # Native - won't work anyway
        }
        for pkg, size in heavy_packages.items():
            pkg_path = node_modules / pkg
            if pkg_path.exists():
                heavy_deps.append((pkg, size))
                estimated_size_kb += size

    # Bundle size limits
    FREE_LIMIT_KB = 1024  # 1MB
    STANDARD_LIMIT_KB = 10240  # 10MB

    # Determine tier from config (default to free for safety)
    usage_model = config.get("usage_model", "bundled")  # "bundled" = free, "unbound" = paid

    if estimated_size_kb > 0:
        if estimated_size_kb > STANDARD_LIMIT_KB:
            issues.append({
                "id": "PERF005",
                "severity": "CRITICAL",
                "message": f"Estimated bundle size ~{estimated_size_kb:.0f}KB exceeds 10MB limit",
                "fix": "Reduce bundle size: remove unused deps, use tree-shaking, split into service bindings",
            })
        elif estimated_size_kb > FREE_LIMIT_KB:
            if usage_model == "bundled":
                issues.append({
                    "id": "PERF005",
                    "severity": "HIGH",
                    "message": f"Estimated bundle size ~{estimated_size_kb:.0f}KB exceeds Free tier 1MB limit",
                    "fix": 'Either reduce bundle or add "usage_model": "standard" for 10MB limit',
                })
            else:
                issues.append({
                    "id": "PERF005",
                    "severity": "LOW",
                    "message": f"Bundle size ~{estimated_size_kb:.0f}KB (within Standard tier limit)",
                    "fix": "Consider optimization for faster cold starts",
                })
        elif estimated_size_kb > FREE_LIMIT_KB * 0.8:  # 80% warning
            issues.append({
                "id": "PERF005",
                "severity": "LOW",
                "message": f"Bundle size ~{estimated_size_kb:.0f}KB approaching 1MB Free tier limit",
                "fix": "Monitor bundle growth; consider code splitting",
            })

    # Warn about specific heavy dependencies
    for pkg, size in heavy_deps:
        if pkg == "sharp":
            issues.append({
                "id": "PERF006",
                "severity": "HIGH",
                "message": f"Package '{pkg}' uses native bindings - won't work on Workers",
                "fix": "Use Cloudflare Images API instead",
            })
        elif pkg in ["aws-sdk", "@aws-sdk"]:
            issues.append({
                "id": "PERF006",
                "severity": "MEDIUM",
                "message": f"Package '{pkg}' is ~{size}KB - very heavy for Workers",
                "fix": "Use R2 S3-compatible API or specific lightweight clients",
            })

    return issues


def check_queue_dlq_comprehensive(config: dict) -> list[dict]:
    """Enhanced DLQ check with more context."""
    issues = []
    queues = config.get("queues", {})
    consumers = queues.get("consumers", [])
    producers = queues.get("producers", [])

    # Build list of all queue names for cross-reference
    all_queues = set()
    for consumer in consumers:
        if isinstance(consumer, dict):
            all_queues.add(consumer.get("queue", ""))
            dlq = consumer.get("dead_letter_queue", "")
            if dlq:
                all_queues.add(dlq)
    for producer in producers:
        if isinstance(producer, dict):
            all_queues.add(producer.get("queue", ""))

    for i, consumer in enumerate(consumers):
        if isinstance(consumer, dict):
            queue_name = consumer.get("queue", f"consumer[{i}]")
            # Skip DLQ check for queues that ARE dead letter queues
            is_dlq = queue_name.endswith("-dlq") or "dead_letter" in queue_name.lower()

            if "dead_letter_queue" not in consumer and not is_dlq:
                dlq_suggestion = f"{queue_name}-dlq"
                issues.append({
                    "id": "RES001",
                    "severity": "HIGH",
                    "message": f"Queue '{queue_name}' missing dead_letter_queue",
                    "fix": f'Add: "dead_letter_queue": "{dlq_suggestion}"',
                })

            # Check for high retries (cost multiplier)
            max_retries = consumer.get("max_retries", 3)
            if max_retries > 2:
                issues.append({
                    "id": "COST001",
                    "severity": "MEDIUM",
                    "message": f"Queue '{queue_name}' has max_retries={max_retries} (each retry costs $0.40/M)",
                    "fix": 'Set max_retries to 1-2 if consumer is idempotent',
                })

            # Check for missing max_concurrency (resilience)
            if "max_concurrency" not in consumer:
                issues.append({
                    "id": "RES002",
                    "severity": "MEDIUM",
                    "message": f"Queue '{queue_name}' has no max_concurrency limit",
                    "fix": 'Add "max_concurrency": 10 to prevent overload',
                })

    return issues


def run_audit(config: dict, working_dir: str = "") -> list[dict]:
    """Run all audit checks on config."""
    issues = []
    issues.extend(check_secrets_in_vars(config))
    issues.extend(check_queue_dlq_comprehensive(config))  # Enhanced DLQ check
    issues.extend(check_observability(config))
    issues.extend(check_smart_placement(config))

    # Performance Budgeter - check bundle size
    if working_dir:
        issues.extend(check_bundle_size(working_dir, config))

    return issues


def format_issues(issues: list[dict]) -> str:
    """Format issues for display."""
    if not issues:
        return ""

    lines = ["", "⚠️  PRE-DEPLOY VALIDATION ISSUES FOUND", "=" * 45, ""]

    by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for issue in issues:
        severity = issue.get("severity", "MEDIUM")
        by_severity.setdefault(severity, []).append(issue)

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        severity_issues = by_severity.get(severity, [])
        if severity_issues:
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}[severity]
            lines.append(f"{emoji} {severity}")
            for issue in severity_issues:
                lines.append(f"   [{issue['id']}] {issue['message']}")
                lines.append(f"   Fix: {issue['fix']}")
                lines.append("")

    return "\n".join(lines)


def main():
    """Main hook function."""
    # Read input from stdin
    try:
        raw_input = sys.stdin.read()
        input_data = json.loads(raw_input)
    except json.JSONDecodeError as e:
        debug_log(f"JSON decode error: {e}")
        sys.exit(0)  # Allow if we can't parse

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only check Bash commands
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")

    # Only check wrangler deploy commands
    if not is_wrangler_deploy(command):
        sys.exit(0)

    debug_log(f"Intercepted wrangler deploy: {command}")

    # Get working directory from environment
    working_dir = os.environ.get("PWD", os.getcwd())

    # Find wrangler config
    config_path = find_wrangler_config(working_dir)
    if not config_path:
        # No config found - might be in a subdirectory, allow
        debug_log(f"No wrangler config found in {working_dir}")
        sys.exit(0)

    debug_log(f"Found config: {config_path}")

    # Load and parse config
    config = load_wrangler_config(config_path)
    if not config:
        debug_log("Failed to parse config")
        sys.exit(0)  # Allow if we can't parse

    # Run audit with working directory for bundle size check
    issues = run_audit(config, working_dir)

    if not issues:
        debug_log("No issues found, allowing deploy")
        sys.exit(0)

    # Check severity
    critical_count = sum(1 for i in issues if i.get("severity") == "CRITICAL")
    high_count = sum(1 for i in issues if i.get("severity") == "HIGH")

    # Format and output issues
    output = format_issues(issues)

    if critical_count > 0:
        output += f"\n🛑 DEPLOYMENT BLOCKED: {critical_count} critical issue(s) found.\n"
        output += "Fix critical issues before deploying.\n"
        print(output, file=sys.stderr)
        sys.exit(2)  # Block deployment
    elif high_count > 0:
        output += f"\n⚠️  WARNING: {high_count} high priority issue(s) found.\n"
        output += "Consider fixing before deploying to production.\n"
        print(output, file=sys.stderr)
        sys.exit(0)  # Warn but allow
    else:
        output += "\nℹ️  Minor issues found. Deployment allowed.\n"
        print(output, file=sys.stderr)
        sys.exit(0)  # Allow


if __name__ == "__main__":
    main()
