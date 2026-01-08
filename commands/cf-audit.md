---
description: "Audit wrangler config with dual-mode: Resource Discovery (default) finds unused/dangling resources, --validate verifies against production metrics"
argument-hint: "[wrangler-path] [--category=security|performance|cost|resilience|resources|all] [--validate] [--discover]"
allowed-tools: ["Read", "Glob", "Grep", "Bash", "mcp__cloudflare-observability__*", "mcp__cloudflare-bindings__*"]
---

# Cloudflare Configuration Audit

Comprehensive audit of your wrangler configuration with **dual-mode** operation:
- **Resource Discovery** (default): Identify unused KV namespaces, R2 buckets, dangling DNS records, orphaned D1 databases
- **Validation** (`--validate`): Verify findings against live production metrics

**Arguments:** "$ARGUMENTS"

## Modes

| Mode | Description | MCP Tools |
|------|-------------|-----------|
| **Discovery** (default) | Find unused resources + static config analysis | bindings (optional) |
| **Validate** (`--validate`) | Verify findings against live production data | observability, bindings |
| **Discover** (`--discover`) | Resource discovery only (explicit mode) | bindings |

## Quick Start

```bash
/cf-audit                              # Resource discovery + config audit (default)
/cf-audit workers/wrangler.jsonc       # Specific file
/cf-audit --category=security          # Security-only audit
/cf-audit --category=resources         # Resource discovery only
/cf-audit --discover                   # Explicit resource discovery mode
/cf-audit --validate                   # Verify findings with live production data
/cf-audit --validate --category=perf   # Live-validated performance audit
```

## Audit Workflow

### Step 0: Parse Arguments and Detect Mode

Parse `$ARGUMENTS` for:
- `--validate`: Enable live data validation
- `--discover`: Explicit resource discovery mode
- `--category=X`: Filter to specific category (now includes `resources`)
- `[path]`: Explicit wrangler config path

### Step 0b: Resource Discovery Mode (Default Behavior)

**NEW in v1.2.0**: By default, `/cf-audit` now performs resource discovery before config analysis.

#### Resource Discovery Checks

| Resource Type | Discovery Check | Provenance |
|---------------|-----------------|------------|
| KV Namespaces | List all → compare to wrangler bindings | `[STATIC]` or `[LIVE-VALIDATED]` |
| R2 Buckets | List all → check for references in code | `[STATIC]` or `[LIVE-VALIDATED]` |
| D1 Databases | List all → compare to active bindings | `[STATIC]` or `[LIVE-VALIDATED]` |
| DNS Records | List dangling CNAME/A records | `[LIVE-VALIDATED]` only |
| Queues | List all → check consumer bindings | `[STATIC]` or `[LIVE-VALIDATED]` |
| Workers | List all → check for orphaned workers | `[LIVE-VALIDATED]` only |

#### Resource Discovery Workflow

```javascript
// Step 1: Inventory account resources (if MCP available)
mcp__cloudflare-bindings__kv_namespaces_list()
mcp__cloudflare-bindings__r2_buckets_list()
mcp__cloudflare-bindings__d1_databases_list()
mcp__cloudflare-bindings__queues_list()
mcp__cloudflare-bindings__workers_list()

// Step 2: Parse all wrangler configs in project
// Find all wrangler.toml/wrangler.jsonc files
// Extract all bindings: kv_namespaces, r2_buckets, d1_databases, queues

// Step 3: Compare and identify
// - Unused: In account but not in any wrangler config
// - Dangling: In wrangler config but not in account
// - Orphaned: Workers with no recent requests (via observability)
```

#### Resource Discovery Output

```markdown
## Resource Discovery Results

### Unused Resources (Cleanup Candidates)

| Type | Name/ID | Last Activity | Action |
|------|---------|---------------|--------|
| KV | `old-cache-namespace` | 90+ days | Consider deletion |
| R2 | `staging-uploads-2024` | No recent ops | Verify and delete |
| D1 | `test-db-backup` | Never queried | Archive or delete |

### Dangling References

| Type | Binding | Issue | Fix |
|------|---------|-------|-----|
| KV | `LEGACY_CACHE` | Namespace doesn't exist | Remove binding or create namespace |
| Queue | `OLD_QUEUE` | Queue deleted | Remove consumer config |

### Orphaned Workers

| Worker | Last Request | Recommendation |
|--------|--------------|----------------|
| `api-v1-deprecated` | 180 days ago | Delete if unused |
```

