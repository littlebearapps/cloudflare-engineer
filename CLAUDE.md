# Cloudflare Engineer Plugin - Development Guide

## Overview

Claude Code plugin providing **Platform Architect** capabilities for Cloudflare (upgraded from Senior Developer in v1.2.0).

**GitHub**: https://github.com/littlebearapps/cloudflare-engineer
**Local**: `~/.claude/local-marketplace/cloudflare-engineer/`
**Status**: Public, PR pending at [anthropics/claude-plugins-official#170](https://github.com/anthropics/claude-plugins-official/pull/170)

## CI/CD

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `validate.yml` | push/PR to main | Validates plugin.json, Python syntax, required files, markdown |
| `release.yml` | version tags (v*) | Creates GitHub releases with install instructions |
| `claude.yml` | PRs, @claude mentions | Claude Max PR review via OAuth |

## Plugin Structure

```
cloudflare-engineer/
├── .claude-plugin/plugin.json  # Manifest (name, description, version)
├── skills/
│   ├── architect/SKILL.md      # Architecture + Edge-Native Constraints
│   ├── guardian/SKILL.md       # Security + Budget + Privacy Enforcement
│   ├── implement/SKILL.md      # Code scaffolding
│   ├── optimize-costs/SKILL.md # Cost analysis
│   ├── scale/SKILL.md          # Scaling patterns
│   ├── probes/SKILL.md         # MCP audit probe queries
│   ├── patterns/               # Architecture patterns
│   │   ├── SKILL.md
│   │   ├── service-bindings.md
│   │   ├── d1-batching.md
│   │   └── circuit-breaker.md
│   ├── zero-trust/SKILL.md     # Access policy auditing (NEW)
│   ├── custom-hostnames/SKILL.md # SSL for SaaS (NEW)
│   └── media-streaming/SKILL.md  # Stream & Images (NEW)
├── agents/*.md                 # Auto-discovered agents (with MCP tools)
├── commands/*.md               # Slash commands (--validate, --discover)
├── hooks/
│   ├── hooks.json              # Hook configuration
│   └── pre-deploy-check.py     # Python validation + Performance Budgeter
└── README.md                   # User documentation
```

## Adding Components

### New Skill
```bash
mkdir -p skills/new-skill
# Create skills/new-skill/SKILL.md with:
# - Trigger conditions (when to auto-invoke)
# - Knowledge content (Cloudflare patterns, pricing, limits)
```

### New Agent
```bash
# Create agents/new-agent.md with YAML frontmatter:
# name, description, tools (Glob, Grep, Read, Bash, etc.)
```

### New Command
```bash
# Create commands/cf-newcmd.md
# User invokes with /cf-newcmd
```

### New Hook
1. Add Python/bash script to `hooks/`
2. Register in `hooks/hooks.json` under PreToolUse/PostToolUse

## Pre-Deploy Hook Development

**File**: `hooks/pre-deploy-check.py`

**Input**: JSON via stdin with `tool_name` and `tool_input.command`

**Output**:
- Exit 0 = allow
- Exit 2 = block
- Print issues to stdout (parsed by Claude Code)

**Testing**:
```bash
# Test against any wrangler config
cd /path/to/worker
echo '{"tool_name":"Bash","tool_input":{"command":"npx wrangler deploy"}}' | \
  python3 ~/.claude/local-marketplace/cloudflare-engineer/hooks/pre-deploy-check.py
```

**JSONC Parser**: Character-by-character to handle `/*` in URL patterns correctly.

## Cloudflare Service Coverage

| Service | Skills | Hook Checks |
|---------|--------|-------------|
| Workers | architect, implement | PERF001, PERF005, PERF006 |
| D1 | implement, scale | BUDGET003 (batching) |
| R2 | implement, media-streaming | BUDGET002 (writes) |
| KV | implement | BUDGET005 (writes) |
| Queues | architect, scale | RES001, RES002, COST001 |
| Vectorize | implement | BUDGET006 (scaling) |
| AI Gateway | optimize-costs | BUDGET004, PRIV003 |
| Workflows | architect | - |
| Durable Objects | scale, guardian | BUDGET001 |
| Access | zero-trust | ZT001-ZT008 |
| Custom Hostnames | custom-hostnames | - |
| Stream | media-streaming | - |
| Images | media-streaming | - |

## Key Files to Know

| File | Purpose |
|------|---------|
| `skills/optimize-costs/SKILL.md` | Pricing formulas, cost patterns |
| `skills/guardian/SKILL.md` | Security + Budget + Privacy checklist |
| `skills/architect/SKILL.md` | Mermaid templates, Edge-Native Constraints |
| `skills/probes/SKILL.md` | MCP tool queries for live validation |
| `skills/patterns/SKILL.md` | Architecture pattern catalog |
| `skills/zero-trust/SKILL.md` | Access policy auditing |
| `skills/custom-hostnames/SKILL.md` | SSL for SaaS patterns |
| `skills/media-streaming/SKILL.md` | Stream & Images patterns |
| `hooks/pre-deploy-check.py` | Validation rules + Performance Budgeter |
| `commands/cf-audit.md` | Audit + Resource Discovery command |
| `commands/cf-pattern.md` | Pattern application command |

## Validation Rule IDs

| ID | Severity | Check |
|----|----------|-------|
| SEC001 | CRITICAL | Plaintext secrets in config |
| RES001 | HIGH | Queue without DLQ |
| RES002 | MEDIUM | Missing max_concurrency |
| COST001 | MEDIUM | max_retries > 2 |
| PERF001 | LOW | smart_placement disabled |
| PERF004 | LOW | observability.logs disabled |
| PERF005 | CRITICAL/HIGH | Bundle size exceeds tier limits |
| PERF006 | HIGH | Incompatible native packages |
| BUDGET001-006 | INFO-HIGH | Budget enforcement triggers |
| PRIV001-005 | MEDIUM-CRITICAL | Privacy enforcement triggers |
| ZT001-008 | HIGH-CRITICAL | Zero Trust gaps |

## Testing Changes

1. Edit source in `~/.claude/local-marketplace/cloudflare-engineer/`
2. Run local validation: `python3 -m py_compile hooks/pre-deploy-check.py`
3. Re-install: `claude plugin update cloudflare-engineer@local-plugins`
4. Start new Claude Code session to reload
5. Test with real project (e.g., Scout at `~/claude-code-tools/lba/scout/workers/`)

## Contributing

1. Fork https://github.com/littlebearapps/cloudflare-engineer
2. Create feature branch
3. Push and open PR - Claude will auto-review via `@claude`
4. CI runs validate.yml on all PRs

## Version History

- v1.2.0 - Platform Architect upgrade: Vibecoder Proactive Safeguards, Resource Discovery, Edge-Native Constraints, Performance Budgeter, zero-trust, custom-hostnames, media-streaming skills (10 skills, 3 agents, 4 commands, 1 hook)
- v1.1.0 - Live validation (`--validate`), provenance tagging, probes skill, patterns skill (7 skills, 3 agents, 4 commands, 1 hook)
- v1.0.0 - Initial release (5 skills, 3 agents, 3 commands, 1 hook)
