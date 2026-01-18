#!/usr/bin/env python3
"""
Pre-Deploy Check Hook for Cloudflare Engineer Plugin

This hook intercepts `wrangler deploy` commands and validates the wrangler
configuration for security, resilience, cost, PERFORMANCE, and LOOP SAFETY
issues before allowing deployment.

Includes:
- Performance Budgeter for bundle size limits (1MB free, 10MB standard)
- Loop-Sensitive Resource Audit (billing safety)
- Cost Simulation for detected loop patterns

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


def extract_suppressions(content: str) -> dict[int, set[str]]:
    """Extract @pre-deploy-ok suppression comments from file content.

    Supports formats:
    - // @pre-deploy-ok LOOP005
    - // @pre-deploy-ok LOOP005 LOOP002
    - /* @pre-deploy-ok LOOP005 */
    - // @pre-deploy-ok (suppresses all rules on next line)

    Returns dict mapping line numbers to set of suppressed rule IDs.
    A None in the set means all rules are suppressed for that line.
    """
    suppressions = {}
    lines = content.split('\n')

    # Pattern to match suppression comments
    suppression_pattern = re.compile(
        r'(?://|/\*)\s*@pre-deploy-ok(?:\s+([A-Z0-9_\s]+))?(?:\s*\*/)?',
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        match = suppression_pattern.search(line)
        if match:
            rules_str = match.group(1)
            if rules_str:
                # Specific rules listed
                rules = set(r.strip().upper() for r in rules_str.split() if r.strip())
            else:
                # No rules = suppress all
                rules = {None}

            # Suppression applies to current line and next line
            # (supports both inline and line-before styles)
            suppressions[i + 1] = suppressions.get(i + 1, set()) | rules
            suppressions[i + 2] = suppressions.get(i + 2, set()) | rules

    return suppressions


def is_suppressed(suppressions: dict[int, set[str]], line_num: int, rule_id: str) -> bool:
    """Check if a rule is suppressed at a given line number."""
    if line_num not in suppressions:
        return False
    rules = suppressions[line_num]
    # None means all rules are suppressed
    return None in rules or rule_id.upper() in rules


def load_ignore_file(working_dir: str) -> dict[str, set[str]]:
    """Load .pre-deploy-ignore file for project-level rule suppression.

    File format:
    ```
    # Comment lines start with #
    RES001              # Suppress RES001 globally
    COST001             # Suppress COST001 globally
    RES001:my-queue     # Suppress RES001 only for 'my-queue'
    LOOP001:*           # Same as just LOOP001
    ```

    Returns dict mapping rule IDs to set of contexts (empty set = global suppression).
    """
    ignore_rules: dict[str, set[str]] = {}
    ignore_path = Path(working_dir) / ".pre-deploy-ignore"

    if not ignore_path.exists():
        return ignore_rules

    try:
        content = ignore_path.read_text()
        for line in content.split('\n'):
            # Strip comments and whitespace
            line = line.split('#')[0].strip()
            if not line:
                continue

            # Parse rule:context format
            if ':' in line:
                rule_id, context = line.split(':', 1)
                rule_id = rule_id.strip().upper()
                context = context.strip()
                if context == '*':
                    context = ''  # Treat * as global
            else:
                rule_id = line.strip().upper()
                context = ''

            if rule_id:
                if rule_id not in ignore_rules:
                    ignore_rules[rule_id] = set()
                if context:
                    ignore_rules[rule_id].add(context.lower())
                else:
                    # Empty string means global suppression
                    ignore_rules[rule_id].add('')

        debug_log(f"Loaded .pre-deploy-ignore: {ignore_rules}")
    except Exception as e:
        debug_log(f"Failed to load .pre-deploy-ignore: {e}")

    return ignore_rules


def is_rule_ignored(ignore_rules: dict[str, set[str]], rule_id: str, context: str = "") -> bool:
    """Check if a rule is ignored by .pre-deploy-ignore file.

    Args:
        ignore_rules: Dict from load_ignore_file()
        rule_id: The rule ID to check (e.g., "RES001")
        context: Optional context like queue name, bucket name, etc.

    Returns:
        True if the rule should be suppressed
    """
    rule_id = rule_id.upper()
    if rule_id not in ignore_rules:
        return False

    contexts = ignore_rules[rule_id]
    # Empty string in contexts means global suppression
    if '' in contexts:
        return True
    # Check if specific context is suppressed
    if context and context.lower() in contexts:
        return True
    return False


def filter_ignored_issues(issues: list[dict], ignore_rules: dict[str, set[str]]) -> list[dict]:
    """Filter out issues that are suppressed by .pre-deploy-ignore file."""
    if not ignore_rules:
        return issues

    filtered = []
    for issue in issues:
        rule_id = issue.get("id", "")
        message = issue.get("message", "")

        # Extract context from message if present (e.g., queue name, bucket name)
        context = ""
        # Try to extract queue name
        queue_match = re.search(r"Queue '([^']+)'", message)
        if queue_match:
            context = queue_match.group(1)
        # Try to extract bucket name
        bucket_match = re.search(r"bucket '([^']+)'", message)
        if bucket_match:
            context = bucket_match.group(1)

        if is_rule_ignored(ignore_rules, rule_id, context):
            debug_log(f"Ignored {rule_id} (context: {context or 'global'})")
            continue

        filtered.append(issue)

    return filtered


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
    """Simple TOML parser for wrangler configs.

    Handles both regular sections [section] and array-of-tables [[section]]
    which is common in wrangler.toml for r2_buckets, kv_namespaces, etc.
    """
    # This is a simplified parser - for production, use tomllib
    result = {}
    current_section = result
    current_array_table = None  # Track current array-of-tables name

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Array-of-tables header [[section]] - must check before single bracket
        if line.startswith("[[") and line.endswith("]]"):
            section_name = line[2:-2].strip()
            # Handle dotted names like [[queues.consumers]]
            if "." in section_name:
                parts = section_name.split(".")
                parent = result
                for part in parts[:-1]:
                    if part not in parent:
                        parent[part] = {}
                    parent = parent[part]
                array_key = parts[-1]
                if array_key not in parent:
                    parent[array_key] = []
                new_entry = {}
                parent[array_key].append(new_entry)
                current_section = new_entry
            else:
                # Simple array-of-tables
                if section_name not in result:
                    result[section_name] = []
                new_entry = {}
                result[section_name].append(new_entry)
                current_section = new_entry
            current_array_table = section_name
            continue

        # Regular section header [section]
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            current_array_table = None  # Reset array table tracking
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
            # Handle boolean values
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            # Handle numeric values
            elif value.isdigit():
                value = int(value)
            elif re.match(r'^-?\d+$', value):
                value = int(value)
            elif re.match(r'^-?\d+\.\d+$', value):
                value = float(value)
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
                    "fix": 'Either reduce bundle or add "usage_model": "unbound" for 10MB limit',
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


def check_cpu_limits(config: dict) -> list[dict]:
    """Check for missing CPU time limits (loop protection)."""
    issues = []

    limits = config.get("limits", {})
    cpu_ms = limits.get("cpu_ms")

    if cpu_ms is None:
        issues.append({
            "id": "LOOP001",
            "severity": "MEDIUM",
            "message": "No cpu_ms limit configured - loops could run unchecked",
            "fix": 'Add "limits": { "cpu_ms": 100 } to kill runaway loops',
        })
    elif cpu_ms > 10000:
        issues.append({
            "id": "LOOP001",
            "severity": "LOW",
            "message": f"High cpu_ms limit ({cpu_ms}ms) - consider lower for API endpoints",
            "fix": "Use 100-500ms for APIs, 5000-10000ms for heavy processing",
        })

    return issues


def check_deprecated_site_config(config: dict) -> list[dict]:
    """Check for deprecated [site] or pages_build_output_dir configuration (NEW v1.4.0)."""
    issues = []

    # Check for deprecated [site] block
    if "site" in config:
        issues.append({
            "id": "ARCH001",
            "severity": "MEDIUM",
            "message": "Deprecated [site] configuration detected - use [assets] instead",
            "fix": 'Replace [site] with "assets": { "directory": "./dist", "html_handling": "auto-trailing-slash" }',
        })

    # Check for deprecated pages_build_output_dir
    if "pages_build_output_dir" in config:
        issues.append({
            "id": "ARCH001",
            "severity": "MEDIUM",
            "message": "Deprecated pages_build_output_dir detected - use [assets] instead",
            "fix": 'Replace with "assets": { "directory": "./dist", "not_found_handling": "single-page-application" }',
        })

    return issues


def check_r2_infrequent_access(working_dir: str, config: dict) -> list[dict]:
    """Check for R2 Infrequent Access storage usage with reads (NEW v1.4.0)."""
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    # Check if there are R2 buckets configured
    r2_buckets = config.get("r2_buckets", [])
    if not r2_buckets:
        return issues

    # Scan for .get() calls on R2 buckets - could indicate IA trap
    # This is a heuristic - we can't know storage class from code
    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # Extract suppressions from this file
            suppressions = extract_suppressions(content)

            # Find .get() calls with line numbers
            get_pattern = re.compile(r'\.get\s*\([^)]+\)')
            for match in get_pattern.finditer(content):
                line_num = content[:match.start()].count('\n') + 1

                # Check if this issue is suppressed
                if is_suppressed(suppressions, line_num, "BUDGET009"):
                    debug_log(f"Suppressed BUDGET009 at {relative_path}:{line_num}")
                    continue

                # Check if Cache API is used
                has_cache = 'caches.default' in content or 'cache.match' in content.lower()
                has_cache_control = 'Cache-Control' in content or 'cacheControl' in content

                if not has_cache and not has_cache_control:
                    # Only warn if bucket name suggests IA (cold, archive, backup, ia)
                    for bucket in r2_buckets:
                        bucket_name = bucket.get("bucket_name", "").lower()
                        if any(kw in bucket_name for kw in ["cold", "archive", "backup", "ia", "infrequent"]):
                            issues.append({
                                "id": "BUDGET009",
                                "severity": "HIGH",
                                "message": f"R2 bucket '{bucket_name}' may use Infrequent Access - reads at {relative_path}:{line_num} could incur $9+ minimum charge",
                                "fix": "Use Standard storage for any bucket with read operations. IA is only safe for write-only cold storage.",
                            })
                            break

        except Exception:
            pass

    # Deduplicate - only one warning per bucket
    seen_buckets = set()
    unique_issues = []
    for issue in issues:
        # Extract bucket name from message
        bucket_match = re.search(r"bucket '([^']+)'", issue["message"])
        if bucket_match:
            bucket = bucket_match.group(1)
            if bucket not in seen_buckets:
                seen_buckets.add(bucket)
                unique_issues.append(issue)
        else:
            unique_issues.append(issue)

    return unique_issues


def check_d1_query_patterns(working_dir: str) -> list[dict]:
    """Check for D1 query anti-patterns (NEW v1.5.0)."""
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # Extract suppressions from this file
            suppressions = extract_suppressions(content)

            # QUERY001: SELECT * without LIMIT
            select_star_pattern = re.compile(
                r'SELECT\s+\*\s+FROM\s+\w+(?:\s+WHERE[^;]*)?(?!\s+LIMIT)',
                re.IGNORECASE | re.MULTILINE
            )
            for match in select_star_pattern.finditer(content):
                line_num = content[:match.start()].count('\n') + 1

                if is_suppressed(suppressions, line_num, "QUERY001"):
                    debug_log(f"Suppressed QUERY001 at {relative_path}:{line_num}")
                    continue

                # Check if LIMIT exists later in the same statement
                stmt_end = content.find(';', match.end())
                if stmt_end != -1:
                    rest = content[match.end():stmt_end].upper()
                    if 'LIMIT' in rest:
                        continue  # LIMIT found later

                issues.append({
                    "id": "QUERY001",
                    "severity": "HIGH",
                    "message": f"SELECT * without LIMIT at {relative_path}:{line_num} - potential row read explosion",
                    "fix": "Add LIMIT clause or use pagination (TRAP-D1-005)",
                })

            # QUERY005: Drizzle .all() or .findMany() without .limit()
            drizzle_patterns = [
                (r'\.select\(\)[^;]*\.from\([^)]+\)(?![^;]*\.limit\()', "select().from() without .limit()"),
                (r'\.findMany\(\s*\{(?![^}]*limit:)', "findMany() without limit option"),
            ]
            for pattern, desc in drizzle_patterns:
                drizzle_regex = re.compile(pattern, re.MULTILINE | re.DOTALL)
                for match in drizzle_regex.finditer(content):
                    line_num = content[:match.start()].count('\n') + 1

                    if is_suppressed(suppressions, line_num, "QUERY005"):
                        debug_log(f"Suppressed QUERY005 at {relative_path}:{line_num}")
                        continue

                    issues.append({
                        "id": "QUERY005",
                        "severity": "HIGH",
                        "message": f"Drizzle {desc} at {relative_path}:{line_num} - unbounded result set",
                        "fix": "Add .limit() to prevent row read explosion (TRAP-D1-006)",
                    })

        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue["id"], issue["message"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return unique_issues


def check_r2_cache_patterns(working_dir: str) -> list[dict]:
    """Check for R2.get() without cache wrapper (NEW v1.5.0)."""
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # Extract suppressions from this file
            suppressions = extract_suppressions(content)

            # Check if file uses R2 .get() but doesn't use cache
            has_r2_get = re.search(r'\.\s*get\s*\([^)]+\)', content)
            has_cache_api = 'caches.default' in content or 'cache.match' in content

            if has_r2_get and not has_cache_api:
                # Find R2 get patterns on hot paths (routes)
                route_patterns = [
                    r'app\.(get|post)\s*\([^,]+,\s*async[^}]+\.get\s*\(',
                    r'router\.(get|post)\s*\([^,]+,\s*async[^}]+\.get\s*\(',
                    r'fetch\s*\([^)]*request[^)]*\)[^}]*\.get\s*\(',
                ]
                for pattern in route_patterns:
                    route_regex = re.compile(pattern, re.MULTILINE | re.DOTALL)
                    for match in route_regex.finditer(content):
                        line_num = content[:match.start()].count('\n') + 1

                        if is_suppressed(suppressions, line_num, "R2002"):
                            debug_log(f"Suppressed R2002 at {relative_path}:{line_num}")
                            continue

                        issues.append({
                            "id": "R2002",
                            "severity": "MEDIUM",
                            "message": f"R2.get() on request path without cache at {relative_path}:{line_num}",
                            "fix": "Wrap with caches.default for edge caching (TRAP-R2-006)",
                        })
                        break  # One warning per file

        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue["id"], issue["message"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return unique_issues


def check_observability_extended(config: dict, working_dir: str) -> list[dict]:
    """Extended observability checks (NEW v1.5.0)."""
    issues = []

    observability = config.get("observability", {})
    logs = observability.get("logs", {})

    # OBS001: Observability not enabled (already covered by PERF004, just return)
    if not logs.get("enabled"):
        return issues

    # OBS002: Logs enabled but no export destination indication
    # We can't detect dashboard destinations, but we can check for SDK usage
    src_dir = Path(working_dir) / "src" if working_dir else None
    has_logging_sdk = False

    if src_dir and src_dir.exists():
        for ts_file in src_dir.rglob("*.ts"):
            if "node_modules" in str(ts_file):
                continue
            try:
                content = ts_file.read_text()
                # Check for common logging SDK imports
                if any(sdk in content for sdk in [
                    '@logtail/',
                    'axiom',
                    'pino',
                    'winston',
                    'tail_consumers',  # Tail worker config
                ]):
                    has_logging_sdk = True
                    break
            except Exception:
                pass

    # Check for tail_consumers in config (indicates tail worker export)
    has_tail_consumers = bool(config.get("tail_consumers"))

    if not has_logging_sdk and not has_tail_consumers:
        issues.append({
            "id": "OBS002",
            "severity": "MEDIUM",
            "message": "Logs enabled but no export destination detected",
            "fix": "Configure Axiom/Better Stack export or add tail_consumers for log forwarding",
        })

    # OBS003: High sampling rate on potentially high-volume worker
    head_sampling_rate = logs.get("head_sampling_rate", 1)
    if head_sampling_rate >= 1:
        # Check if this looks like a high-volume worker (queue consumer or multiple routes)
        has_queue_consumer = bool(config.get("queues", {}).get("consumers"))
        routes = config.get("routes", [])
        has_multiple_routes = len(routes) > 1 or any(
            '*' in str(route.get("pattern", "")) for route in routes if isinstance(route, dict)
        )

        if has_queue_consumer or has_multiple_routes:
            issues.append({
                "id": "OBS003",
                "severity": "INFO",
                "message": f"100% sampling rate on worker with queue/routes - may generate high log volume",
                "fix": "Consider head_sampling_rate: 0.1-0.5 for production (see /cf-logs --analyze)",
            })

    return issues


def scan_source_for_loop_patterns(working_dir: str) -> list[dict]:
    """Scan source code for loop-sensitive patterns that could cause billing issues."""
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    # Patterns to detect
    loop_patterns = [
        # D1 queries in loops
        (
            r'(for|while|forEach|\.map)\s*\([^)]*\)[^{]*\{[^}]*\.(prepare|run|first|all)\s*\(',
            "LOOP002",
            "CRITICAL",
            "D1 query inside loop - N+1 cost explosion",
            "Use db.batch() for bulk operations (TRAP-D1-001)",
        ),
        # R2 writes in loops
        (
            r'(for|while|forEach|\.map)\s*\([^)]*\)[^{]*\{[^}]*\.put\s*\(',
            "LOOP003",
            "HIGH",
            "R2 write inside loop - Class A operation explosion",
            "Buffer writes or use multipart upload (TRAP-R2-001)",
        ),
        # setInterval without clear pattern
        (
            r'setInterval\s*\([^)]+\)',
            "LOOP004",
            "MEDIUM",
            "setInterval detected - verify termination condition exists",
            "Use state.storage.setAlarm() in Durable Objects for hibernation",
        ),
        # Unbounded while loops
        (
            r'while\s*\(\s*true\s*\)|for\s*\(\s*;\s*;\s*\)',
            "LOOP007",
            "CRITICAL",
            "Unbounded loop detected - could run until CPU limit",
            "Add explicit break condition and iteration limit",
        ),
        # Self-fetch patterns
        (
            r'fetch\s*\(\s*request\.url',
            "LOOP005",
            "CRITICAL",
            "Worker fetching own URL - potential infinite recursion",
            "Add X-Recursion-Depth middleware (see loop-breaker skill)",
        ),
        # Recursive function without depth
        (
            r'(async\s+)?function\s+(\w+)[^{]*\{[^}]*\2\s*\(',
            "LOOP005",
            "HIGH",
            "Recursive function detected - verify depth limit exists",
            "Add maxDepth parameter and check before recursing",
        ),
    ]

    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # Extract suppressions from this file
            suppressions = extract_suppressions(content)

            for pattern, rule_id, severity, message, fix in loop_patterns:
                matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
                for match in matches:
                    # Get line number
                    line_num = content[:match.start()].count('\n') + 1

                    # Check if this issue is suppressed
                    if is_suppressed(suppressions, line_num, rule_id):
                        debug_log(f"Suppressed {rule_id} at {relative_path}:{line_num}")
                        continue

                    # For recursive function detection (LOOP005), check for depth limiting
                    if rule_id == "LOOP005" and "Recursive function" in message:
                        # Get context around the match to check for depth limiting
                        match_text = match.group(0)
                        # Check if function has depth/maxDepth parameter or checks depth
                        if re.search(r'(depth|maxDepth|level|count)\s*[<>=!]', match_text):
                            continue  # Has depth check, skip
                        # Check surrounding context (function signature and early body)
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 200)
                        context = content[start:end]
                        if re.search(r'(depth|maxDepth|level)\s*[:<>=]|if\s*\(\s*(depth|maxDepth|level)', context, re.IGNORECASE):
                            continue  # Has depth limiting, skip

                    issues.append({
                        "id": rule_id,
                        "severity": severity,
                        "message": f"{message} at {relative_path}:{line_num}",
                        "fix": fix,
                    })
        except Exception:
            pass

    # Deduplicate by rule and file location (full message includes file:line)
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue["id"], issue["message"])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return unique_issues


def estimate_loop_cost(working_dir: str, config: dict) -> list[dict]:
    """Estimate potential cost impact of detected loop patterns."""
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    # Cost rates (per million)
    COSTS = {
        "d1_write": 1.00,  # $1/M writes
        "d1_read": 0.25 / 1000,  # $0.25/B reads = $0.00025/M
        "r2_class_a": 4.50,  # $4.50/M writes
        "r2_class_b": 0.36,  # $0.36/M reads
        "kv_write": 5.00,  # $5/M writes
        "queue_msg": 0.40,  # $0.40/M messages
    }

    estimated_costs = []

    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # D1 writes in loops
            d1_loop_matches = re.findall(
                r'(for|while|forEach)\s*\([^)]*\)[^{]*\{[^}]*\.(run|batch)\s*\(',
                content,
                re.MULTILINE | re.DOTALL
            )
            if d1_loop_matches:
                estimated_costs.append({
                    "pattern": "D1 writes in loop",
                    "file": str(relative_path),
                    "estimate": "If loop runs 1000× on 1000 requests: ~$1.00/day",
                    "formula": "iterations × requests × $1/M",
                })

            # R2 writes in loops
            r2_loop_matches = re.findall(
                r'(for|while|forEach)\s*\([^)]*\)[^{]*\.put\s*\(',
                content,
                re.MULTILINE | re.DOTALL
            )
            if r2_loop_matches:
                estimated_costs.append({
                    "pattern": "R2 writes in loop",
                    "file": str(relative_path),
                    "estimate": "If loop runs 1000× on 1000 requests: ~$4.50/day",
                    "formula": "iterations × requests × $4.50/M",
                })

        except Exception:
            pass

    if estimated_costs:
        cost_summary = "\n".join(
            f"  - {c['pattern']} in {c['file']}: {c['estimate']}"
            for c in estimated_costs[:3]  # Limit to top 3
        )
        issues.append({
            "id": "COST_SIM",
            "severity": "INFO",
            "message": f"Loop Cost Simulation:\n{cost_summary}",
            "fix": "Review loop patterns and add batching/buffering",
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

    # Load .pre-deploy-ignore file for project-level suppressions
    ignore_rules = load_ignore_file(working_dir) if working_dir else {}

    # Security checks
    issues.extend(check_secrets_in_vars(config))

    # Resilience checks
    issues.extend(check_queue_dlq_comprehensive(config))  # Enhanced DLQ check

    # Performance checks
    issues.extend(check_observability(config))
    issues.extend(check_smart_placement(config))

    # Loop Safety checks (Billing Protection)
    issues.extend(check_cpu_limits(config))

    # Architecture checks (NEW v1.4.0)
    issues.extend(check_deprecated_site_config(config))

    if working_dir:
        # Performance Budgeter - check bundle size
        issues.extend(check_bundle_size(working_dir, config))

        # Loop-Sensitive Resource Audit
        issues.extend(scan_source_for_loop_patterns(working_dir))

        # Cost Simulation for detected patterns
        issues.extend(estimate_loop_cost(working_dir, config))

        # R2 Infrequent Access trap detection (NEW v1.4.0)
        issues.extend(check_r2_infrequent_access(working_dir, config))

        # D1 Query pattern checks (NEW v1.5.0)
        issues.extend(check_d1_query_patterns(working_dir))

        # R2 cache pattern checks (NEW v1.5.0)
        issues.extend(check_r2_cache_patterns(working_dir))

        # Extended observability checks (NEW v1.5.0)
        issues.extend(check_observability_extended(config, working_dir))

    # Apply .pre-deploy-ignore suppressions
    issues = filter_ignored_issues(issues, ignore_rules)

    return issues


def format_issues(issues: list[dict]) -> str:
    """Format issues for display."""
    if not issues:
        return ""

    lines = ["", "⚠️  PRE-DEPLOY VALIDATION ISSUES FOUND", "=" * 45, ""]

    # Separate loop safety issues for special section
    loop_issues = [i for i in issues if i.get("id", "").startswith("LOOP")]
    other_issues = [i for i in issues if not i.get("id", "").startswith("LOOP") and i.get("id") != "COST_SIM"]
    cost_sim = [i for i in issues if i.get("id") == "COST_SIM"]

    # Format loop safety section if present
    if loop_issues:
        lines.append("🔄 LOOP SAFETY (Billing Protection)")
        lines.append("-" * 40)
        for issue in loop_issues:
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(issue["severity"], "⚪")
            lines.append(f"   {emoji} [{issue['id']}] {issue['message']}")
            lines.append(f"      Fix: {issue['fix']}")
        lines.append("")

    # Format cost simulation if present
    if cost_sim:
        lines.append("💰 COST SIMULATION")
        lines.append("-" * 40)
        for issue in cost_sim:
            lines.append(f"   {issue['message']}")
            lines.append(f"   Recommendation: {issue['fix']}")
        lines.append("")

    # Format other issues by severity
    by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}
    for issue in other_issues:
        severity = issue.get("severity", "MEDIUM")
        by_severity.setdefault(severity, []).append(issue)

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        severity_issues = by_severity.get(severity, [])
        if severity_issues:
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "ℹ️"}[severity]
            lines.append(f"{emoji} {severity}")
            for issue in severity_issues:
                lines.append(f"   [{issue['id']}] {issue['message']}")
                lines.append(f"   Fix: {issue['fix']}")
                lines.append("")

    return "\n".join(lines)


def main():
    """Main hook function."""
    # Check for environment variable bypass
    if os.environ.get("SKIP_PREDEPLOY_CHECK", "").lower() in ("1", "true", "yes"):
        debug_log("SKIP_PREDEPLOY_CHECK is set, bypassing validation")
        sys.exit(0)

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

    # Check severity (LOOP issues with CRITICAL are especially dangerous)
    critical_count = sum(1 for i in issues if i.get("severity") == "CRITICAL")
    high_count = sum(1 for i in issues if i.get("severity") == "HIGH")
    loop_critical = sum(1 for i in issues if i.get("id", "").startswith("LOOP") and i.get("severity") == "CRITICAL")

    # Format and output issues
    output = format_issues(issues)

    # Add suppression hint
    suppression_hint = "\n💡 To suppress known-safe patterns:\n"
    suppression_hint += "   • Inline: // @pre-deploy-ok RULE_ID\n"
    suppression_hint += "   • Project: Add rule to .pre-deploy-ignore file\n"
    suppression_hint += "   • Emergency: SKIP_PREDEPLOY_CHECK=1 npx wrangler deploy\n"

    if critical_count > 0:
        output += f"\n🛑 DEPLOYMENT BLOCKED: {critical_count} critical issue(s) found.\n"
        if loop_critical > 0:
            output += f"   ⚠️  {loop_critical} loop safety issue(s) could cause billing explosion.\n"
        output += "Fix critical issues before deploying.\n"
        output += suppression_hint
        print(output, file=sys.stderr)
        sys.exit(2)  # Block deployment
    elif high_count > 0:
        output += f"\n⚠️  WARNING: {high_count} high priority issue(s) found.\n"
        output += "Consider fixing before deploying to production.\n"
        output += suppression_hint
        print(output, file=sys.stderr)
        sys.exit(0)  # Warn but allow
    else:
        output += "\nℹ️  Minor issues found. Deployment allowed.\n"
        print(output, file=sys.stderr)
        sys.exit(0)  # Allow


if __name__ == "__main__":
    main()
