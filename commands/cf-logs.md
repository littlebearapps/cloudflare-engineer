---
description: "Configure external logging for Workers. Wizard for vendor selection, check existing config, or analyze log volume for sampling recommendations"
argument-hint: "[--vendor=axiom|betterstack|http] [--check] [--analyze]"
allowed-tools: ["Read", "Glob", "Grep", "Bash", "mcp__cloudflare-observability__*", "mcp__cloudflare-bindings__*"]
---

# External Logging Configuration

Configure observability export to external logging vendors with privacy-first defaults and cost-aware sampling.

**Arguments:** "$ARGUMENTS"

## Modes

| Mode | Flag | Description |
|------|------|-------------|
| **Interactive** | (default) | Wizard for vendor selection and configuration |
| **Direct** | `--vendor=axiom` | Skip wizard, configure specific vendor |
| **Check** | `--check` | Validate existing observability config |
| **Analyze** | `--analyze` | Analyze log volume for sampling recommendations |

## Quick Start

```bash
/cf-logs                    # Interactive wizard
/cf-logs --vendor=axiom     # Direct Axiom configuration
/cf-logs --check            # Validate current config
/cf-logs --analyze          # Log volume analysis
```

## Vendor Comparison

| Vendor | Free Tier | Config Type | Best For |
|--------|-----------|-------------|----------|
| **Axiom** | 500GB/month | OTel destination | High-volume, long retention |
| **Better Stack** | 1GB/month | SDK integration | Real-time dashboards |
| **HTTP Endpoint** | N/A | Tail Worker | Custom/self-hosted |

### Axiom (Recommended for Solo Devs)

**Free Tier**: 500GB/month, 30-day retention
**Config**: OpenTelemetry export destination

```jsonc
// wrangler.jsonc
{
  "observability": {
    "logs": {
      "enabled": true,
      "invocation_logs": true,
      "head_sampling_rate": 1  // Adjust based on volume
    }
  }
}
```

**Axiom Destination Setup**:
1. Create Axiom account at axiom.co
2. Create dataset for your Worker
3. Get API token (Settings → API Tokens → New Token)
4. Configure via Cloudflare Dashboard:
   - Workers → Observability → Export Destinations
   - Add Axiom destination with API token

### Better Stack

**Free Tier**: 1GB/month, 3-day retention
**Config**: SDK integration via Logtail

```typescript
// src/utils/logger.ts
import { Logtail } from '@logtail/edge';

export function createLogger(env: Env) {
  const logtail = new Logtail(env.BETTERSTACK_TOKEN);

  return {
    info: (msg: string, meta?: object) => logtail.info(msg, meta),
    error: (msg: string, meta?: object) => logtail.error(msg, meta),
    flush: () => logtail.flush(),
  };
}

// Usage in Worker
app.use('*', async (c, next) => {
  const logger = createLogger(c.env);
  c.set('logger', logger);
  await next();
  c.executionCtx.waitUntil(logger.flush());
});
```

### HTTP Tail Worker

**Config**: Custom endpoint via Tail Worker

