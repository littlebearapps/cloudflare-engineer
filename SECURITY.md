# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.5.x   | :white_check_mark: |
| 1.4.x   | :white_check_mark: |
| 1.3.x   | :x:                |
| 1.2.x   | :x:                |
| 1.1.x   | :x:                |
| 1.0.x   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in the Cloudflare Engineer plugin, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email security concerns to the maintainers via GitHub private vulnerability reporting
3. Or open a [GitHub Security Advisory](https://github.com/littlebearapps/cloudflare-engineer/security/advisories/new)

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 7 days
- **Resolution target**: Within 30 days for critical issues

### Scope

This security policy covers:
- The pre-deploy validation hook (`hooks/pre-deploy-check.py`)
- Command and agent definitions
- Any code that executes on the user's machine

### Out of Scope

- Cloudflare's own services and APIs
- MCP server implementations (report to respective maintainers)
- Issues in Claude Code itself (report to Anthropic)

## Security Best Practices

When using this plugin:

1. **Review hook output** before deploying - the pre-deploy hook catches common issues but is not exhaustive
2. **Use `--validate` mode** to verify configurations against live Cloudflare data
3. **Keep the plugin updated** to receive security fixes
4. **Review generated wrangler.toml** configurations before applying them

## Known Security Considerations

- The plugin reads `wrangler.toml` and `wrangler.jsonc` files to validate configurations
- The pre-deploy hook executes Python code locally
- MCP tools may access your Cloudflare account when using `--validate` mode

## Billing Safety (v1.3.0+)

The plugin includes **Loop Protection** to prevent "denial-of-wallet" attacks:

- **Pre-deploy hook** blocks deployment when CRITICAL loop patterns are detected
- **Loop-breaker skill** provides middleware templates for recursion protection
- **Guardian skill** audits for loop-sensitive resource usage
- **Cost simulation** estimates potential billing impact of detected patterns

These features help prevent accidental billing explosions from:
- Worker self-recursion (infinite fetch chains)
- Queue retry storms (missing DLQs)
- N+1 database queries
- Unbounded loops
- Durable Objects kept awake by setInterval

## Cost Awareness (v1.4.0+)

The plugin includes **Cost Awareness** to protect against primary billing traps:

- **D1 Row Read Protection** (BUDGET007) - Detects unindexed queries causing full table scans
- **R2 Class B Caching** (BUDGET008) - Flags public bucket reads without CDN cache
- **R2 Infrequent Access Trap** (BUDGET009) - Warns about $9 minimum charge on IA bucket reads
- **Architecture Validation** (ARCH001) - Flags deprecated [site] configurations

These features help prevent accidental billing explosions from:
- Unindexed D1 queries reading millions of rows per request
- R2 Class B operations on every request instead of edge cache
- R2 Infrequent Access storage with read operations (minimum billing trap)

See [COST_SENSITIVE_RESOURCES.md](COST_SENSITIVE_RESOURCES.md) for detailed documentation of cost traps.

## Query Optimization & Privacy (v1.5.0+)

The plugin includes **Query Optimization** to protect against D1 billing traps:

- **QUERY001-005** - Detects unbounded SELECT *, N+1 queries, and Drizzle ORM anti-patterns
- **TRAP-D1-005, TRAP-D1-006** - Cost traps for query patterns that read excess rows

The plugin also includes **Privacy Filters** for logging:

- **TRAP-PRIVACY-001** - Logging Authorization headers (CRITICAL)
- **TRAP-PRIVACY-002** - Logging PII like email, phone (HIGH)
- **TRAP-PRIVACY-003** - Logging financial data like credit cards (CRITICAL)

These features help prevent:
- D1 queries reading entire tables instead of indexed rows
- Accidental exposure of credentials in external logs
- PII and financial data leakage through observability pipelines
