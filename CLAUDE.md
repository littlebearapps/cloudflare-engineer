# Cloudflare Engineer Plugin - Development Guide

## Overview

Claude Code plugin providing **Platform Architect** capabilities for Cloudflare with **D1 Query Optimization**, **Cloudflare Workflows**, **External Logging**, **Python Workers**, **Zero Trust Tooling**, **R2 Cost Protection**, **AI Cost Detection**, and **Opt-In Blocking** (v1.6.1).

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
│   ├── session-start.py        # CF project detection + capability announcement (NEW v1.6.0)
│   ├── post-deploy-verify.py   # Deployment verification + next steps (NEW v1.6.0)
│   └── pre-deploy-check.py     # Validation + Performance Budgeter + Loop Detection + Query + AI Checks
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
2. Register in `hooks/hooks.json` under SessionStart/PreToolUse/PostToolUse

## Pre-Deploy Hook Development

**File**: `hooks/pre-deploy-check.py`

**Input**: JSON via stdin with `tool_name` and `tool_input.command`

**Output**:
- Exit 0 = allow (default - all rules are warnings)
- Exit 2 = block (only for rules with `!RULE_ID` in .pre-deploy-ignore)
- Self-documenting output with severity guide and detection types

**Philosophy**: Warnings by default, blocking is opt-in. Users stay in control.

**Detection Types** (confidence levels):
- `[CONFIG]` - Found in wrangler.toml - definite issue
- `[STATIC]` - Code pattern match - high confidence
- `[HEURISTIC]` - Inferred from names/patterns - may be false positive

**Test File Exclusion**: Automatically skips `*.test.ts`, `*.spec.ts`, `__tests__/`, etc.

**Bypass**: Set `SKIP_PREDEPLOY_CHECK=1` in environment OR command string (session-only).

**Suppression Comments**: Users can suppress specific rules with inline comments:
```typescript
// @pre-deploy-ok LOOP005        // Suppress on next line
while (true) { /* @pre-deploy-ok LOOP007 */ }  // Inline suppression
```

