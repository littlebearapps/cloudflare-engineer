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

## Features

### Skills (5)

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `optimize-costs` | Cost questions, billing concerns | Monthly bill prediction, optimization recommendations |
| `guardian` | Security audit, resilience review | Security posture audit, failure mode analysis |
| `architect` | System design, architecture | Mermaid diagrams, wrangler.toml generation |
| `implement` | Scaffolding, code generation | Hono/Drizzle templates, TypeScript patterns |
| `scale` | Scaling, performance | Sharding, caching, read-replication strategies |

### Commands (3)

| Command | Purpose |
|---------|---------|
| `/cf-costs` | Quick cost report for current project |
| `/cf-audit` | Security and configuration audit |
| `/cf-design` | Interactive architecture design wizard |

### Agents (3)

| Agent | Purpose |
|-------|---------|
| `cost-analyzer` | Deep cost analysis using AI Gateway logs and Analytics Engine |
| `security-auditor` | Comprehensive security audit with fix recommendations |
| `architecture-reviewer` | Pattern analysis and optimization suggestions |

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

```
# Get cost optimization recommendations
/cf-costs

# Run security audit
/cf-audit

# Design new architecture interactively
/cf-design

# Skills are auto-invoked based on context:
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
│   └── plugin.json       # Plugin manifest
├── skills/
│   ├── optimize-costs/SKILL.md
│   ├── guardian/SKILL.md
│   ├── architect/SKILL.md
│   ├── implement/SKILL.md
│   └── scale/SKILL.md
├── agents/
│   ├── cost-analyzer.md
│   ├── security-auditor.md
│   └── architecture-reviewer.md
├── commands/
│   ├── cf-costs.md
│   ├── cf-audit.md
│   └── cf-design.md
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

## Version

v1.0.0 - Initial release
