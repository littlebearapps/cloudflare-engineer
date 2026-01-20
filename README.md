# Cloudflare Engineer Plugin

[![Version](https://img.shields.io/badge/version-1.6.0-blue.svg)](https://github.com/littlebearapps/cloudflare-engineer/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-v2.0.12+-purple.svg)](https://claude.com/claude-code)
[![GitHub Issues](https://img.shields.io/github/issues/littlebearapps/cloudflare-engineer)](https://github.com/littlebearapps/cloudflare-engineer/issues)
[![GitHub Discussions](https://img.shields.io/github/discussions/littlebearapps/cloudflare-engineer)](https://github.com/littlebearapps/cloudflare-engineer/discussions)

A Claude Code plugin that provides **Platform Architect** capabilities for designing, implementing, optimizing, and securing Cloudflare Workers applications. Features **D1 Query Optimization**, **Cloudflare Workflows**, **External Logging**, **Python Workers**, **Zero Trust Tooling**, **R2 Cost Protection**, and **AI Cost Detection**.

## Quick Install

```bash
# Step 1: Add the marketplace
/plugin marketplace add littlebearapps/cloudflare-engineer

# Step 2: Install the plugin
/plugin install cloudflare-engineer@littlebearapps-cloudflare-engineer
```

To update to the latest version:

```bash
/plugin update cloudflare-engineer@littlebearapps-cloudflare-engineer
```

> [!TIP]
> This plugin works fully without any additional setup. For enhanced capabilities like live validation and real-time cost analysis, configure the optional [Cloudflare MCP servers](#mcp-tool-integration).

## Features at a Glance

| Category | What You Get |
|----------|--------------|
| **13 Skills** | D1 Query Optimization, Cloudflare Workflows, Cost optimization, security auditing, architecture design, Loop Protection, Zero Trust, Custom Hostnames, Media/Streaming, and more |
| **5 Commands** | `/cf-costs`, `/cf-audit` (with Resource Discovery), `/cf-design`, `/cf-pattern`, `/cf-logs` |
| **3 Agents** | Deep analysis with MCP tool integration |
| **3 Hooks** | SessionStart (project detection), PreToolUse (pre-deploy validation), PostToolUse (deploy verification) |

## What's New in v1.6.0

### Session-Aware Hooks

The plugin now includes a complete hook lifecycle for Cloudflare projects:

| Hook | When | What It Does |
|------|------|--------------|
| **SessionStart** | Session begins | Detects CF projects, announces bindings (D1, R2, KV, Queues, DO, AI, Vectorize, Workflows) |
| **PreToolUse** | Before `wrangler deploy` | Validates config and source code (30+ rules) |
| **PostToolUse** | After `wrangler deploy` | Parses deployment output, suggests next steps (`/cf-audit --validate`) |

SessionStart uses fingerprint caching to avoid repeated announcements when resuming sessions.

### AI Cost Detection

New rules in the pre-deploy hook detect expensive Workers AI patterns:

| Rule | Severity | Detection |
|------|----------|-----------|
| **AI001** | 🟠 HIGH | Expensive model usage (llama-3.1-405b, llama-3.3-70b, deepseek-r1) without cost awareness comment |
| **AI002** | 🟡 MEDIUM | AI binding without cache wrapper pattern |

## What's New in v1.5.0

### D1 Query Optimization

New `query-optimizer` skill protects against the #1 D1 billing trap—row read explosion from unindexed queries:

| Feature | Problem Solved | Guardian Rule |
|---------|---------------|---------------|
| **SELECT * Detection** | Unbounded queries reading entire tables | QUERY001 |
| **Drizzle .all() Checks** | ORM-hidden unbounded queries | QUERY005 |
| **N+1 Query Detection** | Database calls inside loops | QUERY002 |
| **Pagination Guidance** | List endpoints without limits | QUERY004 |
| **Caching Decision Tree** | When to use KV vs Cache API | Skill guidance |

### Cloudflare Workflows

New `workflow-architect` skill guides you toward Workflows for multi-step processes instead of complex Queue patterns:

- **Queues vs Workflows Decision Tree**: When each is appropriate
- **WorkflowEntrypoint Boilerplate**: TypeScript templates with `step.do()`, `step.sleep()`
- **Step Patterns**: Sequential, parallel, conditional branching, fan-out/fan-in
- **Anti-Patterns**: What to avoid in workflow design

### External Logging (`/cf-logs`)

New command for configuring observability export to external vendors:

| Vendor | Free Tier | Best For |
|--------|-----------|----------|
| **Axiom** | 500GB/month | High-volume, long retention |
| **Better Stack** | 1GB/month | Real-time dashboards |
| **HTTP Endpoint** | N/A | Custom/self-hosted |

Includes **Privacy Filters** with auto-recommended redaction patterns for Authorization headers, API keys, PII, and financial data.

### Python Workers Support

Extended `architect` skill with Python Workers decision tree:

- **Use Python Workers**: For familiar syntax, simple data processing
- **Use JS Workers**: For best cold start, npm ecosystem
- **Use Containers**: For numpy, pandas, opencv, or native libs

### Zero Trust Tooling Expansion

Extended `zero-trust` skill with new capabilities:

| Feature | Purpose |
|---------|---------|
| **Tunnel Configuration** | Quick start YAML templates for cloudflared |
| **Access Policy Generator** | Email OTP, Service Token, combined patterns |
| **Admin Protection Checklist** | Common security gaps for admin panels |
| **ZT009-012 Rules** | New validation for service tokens, MFA, sessions |

### R2 Class B Cost Protection

Enhanced `cost-analyzer` agent with R2-specific checks:

| Check | Detection |
|-------|-----------|
| **R2002** | `R2.get()` without `caches.default` wrapper |
| **TRAP-R2-005** | Public bucket without CDN configuration |
| **TRAP-R2-006** | Uncached reads on hot paths |

---

## What's New in v1.4.0

### Cost Awareness Upgrade

Comprehensive cost protection for the primary billing dangers facing solo developers:

| Feature | Problem Solved | Guardian Rule |
|---------|---------------|---------------|
| **D1 Row Read Protection** | Unindexed queries causing millions of reads | BUDGET007 |
| **R2 Class B Caching** | Public bucket reads without CDN cache | BUDGET008 |
| **R2 IA Trap Warning** | $9 minimum charge on IA bucket reads | BUDGET009 |
| **KV-Cache-First Pattern** | Cache D1 reads to avoid row read explosion | New pattern |
| **R2-CDN-Cache Pattern** | Edge cache for R2 public assets | New pattern |

### Workers + Assets Architecture

Cloudflare has merged Pages into Workers. The plugin now:

- Defaults to unified `[assets]` block for fullstack apps
- Flags deprecated `[site]` configuration (ARCH001)
- Scaffolds Workers + Assets for React/Vue/Svelte SPAs

```jsonc
// Modern configuration (recommended)
{
  "assets": {
    "directory": "./dist",
    "html_handling": "auto-trailing-slash",
    "not_found_handling": "single-page-application"
  }
}
```

### Workload Router: Isolates vs Containers

With Cloudflare Containers launching in 2025, the plugin now includes a decision tree:

- **Use Workers (Isolates)**: Standard APIs, D1/KV/R2, AI inference
- **Use Containers**: FFmpeg, Puppeteer, Python with native libs
- Hybrid architecture patterns for complex workloads

### Observability Export

Native Cloudflare log retention is short (3-7 days). New scaffolding for:

- **Axiom** (recommended free tier: 500GB/month)
- **Better Stack / Logtail**
- **OpenTelemetry native export**

---

## Loop Protection

Infinite loops in serverless aren't just frozen tabs—they're **billing multipliers**. This plugin provides comprehensive protection:

| Protection | What It Does |
|------------|--------------|
| **Recursion Guards** | Detects Worker self-fetch patterns, scaffolds X-Recursion-Depth middleware |
| **CPU Time Caps** | Enforces `limits.cpu_ms` to kill runaway loops before they bill |
| **Queue Safety** | Idempotency patterns + DLQ enforcement to break retry storms |
| **DO Hibernation** | Alarm-based timers instead of `setInterval` to stop duration billing |
| **N+1 Detection** | Flags D1 queries and R2 writes inside loops |
| **Cost Simulation** | Estimates potential cost impact of detected loop patterns |

See the `loop-breaker` skill for complete middleware templates and patterns.

## Vibecoder Proactive Safeguards

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
- Containers (Beta)
- D1 (SQLite database)
- R2 (object storage)
- KV (key-value store)
- Queues (with DLQ support)
- Vectorize (vector database)
- AI Gateway (LLM routing)
- Workflows (durable execution)
- Hyperdrive (connection pooling)
- Analytics Engine
- Access (Zero Trust)
- Custom Hostnames (SSL for SaaS)
- Stream (video delivery)
- Images (transformations)

## Commands

| Command | Purpose |
|---------|---------|
| `/cf-costs [--validate]` | Cost report with monthly projections |
| `/cf-audit [--validate] [--category=<cat>]` | Security/performance/cost audit with Resource Discovery |
| `/cf-design` | Interactive architecture design wizard |
| `/cf-pattern <name> [--analyze-only]` | Apply architecture pattern |
| `/cf-logs [--vendor=axiom\|betterstack\|http] [--check] [--analyze]` | External logging configuration (NEW v1.5.0) |

## Skills (Auto-Invoked)

Skills activate automatically based on your questions:

```
"How much will this worker cost?"           -> optimize-costs
"Is my worker secure?"                      -> guardian (with Budget & Privacy & Loop Audit)
"Design a queue-based pipeline"             -> architect (with Billing Safety Limits)
"Scaffold a Hono API with D1"               -> implement (with Queue Safety)
"How do I scale to 1M requests/day?"        -> scale
"Prevent infinite loops in my worker"       -> loop-breaker
"Add recursion protection to webhooks"      -> loop-breaker
"Is my staging environment protected?"      -> zero-trust
"How do I add custom domains for SaaS?"     -> custom-hostnames
"How do I serve videos with signed URLs?"   -> media-streaming
"Optimize my D1 queries"                    -> query-optimizer (NEW v1.5.0)
"Should I use Queues or Workflows?"         -> workflow-architect (NEW v1.5.0)
"Set up a Cloudflare Tunnel"                -> zero-trust (Tunnel config)
```

### All 13 Skills

| Skill | Purpose |
|-------|---------|
| `architect` | Architecture design with Edge-Native Constraints + Billing Safety + Pages Migration |
| `guardian` | Security + Budget + Privacy + Loop Auditing |
| `implement` | Code scaffolding (Hono, D1, Drizzle) + Queue Safety |
| `loop-breaker` | Recursion guards, idempotency, DO hibernation |
| `optimize-costs` | Cost analysis and optimization |
| `scale` | Scaling strategies and patterns |
| `probes` | MCP audit queries |
| `patterns` | Architecture pattern catalog (5 patterns) |
| `zero-trust` | Access policy auditing + Tunnel config + Admin Protection |
| `custom-hostnames` | SSL for SaaS management |
| `media-streaming` | Stream and Images patterns |
| `query-optimizer` | D1 query optimization, N+1 detection, caching decisions (NEW v1.5.0) |
| `workflow-architect` | Cloudflare Workflows patterns, Queues vs Workflows (NEW v1.5.0) |

## Pre-Deploy Validation Hook

Automatically validates `wrangler.toml` and source code before deployment.

### Severity Levels and Blocking Behavior

| Severity | Blocking? | Action |
|----------|-----------|--------|
| 🔴 CRITICAL | **YES** | Deployment blocked - must fix or suppress |
| 🟠 HIGH | No | Warning only - deployment allowed |
| 🟡 MEDIUM | No | Advisory - deployment allowed |
| 🔵 LOW/INFO | No | Informational - deployment allowed |

### Detection Types

The hook uses three detection methods with different confidence levels:

| Type | Meaning | False Positive Risk |
|------|---------|---------------------|
| `[CONFIG]` | Found directly in wrangler.toml | Very low - definite issue |
| `[STATIC]` | Code pattern match in source | Low - high confidence |
| `[HEURISTIC]` | Inferred from names/patterns | **Higher** - may need verification |

**Heuristic detections** include verification instructions in their output. For example, bucket name patterns may not reflect actual storage class settings.

### Rule Catalog

| Check | Severity | Detection | Description |
|-------|----------|-----------|-------------|
| SEC001 | 🔴 CRITICAL | HEURISTIC | Plaintext secrets in config |
| RES001 | 🟠 HIGH | CONFIG | Queues without dead letter queues |
| RES002 | 🟡 MEDIUM | CONFIG | Missing max_concurrency limit |
| COST001 | 🟡 MEDIUM | CONFIG | High retry counts ($0.40/M per retry) |
| PERF001 | 🔵 LOW | CONFIG | Smart placement disabled |
| PERF004 | 🔵 LOW | CONFIG | Observability not configured |
| PERF005 | 🔴/🟠 | HEURISTIC | Bundle size exceeds tier limits |
| PERF006 | 🟠 HIGH | STATIC | Incompatible native packages |
| ARCH001 | 🟡 MEDIUM | CONFIG | Deprecated `[site]` configuration |
| BUDGET007 | 🔴 CRITICAL | STATIC | D1 row read explosion (unindexed queries) |
| BUDGET008 | 🟡 MEDIUM | STATIC | R2 Class B without edge caching |
| BUDGET009 | 🔵 INFO | HEURISTIC | R2 bucket name suggests Infrequent Access |
| LOOP001 | 🟡 MEDIUM | CONFIG | Missing `cpu_ms` limit |
| LOOP002 | 🔴 CRITICAL | STATIC | D1 query in loop - N+1 |
| LOOP003 | 🟠 HIGH | STATIC | R2 write in loop |
| LOOP004 | 🟡 MEDIUM | STATIC | `setInterval` in DO |
| LOOP005 | 🔴/🟠 | STATIC/HEURISTIC | Worker self-fetch recursion |
| LOOP006 | 🟠 HIGH | CONFIG | Queue without DLQ |
| LOOP007 | 🔴 CRITICAL | STATIC | Unbounded `while(true)` |
| LOOP008 | 🟡 MEDIUM | CONFIG | High queue retry count |
| QUERY001 | 🟠 HIGH | STATIC | SELECT * without LIMIT |
| QUERY005 | 🟠 HIGH | STATIC | Drizzle .all() without .limit() |
| R2002 | 🟡 MEDIUM | STATIC | R2.get() without cache wrapper |
| OBS002 | 🟡 MEDIUM | HEURISTIC | Logs enabled but no export destination |
| OBS003 | 🔵 INFO | CONFIG | High sampling rate with high-volume worker |
| AI001 | 🟠 HIGH | STATIC | Expensive AI model without cost awareness |
| AI002 | 🟡 MEDIUM | STATIC | AI binding without cache wrapper |

### Test File Exclusion

The hook automatically skips test files to reduce false positives. These patterns are excluded:
- `*.test.ts`, `*.spec.ts`, `*.e2e.ts`
- `__tests__/`, `/test/`, `/tests/`
- `*.stories.ts`, `/fixtures/`, `/mocks/`

### Suppressing Warnings

For known-safe patterns, use inline comments to suppress specific rules:

```typescript
// @pre-deploy-ok LOOP005
async function traverse(node: Node, depth = 0) {
  if (depth > 10) return;  // Has depth limit - safe
  for (const child of node.children) {
    await traverse(child, depth + 1);
  }
}

while (true) { // @pre-deploy-ok LOOP007
  // Controlled loop with break condition
  if (shouldStop) break;
}
```

Supported formats:
- `// @pre-deploy-ok LOOP005` - Suppress specific rule
- `// @pre-deploy-ok LOOP005 LOOP002` - Multiple rules
- `// @pre-deploy-ok` - Suppress all rules on that line

### Project-Level Suppression

Create a `.pre-deploy-ignore` file in your project root for config-level rules:

```bash
# .pre-deploy-ignore
RES001:my-queue     # Suppress DLQ warning only for my-queue
COST001             # Suppress high retry warnings globally
RES002              # Suppress max_concurrency warnings globally
LOOP001             # We need high cpu_ms for this worker
```

Format: `RULE_ID` or `RULE_ID:context` (context = queue name, bucket name, etc.)

### Emergency Bypass (Session-Only)

To bypass validation entirely for emergency deploys:

```bash
SKIP_PREDEPLOY_CHECK=1 npx wrangler deploy
```

This bypass is **session-only** and reverts automatically in a new session. The hook detects this environment variable both when set in the shell environment and when prefixed to the command.

### Performance Budgeter

The hook estimates bundle size and warns about tier limits:
- **Free tier**: 1MB compressed - `[HIGH]` if exceeded
- **Standard tier**: 10MB compressed - `[CRITICAL]` if exceeded
- Detects heavy dependencies: `moment`, `lodash`, `aws-sdk`, `sharp`

### Loop Detection & Cost Simulation

The hook scans source code for loop-sensitive patterns:
- D1 queries inside `for`/`while`/`forEach` blocks
- R2 `.put()` calls inside loops
- `setInterval` in Durable Objects without termination
- `fetch(request.url)` self-recursion patterns
- Unbounded `while(true)` or `for(;;)` loops

Detected patterns include **cost simulation** estimates.

## Live Validation Mode

Commands support **live validation** against Cloudflare MCP tools:

```bash
/cf-costs --validate    # Compare estimates with live observability data
/cf-audit --validate    # Verify findings against production metrics
```

All findings are tagged with their data source:

| Tag | Meaning |
|-----|---------|
| `[STATIC]` | Inferred from code/config analysis |
| `[LIVE-VALIDATED]` | Confirmed by observability data |
| `[LIVE-REFUTED]` | Code smell not observed in production |
| `[INCOMPLETE]` | MCP tools unavailable for verification |

## Architecture Pattern Catalog

Apply battle-tested patterns with code examples:

| Pattern | Problem | Solution |
|---------|---------|----------|
| `service-bindings` | Monolithic Worker hitting subrequest limits | Decompose with RPC |
| `d1-batching` | High D1 write costs | Batch INSERT operations |
| `circuit-breaker` | External API cascading failures | Fail-fast with fallback |
| `kv-cache-first` | D1 row read explosion | Cache reads in KV |
| `r2-cdn-cache` | R2 Class B operation costs | Edge cache public assets |

```bash
/cf-pattern service-bindings
/cf-pattern kv-cache-first --analyze-only
```

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
| `/cf-logs` | Full functionality | + Log volume analysis |
| Pre-deploy hook | Full functionality | Same |
| All 13 skills | Full functionality | Same |
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

# External logging (NEW v1.5.0)
/cf-logs                               # Interactive vendor selection wizard
/cf-logs --vendor=axiom                # Direct Axiom configuration
/cf-logs --check                       # Validate existing observability config
/cf-logs --analyze                     # Log volume analysis for sampling recs
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
| D1 | Row read explosion | BUDGET007 | Unindexed queries |
| D1 | Per-row inserts instead of batch | BUDGET003 | `for.*\.run\(` pattern |
| R2 | Class B without caching | BUDGET008 | Public bucket reads |
| R2 | IA minimum billing | BUDGET009 | Reads on IA storage |
| R2 | Frequent small writes | BUDGET002 | `.put()` in loops |
| Durable Objects | Overuse for simple KV | BUDGET001 | DO without coordination need |
| KV | Write-heavy patterns | BUDGET005 | High `.put()` frequency |
| Queues | High retry counts | COST001 | `max_retries > 2` |
| Workers AI | Large models for simple tasks | BUDGET004 | Model name contains `70b` |

### Loop Safety Quick Reference

| Loop Type | Trap ID | Guardian Rule | Detection |
|-----------|---------|---------------|-----------|
| Worker self-fetch | TRAP-LOOP-001 | LOOP005 | `fetch(request.url)` |
| Queue retry storm | TRAP-LOOP-002 | LOOP006, LOOP008 | No DLQ, high retries |
| DO setInterval | TRAP-LOOP-003 | LOOP004 | `setInterval` in DO |
| N+1 queries | TRAP-LOOP-004 | LOOP002 | SQL in loop |
| R2 write flood | TRAP-LOOP-005 | LOOP003 | `.put()` in loop |

### Budget Whisperer

When Claude suggests code changes involving D1, R2, or Durable Objects, the guardian skill automatically:
1. Searches for cost-optimized patterns (`.batch()`, `CREATE INDEX`, buffering)
2. Warns if expensive patterns are detected
3. Cites specific traps from the Cost Watchlist

## Directory Structure

```
cloudflare-engineer/
├── .claude-plugin/plugin.json    # Plugin manifest
├── skills/                       # 13 auto-invoked skills
│   ├── architect/                # Architecture + Edge-Native + Billing Safety + Pages Migration
│   ├── guardian/                 # Security + Budget + Privacy + Loop Auditing
│   ├── implement/                # Code scaffolding + Queue Safety
│   ├── loop-breaker/             # Recursion guards + Loop protection
│   ├── optimize-costs/           # Cost analysis
│   ├── scale/                    # Scaling patterns
│   ├── probes/                   # MCP queries
│   ├── patterns/                 # Pattern catalog (5 patterns)
│   ├── zero-trust/               # Access policies + Tunnel config + Admin Protection
│   ├── custom-hostnames/         # SSL for SaaS
│   ├── media-streaming/          # Stream & Images
│   ├── query-optimizer/          # D1 query optimization (NEW v1.5.0)
│   └── workflow-architect/       # Cloudflare Workflows (NEW v1.5.0)
├── agents/                       # 3 deep-analysis agents
├── commands/                     # 5 slash commands (including /cf-logs)
├── hooks/                        # 3 hooks: SessionStart, PreToolUse, PostToolUse
├── COST_SENSITIVE_RESOURCES.md   # Cost trap catalog
├── LICENSE                       # MIT
├── CONTRIBUTING.md               # Contribution guide
├── SECURITY.md                   # Security policy
└── CHANGELOG.md                  # Version history
```

## Support & Community

| Channel | Purpose |
|---------|---------|
| [GitHub Issues](https://github.com/littlebearapps/cloudflare-engineer/issues) | Bug reports and feature requests |
| [GitHub Discussions](https://github.com/littlebearapps/cloudflare-engineer/discussions) | Questions, ideas, and community chat |
| [Changelog](CHANGELOG.md) | Version history and what's new |

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