**Project-Level Configuration**: Create `.pre-deploy-ignore` in project root:
```bash
# Suppress rules (hide warnings)
RES001:my-queue     # Suppress for specific queue
COST001             # Suppress globally
LOOP001             # Allow high cpu_ms
LOOP002:helpers.ts  # Suppress for specific file

# Enable blocking (opt-in)
!SEC001             # Block on plaintext secrets
!LOOP005            # Block on self-recursion
!LOOP007            # Block on unbounded loops
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
| `hooks/session-start.py` | CF project detection + fingerprint caching (NEW v1.6.0) |
| `hooks/post-deploy-verify.py` | Deployment verification + next steps (NEW v1.6.0) |
| `hooks/pre-deploy-check.py` | Validation + Performance Budgeter + Loop + Query + AI Checks |
| `COST_SENSITIVE_RESOURCES.md` | Cost trap catalog with TRAP-LOOP-*, TRAP-PRIVACY-*, TRAP-AI-* entries |
| `commands/cf-audit.md` | Audit + Resource Discovery command |
| `commands/cf-pattern.md` | Pattern application command |
| `commands/cf-logs.md` | External logging configuration (NEW v1.5.0) |

## Validation Rule IDs

**Blocking**: Opt-in via `.pre-deploy-ignore` with `!RULE_ID`. All rules are warnings by default.

| ID | Severity | Detection | Check |
|----|----------|-----------|-------|
| SEC001 | CRITICAL | HEURISTIC | Plaintext secrets in config |
| RES001 | HIGH | CONFIG | Queue without DLQ |
| RES002 | MEDIUM | CONFIG | Missing max_concurrency |
| COST001 | MEDIUM | CONFIG | max_retries > 2 |
| PERF001 | LOW | CONFIG | smart_placement disabled |
| PERF004 | LOW | CONFIG | observability.logs disabled |
| PERF005 | CRITICAL/HIGH | HEURISTIC | Bundle size exceeds tier limits |
| PERF006 | HIGH | STATIC | Incompatible native packages |
| ARCH001 | MEDIUM | CONFIG | Deprecated [site] or pages_build_output_dir |
| BUDGET007 | CRITICAL | STATIC | D1 row read explosion - unindexed queries |
| BUDGET008 | MEDIUM | STATIC | R2 Class B without edge caching |
| BUDGET009 | INFO | HEURISTIC | R2 bucket name suggests IA storage |
| LOOP001 | MEDIUM | CONFIG | Missing cpu_ms limit |
| LOOP002 | CRITICAL | STATIC | D1 query in loop (N+1) |
| LOOP003 | HIGH | STATIC | R2 write in loop |
| LOOP004 | MEDIUM | STATIC | setInterval in DO without termination |
| LOOP005 | CRITICAL/HIGH | STATIC/HEURISTIC | Worker self-fetch / recursion |
| LOOP007 | CRITICAL | STATIC | Unbounded while(true) loop |
| QUERY001 | HIGH | STATIC | SELECT * without LIMIT |
| QUERY005 | HIGH | STATIC | Drizzle .all() without .limit() |
| R2002 | MEDIUM | STATIC | R2.get() without cache wrapper |
| OBS002 | MEDIUM | HEURISTIC | Logs enabled but no export destination |
| OBS003 | INFO | CONFIG | High sampling rate with high-volume worker |
| AI001 | HIGH | STATIC | Expensive AI model usage (NEW v1.6.0) |
| AI002 | MEDIUM | HEURISTIC | AI inference without cache wrapper (NEW v1.6.0) |

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

- v1.6.1 - **Opt-In Blocking + File Path Suppression**: All rules are warnings by default (exit 0). Blocking is opt-in via `!RULE_ID` in `.pre-deploy-ignore`. File path context extraction for `RULE_ID:filename.ts` suppression. Respects user agency while maintaining visibility (13 skills, 3 agents, 5 commands, 3 hooks)
- v1.6.0 - **Session Hooks + AI Detection**: SessionStart hook for CF project detection with fingerprint caching, PostToolUse hook for deployment verification with next-step suggestions, AI001/AI002 rules for Workers AI cost detection (expensive models, missing cache), hooks.json restructured to support SessionStart/PreToolUse/PostToolUse (13 skills, 3 agents, 5 commands, 3 hooks)
- v1.5.1 - **Best Practices Audit**: Progressive disclosure refactoring (architect, implement, zero-trust skills split into references/), agent `<example>` blocks added for improved triggering, skill frontmatter standardisation, writing style converted to imperative form (~2,300 lines reduced through modularisation)
- v1.5.0 - **Query Optimization + External Logging + Privacy**: D1 query-optimizer skill (QUERY001-005), workflow-architect skill for Cloudflare Workflows, cf-logs command for external logging (Axiom/Better Stack), Python Workers decision tree, Pages vs Workers migration triggers, Zero Trust extensions (Tunnel config, Access Policy Generator, ZT009-012), R2 Class B cost protection (R2002), Privacy cost traps (TRAP-PRIVACY-001-003), 7 new cost traps, 14 new validation rules (13 skills, 3 agents, 5 commands, 1 hook)
- v1.4.1 - **Hook Suppression**: `@pre-deploy-ok` inline comments, `.pre-deploy-ignore` project file, `SKIP_PREDEPLOY_CHECK` env var bypass, BUDGET009 suppression support, improved LOOP005 depth detection, TOML parser fixes
- v1.4.0 - **Cost Awareness + Containers + Observability**: D1 row read protection (BUDGET007, kv-cache-first pattern), R2 Class B caching (BUDGET008, r2-cdn-cache pattern), R2 IA minimum billing trap (BUDGET009), Workers + Assets architecture (ARCH001), Workload Router for Isolates vs Containers, Observability Export (Axiom/Better Stack/OTel), 2 new patterns, 4 new cost traps (11 skills, 3 agents, 4 commands, 1 hook)
- v1.3.0 - **Loop Protection upgrade**: Billing Safety Limits in architect, new loop-breaker skill for recursion guards, Queue Safety patterns with idempotency in implement, Loop-Sensitive Resource Auditing in guardian, pre-deploy hook with loop detection and cost simulation, TRAP-LOOP-* cost traps (11 skills, 3 agents, 4 commands, 1 hook)
- v1.2.0 - Platform Architect upgrade: Vibecoder Proactive Safeguards, Resource Discovery, Edge-Native Constraints, Performance Budgeter, zero-trust, custom-hostnames, media-streaming skills (10 skills, 3 agents, 4 commands, 1 hook)
- v1.1.0 - Live validation (`--validate`), provenance tagging, probes skill, patterns skill (7 skills, 3 agents, 4 commands, 1 hook)
- v1.0.0 - Initial release (5 skills, 3 agents, 3 commands, 1 hook)
