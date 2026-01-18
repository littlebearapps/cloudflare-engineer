# Cloudflare Engineer Plugin - Development Guide

## Overview

Claude Code plugin providing **Platform Architect** capabilities for Cloudflare with **D1 Query Optimization**, **Cloudflare Workflows**, **External Logging**, **Python Workers**, **Zero Trust Tooling**, and **R2 Cost Protection** (v1.5.0).

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
│   ├── architect/SKILL.md      # Architecture + Edge-Native Constraints + Billing Safety + Pages Migration
│   ├── guardian/SKILL.md       # Security + Budget + Privacy + Loop Auditing
│   ├── implement/SKILL.md      # Code scaffolding + Queue Safety
│   ├── loop-breaker/SKILL.md   # Recursion guards + Loop protection
│   ├── optimize-costs/SKILL.md # Cost analysis
│   ├── scale/SKILL.md          # Scaling patterns
│   ├── probes/SKILL.md         # MCP audit probe queries
│   ├── query-optimizer/SKILL.md # D1 query optimization + N+1 detection (NEW v1.5.0)
│   ├── workflow-architect/SKILL.md # Cloudflare Workflows patterns (NEW v1.5.0)
│   ├── patterns/               # Architecture patterns
│   │   ├── SKILL.md
│   │   ├── service-bindings.md
│   │   ├── d1-batching.md
│   │   ├── circuit-breaker.md
│   │   ├── kv-cache-first.md   # D1 row read protection
│   │   └── r2-cdn-cache.md     # R2 Class B caching
│   ├── zero-trust/SKILL.md     # Access policy auditing + Tunnel config + Admin Protection
│   ├── custom-hostnames/SKILL.md # SSL for SaaS
│   └── media-streaming/SKILL.md  # Stream & Images
├── agents/*.md                 # Auto-discovered agents (with MCP tools)
├── commands/
│   ├── cf-audit.md             # Audit + Resource Discovery
│   ├── cf-pattern.md           # Pattern application
│   ├── cf-logs.md              # External logging configuration (NEW v1.5.0)
│   └── ...
├── hooks/
│   ├── hooks.json              # Hook configuration
│   └── pre-deploy-check.py     # Validation + Performance Budgeter + Loop Detection + Query Checks
├── COST_SENSITIVE_RESOURCES.md # Cost trap catalog including loop + privacy traps
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

**Bypass**: Set `SKIP_PREDEPLOY_CHECK=1` environment variable to skip validation entirely.

**Suppression Comments**: Users can suppress specific rules with inline comments:
```typescript
// @pre-deploy-ok LOOP005        // Suppress on next line
while (true) { /* @pre-deploy-ok LOOP007 */ }  // Inline suppression
```

**Project-Level Ignore**: Create `.pre-deploy-ignore` in project root:
```bash
RES001:my-queue     # Suppress for specific queue
COST001             # Suppress globally
LOOP001             # Allow high cpu_ms
```

**Testing**:
```bash
# Test against any wrangler config
cd /path/to/worker
echo '{"tool_name":"Bash","tool_input":{"command":"npx wrangler deploy"}}' | \
  python3 ~/.claude/local-marketplace/cloudflare-engineer/hooks/pre-deploy-check.py

# Test with bypass
echo '{"tool_name":"Bash","tool_input":{"command":"npx wrangler deploy"}}' | \
  SKIP_PREDEPLOY_CHECK=1 python3 ~/.claude/local-marketplace/cloudflare-engineer/hooks/pre-deploy-check.py