```typescript
// src/tail-worker.ts
interface TailEvent {
  scriptName: string;
  outcome: string;
  exceptions: { message: string }[];
  logs: { message: string[] }[];
}

export default {
  async tail(events: TailEvent[], env: Env) {
    const payload = events.map(e => ({
      worker: e.scriptName,
      status: e.outcome,
      errors: e.exceptions.map(ex => ex.message),
      logs: e.logs.flatMap(l => l.message),
      timestamp: new Date().toISOString(),
    }));

    await fetch(env.LOG_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.LOG_TOKEN}`,
      },
      body: JSON.stringify(payload),
    });
  }
};
```

```jsonc
// wrangler.jsonc for tail worker
{
  "name": "log-forwarder",
  "main": "src/tail-worker.ts",
  "compatibility_date": "2025-01-01",
  "tail_consumers": [
    { "service": "my-worker" }  // Worker to tail
  ]
}
```

---

## Privacy Filters (Auto-Recommended)

When configuring logging, always recommend these privacy filters to prevent sensitive data leakage.

### Default Redaction Patterns

| Category | Patterns | Action |
|----------|----------|--------|
| **Authorization** | `Authorization:`, `Bearer `, `Basic ` | Redact value |
| **API Keys** | `api_key=`, `apikey=`, `x-api-key:` | Redact value |
| **Tokens** | `token=`, `access_token=`, `refresh_token=` | Redact value |
| **Passwords** | `password=`, `passwd=`, `secret=` | Redact value |
| **PII - Email** | `email@domain.com` pattern | Hash or redact |
| **PII - Credit Card** | 16-digit patterns | Redact |
| **PII - SSN** | XXX-XX-XXXX pattern | Redact |
| **Environment Leaks** | `process.env`, `import.meta.env` | Flag |

### Privacy Filter Implementation

```typescript
// src/utils/log-sanitizer.ts
const REDACT_PATTERNS = [
  // Headers
  { pattern: /(authorization:\s*)(bearer\s+)?[\w\-._~+\/]+=*/gi, replace: '$1[REDACTED]' },
  { pattern: /(x-api-key:\s*)[\w\-]+/gi, replace: '$1[REDACTED]' },
  { pattern: /(cf-access-client-secret:\s*)[\w\-]+/gi, replace: '$1[REDACTED]' },

  // Query params and body
  { pattern: /(api_?key=)[\w\-]+/gi, replace: '$1[REDACTED]' },
  { pattern: /(token=)[\w\-]+/gi, replace: '$1[REDACTED]' },
  { pattern: /(password=)[^&\s]+/gi, replace: '$1[REDACTED]' },
  { pattern: /(secret=)[^&\s]+/gi, replace: '$1[REDACTED]' },

  // PII
  { pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, replace: '[EMAIL]' },
  { pattern: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g, replace: '[CARD]' },
  { pattern: /\b\d{3}-\d{2}-\d{4}\b/g, replace: '[SSN]' },
];

export function sanitizeLogs(message: string): string {
  let sanitized = message;
  for (const { pattern, replace } of REDACT_PATTERNS) {
    sanitized = sanitized.replace(pattern, replace);
  }
  return sanitized;
}
```

---

## Sampling Recommendations

### Log Volume Analysis

```javascript
// Query current log volume
mcp__cloudflare-observability__query_worker_observability({
  view: "calculations",
  parameters: {
    calculations: [
      { operator: "count", as: "total_logs" }
    ],
    groupBys: [{ type: "string", value: "$metadata.service" }]
  },
  timeframe: { reference: "now", offset: "-7d" }
})
```

### Sampling Rate Calculator

| Daily Requests | Recommended Sampling | Est. Monthly Volume |
|----------------|---------------------|---------------------|
| < 100K | 1.0 (100%) | < 3GB |
| 100K - 1M | 0.5 (50%) | 1.5 - 15GB |
| 1M - 10M | 0.1 (10%) | 3 - 30GB |
| 10M - 100M | 0.01 (1%) | 3 - 30GB |
| > 100M | 0.001 (0.1%) | ~30GB |

**Sampling Strategy**:
- Always log errors at 100%: `head_sampling_rate` applies to successful requests
- Use `invocation_logs: true` for debugging phases
- Reduce to `invocation_logs: false` for production cost savings

```jsonc
// High-volume production config
{
  "observability": {
    "logs": {
      "enabled": true,
      "invocation_logs": false,  // Reduce noise
      "head_sampling_rate": 0.1  // 10% sampling
    }
  }
}
```

---

## Validation Rules

| ID | Severity | Check |
|----|----------|-------|
| OBS001 | LOW | Observability not enabled |
| OBS002 | MEDIUM | Logs enabled but no export destination |
| OBS003 | INFO | High sampling rate with high-volume worker |

### OBS001: Observability Not Enabled

**Pattern**: Missing `observability.logs` configuration.

**Detection**:
```javascript
// Check wrangler config for observability block
const config = /* parsed wrangler.jsonc */;
if (!config.observability?.logs?.enabled) {
  // Flag OBS001
}
```

**Risk**: No visibility into Worker behavior, harder to debug issues.

**Fix**:
```jsonc
{
  "observability": {
    "logs": {
      "enabled": true,
      "invocation_logs": true,
      "head_sampling_rate": 1
    }
  }
}
```

### OBS002: Logs Without Export

**Pattern**: Logs enabled but no external destination configured.

**Detection**:
- Check Cloudflare dashboard for export destinations
- No tail worker configured
- No SDK integration detected in code

**Risk**: Logs only visible in Cloudflare dashboard, limited retention (24-72h).

**Fix**: Configure export destination (Axiom, Better Stack, or HTTP endpoint).

### OBS003: High Sampling on High-Volume Worker

**Pattern**: `head_sampling_rate: 1` on worker with >1M daily requests.

**Detection**:
```javascript
// Get request volume
mcp__cloudflare-observability__query_worker_observability({
  view: "calculations",
  parameters: {
    calculations: [{ operator: "count", as: "daily_requests" }]
  },
  timeframe: { reference: "now", offset: "-1d" }
})