### Step 1: MCP Availability Check (if --validate or resource discovery)

Before using MCP tools, verify availability:

```javascript
// Lightweight probe to test MCP connectivity
mcp__cloudflare-bindings__workers_list()
```

**Expected outcomes:**
- **Success**: MCP tools available, proceed with live validation
- **Failure/Timeout**: Note "MCP tools unavailable"
  - Continue with static analysis
  - Tag all findings as `[STATIC]`

### Step 2: Find Configuration

```bash
# If no path provided, search for wrangler config
find . -maxdepth 3 -name "wrangler.toml" -o -name "wrangler.jsonc"
```

### Step 3: Parse and Analyze

Read the wrangler config and check against rules:

**Security Checks:**
- SEC001: Secrets in plaintext vars (CRITICAL)
- SEC002: Missing route authentication (HIGH)
- SEC003: CORS wildcard origin (MEDIUM)
- SEC004: Exposed admin routes (HIGH)
- SEC005: Missing rate limiting (MEDIUM)
- SEC006: Debug mode enabled (HIGH)

**Performance Checks:**
- PERF001: Missing Smart Placement (LOW)
- PERF002: D1 without indexes (MEDIUM)
- PERF003: Large bundle size (MEDIUM)
- PERF004: Missing observability (LOW)
- PERF005: Excessive cron frequency (MEDIUM)

**Cost Checks:**
- COST001: Queue retries too high (MEDIUM)
- COST002: Crons not batched (LOW)
- COST003: AI without caching (MEDIUM)
- COST004: Large model usage (LOW)
- COST005: Per-row D1 inserts (HIGH)

**Resilience Checks:**
- RES001: Missing DLQ (HIGH)
- RES002: No concurrency limit (MEDIUM)
- RES003: Missing retry config (MEDIUM)
- RES004: No circuit breaker for external APIs (MEDIUM)
- RES005: Single point of failure (HIGH)

### Step 4: Check Migrations (if D1)

If D1 bindings exist, scan migration files for:
- Missing indexes on query columns
- SCAN TABLE instead of SEARCH USING INDEX
- Compound index needs

### Step 5: Live Validation (if --validate and MCP available)

Verify static findings against live data. Reference @skills/probes/SKILL.md for query patterns.

#### Security Validation
```javascript
// Check for actual error rates (may indicate attack patterns)
mcp__cloudflare-observability__query_worker_observability({
  view: "calculations",
  parameters: {
    calculations: [
      { operator: "count", as: "total" },
      { operator: "countIf", as: "errors",
        condition: { field: "$metadata.outcome", operator: "eq", value: "exception" }}
    ],
    groupBys: [{ type: "string", value: "$metadata.path" }]
  },
  timeframe: { reference: "now", offset: "-7d" }
})
```

#### Performance Validation
```javascript
// EXPLAIN QUERY PLAN for detected queries
mcp__cloudflare-bindings__d1_database_query({
  database_id: "...",
  sql: "EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = ?"
})
```

**Interpretation:**
- `SCAN TABLE` → `[LIVE-VALIDATED]` PERF002 confirmed
- `SEARCH USING INDEX` → `[LIVE-REFUTED]` Index exists but not in migrations

```javascript
// Check latency percentiles
mcp__cloudflare-observability__query_worker_observability({
  view: "calculations",
  parameters: {
    calculations: [
      { operator: "p50", field: "$metadata.duration", as: "p50_ms" },
      { operator: "p99", field: "$metadata.duration", as: "p99_ms" }
    ]
  },
  timeframe: { reference: "now", offset: "-24h" }
})
```

#### Resilience Validation
```javascript
// Check actual error rates and patterns
// High error rate may indicate resilience issues
```

### Step 6: Generate Report with Provenance Tags

Output score and findings:

