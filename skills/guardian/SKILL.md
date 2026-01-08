---
name: guardian
description: Proactively audit Cloudflare configurations for security vulnerabilities, resilience gaps, cost traps, AND budget/privacy risks. Use this skill when reviewing wrangler configs, before deployments, investigating issues, or when ANY architecture decision involves Durable Objects, R2, Workers AI, or high-volume operations. This skill PROACTIVELY warns about cost impacts before users ask.
---

# Cloudflare Guardian Skill

Audit wrangler configurations for security vulnerabilities, performance issues, cost traps, resilience gaps, **and proactively enforce budget/privacy constraints**. Acts as a senior SRE and FinOps engineer reviewing infrastructure-as-code.

## Cost Watchlist Reference

**IMPORTANT**: For detailed cost trap documentation, reference `${CLAUDE_PLUGIN_ROOT}/COST_SENSITIVE_RESOURCES.md`.

When issuing cost warnings, use provenance tags:
- `[STATIC:COST_WATCHLIST]` - Pattern detected via code analysis
- `[LIVE-VALIDATED:COST_WATCHLIST]` - Confirmed by observability data
- `[REFUTED:COST_WATCHLIST]` - Pattern exists but not hitting thresholds

## Budget Whisperer Behavior

**CRITICAL**: When Claude suggests ANY code change involving the following, the guardian skill MUST trigger proactive checks:

### D1 Write Operations
If suggesting code that includes `.run()`, `.first()`, or database writes:
1. **Search for `.batch()`** - If missing, warn about per-row insert costs
2. **Search for `CREATE INDEX`** - If querying unindexed columns, warn about scan costs
3. **Cite**: `TRAP-D1-001` or `TRAP-D1-002` from COST_SENSITIVE_RESOURCES.md

```
Budget Whisperer Check:
- Detected: D1 write operation in proposed code
- Searched for: db.batch() usage
- Found: ❌ Missing batch operations
- Warning: [STATIC:COST_WATCHLIST] TRAP-D1-001
  Per-row INSERT detected. At 10K rows, this costs $0.01 vs $0.00001 batched.
  Recommendation: Wrap in db.batch() with max 1000 statements per batch.
```

### R2 Write Operations
If suggesting code that includes `.put()`:
1. **Check loop context** - Is `.put()` inside a loop or frequently called handler?
2. **Search for buffering** - Any aggregation before write?
3. **Cite**: `TRAP-R2-001` from COST_SENSITIVE_RESOURCES.md

### Durable Objects Usage
If suggesting DO architecture:
1. **Check use case** - Is coordination/locking actually needed?
2. **Suggest alternatives** - KV for simple storage, D1 for relational
3. **Cite**: `TRAP-DO-001` from COST_SENSITIVE_RESOURCES.md

## Vibecoder Proactive Safeguards

**IMPORTANT**: This skill should proactively warn users about cost and privacy impacts BEFORE they deploy or even ask about costs. When reviewing ANY architecture that includes the following, immediately surface budget/privacy alerts:

### Budget Enforcement Triggers

| Service/Pattern | Threshold | Proactive Warning |
|-----------------|-----------|-------------------|
| Durable Objects | Any usage | "DO charges ~$0.15/GB-month storage + $0.50/M requests. Consider KV for simple key-value." |
| R2 Class A ops | >1M/month | "R2 writes cost $4.50/M. Buffer writes or use presigned URLs for client uploads." |
| D1 Writes | >10M/month | "D1 writes cost $1/M. Detected pattern suggests >$10/mo. Batch to ≤1,000 rows." |
| Workers AI (>8B) | Any usage | "Large models (Llama 11B+) cost $0.68/M tokens. Use 8B or smaller for bulk." |
| Vectorize | >1M vectors | "Approaching 5M vector limit. Plan sharding strategy." |
| KV Writes | >5M/month | "KV writes cost $5/M (10× reads). Consider D1 or R2 for write-heavy." |

### Privacy Enforcement Triggers

| Pattern | Severity | Proactive Warning |
|---------|----------|-------------------|
| PII in logs | CRITICAL | "Detected potential PII logging. Use structured logging with redaction." |
| User data in KV keys | HIGH | "KV keys with user IDs may leak via Workers dashboard. Hash or encrypt." |
| AI prompts with PII | HIGH | "AI Gateway logs may contain user data. Enable prompt redaction." |
| R2 public buckets | HIGH | "R2 bucket appears public. Verify intentional or add authentication." |
| Analytics with user IDs | MEDIUM | "User IDs in Analytics Engine may persist. Use anonymized identifiers." |

## Audit Categories

### Security Audit Rules

