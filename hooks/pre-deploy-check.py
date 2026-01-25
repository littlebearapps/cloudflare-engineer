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


def load_ignore_file(working_dir: str) -> tuple[dict[str, set[str]], set[str]]:
    """Load .pre-deploy-ignore file for project-level rule configuration.

    File format:
    ```
    # Comment lines start with #

    # SUPPRESS rules (hide warnings)
    RES001              # Suppress RES001 globally
    COST001             # Suppress COST001 globally
    RES001:my-queue     # Suppress RES001 only for 'my-queue'
    LOOP001:*           # Same as just LOOP001

    # BLOCKING rules (opt-in to exit 2)
    !SEC001             # Make SEC001 block deployment
    !LOOP005            # Make LOOP005 block deployment
    ```

    Returns tuple of:
    - ignore_rules: dict mapping rule IDs to set of contexts (empty set = global suppression)
    - blocking_rules: set of rule IDs that should block deployment
    """
    ignore_rules: dict[str, set[str]] = {}
    blocking_rules: set[str] = set()
    ignore_path = Path(working_dir) / ".pre-deploy-ignore"

    if not ignore_path.exists():
        return ignore_rules, blocking_rules

    try:
        content = ignore_path.read_text()
        for line in content.split('\n'):
            # Strip comments and whitespace
            line = line.split('#')[0].strip()
            if not line:
                continue

            # Check for blocking rule prefix (!)
            if line.startswith('!'):
                rule_id = line[1:].strip().upper()
                if rule_id:
                    blocking_rules.add(rule_id)
                    debug_log(f"Blocking rule enabled: {rule_id}")
                continue

            # Parse rule:context format for suppression
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

        debug_log(f"Loaded .pre-deploy-ignore: ignore={ignore_rules}, blocking={blocking_rules}")
    except Exception as e:
        debug_log(f"Failed to load .pre-deploy-ignore: {e}")

    return ignore_rules, blocking_rules


