# Observability Export Patterns

Native Cloudflare log retention is short (3-7 days). For production-grade applications, export OpenTelemetry (OTel) data to third-party tools for long-term debugging and analysis.

## Wrangler Observability Configuration

```jsonc
{
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",

  // Enable observability (required for log export)
  "observability": {
    "logs": {
      "enabled": true,
      "invocation_logs": true,    // Log each request
      "head_sampling_rate": 1.0   // Sample 100% (adjust for high volume)
    }
  },

  // Tail workers for real-time log processing
  "tail_consumers": [
    { "service": "log-exporter" }  // Optional: process logs in another Worker
  ]
}
```

## Export to Axiom (Recommended Free Tier)

Axiom offers 500GB/month free ingest - excellent for solo developers.

### Step 1: Wrangler Configuration

```jsonc
{
  "name": "my-worker",
  "observability": {
    "logs": { "enabled": true }
  },
  // Axiom integration via Logpush
  "logpush": true  // Enable logpush for the worker
}
```

### Step 2: Set Up Axiom Logpush (Dashboard)

1. Go to Cloudflare Dashboard -> Analytics & Logs -> Logpush
2. Create a job for Workers trace events
3. Select Axiom as destination
4. Enter your Axiom API token and dataset name

### Step 3: Structured Logging in Code

```typescript
// src/utils/logger.ts
interface LogContext {
  requestId: string;
  userId?: string;
  action: string;
  duration?: number;
  [key: string]: unknown;
}

export function log(level: 'info' | 'warn' | 'error', message: string, ctx: LogContext) {
  const entry = {
    level,
    message,
    timestamp: new Date().toISOString(),
    ...ctx,
  };

  // console.log outputs to Workers logs -> Axiom via Logpush
  console.log(JSON.stringify(entry));
}

// Usage in handlers
app.get('/api/users/:id', async (c) => {
  const requestId = c.req.header('cf-ray') || crypto.randomUUID();
  const start = Date.now();

  try {
    const user = await getUser(c.env.DB, c.req.param('id'));

    log('info', 'User fetched', {
      requestId,
      userId: c.req.param('id'),
      action: 'get_user',
      duration: Date.now() - start,
    });

    return c.json(user);
  } catch (error) {
    log('error', 'Failed to fetch user', {
      requestId,
      userId: c.req.param('id'),
      action: 'get_user',
      error: String(error),
      duration: Date.now() - start,
    });
    throw error;
  }
});
```

## Export to Better Stack (Logtail)

Better Stack offers real-time log viewing with free tier.

### Step 1: Install Logtail SDK

```bash
npm install @logtail/js
```

### Step 2: Configure Logger

```typescript
// src/utils/logtail.ts
import { Logtail } from '@logtail/js';

let logtail: Logtail | null = null;

export function getLogger(sourceToken: string): Logtail {
  if (!logtail) {
    logtail = new Logtail(sourceToken, {
      // Don't batch in Workers - flush immediately
      sendLogsToConsoleOutput: false,
    });
  }
  return logtail;
}

// In handler
app.get('/api/*', async (c, next) => {
  const logger = getLogger(c.env.LOGTAIL_TOKEN);
  const requestId = c.req.header('cf-ray') || crypto.randomUUID();

  try {
    await next();
    logger.info('Request completed', {
      requestId,
      path: c.req.path,
      status: c.res.status,
    });
  } catch (error) {
    logger.error('Request failed', {
      requestId,
      path: c.req.path,
      error: String(error),
    });
    throw error;
  } finally {
    // Flush logs before Worker terminates
    c.executionCtx.waitUntil(logger.flush());
  }
});
```

### Wrangler Configuration

```jsonc
{
  "name": "my-worker",
  "vars": {
    "LOGTAIL_TOKEN": ""  // Set via: wrangler secret put LOGTAIL_TOKEN
  }
}
```

## OpenTelemetry Native Export (Advanced)

For full OTel traces, metrics, and logs:

```typescript
// src/utils/otel.ts
interface Span {
  traceId: string;
  spanId: string;
  name: string;
  startTime: number;
  endTime?: number;
  attributes: Record<string, unknown>;
  status: 'OK' | 'ERROR';
}

export function createTracer(serviceName: string) {
  return {
    startSpan(name: string, attributes: Record<string, unknown> = {}): Span {
      return {
        traceId: crypto.randomUUID().replace(/-/g, ''),
        spanId: crypto.randomUUID().replace(/-/g, '').slice(0, 16),
        name,
        startTime: Date.now(),
        attributes: { 'service.name': serviceName, ...attributes },
        status: 'OK',
      };
    },

    endSpan(span: Span, error?: Error) {
      span.endTime = Date.now();
      if (error) {
        span.status = 'ERROR';
        span.attributes['error.message'] = error.message;
      }

      // Export to OTel collector
      console.log(JSON.stringify({
        resourceSpans: [{
          resource: { attributes: [{ key: 'service.name', value: { stringValue: span.attributes['service.name'] } }] },
          scopeSpans: [{
            spans: [{
              traceId: span.traceId,
              spanId: span.spanId,
              name: span.name,
              startTimeUnixNano: span.startTime * 1e6,
              endTimeUnixNano: (span.endTime || Date.now()) * 1e6,
              attributes: Object.entries(span.attributes).map(([k, v]) => ({
                key: k,
                value: { stringValue: String(v) }
              })),
              status: { code: span.status === 'OK' ? 1 : 2 }
            }]
          }]
        }]
      }));
    }
  };
}
```

## Observability Best Practices

| Practice | Recommendation |
|----------|----------------|
| **Sampling** | Use 10-20% sampling for high-volume endpoints |
| **Structured Logs** | Always use JSON format with consistent fields |
| **Request IDs** | Use `cf-ray` header or generate UUID |
| **Error Context** | Include stack traces only in development |
| **PII Redaction** | Never log passwords, tokens, or user PII |
| **Retention** | Export to Axiom/Better Stack for >7 day retention |

## Wrangler Config Template (Full Observability)

```jsonc
{
  "name": "production-worker",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",

  "observability": {
    "logs": {
      "enabled": true,
      "invocation_logs": true,
      "head_sampling_rate": 0.1  // 10% sampling for high volume
    }
  },

  // Enable logpush for export to Axiom/Datadog/etc.
  "logpush": true,

  // Analytics Engine for metrics (free)
  "analytics_engine_datasets": [
    { "binding": "METRICS", "dataset": "worker_metrics" }
  ]
}
```