| ID | Name | Severity | Check |
|----|------|----------|-------|
| SEC001 | Secrets in plaintext | CRITICAL | `vars.*` contains API_KEY, SECRET, PASSWORD, TOKEN patterns |
| SEC002 | Missing route auth | HIGH | Routes without `cf.access` or auth middleware |
| SEC003 | CORS wildcard | MEDIUM | `cors.origins` includes `*` |
| SEC004 | Exposed admin routes | HIGH | `/admin/*` routes without auth |
| SEC005 | Missing rate limiting | MEDIUM | No rate limit bindings for public APIs |
| SEC006 | Debug mode enabled | LOW | `ENVIRONMENT` or `DEBUG` set to development/true |

### Performance Audit Rules

| ID | Name | Severity | Check |
|----|------|----------|-------|
| PERF001 | Missing Smart Placement | LOW | `placement.mode` not set |
| PERF002 | D1 without indexes | MEDIUM | D1 bindings but no CREATE INDEX in migrations |
| PERF003 | Large bundled dependencies | MEDIUM | Bundle >10MB (check `main` entry) |
| PERF004 | Missing observability | LOW | No `observability` config block |
| PERF005 | Frequent cron | LOW | Cron more often than every 5 minutes |

### Cost Audit Rules

| ID | Name | Severity | Check |
|----|------|----------|-------|
| COST001 | Queue retries high | MEDIUM | `max_retries > 1` for potentially idempotent consumers |
| COST002 | No cron batching | LOW | Multiple crons that could be combined |
| COST003 | AI without caching | MEDIUM | AI bindings but no AI Gateway |
| COST004 | Large model usage | LOW | Workers AI with >8B parameter models |
| COST005 | Missing Analytics Engine | INFO | Using D1/KV for metrics instead of free AE |

### Resilience Audit Rules

| ID | Name | Severity | Check |
|----|------|----------|-------|
| RES001 | Missing DLQ | HIGH | Queues without `dead_letter_queue` binding |
| RES002 | No concurrency limit | MEDIUM | `max_concurrency` not set for queue consumers |
| RES003 | Single region | LOW | No `cf.smart_placement` for latency-sensitive |
| RES004 | Missing retry config | MEDIUM | Queue consumer without explicit retry config |
| RES005 | No circuit breaker | LOW | External API calls without timeout/fallback |

### Budget Audit Rules (Proactive)

| ID | Name | Severity | Check |
|----|------|----------|-------|
| BUDGET001 | Durable Objects usage | INFO | Any DO binding - proactively explain cost model |
| BUDGET002 | R2 write-heavy pattern | MEDIUM | Frequent R2 Class A ops without buffering |
| BUDGET003 | D1 per-row inserts | HIGH | Loop-based INSERTs instead of batch |
| BUDGET004 | Large AI model | MEDIUM | Workers AI with >8B parameter model |
| BUDGET005 | KV write-heavy | MEDIUM | >5M KV writes/month pattern |
| BUDGET006 | Vectorize scaling | INFO | >1M vectors - warn about 5M limit |

### Privacy Audit Rules

| ID | Name | Severity | Check |
|----|------|----------|-------|
| PRIV001 | PII in logs | CRITICAL | console.log with user data patterns |
| PRIV002 | User IDs in KV keys | HIGH | KV key patterns containing user/email/phone |
| PRIV003 | AI prompts PII | HIGH | AI bindings without redaction middleware |
| PRIV004 | R2 public access | HIGH | R2 bucket without authentication |
| PRIV005 | Analytics PII | MEDIUM | User identifiers in Analytics Engine writes |

## Audit Workflow

### Step 1: Parse Wrangler Config

Support both TOML and JSONC formats:
```
1. Read wrangler.toml or wrangler.jsonc
2. Parse into structured format
3. Extract: name, bindings, routes, triggers, vars
```

### Step 2: Run Security Checks

```
For each security rule:
1. Check if pattern exists in config
2. If violation found:
   - Record rule ID, severity, location
   - Generate specific recommendation
   - Include docs URL if available
```

### Step 3: Run Performance Checks

```
For each performance rule:
1. Check config for anti-patterns
2. Cross-reference with migrations (for D1 index checks)
3. Record findings with optimization recommendations
```

### Step 4: Run Cost Checks

```
For each cost rule:
1. Identify cost-amplifying patterns
2. Estimate impact if possible
3. Provide specific fixes
```

### Step 5: Run Resilience Checks

```
For each resilience rule:
1. Check for missing failure handling
2. Identify single points of failure
3. Recommend redundancy patterns
```

### Step 5b: Run Budget Enforcement Checks (Proactive)

```
For bindings that trigger budget warnings:
1. Detect Durable Objects → Explain cost model proactively
2. Detect R2 writes → Check for buffering patterns
3. Detect D1 writes → Check for batch vs per-row
4. Detect Workers AI → Check model size selection
5. Detect high-volume KV → Suggest alternatives
```

**Key principle**: Surface budget impacts BEFORE the user asks about costs.

### Step 5c: Run Privacy Checks

