---
description: "Audit wrangler config for security, performance, cost, and resilience issues"
argument-hint: "[wrangler-path] [--category=security|performance|cost|resilience|all]"
allowed-tools: ["Read", "Glob", "Grep", "Bash", "mcp__cloudflare-bindings__*"]
---

# Cloudflare Configuration Audit

Comprehensive audit of your wrangler configuration against security, performance, cost, and resilience best practices.

**Arguments:** "$ARGUMENTS"

## Quick Start

```bash
/cf-audit                           # Audit current directory
/cf-audit workers/wrangler.jsonc    # Specific file
/cf-audit --category=security       # Security-only audit
```

## Audit Workflow

### Step 1: Find Configuration

```bash
# If no path provided, search for wrangler config
find . -maxdepth 3 -name "wrangler.toml" -o -name "wrangler.jsonc"
```

### Step 2: Parse and Analyze

Read the wrangler config and check against rules:

**Security Checks:**
- SEC001: Secrets in plaintext vars (CRITICAL)
- SEC002: Missing route authentication (HIGH)
- SEC003: CORS wildcard origin (MEDIUM)
- SEC004: Exposed admin routes (HIGH)
- SEC005: Missing rate limiting (MEDIUM)

**Performance Checks:**
- PERF001: Missing Smart Placement (LOW)
- PERF002: D1 without indexes (MEDIUM)
- PERF003: Large bundle size (MEDIUM)
- PERF004: Missing observability (LOW)

**Cost Checks:**
- COST001: Queue retries too high (MEDIUM)
- COST002: Crons not batched (LOW)
- COST003: AI without caching (MEDIUM)
- COST004: Large model usage (LOW)

**Resilience Checks:**
- RES001: Missing DLQ (HIGH)
- RES002: No concurrency limit (MEDIUM)
- RES003: Missing retry config (MEDIUM)

### Step 3: Check Migrations (if D1)

If D1 bindings exist, scan migration files for:
- Missing indexes on query columns
- SCAN TABLE instead of SEARCH USING INDEX
- Compound index needs

### Step 4: Generate Report

Output score and findings:

```markdown
# Audit Report

**Score**: XX/100 (Grade)
**File**: path/to/wrangler.jsonc

## Summary Table

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Security | X | X | X | X |
| Performance | X | X | X | X |
| Cost | X | X | X | X |
| Resilience | X | X | X | X |

## Critical Issues
[Details with specific locations and fixes]

## High Priority
[Details]

## Recommendations
[Prioritized action items]
```

## Category Details

### Security (`--category=security`)

Focus on:
- Exposed secrets
- Missing authentication
- CORS misconfiguration
- Attack surface

### Performance (`--category=performance`)

Focus on:
- Smart Placement
- D1 indexing
- Bundle size
- Observability

### Cost (`--category=cost`)

Focus on:
- Queue retry costs
- Cron efficiency
- AI caching
- Model selection

### Resilience (`--category=resilience`)

Focus on:
- Dead letter queues
- Concurrency limits
- Retry strategies
- Failure handling

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

## Example Output

```markdown
# Cloudflare Configuration Audit

**Score**: 72/100 (Grade: C)
**File**: workers/wrangler.jsonc

## Summary

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Security | 0 | 1 | 2 | 0 |
| Performance | 0 | 0 | 1 | 2 |
| Cost | 0 | 0 | 1 | 0 |
| Resilience | 0 | 1 | 1 | 0 |

## High Priority Issues

### RES001: Missing dead letter queue
- **Location**: `queues.consumers[0]` (harvest-queue)
- **Issue**: Failed messages are silently dropped
- **Fix**: Add `"dead_letter_queue": "harvest-dlq"`

### SEC002: Missing route authentication
- **Location**: `routes[2]` (/api/admin/*)
- **Issue**: Admin routes accessible without auth
- **Fix**: Add Cloudflare Access or bearer token validation

## Medium Priority Issues

### COST001: Queue retries set to 3
- **Location**: `queues.consumers[1].max_retries`
- **Issue**: Each retry = additional message cost
- **Fix**: Set to 1 if consumer is idempotent

## Action Items

1. [ ] Add DLQ binding for harvest-queue
2. [ ] Add authentication for /api/admin/* routes
3. [ ] Reduce queue retries to 1
```

## Pre-Deployment Gate

Use in CI/CD:
```bash
# Block deployment if score < 80
/cf-audit --min-score=80
```

## Tips

- Run before every PR that touches wrangler config
- Focus on CRITICAL and HIGH issues first
- Address security issues before performance
- Track score improvements over time
