---
description: "Generate Cloudflare cost report with projections and optimization recommendations"
argument-hint: "[wrangler-path] [--detailed]"
allowed-tools: ["Read", "Glob", "Grep", "Bash", "mcp__cloudflare-observability__*", "mcp__cloudflare-ai-gateway__*", "mcp__cloudflare-bindings__*"]
---

# Cloudflare Cost Report

Generate a comprehensive cost analysis for your Cloudflare architecture with optimization recommendations.

**Arguments:** "$ARGUMENTS"

## Workflow

### Step 1: Locate Wrangler Config

If path provided, use it. Otherwise search:
```bash
# Find wrangler.toml or wrangler.jsonc
find . -name "wrangler.toml" -o -name "wrangler.jsonc" | head -5
```

### Step 2: Parse Configuration

Read the wrangler config and identify all bindings:
- D1 databases
- R2 buckets
- KV namespaces
- Queues (check `max_retries`)
- Vectorize indexes
- AI bindings
- Durable Objects
- Analytics Engine datasets

### Step 3: Gather Usage Data

Use MCP tools to collect real usage metrics:

1. **Worker Metrics** (cloudflare-observability):
   - Request count
   - CPU time
   - Duration

2. **AI Gateway Logs** (cloudflare-ai-gateway):
   - Request count
   - Model usage
   - Token counts

3. **Resource Lists** (cloudflare-bindings):
   - D1 database details
   - R2 bucket info
   - KV namespace metadata

### Step 4: Calculate Costs

Apply 2026 Cloudflare pricing:

| Service | Read | Write | Storage |
|---------|------|-------|---------|
| D1 | $0.25/B rows | $1.00/M rows | $0.75/GB |
| R2 | $0.36/M (Class B) | $4.50/M (Class A) | $0.015/GB |
| KV | $0.50/M | $5.00/M | $0.50/GB |
| Queues | $0.40/M messages | - | - |
| Workers | $0.30/M requests | - | - |
| Workers AI | Varies by model | - | - |

### Step 5: Identify Optimizations

Check for common cost traps:

1. **D1 Anti-patterns:**
   - Per-row inserts (should batch)
   - Missing indexes (SCAN TABLE)
   - SELECT * usage

2. **Queue Anti-patterns:**
   - `max_retries > 1` for idempotent consumers
   - Missing dead-letter queue

3. **AI Anti-patterns:**
   - No caching for repeated prompts
   - Large models for simple tasks
   - Missing rate limiting

4. **General Anti-patterns:**
   - Frequent cron jobs (batch work)
   - Missing Smart Placement
   - Subrequest exhaustion

### Step 6: Generate Report

Output format:

```markdown
# Cloudflare Cost Report
Generated: [date]
Project: [wrangler name]

## Summary
- **Estimated Monthly Cost**: $XX.XX
- **Cost Trend**: [Stable|Rising|Declining]
- **Optimization Potential**: $XX.XX/month

## Service Breakdown

| Service | Monthly Cost | % Total | Status |
|---------|-------------|---------|--------|
| D1 | $XX.XX | XX% | [OK|Warning|Critical] |
| Workers | $XX.XX | XX% | [OK|Warning|Critical] |
| ... | ... | ... | ... |

## Cost Drivers

1. **[Service Name]** - XX% of total cost
   - Root cause: [explanation]
   - Impact: $XX.XX/month

## Optimization Opportunities

| Opportunity | Savings | Effort | Priority |
|-------------|---------|--------|----------|
| [Description] | $XX/mo | [Low|Med|High] | [P1|P2|P3] |

## Warnings

- [List any concerning patterns]

## Action Items

1. [ ] [Specific action with file:line reference]
2. [ ] [Specific action with file:line reference]
```

## Usage Examples

**Basic cost report:**
```
/cf-costs
```

**Specific wrangler file:**
```
/cf-costs workers/wrangler.jsonc
```

**Detailed report with per-binding breakdown:**
```
/cf-costs --detailed
```

## Tips

- Run weekly to track cost trends
- Compare before/after deployments
- Use `--detailed` for capacity planning
- Check D1 writes first (usually the culprit)