```markdown
# Audit Report

**Score**: XX/100 (Grade)
**File**: path/to/wrangler.jsonc
**Mode**: [Static | Live Validated]
**Validation Status**: [Full | Partial | Static Only]

## Summary Table

| Category | Critical | High | Medium | Low | Validated |
|----------|----------|------|--------|-----|-----------|
| Security | X | X | X | X | [Y/N] |
| Performance | X | X | X | X | [Y/N] |
| Cost | X | X | X | X | [Y/N] |
| Resilience | X | X | X | X | [Y/N] |

## Critical Issues

### [STATIC] SEC001: Secrets in plaintext vars
- **Location**: `vars.API_KEY` (line 15)
- **Issue**: Plaintext secret detected
- **Fix**: Move to `secrets` or use encrypted vars

### [LIVE-VALIDATED] PERF002: D1 missing indexes
- **Location**: `migrations/0001_init.sql`
- **Static Finding**: No index on `users.email`
- **Live Evidence**: `EXPLAIN QUERY PLAN` shows `SCAN TABLE users`
- **Fix**: Add index: `CREATE INDEX idx_users_email ON users(email);`

## High Priority

### [LIVE-REFUTED] RES001: Missing dead letter queue
- **Location**: `queues.consumers[0]` (harvest-queue)
- **Static Finding**: No DLQ configured
- **Live Evidence**: Queue has 0 failed messages in 30 days
- **Recommendation**: Still add DLQ for future resilience

## Medium Priority

### [INCOMPLETE] COST003: AI without caching
- **Location**: AI Gateway binding
- **Static Finding**: No cache configuration detected
- **Note**: Could not verify - AI Gateway MCP unavailable

## Recommendations

[Prioritized action items with provenance tags]

---
**Finding Tags:**
- `[STATIC]` - Inferred from code/config analysis
- `[LIVE-VALIDATED]` - Confirmed by observability (--validate mode)
- `[LIVE-REFUTED]` - Code smell not observed in production
- `[INCOMPLETE]` - Some MCP tools unavailable
```

## Category Details

### Resources (`--category=resources`)

Focus on:
- Unused KV namespaces
- Orphaned R2 buckets
- Dangling D1 databases
- Stale DNS records
- Inactive Workers

**Live Validation Adds:**
- Last activity timestamps
- Request volume analysis
- Storage utilization metrics

### Security (`--category=security`)

Focus on:
- Exposed secrets
- Missing authentication
- CORS misconfiguration
- Attack surface

**Live Validation Adds:**
- Error rate analysis (may indicate attacks)
- Path-level access patterns

### Performance (`--category=performance`)

Focus on:
- Smart Placement
- D1 indexing
- Bundle size
- Observability

**Live Validation Adds:**
- EXPLAIN QUERY PLAN verification
- Latency percentile analysis
- CPU time hotspots

### Cost (`--category=cost`)

Focus on:
- Queue retry costs
- Cron efficiency
- AI caching
- Model selection

**Live Validation Adds:**
- Actual write counts vs estimates
- Retry rate reality check

### Resilience (`--category=resilience`)

Focus on:
- Dead letter queues
- Concurrency limits
- Retry strategies
- Failure handling

**Live Validation Adds:**
- Error rate by endpoint
- Timeout patterns
- Queue backlog depth

## Scoring

```
Score = 100 - (critical × 25) - (high × 15) - (medium × 5) - (low × 2)

Grades:
A (90-100): Production ready
B (80-89): Minor issues
C (70-79): Address before deploy
D (60-69): Significant issues
F (<60): Critical problems
```

## Pre-Deployment Gate

Use in CI/CD:
```bash
# Block deployment if score < 80
/cf-audit --min-score=80

# Block if any CRITICAL issues
/cf-audit --fail-on-critical
```

## MCP Tool Requirements

For `--validate` mode, these MCP servers should be configured:
- `cloudflare-observability` - Error rates, latency metrics
- `cloudflare-bindings` - D1 EXPLAIN QUERY PLAN

If any MCP server is unavailable, the command will:
1. Note which tools are missing
2. Continue with static analysis
3. Tag affected findings as `[INCOMPLETE]`

## Tips

- Run before every PR that touches wrangler config
- Use `--validate` for pre-production verification
- Focus on CRITICAL and HIGH issues first
- Address security issues before performance
- Track score improvements over time
- `[LIVE-REFUTED]` findings may still be worth fixing proactively
