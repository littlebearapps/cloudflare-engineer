#!/usr/bin/env python3
"""
PostToolUse hook for Cloudflare Engineer plugin.

Verifies deployment success and suggests follow-up actions after wrangler deploy.
Uses tiered verification: stdout parsing first, then suggests MCP observability.

Exit codes:
  0 = success (PostToolUse hooks should not block)

Input (JSON via stdin):
{
  "tool_name": "Bash",
  "tool_input": {"command": "..."},
  "tool_response": {"stdout": "...", "stderr": "...", "exit_code": 0}
}
"""

import json
import re
import sys
from typing import Optional


def is_wrangler_deploy(command: str) -> bool:
    """Check if command is a wrangler deploy."""
    if not command:
        return False

    # Match various deploy patterns
    patterns = [
        r"wrangler\s+deploy",
        r"wrangler\s+publish",  # Legacy
        r"npx\s+wrangler\s+deploy",
        r"pnpm\s+(?:exec\s+)?wrangler\s+deploy",
        r"bunx?\s+wrangler\s+deploy",
    ]

    command_lower = command.lower()
    return any(re.search(p, command_lower) for p in patterns)


def extract_deployment_url(stdout: str) -> Optional[str]:
    """Extract deployed URL from wrangler output."""
    if not stdout:
        return None

    # Pattern: "Published <name> (<version>)\n  https://worker.domain.workers.dev"
    # or "Deployed <name> to https://..."
    patterns = [
        r"https://[\w.-]+\.workers\.dev",
        r"https://[\w.-]+\.pages\.dev",
        r"Published.*?\n\s+(https://[^\s]+)",
        r"Deployed.*?to\s+(https://[^\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, stdout)
        if match:
            # Return the captured group if exists, otherwise full match
            return match.group(1) if match.lastindex else match.group(0)

    return None


def extract_worker_name(stdout: str, command: str) -> Optional[str]:
    """Extract worker name from output or command."""
    if stdout:
        # "Published my-worker (1.0.0)"
        match = re.search(r"Published\s+(\S+)", stdout)
        if match:
            return match.group(1)

        # "Deployed my-worker to..."
        match = re.search(r"Deployed\s+(\S+)", stdout)
        if match:
            return match.group(1)

    # Try from command: wrangler deploy --name my-worker
    if command:
        match = re.search(r"--name[=\s]+(\S+)", command)
        if match:
            return match.group(1)

    return None


def check_deployment_success(exit_code: int, stdout: str, stderr: str) -> dict:
    """Analyse deployment result."""
    result = {
        "success": False,
        "url": None,
        "worker_name": None,
        "warnings": [],
        "errors": [],
    }

    # Check exit code first
    if exit_code != 0:
        result["errors"].append(f"Deploy failed with exit code {exit_code}")
        if stderr:
            # Extract meaningful error
            error_lines = [l for l in stderr.split("\n") if l.strip()]
            if error_lines:
                result["errors"].append(error_lines[0][:200])
        return result

    result["success"] = True
    result["url"] = extract_deployment_url(stdout)

    # Check for warnings in output
    combined = (stdout or "") + (stderr or "")
    warning_patterns = [
        (r"deprecat", "Deprecated feature detected"),
        (r"compatibility.*date.*old", "Compatibility date may need updating"),
        (r"no routes", "No routes configured - worker may not be accessible"),
        (r"secret.*not.*found", "Missing secret binding"),
    ]

    for pattern, message in warning_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            result["warnings"].append(message)

    return result


def format_verification_message(result: dict, worker_name: Optional[str]) -> str:
    """Format post-deploy verification message."""
    lines = []

    if result["success"]:
        name_str = f" ({worker_name})" if worker_name else ""
        lines.append(f"✅ **Deployment successful**{name_str}")

        if result["url"]:
            lines.append(f"   URL: {result['url']}")

        # Suggest verification
        lines.append("")
        lines.append("📊 **Suggested next steps:**")
        lines.append("   • Check Worker logs via Cloudflare dashboard or observability MCP")
        lines.append("   • Run `/cf-audit --validate` to verify against production metrics")

        if result["warnings"]:
            lines.append("")
            lines.append("⚠️ **Warnings:**")
            for w in result["warnings"]:
                lines.append(f"   • {w}")
    else:
        lines.append("❌ **Deployment failed**")
        for err in result["errors"]:
            lines.append(f"   • {err}")
        lines.append("")
        lines.append("💡 **Troubleshooting:**")
        lines.append("   • Check wrangler.toml syntax")
        lines.append("   • Verify all secrets are configured: `wrangler secret list`")
        lines.append("   • Run `/cf-audit` to check for configuration issues")

    return "\n".join(lines)


def main():
    """Main entry point."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_response = input_data.get("tool_response", {})

    # Only process Bash commands
    if tool_name != "Bash":
        sys.exit(0)

    command = tool_input.get("command", "")

    # Only process wrangler deploy commands
    if not is_wrangler_deploy(command):
        sys.exit(0)

    # Extract response details
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")
    exit_code = tool_response.get("exit_code", 0)

    # Analyse deployment
    result = check_deployment_success(exit_code, stdout, stderr)
    worker_name = extract_worker_name(stdout, command)

    # Output verification message
    message = format_verification_message(result, worker_name)
    print(message)

    sys.exit(0)


if __name__ == "__main__":
    main()