```
For privacy-sensitive patterns:
1. Scan code for console.log with user data patterns
2. Check KV key naming for PII patterns
3. Verify AI prompts have redaction middleware
4. Check R2 bucket access controls
5. Review Analytics Engine write patterns
```

### Step 6: Calculate Score

```
score = 100 - (critical × 25) - (high × 15) - (medium × 5) - (low × 2)
```

Grades:
- 90-100: A (Production ready)
- 80-89: B (Minor issues)
- 70-79: C (Address before deployment)
- 60-69: D (Significant issues)
- <60: F (Critical problems)

## Output Format

```markdown
# Cloudflare Configuration Audit

**Score**: XX/100 (Grade: X)
**File**: wrangler.jsonc

## Proactive Budget & Privacy Alerts

> **Budget Impact Detected**: [List any BUDGET* findings with cost estimates]
> **Privacy Concern**: [List any PRIV* findings requiring attention]

## Summary

| Category | Critical | High | Medium | Low | Info |
|----------|----------|------|--------|-----|------|
| Security | X | X | X | X | - |
| Performance | X | X | X | X | - |
| Cost | X | X | X | X | - |
| Resilience | X | X | X | X | - |
| Budget | - | X | X | - | X |
| Privacy | X | X | X | - | - |

## Critical Issues (Must Fix)

### SEC001: Secrets in plaintext
- **Location**: `vars.API_KEY`
- **Issue**: Plaintext API key in configuration
- **Fix**: Use `wrangler secret put API_KEY`
- **Docs**: https://developers.cloudflare.com/workers/configuration/secrets/

## High Priority Issues

### RES001: Missing dead letter queue
- **Location**: `queues[0]` (harvest-queue)
- **Issue**: No DLQ for failed message inspection
- **Fix**: Add `dead_letter_queue = "harvest-dlq"`

## Medium Priority Issues

[List all medium issues]

## Low Priority Issues

[List all low issues]

## Recommendations

1. [ ] Move secrets to wrangler secret
2. [ ] Add DLQ for all production queues
3. [ ] Enable Smart Placement
4. [ ] Consider Analytics Engine for metrics
```

## Migration Checks

When D1 bindings exist, also scan migration files:

```sql
-- Good: Has index
CREATE INDEX idx_projects_source ON projects(source);

-- Bad: Missing index for common query pattern
SELECT * FROM projects WHERE source = ? ORDER BY created_at DESC;
```

Flag missing indexes for:
- Columns in WHERE clauses
- Columns in ORDER BY
- Compound queries (need compound indexes)

## Wrangler Config Patterns

### Good Patterns to Recognize

```jsonc
{
  // Smart Placement enabled
  "placement": { "mode": "smart" },

  // Observability configured
  "observability": { "logs": { "enabled": true } },

  // Queue with DLQ
  "queues": {
    "consumers": [{
      "queue": "my-queue",
      "dead_letter_queue": "my-dlq",
      "max_retries": 1,
      "max_concurrency": 10
    }]
  }
}
```

### Bad Patterns to Flag

```jsonc
{
  // Secrets in vars
  "vars": { "API_KEY": "sk-xxxxx" },

  // No DLQ
  "queues": { "consumers": [{ "queue": "my-queue" }] },

  // High retries
  "queues": { "consumers": [{ "max_retries": 10 }] }
}
```

## Live Validation with Probes

When MCP tools are available (via `--validate` mode in `/cf-audit`), enhance static findings with live data.

Reference @skills/probes/SKILL.md for detailed query patterns.

### Security Validation
- **Error rate analysis**: High errors on specific paths may indicate attacks
- **Request patterns**: Verify authentication is actually enforced
- **Resource exposure**: Check KV/R2 for public access settings

### Performance Validation
- **EXPLAIN QUERY PLAN**: Verify D1 index usage
- **Latency percentiles**: P50/P95/P99 analysis
- **CPU time analysis**: Identify hotspots

### Resilience Validation
- **Queue health**: Check DLQ depth and retry rates
- **Error patterns**: Identify cascading failures

## Provenance Tagging

Tag findings based on data source:
- `[STATIC]` - Inferred from code/config analysis only
- `[LIVE-VALIDATED]` - Confirmed by observability data
- `[LIVE-REFUTED]` - Code smell not observed in production
- `[INCOMPLETE]` - MCP tools unavailable for verification

## Pattern Recommendations

When issues are found, recommend applicable patterns from @skills/patterns/:

| Finding | Recommended Pattern |
|---------|-------------------|
| Per-row D1 inserts | `d1-batching` |
| External API issues | `circuit-breaker` |
| Monolithic Worker | `service-bindings` |

## Tips

- Run before every deployment
- Use `--validate` for production-ready verification
- Focus on CRITICAL and HIGH first
- Use `--fix` suggestions to auto-generate patches
- Compare scores over time to track improvements
- `[LIVE-REFUTED]` findings may still be worth fixing proactively