// If daily_requests > 1M and head_sampling_rate == 1
// Flag OBS003
```

**Risk**: Excessive log volume, potential cost overruns on logging vendor.

**Fix**: Reduce sampling rate based on volume (see calculator above).

---

## Workflow

### Interactive Mode (Default)

1. **Detect existing config**: Check wrangler.jsonc for observability settings
2. **Analyze log volume**: Query observability data for request counts
3. **Present vendor options**: Show comparison table with recommendations
4. **Generate config**: Output wrangler.jsonc additions and setup steps
5. **Privacy recommendations**: Show filter patterns to implement

### Check Mode (`--check`)

1. **Parse wrangler config**: Read observability settings
2. **Validate completeness**: Check for OBS001, OBS002, OBS003
3. **Check privacy filters**: Scan code for sanitization
4. **Output findings**: List issues with fix recommendations

### Analyze Mode (`--analyze`)

1. **Query log volume**: Get 7-day request metrics per worker
2. **Calculate sampling**: Recommend rate based on volume
3. **Estimate costs**: Project vendor costs at different sampling rates
4. **Output report**: Volume analysis with recommendations

---

## Output Format

```markdown
# Observability Configuration Report

**Worker**: my-worker
**Current Status**: Logs enabled, no export destination

## Findings

### [OBS002] Logs Without Export Destination
- **Status**: Logs enabled but no external destination configured
- **Impact**: Limited retention (24-72h), no advanced querying
- **Fix**: Configure Axiom export destination (500GB/month free)

### [OBS003] High Sampling on High-Volume Worker
- **Daily Requests**: 2.5M
- **Current Sampling**: 100%
- **Recommended**: 10% (save ~90% on log storage)

## Recommendations

1. **Vendor**: Axiom (best fit for 2.5M daily requests)
   - Free tier: 500GB/month
   - Estimated usage: ~7.5GB/month at 10% sampling
   - Headroom: 66x free tier capacity

2. **Sampling Configuration**:
   ```jsonc
   {
     "observability": {
       "logs": {
         "enabled": true,
         "invocation_logs": false,
         "head_sampling_rate": 0.1
       }
     }
   }
   ```

3. **Privacy Filters**: Implement sanitization for:
   - [ ] Authorization headers
   - [ ] API keys in URLs
   - [ ] Email addresses in logs

## Setup Steps

1. Create Axiom account at axiom.co
2. Create dataset "my-worker-logs"
3. Generate API token with ingest permissions
4. Add export destination in Cloudflare Dashboard:
   - Workers → Observability → Export Destinations → Axiom
5. Deploy updated wrangler.jsonc
```

---

## Related Skills

- **guardian**: Privacy and security auditing
- **architect**: Observability architecture patterns
- **cost-analyzer**: Log storage cost analysis

---

*Added in v1.5.0 - External Logging Configuration*