```

**JSONC Parser**: Character-by-character to handle `/*` in URL patterns correctly.

## Cloudflare Service Coverage

| Service | Skills | Hook Checks |
|---------|--------|-------------|
| Workers | architect, implement, loop-breaker | PERF001, PERF005, PERF006, LOOP001, LOOP005, LOOP007, ARCH001 |
| Python Workers | architect | - (decision tree v1.5.0) |
| Containers | architect | - |
| D1 | query-optimizer, implement, scale, loop-breaker, patterns | BUDGET003, BUDGET007, LOOP002, QUERY001, QUERY005 |
| R2 | implement, media-streaming, patterns | BUDGET002, BUDGET008, BUDGET009, LOOP003, R2002 |
| KV | implement, patterns | BUDGET005 (writes) |
| Queues | architect, scale, loop-breaker | RES001, RES002, COST001, LOOP006, LOOP008 |
| Workflows | workflow-architect | - (NEW v1.5.0) |
| Vectorize | implement | BUDGET006 (scaling) |
| AI Gateway | optimize-costs | BUDGET004, PRIV003 |
| Durable Objects | scale, guardian, loop-breaker | BUDGET001, LOOP004 (setInterval) |
| Access | zero-trust | ZT001-ZT012 |
| Tunnel | zero-trust | - (NEW v1.5.0) |
| Custom Hostnames | custom-hostnames | - |
| Stream | media-streaming | - |
| Images | media-streaming | - |
| Observability | cf-logs command | OBS001-OBS003 (NEW v1.5.0) |

## Key Files to Know

| File | Purpose |
|------|---------|
| `skills/optimize-costs/SKILL.md` | Pricing formulas, cost patterns |
| `skills/guardian/SKILL.md` | Security + Budget + Privacy + Loop Auditing |
| `skills/architect/SKILL.md` | Mermaid templates, Edge-Native Constraints, Billing Safety, Pages Migration |
| `skills/query-optimizer/SKILL.md` | D1 query optimization, N+1 detection, caching decisions (NEW v1.5.0) |
| `skills/workflow-architect/SKILL.md` | Cloudflare Workflows patterns, Queues vs Workflows (NEW v1.5.0) |
| `skills/loop-breaker/SKILL.md` | Recursion guards, idempotency, DO hibernation |
| `skills/probes/SKILL.md` | MCP tool queries for live validation |
| `skills/patterns/SKILL.md` | Architecture pattern catalog |
| `skills/zero-trust/SKILL.md` | Access policy auditing, Tunnel config, Admin Protection |
| `skills/custom-hostnames/SKILL.md` | SSL for SaaS patterns |
| `skills/media-streaming/SKILL.md` | Stream & Images patterns |
| `skills/implement/SKILL.md` | Code scaffolding + Queue Safety patterns |
| `hooks/pre-deploy-check.py` | Validation + Performance Budgeter + Loop Detection + Query Checks |
| `COST_SENSITIVE_RESOURCES.md` | Cost trap catalog with TRAP-LOOP-*, TRAP-PRIVACY-* entries |
| `commands/cf-audit.md` | Audit + Resource Discovery command |
| `commands/cf-pattern.md` | Pattern application command |
| `commands/cf-logs.md` | External logging configuration (NEW v1.5.0) |

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
| ARCH001 | MEDIUM | Deprecated [site] or pages_build_output_dir |
| BUDGET001-006 | INFO-HIGH | Budget enforcement triggers |
| BUDGET007 | CRITICAL | D1 row read explosion - unindexed queries |
| BUDGET008 | MEDIUM | R2 Class B without edge caching |
| BUDGET009 | HIGH | R2 Infrequent Access with reads |
| PRIV001-003 | MEDIUM-CRITICAL | Privacy enforcement (auth headers, PII, financial) |
| ZT001-008 | HIGH-CRITICAL | Zero Trust gaps |
| ZT009 | CRITICAL | /jobs/* route without service token auth (NEW v1.5.0) |
| ZT010 | HIGH | Admin uses password-only (no OTP/MFA) (NEW v1.5.0) |
| ZT011 | CRITICAL | Service token credentials hardcoded (NEW v1.5.0) |
| ZT012 | MEDIUM | Admin session > 4h (NEW v1.5.0) |
| LOOP001 | MEDIUM | Missing cpu_ms limit |
| LOOP002 | CRITICAL | D1 query in loop (N+1) |
| LOOP003 | HIGH | R2 write in loop |
| LOOP004 | HIGH | setInterval in DO without termination |
| LOOP005 | CRITICAL | Worker self-fetch / recursion |
| LOOP006 | HIGH | Queue without DLQ (retry loop) |
| LOOP007 | CRITICAL | Unbounded while(true) loop |
| LOOP008 | MEDIUM | High queue retry count |
| QUERY001 | HIGH | SELECT * without LIMIT (NEW v1.5.0) |
| QUERY005 | HIGH | Drizzle .all() without .limit() (NEW v1.5.0) |
| R2002 | MEDIUM | R2.get() without cache wrapper (NEW v1.5.0) |
| OBS001 | LOW | Observability not enabled (NEW v1.5.0) |
| OBS002 | MEDIUM | Logs enabled but no export destination (NEW v1.5.0) |
| OBS003 | INFO | High sampling rate with high-volume worker (NEW v1.5.0) |

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

- v1.5.0 - **Query Optimization + External Logging + Privacy**: D1 query-optimizer skill (QUERY001-005), workflow-architect skill for Cloudflare Workflows, cf-logs command for external logging (Axiom/Better Stack), Python Workers decision tree, Pages vs Workers migration triggers, Zero Trust extensions (Tunnel config, Access Policy Generator, ZT009-012), R2 Class B cost protection (R2002), Privacy cost traps (TRAP-PRIVACY-001-003), 7 new cost traps, 14 new validation rules (13 skills, 3 agents, 5 commands, 1 hook)
- v1.4.1 - **Hook Suppression**: `@pre-deploy-ok` inline comments, `.pre-deploy-ignore` project file, `SKIP_PREDEPLOY_CHECK` env var bypass, BUDGET009 suppression support, improved LOOP005 depth detection, TOML parser fixes
- v1.4.0 - **Cost Awareness + Containers + Observability**: D1 row read protection (BUDGET007, kv-cache-first pattern), R2 Class B caching (BUDGET008, r2-cdn-cache pattern), R2 IA minimum billing trap (BUDGET009), Workers + Assets architecture (ARCH001), Workload Router for Isolates vs Containers, Observability Export (Axiom/Better Stack/OTel), 2 new patterns, 4 new cost traps (11 skills, 3 agents, 4 commands, 1 hook)
- v1.3.0 - **Loop Protection upgrade**: Billing Safety Limits in architect, new loop-breaker skill for recursion guards, Queue Safety patterns with idempotency in implement, Loop-Sensitive Resource Auditing in guardian, pre-deploy hook with loop detection and cost simulation, TRAP-LOOP-* cost traps (11 skills, 3 agents, 4 commands, 1 hook)
- v1.2.0 - Platform Architect upgrade: Vibecoder Proactive Safeguards, Resource Discovery, Edge-Native Constraints, Performance Budgeter, zero-trust, custom-hostnames, media-streaming skills (10 skills, 3 agents, 4 commands, 1 hook)
- v1.1.0 - Live validation (`--validate`), provenance tagging, probes skill, patterns skill (7 skills, 3 agents, 4 commands, 1 hook)
- v1.0.0 - Initial release (5 skills, 3 agents, 3 commands, 1 hook)
