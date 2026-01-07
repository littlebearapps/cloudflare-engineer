# Cloudflare Engineer Plugin

A Claude Code plugin that provides Senior Cloudflare Systems Engineer capabilities for designing, implementing, optimizing, and securing Cloudflare Workers applications.

## Installation

```bash
# Add local marketplace (once)
claude plugin marketplace add ~/.claude/local-marketplace

# Install plugin
claude plugin install cloudflare-engineer@local-plugins
```

**Source**: `~/.claude/local-marketplace/cloudflare-engineer/`
**Cache**: `~/.claude/plugins/cache/local-plugins/cloudflare-engineer/`

## What's New in v1.1.0

### Live Validation Mode (`--validate`)

Commands and agents now support **live validation** against Cloudflare MCP tools:

- **Architecture verification**: Run `EXPLAIN QUERY PLAN` to verify D1 index usage
- **Cost validation**: Compare static estimates against actual observability data
- **Security verification**: Check real request patterns against static findings

```bash
/cf-costs --validate    # Compare estimates with live observability
/cf-audit --validate    # Verify findings against production data
```

### Provenance Tagging

All findings are now tagged with their data source:

| Tag | Meaning |
|-----|---------|
| `[STATIC]` | Inferred from code/config analysis |
| `[LIVE-VALIDATED]` | Confirmed by observability data |
| `[LIVE-REFUTED]` | Code smell not observed in production |
| `[INCOMPLETE]` | MCP tools unavailable for verification |

### Pattern Catalog

New actionable patterns with before/after code examples:

| Pattern | Problem | Solution |
|---------|---------|----------|
| `service-bindings` | Monolithic Worker hitting subrequest limits | Decompose with RPC |
| `d1-batching` | High D1 write costs | Batch INSERT operations |
| `circuit-breaker` | External API cascading failures | Fail-fast with fallback |

Apply patterns with: `/cf-pattern service-bindings`

### Audit Probes

Pre-built diagnostic queries for live validation:

- **D1**: Schema discovery, index inventory, EXPLAIN QUERY PLAN
- **Observability**: Error rates, latency percentiles
- **AI Gateway**: Cost by model, cache hit rates
- **Queues**: DLQ depth, retry rate analysis

## Features

### Skills (7)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `optimize-costs` | Cost questions, billing concerns | Monthly bill prediction, optimization recommendations |
| `guardian` | Security audit, resilience review | Security posture audit, failure mode analysis |
| `architect` | System design, architecture | Mermaid diagrams, wrangler.toml generation |
| `implement` | Scaffolding, code generation | Hono/Drizzle templates, TypeScript patterns |
| `scale` | Scaling, performance | Sharding, caching, read-replication strategies |
| `probes` | Audit queries | Pre-built MCP tool queries for live validation |
| `patterns` | Architecture patterns | Remediation patterns with code examples |

### Commands (4)

| Command | Purpose |
|---------|---------|
| `/cf-costs [--validate]` | Cost report with optional live data validation |
| `/cf-audit [--validate]` | Security and configuration audit |
| `/cf-design` | Interactive architecture design wizard |
| `/cf-pattern <name>` | Apply architecture pattern to current project |

### Agents (3)

| Agent | Purpose | MCP Tools |
|-------|---------|-----------|
| `cost-analyzer` | Deep cost analysis with live validation | observability, ai-gateway, bindings |
| `security-auditor` | Comprehensive security audit | bindings, observability |
| `architecture-reviewer` | Pattern analysis with EXPLAIN QUERY PLAN | bindings, observability |

### Hooks (1)

| Hook | Event | Purpose |
|------|-------|---------|
| `pre-deploy-check` | PreToolUse (Bash) | Validates wrangler config before `wrangler deploy` |

## Pre-Deploy Hook

The pre-deploy hook automatically validates your wrangler.toml/wrangler.jsonc before deployment:

