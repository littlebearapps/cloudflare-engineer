# Cloudflare Engineer Plugin

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/littlebearapps/cloudflare-engineer/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-v2.0.12+-purple.svg)](https://claude.com/claude-code)

A Claude Code plugin that provides **Platform Architect** capabilities for designing, implementing, optimizing, and securing Cloudflare Workers applications. Now with **Vibecoder Proactive Safeguards** that warn about cost and privacy impacts before you ask.

## Quick Install

```bash
# From GitHub (recommended)
/plugin marketplace add littlebearapps/cloudflare-engineer
/plugin install cloudflare-engineer@littlebearapps

# Or install directly
/plugin install github:littlebearapps/cloudflare-engineer
```

> [!TIP]
> This plugin works fully without any additional setup. For enhanced capabilities like live validation and real-time cost analysis, configure the optional [Cloudflare MCP servers](#mcp-tool-integration).

## Features at a Glance

| Category | What You Get |
|----------|--------------|
| **10 Skills** | Cost optimization, security auditing, architecture design, Zero Trust, Custom Hostnames, Media/Streaming, and more |
| **4 Commands** | `/cf-costs`, `/cf-audit` (with Resource Discovery), `/cf-design`, `/cf-pattern` |
| **3 Agents** | Deep analysis with MCP tool integration |
| **1 Hook** | Pre-deploy validation with Performance Budgeter |

## Vibecoder Proactive Safeguards (NEW in v1.2.0)

This plugin **proactively warns** you about cost and privacy impacts **before you ask**:

| Trigger | Warning |
|---------|---------|
| Durable Objects usage | "DO charges ~$0.15/GB-month storage. Consider KV for simple key-value." |
| R2 Class A ops >1M/mo | "R2 writes cost $4.50/M. Buffer writes or use presigned URLs." |
| D1 Writes >10M/mo | "D1 writes cost $1/M. Batch to 1,000 rows." |
| Workers AI >8B models | "Large models cost $0.68/M tokens. Use 8B or smaller for bulk." |
| PII in logs | "Detected potential PII logging. Use structured logging with redaction." |
| User data in KV keys | "KV keys with user IDs may leak via dashboard. Hash or encrypt." |

## Supported Cloudflare Services

- Workers (standard & Durable Objects)
- D1 (SQLite database)
- R2 (object storage)
- KV (key-value store)
- Queues (with DLQ support)
- Vectorize (vector database)
- AI Gateway (LLM routing)
- Workflows (durable execution)
- Hyperdrive (connection pooling)
- Analytics Engine
- **Access (Zero Trust)** - NEW
- **Custom Hostnames (SSL for SaaS)** - NEW
- **Stream (video delivery)** - NEW
- **Images (transformations)** - NEW

## What's New in v1.2.0

### Vibecoder Proactive Safeguards

The guardian skill now **proactively warns** about Budget and Privacy impacts:
- Budget enforcement: Warns about expensive patterns (Durable Objects, R2 writes, D1 writes, large AI models)
- Privacy enforcement: Detects PII in logs, user data in KV keys, AI prompts without redaction

### Resource Discovery Mode

`/cf-audit` now includes **Resource Discovery** by default:
- Finds unused KV namespaces, R2 buckets, D1 databases
- Identifies dangling references and orphaned Workers
- Use `--discover` for explicit discovery-only mode

### Edge-Native Constraints

The architect skill now validates **Workers runtime compatibility**:
- Flags incompatible Node.js libraries (fs, net, http)
- Suggests Cloudflare alternatives (R2, fetch, Hono)
- Includes compatibility flag requirements

### Performance Budgeter

Pre-deploy hook now checks **bundle size limits**:
- Free tier: 1MB warning
- Standard tier: 10MB limit
- Detects heavy dependencies (aws-sdk, sharp, moment)

### New Skills

| Skill | Purpose |
|-------|---------|
| `zero-trust` | Audit Access policies, detect unprotected staging/dev environments |
| `custom-hostnames` | Manage SSL for SaaS, vanity domains, hostname lifecycle |
| `media-streaming` | Cloudflare Stream (signed URLs) and Images (transformations) |

---

## What's New in v1.1.0

### Live Validation Mode (`--validate`)

Commands now support **live validation** against Cloudflare MCP tools:

```bash
/cf-costs --validate    # Compare estimates with live observability data
/cf-audit --validate    # Verify findings against production metrics
```

### Provenance Tagging

All findings are tagged with their data source:

| Tag | Meaning |
|-----|---------|
| `[STATIC]` | Inferred from code/config analysis |
| `[LIVE-VALIDATED]` | Confirmed by observability data |
| `[LIVE-REFUTED]` | Code smell not observed in production |
| `[INCOMPLETE]` | MCP tools unavailable for verification |

### Architecture Pattern Catalog

Apply battle-tested patterns with code examples:

| Pattern | Problem | Solution |
|---------|---------|----------|
| `service-bindings` | Monolithic Worker hitting subrequest limits | Decompose with RPC |
| `d1-batching` | High D1 write costs | Batch INSERT operations |
| `circuit-breaker` | External API cascading failures | Fail-fast with fallback |

```bash
/cf-pattern service-bindings
/cf-pattern d1-batching --analyze-only
```

## Commands

| Command | Purpose |
|---------|---------|
| `/cf-costs [--validate]` | Cost report with monthly projections |
| `/cf-audit [--validate] [--category=<cat>]` | Security/performance/cost audit |
| `/cf-design` | Interactive architecture design wizard |
| `/cf-pattern <name> [--analyze-only]` | Apply architecture pattern |

## Skills (Auto-Invoked)

Skills activate automatically based on your questions:

```
"How much will this worker cost?"           -> optimize-costs
"Is my worker secure?"                      -> guardian (with Budget & Privacy)
"Design a queue-based pipeline"             -> architect (with Edge-Native checks)
"Scaffold a Hono API with D1"               -> implement
"How do I scale to 1M requests/day?"        -> scale
"Is my staging environment protected?"      -> zero-trust (NEW)
"How do I add custom domains for SaaS?"     -> custom-hostnames (NEW)
"How do I serve videos with signed URLs?"   -> media-streaming (NEW)
```

### All 10 Skills

| Skill | Purpose |
|-------|---------|
| `architect` | Architecture design with Edge-Native Constraints |
| `guardian` | Security + Budget + Privacy auditing |
| `implement` | Code scaffolding (Hono, D1, Drizzle) |
| `optimize-costs` | Cost analysis and optimization |
| `scale` | Scaling strategies and patterns |
| `probes` | MCP audit queries |
| `patterns` | Architecture pattern catalog |
| `zero-trust` | Access policy auditing |
| `custom-hostnames` | SSL for SaaS management |
| `media-streaming` | Stream and Images patterns |

## Pre-Deploy Validation Hook

Automatically validates `wrangler.toml` before deployment:

| Check | Severity | Description |
|-------|----------|-------------|
| SEC001 | CRITICAL | Plaintext secrets in config |
| RES001 | HIGH | Queues without dead letter queues |
| RES002 | MEDIUM | Missing max_concurrency limit |
| COST001 | MEDIUM | High retry counts ($0.40/M per retry) |
| PERF001 | LOW | Smart placement disabled |
| PERF004 | LOW | Observability not configured |
| PERF005 | CRITICAL/HIGH | Bundle size exceeds tier limits (NEW) |
| PERF006 | HIGH | Incompatible native packages (NEW) |

**CRITICAL issues block deployment.** Other severities are warnings.

### Performance Budgeter (NEW)

The hook now estimates bundle size and warns about tier limits:
- **Free tier**: 1MB compressed - `[HIGH]` if exceeded
- **Standard tier**: 10MB compressed - `[CRITICAL]` if exceeded
- Detects heavy dependencies: `moment`, `lodash`, `aws-sdk`, `sharp`

## MCP Tool Integration

For `--validate` mode, configure these Cloudflare MCP servers:

| MCP Server | Used For |
|------------|----------|
| `cloudflare-observability` | Worker metrics, error rates, latency |
| `cloudflare-ai-gateway` | AI costs, cache hit rates |
| `cloudflare-bindings` | D1 queries, resource inventory |

### What Works Without MCP

| Feature | Without MCP | With MCP |
|---------|-------------|----------|
| `/cf-costs` | Static estimates from config | + Live usage validation |
| `/cf-audit` | Config & code analysis | + Production metrics |
| `/cf-design` | Full functionality | Same |
| `/cf-pattern` | Full functionality | Same |
| Pre-deploy hook | Full functionality | Same |
| All 7 skills | Full functionality | Same |
| All 3 agents | Static analysis | + Real-time data |

**Graceful Degradation**: Commands continue with static analysis if MCP tools are unavailable, tagging affected findings as `[INCOMPLETE]`.

## Usage Examples

```bash
# Cost analysis
/cf-costs                              # Static cost estimate
/cf-costs --validate                   # With live data validation

# Security audit
/cf-audit                              # Full audit
/cf-audit --validate --category=security

# Architecture design
/cf-design                             # Interactive wizard

# Apply patterns
/cf-pattern circuit-breaker            # Apply pattern
/cf-pattern service-bindings --analyze-only  # Analysis only
```

## Requirements

- Claude Code v2.0.12+
- Python 3.8+ (for pre-deploy hook)
- Cloudflare account with Workers enabled
- (Optional) Cloudflare MCP servers for `--validate` mode

## Safety & Costs

This plugin includes built-in guardrails to prevent unexpected Cloudflare bills. See the **[Cost-Sensitive Resources Watchlist](COST_SENSITIVE_RESOURCES.md)** for detailed documentation of pricing traps and how to avoid them.

### Cost Trap Quick Reference

| Service | Top Cost Trap | Guardian Rule | Detection |
|---------|---------------|---------------|-----------|
| D1 | Per-row inserts instead of batch | BUDGET003 | `for.*\.run\(` pattern |
| R2 | Frequent small writes | BUDGET002 | `.put()` in loops |
| Durable Objects | Overuse for simple KV | BUDGET001 | DO without coordination need |
| KV | Write-heavy patterns | BUDGET005 | High `.put()` frequency |
| Queues | High retry counts | COST001 | `max_retries > 2` |
| Workers AI | Large models for simple tasks | BUDGET004 | Model name contains `70b` |

### Provenance Tagging for Cost Warnings

All cost warnings include provenance tags for transparency:

| Tag | Meaning |
|-----|---------|
| `[STATIC:COST_WATCHLIST]` | Pattern detected via code analysis |
| `[LIVE-VALIDATED:COST_WATCHLIST]` | Confirmed by observability data |
| `[REFUTED:COST_WATCHLIST]` | Pattern exists but not hitting thresholds |

### Budget Whisperer

When Claude suggests code changes involving D1, R2, or Durable Objects, the guardian skill automatically:
1. Searches for cost-optimized patterns (`.batch()`, `CREATE INDEX`, buffering)
2. Warns if expensive patterns are detected
3. Cites specific traps from the Cost Watchlist

## Directory Structure

```
cloudflare-engineer/
├── .claude-plugin/plugin.json    # Plugin manifest
├── skills/                       # 10 auto-invoked skills
│   ├── architect/                # Architecture + Edge-Native
│   ├── guardian/                 # Security + Budget + Privacy
│   ├── implement/                # Code scaffolding
│   ├── optimize-costs/           # Cost analysis
│   ├── scale/                    # Scaling patterns
│   ├── probes/                   # MCP queries
│   ├── patterns/                 # Pattern catalog
│   ├── zero-trust/               # Access policies (NEW)
│   ├── custom-hostnames/         # SSL for SaaS (NEW)
│   └── media-streaming/          # Stream & Images (NEW)
├── agents/                       # 3 deep-analysis agents
├── commands/                     # 4 slash commands
├── hooks/                        # Pre-deploy validation
├── LICENSE                       # MIT
├── CONTRIBUTING.md               # Contribution guide
├── SECURITY.md                   # Security policy
└── CHANGELOG.md                  # Version history
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [Changelog](CHANGELOG.md)
- [Cost-Sensitive Resources Watchlist](COST_SENSITIVE_RESOURCES.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

---

Made with care by [Little Bear Apps](https://littlebearapps.com)