def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file based on common naming conventions.

    Test files often contain unbounded queries for setup/teardown,
    which would otherwise trigger false positives.
    """
    test_patterns = [
        r'\.test\.[jt]sx?$',        # file.test.ts, file.test.js
        r'\.spec\.[jt]sx?$',        # file.spec.ts, file.spec.js
        r'_test\.[jt]sx?$',         # file_test.ts
        r'__tests__/',              # __tests__/file.ts
        r'/tests?/',                # /test/file.ts, /tests/file.ts
        r'\.stories\.[jt]sx?$',     # Storybook files
        r'\.e2e\.[jt]sx?$',         # E2E test files
        r'/fixtures?/',             # /fixture/, /fixtures/
        r'/mocks?/',                # /mock/, /mocks/
    ]
    file_path_lower = file_path.lower()
    for pattern in test_patterns:
        if re.search(pattern, file_path_lower):
            return True
    return False


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

        # Extract context from message if present (e.g., queue name, bucket name, file path)
        context = ""

        # Try to extract queue name
        queue_match = re.search(r"Queue '([^']+)'", message)
        if queue_match:
            context = queue_match.group(1)

        # Try to extract bucket name
        bucket_match = re.search(r"bucket '([^']+)'", message)
        if bucket_match:
            context = bucket_match.group(1)

        # Try to extract file path (e.g., "at src/file.ts:227")
        if not context:
            file_match = re.search(r' at ([^:]+):\d+', message)
            if file_match:
                file_path = file_match.group(1)
                # Try full path first, then just filename
                context = file_path

        # Also try just the filename for convenience
        contexts_to_check = [context]
        if context and '/' in context:
            contexts_to_check.append(os.path.basename(context))

        # Check if rule is ignored with any of the contexts
        ignored = False
        for ctx in contexts_to_check:
            if is_rule_ignored(ignore_rules, rule_id, ctx):
                debug_log(f"Ignored {rule_id} (context: {ctx or 'global'})")
                ignored = True
                break

        if not ignored:
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
                        "detection": "HEURISTIC",
                        "verify": f"Check if vars.{key} contains an actual secret value",
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
            "detection": "CONFIG",
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
            "detection": "CONFIG",
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
                "detection": "HEURISTIC",
                "verify": "Run 'npx wrangler deploy --dry-run' to get actual bundle size",
            })
        elif estimated_size_kb > FREE_LIMIT_KB:
            if usage_model == "bundled":
                issues.append({
                    "id": "PERF005",
                    "severity": "HIGH",
                    "message": f"Estimated bundle size ~{estimated_size_kb:.0f}KB exceeds Free tier 1MB limit",
                    "fix": 'Either reduce bundle or add "usage_model": "unbound" for 10MB limit',
                    "detection": "HEURISTIC",
                    "verify": "Run 'npx wrangler deploy --dry-run' to get actual bundle size",
                })
            else:
                issues.append({
                    "id": "PERF005",
                    "severity": "LOW",
                    "message": f"Bundle size ~{estimated_size_kb:.0f}KB (within Standard tier limit)",
                    "fix": "Consider optimization for faster cold starts",
                    "detection": "HEURISTIC",
                })
        elif estimated_size_kb > FREE_LIMIT_KB * 0.8:  # 80% warning
            issues.append({
                "id": "PERF005",
                "severity": "LOW",
                "message": f"Bundle size ~{estimated_size_kb:.0f}KB approaching 1MB Free tier limit",
                "fix": "Monitor bundle growth; consider code splitting",
                "detection": "HEURISTIC",
            })

    # Warn about specific heavy dependencies
    for pkg, size in heavy_deps:
        if pkg == "sharp":
            issues.append({
                "id": "PERF006",
                "severity": "HIGH",
                "message": f"Package '{pkg}' uses native bindings - won't work on Workers",
                "fix": "Use Cloudflare Images API instead",
                "detection": "STATIC",
            })
        elif pkg in ["aws-sdk", "@aws-sdk"]:
            issues.append({
                "id": "PERF006",
                "severity": "MEDIUM",
                "message": f"Package '{pkg}' is ~{size}KB - very heavy for Workers",
                "fix": "Use R2 S3-compatible API or specific lightweight clients",
                "detection": "STATIC",
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
            "detection": "CONFIG",
        })
    elif cpu_ms > 10000:
        issues.append({
            "id": "LOOP001",
            "severity": "LOW",
            "message": f"High cpu_ms limit ({cpu_ms}ms) - consider lower for API endpoints",
            "fix": "Use 100-500ms for APIs, 5000-10000ms for heavy processing",
            "detection": "CONFIG",
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
            "detection": "CONFIG",
        })

    # Check for deprecated pages_build_output_dir
    if "pages_build_output_dir" in config:
        issues.append({
            "id": "ARCH001",
            "severity": "MEDIUM",
            "message": "Deprecated pages_build_output_dir detected - use [assets] instead",
            "fix": 'Replace with "assets": { "directory": "./dist", "not_found_handling": "single-page-application" }',
            "detection": "CONFIG",
        })

    return issues


def check_r2_infrequent_access(working_dir: str, config: dict) -> list[dict]:
    """Check for R2 Infrequent Access storage usage with reads (NEW v1.4.0).

    NOTE: This is a HEURISTIC check based on bucket naming conventions.
    We cannot determine actual storage class from code or wrangler.toml.
    Storage class is configured in the Cloudflare dashboard.

    Common false positive: bucket named "archive" for archiving data,
    but actually using Standard storage class.
    """
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    # Check if there are R2 buckets configured
    r2_buckets = config.get("r2_buckets", [])
    if not r2_buckets:
        return issues

    # Only check buckets with names strongly suggesting IA storage
    # "archive" alone is too common a semantic term - require "ia" or "infrequent"
    ia_keywords = ["infrequent", "-ia", "_ia", "ia-", "ia_"]  # More specific keywords

    ia_suspect_buckets = []
    for bucket in r2_buckets:
        bucket_name = bucket.get("bucket_name", "").lower()
        if any(kw in bucket_name for kw in ia_keywords):
            ia_suspect_buckets.append(bucket_name)

    if not ia_suspect_buckets:
        return issues

    # Scan for .get() calls only if we have IA-suspect buckets
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
                    for bucket_name in ia_suspect_buckets:
                        issues.append({
                            "id": "BUDGET009",
                            "severity": "INFO",  # Downgraded from HIGH - this is speculative
                            "message": f"R2 bucket '{bucket_name}' name suggests Infrequent Access - verify storage class",
                            "fix": "If using IA storage: switch to Standard for buckets with reads. IA is only safe for write-only.",
                            "detection": "HEURISTIC",
                            "verify": f"Check bucket storage class in CF dashboard: R2 > {bucket_name} > Settings",
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
        # Skip test files - they often use unbounded queries for setup/teardown
        if is_test_file(str(ts_file)):
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

                # Check for single-row patterns (WHERE id = ?) - these are safe
                match_text = match.group(0)
                if re.search(r'WHERE\s+\w*id\s*=', match_text, re.IGNORECASE):
                    continue  # Single row lookup by ID is safe

                issues.append({
                    "id": "QUERY001",
                    "severity": "HIGH",
                    "message": f"SELECT * without LIMIT at {relative_path}:{line_num} - potential row read explosion",
                    "fix": "Add LIMIT clause or use pagination (TRAP-D1-005)",
                    "detection": "STATIC",
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
                        "detection": "STATIC",
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
                            "detection": "STATIC",
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


def check_ai_patterns(working_dir: str, config: dict) -> list[dict]:
    """Check for Workers AI usage patterns (NEW v1.6.0).

    AI001: Expensive model usage without cost awareness
    AI002: AI binding without cache wrapper (consider caching)
    """
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    # Check if project has AI binding
    ai_binding = config.get("ai", {})
    if not ai_binding and "[ai]" not in str(config):
        return issues

    # Expensive models that should trigger cost warning
    expensive_models = [
        "llama-3.1-405b",
        "llama-3.3-70b",
        "deepseek-r1",
        "claude",  # If using AI Gateway to Claude
    ]

    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # Extract suppressions from this file
            suppressions = extract_suppressions(content)

            # AI001: Check for expensive models
            for model in expensive_models:
                if model in content.lower():
                    # Find the exact line
                    for line_num, line in enumerate(content.split('\n'), 1):
                        if model in line.lower():
                            if is_suppressed(suppressions, line_num, "AI001"):
                                debug_log(f"Suppressed AI001 at {relative_path}:{line_num}")
                                continue

                            issues.append({
                                "id": "AI001",
                                "severity": "HIGH",
                                "message": f"Expensive AI model '{model}' at {relative_path}:{line_num}",
                                "fix": "Consider smaller model or implement request batching (TRAP-AI-001)",
                                "detection": "STATIC",
                            })
                            break

            # AI002: Check for AI.run without cache wrapper
            has_ai_run = re.search(r'\.run\s*\(\s*["\']@cf/', content)
            has_cache_check = any([
                'caches.default' in content,
                'cache.match' in content,
                'KV' in content and '.get' in content,  # Using KV as cache
            ])

            if has_ai_run and not has_cache_check:
                # Find the first AI.run call
                for line_num, line in enumerate(content.split('\n'), 1):
                    if re.search(r'\.run\s*\(\s*["\']@cf/', line):
                        if is_suppressed(suppressions, line_num, "AI002"):
                            debug_log(f"Suppressed AI002 at {relative_path}:{line_num}")
                            continue

                        issues.append({
                            "id": "AI002",
                            "severity": "MEDIUM",
                            "message": f"AI inference without cache at {relative_path}:{line_num}",
                            "fix": "Consider caching AI responses for repeated prompts (reduces cost + latency)",
                            "detection": "HEURISTIC",
                            "verify": "Check if prompts are dynamic (caching may not apply)",
                        })
                        break

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
            "detection": "HEURISTIC",
            "verify": "Check if exports are configured in Cloudflare dashboard instead of code",
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
                "detection": "CONFIG",
            })

    return issues


def scan_source_for_loop_patterns(working_dir: str) -> list[dict]:
    """Scan source code for loop-sensitive patterns that could cause billing issues."""
    issues = []
    src_dir = Path(working_dir) / "src"

    if not src_dir.exists():
        return issues

    # Patterns to detect: (pattern, rule_id, severity, message, fix, detection_type)
    loop_patterns = [
        # D1 queries in loops
        (
            r'(for|while|forEach|\.map)\s*\([^)]*\)[^{]*\{[^}]*\.(prepare|run|first|all)\s*\(',
            "LOOP002",
            "CRITICAL",
            "D1 query inside loop - N+1 cost explosion",
            "Use db.batch() for bulk operations (TRAP-D1-001)",
            "STATIC",
        ),
        # R2 writes in loops
        (
            r'(for|while|forEach|\.map)\s*\([^)]*\)[^{]*\{[^}]*\.put\s*\(',
            "LOOP003",
            "HIGH",
            "R2 write inside loop - Class A operation explosion",
            "Buffer writes or use multipart upload (TRAP-R2-001)",
            "STATIC",
        ),
        # setInterval without clear pattern
        (
            r'setInterval\s*\([^)]+\)',
            "LOOP004",
            "MEDIUM",
            "setInterval detected - verify termination condition exists",
            "Use state.storage.setAlarm() in Durable Objects for hibernation",
            "STATIC",
        ),
        # Unbounded while loops
        (
            r'while\s*\(\s*true\s*\)|for\s*\(\s*;\s*;\s*\)',
            "LOOP007",
            "CRITICAL",
            "Unbounded loop detected - could run until CPU limit",
            "Add explicit break condition and iteration limit",
            "STATIC",
        ),
        # Self-fetch patterns
        (
            r'fetch\s*\(\s*request\.url',
            "LOOP005",
            "CRITICAL",
            "Worker fetching own URL - potential infinite recursion",
            "Add X-Recursion-Depth middleware (see loop-breaker skill)",
            "STATIC",
        ),
        # Recursive function without depth
        (
            r'(async\s+)?function\s+(\w+)[^{]*\{[^}]*\2\s*\(',
            "LOOP005",
            "HIGH",
            "Recursive function detected - verify depth limit exists",
            "Add maxDepth parameter and check before recursing",
            "HEURISTIC",
        ),
    ]

    for ts_file in src_dir.rglob("*.ts"):
        if "node_modules" in str(ts_file):
            continue
        # Skip test files - they often have patterns for testing edge cases
        if is_test_file(str(ts_file)):
            continue

        try:
            content = ts_file.read_text()
            relative_path = ts_file.relative_to(working_dir)

            # Extract suppressions from this file
            suppressions = extract_suppressions(content)

            for pattern, rule_id, severity, message, fix, detection in loop_patterns:
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

                    issue = {
                        "id": rule_id,
                        "severity": severity,
                        "message": f"{message} at {relative_path}:{line_num}",
                        "fix": fix,
                        "detection": detection,
                    }
                    # Add verify hint for heuristic detections
                    if detection == "HEURISTIC":
                        issue["verify"] = "Check code manually to confirm this pattern"
                    issues.append(issue)
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
                    "detection": "CONFIG",
                })

            # Check for high retries (cost multiplier)
            max_retries = consumer.get("max_retries", 3)
            if max_retries > 2:
                issues.append({
                    "id": "COST001",
                    "severity": "MEDIUM",
                    "message": f"Queue '{queue_name}' has max_retries={max_retries} (each retry costs $0.40/M)",
                    "fix": 'Set max_retries to 1-2 if consumer is idempotent',
                    "detection": "CONFIG",
                })

            # Check for missing max_concurrency (resilience)
            if "max_concurrency" not in consumer:
                issues.append({
                    "id": "RES002",
                    "severity": "MEDIUM",
                    "message": f"Queue '{queue_name}' has no max_concurrency limit",
                    "fix": 'Add "max_concurrency": 10 to prevent overload',
                    "detection": "CONFIG",
                })

    return issues


def run_audit(config: dict, working_dir: str = "") -> tuple[list[dict], set[str]]:
    """Run all audit checks on config.

    Returns tuple of:
    - issues: list of detected issues
    - blocking_rules: set of rule IDs configured to block deployment
    """
    issues = []

    # Load .pre-deploy-ignore file for project-level suppressions and blocking config
    if working_dir:
        ignore_rules, blocking_rules = load_ignore_file(working_dir)
    else:
        ignore_rules, blocking_rules = {}, set()

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

        # AI usage pattern checks (NEW v1.6.0)
        issues.extend(check_ai_patterns(working_dir, config))

    # Apply .pre-deploy-ignore suppressions
    issues = filter_ignored_issues(issues, ignore_rules)

    return issues, blocking_rules


def format_issues(issues: list[dict], blocking_rules: set[str] = None) -> str:
    """Format issues for display with self-documenting output for AI consumption.

    Args:
        issues: List of issue dictionaries
        blocking_rules: Set of rule IDs that actually block deployment.
                       If None, falls back to CRITICAL severity for display.
    """
    if not issues:
        return ""

    # Separate issues based on what actually blocks
    if blocking_rules is not None:
        # Use the actual blocking rules set
        blocking_issues = [i for i in issues if i.get("id") in blocking_rules]
        warning_issues = [i for i in issues if i.get("id") not in blocking_rules and i.get("id") != "COST_SIM"]
    else:
        # Fallback: use severity (legacy behavior)
        blocking_issues = [i for i in issues if i.get("severity") == "CRITICAL"]
        warning_issues = [i for i in issues if i.get("severity") != "CRITICAL" and i.get("id") != "COST_SIM"]

    cost_sim = [i for i in issues if i.get("id") == "COST_SIM"]

    lines = []

    # Self-documenting header explaining blocking behavior
    lines.append("")
    lines.append("━" * 60)
    lines.append("⚠️  CLOUDFLARE PRE-DEPLOY VALIDATION")
    lines.append("━" * 60)
    lines.append("")

    # Severity guide - blocking is now opt-in
    if blocking_rules:
        lines.append("BLOCKING RULES (configured in .pre-deploy-ignore):")
        lines.append(f"  {', '.join(sorted(blocking_rules))}")
        lines.append("")
    else:
        lines.append("BLOCKING: Disabled (all rules are warnings)")
        lines.append("  To enable: add !RULE_ID to .pre-deploy-ignore")
        lines.append("")
    lines.append("SEVERITY LEVELS:")
    lines.append("  🔴 CRITICAL = Serious issue")
    lines.append("  🟠 HIGH     = Important warning - review recommended")
    lines.append("  🟡 MEDIUM   = Advisory - consider addressing")
    lines.append("  🔵 LOW/INFO = Informational")
    lines.append("")
    lines.append("DETECTION TYPES (confidence levels):")
    lines.append("  [CONFIG]    = Found in wrangler config - definite issue")
    lines.append("  [STATIC]    = Code pattern match - high confidence")
    lines.append("  [HEURISTIC] = Inferred from names/patterns - MAY BE FALSE POSITIVE")
    lines.append("")
    lines.append("━" * 60)

    # Summary counts
    blocking_count = len(blocking_issues)
    warning_count = len(warning_issues)
    lines.append(f"SUMMARY: {blocking_count} blocking, {warning_count} warnings")
    if blocking_count > 0:
        lines.append("ACTION: Deployment BLOCKED - fix or suppress blocking issues")
    else:
        lines.append("ACTION: Deployment ALLOWED (warnings only)")
    lines.append("━" * 60)
    lines.append("")

    # BLOCKING ISSUES section
    if blocking_issues:
        lines.append("🛑 BLOCKING ISSUES (deployment will fail):")
        lines.append("-" * 50)
        for issue in blocking_issues:
            detection = issue.get("detection", "STATIC")
            lines.append(f"   🔴 [{issue['id']}] [{detection}] {issue['severity']}")
            lines.append(f"      {issue['message']}")
            lines.append(f"      Fix: {issue['fix']}")
            if detection == "HEURISTIC":
                verify = issue.get("verify", "Check code manually to confirm")
                lines.append(f"      Verify: {verify}")
            suppress = issue.get("suppress", f"// @pre-deploy-ok {issue['id']}")
            lines.append(f"      Suppress: {suppress}")
            lines.append("")

    # NON-BLOCKING WARNINGS section
    if warning_issues:
        lines.append("⚠️  NON-BLOCKING WARNINGS (deployment allowed):")
        lines.append("-" * 50)
        for issue in warning_issues:
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "🔵"}.get(issue["severity"], "⚪")
            detection = issue.get("detection", "STATIC")
            lines.append(f"   {emoji} [{issue['id']}] [{detection}] {issue['severity']}")
            lines.append(f"      {issue['message']}")
            lines.append(f"      Fix: {issue['fix']}")
            if detection == "HEURISTIC":
                verify = issue.get("verify", "Check code manually to confirm")
                lines.append(f"      Verify: {verify}")
            lines.append("")

    # Cost simulation section (if present)
    if cost_sim:
        lines.append("💰 COST SIMULATION (informational):")
        lines.append("-" * 50)
        for issue in cost_sim:
            lines.append(f"   {issue['message']}")
            lines.append(f"   Recommendation: {issue['fix']}")
        lines.append("")

    return "\n".join(lines)


def check_bypass_in_command(command: str) -> bool:
    """Check if bypass env var is set in the command string itself.

    When user runs: SKIP_PREDEPLOY_CHECK=1 npx wrangler deploy
    The env var is set for wrangler, not for the hook process.
    We detect the user's intent by parsing the command.
    """
    bypass_patterns = [
        r'\bSKIP_PREDEPLOY_CHECK\s*=\s*["\']?1["\']?',
        r'\bSKIP_PREDEPLOY_CHECK\s*=\s*["\']?true["\']?',
        r'\bSKIP_PREDEPLOY_CHECK\s*=\s*["\']?yes["\']?',
    ]
    for pattern in bypass_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def main():
    """Main hook function.

    OPT-IN BLOCKING SYSTEM (v1.7.0):

    DEFAULT BEHAVIOR:
    All rules are WARNINGS only. Deployment always proceeds (exit 0).
    Claude sees the output and can advise the user about issues.
    This respects user agency while ensuring visibility.

    OPT-IN BLOCKING:
    Users can configure specific rules to block deployment by adding
    them to .pre-deploy-ignore with a ! prefix:

    ```
    # .pre-deploy-ignore
    !SEC001     # Block on plaintext secrets
    !LOOP005    # Block on self-recursion
    !LOOP007    # Block on unbounded loops
    ```

    Philosophy: Warnings inform, blocking is opt-in.
    Users who want stricter enforcement can configure it per-project.
    """
    # No default blocking rules - all blocking is opt-in via .pre-deploy-ignore
    # blocking_rules will be loaded from the config file

    # Check for environment variable bypass (in hook's environment)
    if os.environ.get("SKIP_PREDEPLOY_CHECK", "").lower() in ("1", "true", "yes"):
        debug_log("SKIP_PREDEPLOY_CHECK is set in environment, bypassing validation")
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

    # Check for bypass in command string (user intent detection)
    # This handles: SKIP_PREDEPLOY_CHECK=1 npx wrangler deploy
    if check_bypass_in_command(command):
        debug_log(f"SKIP_PREDEPLOY_CHECK found in command, bypassing validation: {command}")
        sys.exit(0)

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
    issues, blocking_rules = run_audit(config, working_dir)

    if not issues:
        debug_log("No issues found, allowing deploy")
        sys.exit(0)

    # Separate blocking issues from warnings (blocking is opt-in via .pre-deploy-ignore)
    blocking_issues = [i for i in issues if i.get("id") in blocking_rules]
    warning_issues = [i for i in issues if i.get("id") not in blocking_rules]

    # Count by severity for summary display
    high_count = sum(1 for i in warning_issues if i.get("severity") in ("CRITICAL", "HIGH"))
    medium_count = sum(1 for i in warning_issues if i.get("severity") == "MEDIUM")

    # Format and output issues (pass blocking_rules for proper categorization)
    output = format_issues(issues, blocking_rules if blocking_rules else None)

    # DECISION: Block or Allow?
    if blocking_issues:
        # User has opted-in to blocking for these rules via .pre-deploy-ignore
        # Format agent-readable blocking message
        output += "\n"
        output += "━" * 60 + "\n"
        output += "🛑 DEPLOYMENT BLOCKED (by project config)\n"
        output += "━" * 60 + "\n"
        output += "\n"
        output += f"WHAT: {len(blocking_issues)} blocking issue(s) detected\n"
        output += "WHY:  Project .pre-deploy-ignore has opted into blocking for these rules\n"
        output += "\n"
        output += "BLOCKING ISSUES:\n"
        for issue in blocking_issues:
            rule_id = issue.get("id", "UNKNOWN")
            output += f"  • {rule_id}: {issue.get('message', 'No message')}\n"
        output += "\n"
        output += "OPTIONS:\n"
        output += "  1. FIX: Address the issues listed above (recommended)\n"
        output += "  2. SUPPRESS: Add inline comment: // @pre-deploy-ok RULE_ID\n"
        output += "  3. DISABLE BLOCKING: Remove !RULE_ID from .pre-deploy-ignore\n"
        output += "  4. OVERRIDE: Run with SKIP_PREDEPLOY_CHECK=1\n"
        output += "\n"
        if warning_issues:
            output += f"ALSO: {len(warning_issues)} additional warnings (non-blocking)\n"
        output += "━" * 60 + "\n"

        print(output, file=sys.stderr)
        sys.exit(2)  # Block deployment - returns control to Claude
    else:
        # Default: All issues are warnings - deployment proceeds
        output += "\n"
        output += "━" * 60 + "\n"
        output += "✅ DEPLOYMENT ALLOWED\n"
        output += "━" * 60 + "\n"
        output += "\n"
        total_warnings = len(warning_issues)
        if total_warnings > 0:
            if high_count > 0:
                output += f"⚠️  {high_count} high-priority warning(s) detected\n"
            if medium_count > 0:
                output += f"ℹ️  {medium_count} advisory issue(s) detected\n"
            output += "\n"
            output += "TIP: To block deployment on specific rules, add to .pre-deploy-ignore:\n"
            output += "     !SEC001    # Block on plaintext secrets\n"
            output += "     !LOOP005   # Block on self-recursion\n"
        output += "\n"
        output += "Deployment proceeding.\n"
        output += "━" * 60 + "\n"

        print(output, file=sys.stderr)
        sys.exit(0)  # Allow deployment


if __name__ == "__main__":
    main()