**Checks performed:**
- `SEC001` - Plaintext secrets (CRITICAL - blocks deploy)
- `SEC002` - Missing vars encryption
- `RES001` - Queues without dead letter queues (HIGH)
- `COST001` - High retry counts on queues (MEDIUM)
- `PERF001` - Smart placement disabled (MEDIUM)
- `PERF004` - Missing observability config (LOW)

**Exit codes:**
- `0` - Deploy allowed (no issues or warnings only)
- `2` - Deploy blocked (CRITICAL issues found)

## MCP Tool Requirements

For `--validate` mode, these Cloudflare MCP servers should be configured:

| MCP Server | Used For |
|------------|----------|
| `cloudflare-observability` | Worker metrics, error rates, latency |
| `cloudflare-ai-gateway` | AI costs, cache hit rates |
| `cloudflare-bindings` | D1 EXPLAIN QUERY PLAN, resource lists |

**Graceful Degradation**: If MCP tools are unavailable, commands will:
1. Note which tools are missing
2. Continue with static analysis
3. Tag affected findings as `[INCOMPLETE]`

## Supported Cloudflare Services

- Workers (standard and Durable Objects)
- D1 (SQLite database)
- R2 (object storage)
- KV (key-value store)
- Queues (message queues with DLQ)
- Vectorize (vector database)
- AI Gateway (LLM routing)
- Workflows (durable execution)
- Hyperdrive (database connection pooling)
- Analytics Engine (metrics)

## Usage Examples

```bash
# Get cost optimization recommendations
/cf-costs

# Cost report with live validation
/cf-costs --validate

# Run security audit
/cf-audit

# Security audit with live verification
/cf-audit --validate --category=security

# Design new architecture interactively
/cf-design

# Apply architecture pattern
/cf-pattern d1-batching

# Analyze pattern applicability
/cf-pattern service-bindings --analyze-only
```

Skills are auto-invoked based on context:
```
"How much will this worker cost per month?"  -> optimize-costs
"Is my worker secure?"                        -> guardian
"Design a queue-based pipeline"               -> architect
"Scaffold a Hono API with D1"                 -> implement
"How do I scale to 1M requests/day?"          -> scale
```

## Directory Structure

```
cloudflare-engineer/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest
├── skills/
│   ├── optimize-costs/SKILL.md
│   ├── guardian/SKILL.md
│   ├── architect/SKILL.md
│   ├── implement/SKILL.md
│   ├── scale/SKILL.md
│   ├── probes/SKILL.md       # NEW: Audit probe definitions
│   └── patterns/             # NEW: Architecture patterns
│       ├── SKILL.md
│       ├── service-bindings.md
│       ├── d1-batching.md
│       └── circuit-breaker.md
├── agents/
│   ├── cost-analyzer.md
│   ├── security-auditor.md
│   └── architecture-reviewer.md
├── commands/
│   ├── cf-costs.md
│   ├── cf-audit.md
│   ├── cf-design.md
│   └── cf-pattern.md         # NEW: Pattern application
├── hooks/
│   ├── hooks.json
│   └── pre-deploy-check.py
├── README.md
└── CLAUDE.md
```

## Requirements

- Claude Code with plugin support
- Python 3.x (for pre-deploy hook)
- Cloudflare account with Workers enabled
- (Optional) Cloudflare MCP servers for `--validate` mode

## Version

v1.1.0 - Live validation, provenance tagging, and pattern catalog

### Changelog

**v1.1.0**
- Added `--validate` mode for live data validation via MCP tools
- Added provenance tagging (`[STATIC]`, `[LIVE-VALIDATED]`, `[LIVE-REFUTED]`, `[INCOMPLETE]`)
- Added probes skill with pre-built audit queries
- Added patterns skill with 3 priority patterns (service-bindings, d1-batching, circuit-breaker)
- Added `/cf-pattern` command for pattern application
- Enhanced all agents with explicit MCP tool orchestration
- Added graceful degradation when MCP tools unavailable

**v1.0.0**
- Initial release with 5 skills, 3 agents, 3 commands, 1 hook
