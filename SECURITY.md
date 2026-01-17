# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | :white_check_mark: |
| 1.2.x   | :white_check_mark: |
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

See [COST_SENSITIVE_RESOURCES.md](COST_SENSITIVE_RESOURCES.md) for detailed documentation of cost traps.
