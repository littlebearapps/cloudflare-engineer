# Cost-Sensitive Resources Watchlist

This document details pricing traps and cost-sensitive patterns for Cloudflare services. Referenced by the `guardian` skill and all agents for proactive cost warnings.

**Provenance**: All warnings derived from this document should be tagged with `[STATIC:COST_WATCHLIST]` unless verified against live observability data (`[LIVE-VALIDATED]`).

---

## D1 (SQLite Database)

### Pricing Model (2026)

| Operation | Cost | Free Tier |
|-----------|------|-----------|
| Reads | $0.25 per billion rows | 5B rows/month |
| Writes | $1.00 per million rows | 5M rows/month |
| Storage | $0.75 per GB/month | 5GB |

### Cost Traps

#### TRAP-D1-001: Per-Row Inserts (CRITICAL)

**Pattern**: Loop-based INSERT statements instead of batched operations.

```typescript
// EXPENSIVE: Each insert = 1 write operation
for (const item of items) {
  await db.prepare('INSERT INTO items (name) VALUES (?)').bind(item.name).run();
}
// Cost: 10,000 items = 10,000 write operations = $0.01
// At scale: 1M items/day = $1/day = $30/month

// OPTIMIZED: Batched insert = 1 write operation per batch
const batch = items.map(item =>
  db.prepare('INSERT INTO items (name) VALUES (?)').bind(item.name)
);
await db.batch(batch); // Max 1000 statements per batch
// Cost: 10,000 items = 10 batches = $0.00001
// Savings: 99.9%
```

**Detection**:
- `[STATIC]`: Grep for `for.*\.run\(` or `forEach.*\.run\(` patterns
- `[LIVE-VALIDATED]`: Query observability for write operation counts vs row counts

**Guardian Rule**: `BUDGET003`

---

#### TRAP-D1-002: Missing Indexes (HIGH)

**Pattern**: Queries on unindexed columns cause full table scans.

```sql
-- EXPENSIVE: Full table scan
SELECT * FROM users WHERE email = 'user@example.com';
-- If users table has 1M rows, this reads 1M rows

-- OPTIMIZED: Index-based lookup
CREATE INDEX idx_users_email ON users(email);
SELECT * FROM users WHERE email = 'user@example.com';
-- Now reads ~1-10 rows
```

**Detection**:
- `[STATIC]`: Check migrations for CREATE INDEX on WHERE/ORDER BY columns
- `[LIVE-VALIDATED]`: Run `EXPLAIN QUERY PLAN` - look for `SCAN TABLE` vs `SEARCH USING INDEX`

**Guardian Rule**: `PERF002`

---

#### TRAP-D1-003: SELECT * on Large Tables (MEDIUM)

**Pattern**: Fetching all columns when only specific fields needed.

```typescript
// EXPENSIVE: Fetches all columns
const users = await db.prepare('SELECT * FROM users').all();

// OPTIMIZED: Fetch only needed columns
const users = await db.prepare('SELECT id, name FROM users').all();
```

**Detection**:
- `[STATIC]`: Grep for `SELECT \*` patterns
- `[LIVE-VALIDATED]`: Check average response size in observability

---

#### TRAP-D1-004: Row Read Explosion (CRITICAL) - NEW v1.4.0

**Pattern**: Unindexed queries causing full table scans on high-traffic endpoints. The primary billing danger for solo developers.

```typescript
// DISASTER: Full table scan on every request
app.get('/api/users', async (c) => {
  // No index on 'status' column = reads ALL rows
  const users = await db.prepare(
    'SELECT * FROM users WHERE status = ?'
  ).bind('active').all();
  return c.json(users);
});
// With 100K rows table:
// - 1K requests/day = 100M rows read/day
// - Free tier: 5B rows/month = 166M rows/day
// - Cost: $0.25/B rows = exceeds free tier in <2 days

// OPTIMIZED: Index + KV cache
// 1. Add index
CREATE INDEX idx_users_status ON users(status);

// 2. Cache hot queries in KV
const cacheKey = `users:active`;
let users = await c.env.KV.get(cacheKey, 'json');
if (!users) {
  users = await db.prepare(
    'SELECT id, name FROM users WHERE status = ? LIMIT 100'
  ).bind('active').all();
  await c.env.KV.put(cacheKey, JSON.stringify(users), { expirationTtl: 60 });
}
// KV reads: $0.50/M, cache hit = no D1 cost
// 1000 requests with 95% cache hit = 50 D1 queries/day
```

**Real-World Example**: One developer hit the 5 million daily read limit just by browsing their own site during development—each page load triggered a full table scan.

**Detection**:
- `[STATIC]`: SELECT without WHERE clause on high-traffic routes
- `[STATIC]`: WHERE clause on column without index in migrations
- `[LIVE-VALIDATED]`: D1 row read count >> expected request count

**Guardian Rule**: `BUDGET007`

**Pattern Reference**: See `@skills/patterns/kv-cache-first.md`

---

#### TRAP-D1-005: Unbounded SELECT * (HIGH) - NEW v1.5.0

**Pattern**: SELECT * without LIMIT on tables that grow over time. Combined with missing index, this is a billing explosion waiting to happen.

```typescript
// EXPENSIVE: Fetches ALL rows, ALL columns
app.get('/api/products', async (c) => {
  const products = await db.prepare('SELECT * FROM products').all();
  return c.json(products);
});
// With 50K products:
// - Each request reads 50K rows × all columns
// - 100 requests/day = 5M rows read = free tier limit

// OPTIMIZED: Pagination + column selection
app.get('/api/products', async (c) => {
  const page = parseInt(c.req.query('page') || '1');
  const limit = 20;
  const offset = (page - 1) * limit;

  const products = await db.prepare(
    'SELECT id, name, price FROM products ORDER BY id LIMIT ? OFFSET ?'
  ).bind(limit, offset).all();

  return c.json(products);
});
// Each request reads 20 rows = sustainable at any scale
```

**Detection**:
- `[STATIC]`: `SELECT * FROM` without `LIMIT` clause
- `[STATIC]`: List endpoint handler without pagination parameters
- `[LIVE-VALIDATED]`: Row reads >> expected result set size

**Guardian Rule**: `QUERY001`

---

#### TRAP-D1-006: Drizzle findMany Without Limit (MEDIUM) - NEW v1.5.0

**Pattern**: Drizzle ORM's `findMany()` and `.all()` without `.limit()` return entire tables.

```typescript
// EXPENSIVE: ORM hides the unbounded query
const users = await db.query.users.findMany();  // ALL users
const posts = await db.select().from(posts);     // ALL posts

// OPTIMIZED: Always specify limits
const users = await db.query.users.findMany({
  limit: 100,
  where: eq(users.status, 'active'),
});

const posts = await db.select()
  .from(posts)
  .where(eq(posts.published, true))
  .limit(50);
```

**Detection**:
- `[STATIC]`: `findMany()` without `limit:` option
- `[STATIC]`: `.all()` without preceding `.limit()`
- `[LIVE-VALIDATED]`: Drizzle query row counts

**Guardian Rule**: `QUERY005`

---

## R2 (Object Storage)

### Pricing Model (2026)

| Operation | Cost | Free Tier |
|-----------|------|-----------|
| Class A (writes) | $4.50 per million | 1M/month |
| Class B (reads) | $0.36 per million | 10M/month |
| Storage | $0.015 per GB/month | 10GB |
| Egress | FREE | Unlimited |

### Cost Traps

#### TRAP-R2-001: Frequent Small Writes (HIGH)

**Pattern**: Writing small objects frequently instead of buffering.

```typescript
// EXPENSIVE: Each log line = 1 Class A operation
for (const log of logs) {
  await bucket.put(`logs/${Date.now()}.json`, JSON.stringify(log));
}
// Cost: 1M logs/day = $4.50/day = $135/month

// OPTIMIZED: Buffer and batch write
const buffer = logs.map(l => JSON.stringify(l)).join('\n');
await bucket.put(`logs/${Date.now()}-batch.jsonl`, buffer);
// Cost: 1 batch/minute = 1440 ops/day = $0.006/day
// Savings: 99.99%
```

**Detection**:
- `[STATIC]`: Look for `.put()` inside loops or high-frequency handlers
- `[LIVE-VALIDATED]`: Check Class A operation count vs object count

**Guardian Rule**: `BUDGET002`

---

#### TRAP-R2-002: Direct Client Uploads Missing Presigned URLs (MEDIUM)

**Pattern**: Proxying uploads through Worker instead of direct-to-R2.

```typescript
// EXPENSIVE: Worker proxies entire file
app.post('/upload', async (c) => {
  const file = await c.req.blob();
  await c.env.BUCKET.put(filename, file);
});
// Cost: Worker CPU time + potential timeouts on large files

// OPTIMIZED: Presigned URL for direct upload
app.post('/upload/url', async (c) => {
  const url = await c.env.BUCKET.createMultipartUpload(filename);
  return c.json({ uploadUrl: url });
});
// Client uploads directly to R2, Worker only generates URL
```

**Detection**:
- `[STATIC]`: Check for `await c.req.blob()` or `await request.arrayBuffer()` patterns
- `[LIVE-VALIDATED]`: Check CPU time for upload endpoints

---

#### TRAP-R2-003: Class B Operation Accumulation (MEDIUM) - NEW v1.4.0

**Pattern**: Public R2 bucket serving assets without edge caching. Every request triggers a Class B operation ($0.36/M).

```typescript
// EXPENSIVE: Every request = Class B operation
app.get('/assets/:key', async (c) => {
  const obj = await c.env.ASSETS.get(c.req.param('key'));
  return new Response(obj?.body);
});
// 10M requests/month = $3.60 (exceeds free tier)
// 100M requests/month = $36.00

// OPTIMIZED: Cache at edge
app.get('/assets/:key', async (c) => {
  const cache = caches.default;
  const cacheKey = new Request(c.req.url);

  // Try cache first (FREE)
  let response = await cache.match(cacheKey);
  if (response) return response;

  // Cache miss: fetch from R2
  const obj = await c.env.ASSETS.get(c.req.param('key'));
  if (!obj) return c.notFound();

  response = new Response(obj.body, {
    headers: {
      'Cache-Control': 'public, max-age=31536000, immutable',
      'Content-Type': obj.httpMetadata?.contentType || 'application/octet-stream',
    },
  });

  // Store in cache for next request
  c.executionCtx.waitUntil(cache.put(cacheKey, response.clone()));
  return response;
});
// Most requests served from edge cache (FREE)
// Only ~5% cache misses hit R2
```

**Detection**:
- `[STATIC]`: Public R2 routes without Cache API or Cache-Control headers
- `[LIVE-VALIDATED]`: R2 Class B operations >> unique object count

**Guardian Rule**: `BUDGET008`

**Pattern Reference**: See `@skills/patterns/r2-cdn-cache.md`

---

#### TRAP-R2-004: Infrequent Access Minimum Billing Trap (CRITICAL) - NEW v1.4.0

**Pattern**: Using R2 Infrequent Access (IA) storage for buckets that have ANY read operations. Cloudflare bills IA in minimum units—a single operation can trigger a **$9.00 minimum charge**.

```typescript
// DISASTER: Single read on IA bucket
const backup = await iaBucket.get('small-config.json');
// Even though the file is 1KB, you may be billed:
// - Minimum retrieval unit: ~25M operations worth
// - Minimum charge: $9.00 for ONE OPERATION

// SAFE: IA only for true cold storage (write-only)
await iaBucket.put('database-backup-500GB.sql', largeBackup);
// Never call .get() on IA buckets

// SAFE: Standard storage for any readable content
const config = await standardBucket.get('small-config.json');
```

**Cloudflare IA Billing Model**:
- IA storage is cheaper: ~$0.01/GB/month (vs $0.015 standard)
- IA retrieval is expensive: $0.36/GB + operation charges
- **TRAP**: Minimum billing units round up to ~$9 minimum

**When to Use IA**:
- ✅ True cold storage (disaster recovery backups)
- ✅ Large files (>100MB) where retrieval cost is amortized
- ✅ Write-only archives (compliance data, audit logs)

**When to AVOID IA**:
- ❌ ANY bucket with regular read operations
- ❌ User-facing asset storage
- ❌ Files that might be accessed during development
- ❌ Small files (cost per GB doesn't justify minimum)

**Detection**:
- `[STATIC]`: Bucket name contains "cold", "archive", "backup", "ia" AND has `.get()` calls
- `[LIVE-VALIDATED]`: IA retrieval charges appearing in billing

**Guardian Rule**: `BUDGET009`

---

#### TRAP-R2-005: Public Bucket Without CDN (HIGH) - NEW v1.5.0

**Pattern**: R2 bucket with public access (custom domain or r2.dev) but no Cache Rules or CDN configuration. Every visitor request = Class B operation.

```typescript
// EXPENSIVE: Public bucket, no caching layer
// wrangler.jsonc or dashboard config:
// - Custom domain: assets.example.com → R2 bucket
// - No Cache Rules configured
// - No Worker with caches.default in front

// Every image request:
// 10K visitors/day × 10 images/page = 100K Class B ops/day
// 3M ops/month = $1.08/month (exceeds 10M free tier threshold quickly)

// OPTIMIZED: Cache Rule for R2 assets
// In Cloudflare Dashboard:
// Rules → Cache Rules → Create Rule:
// - When: hostname = assets.example.com
// - Cache: Standard
// - Edge TTL: 1 month
// - Browser TTL: 1 week

// Or via Worker:
export default {
  async fetch(request, env) {
    const cache = caches.default;
    let response = await cache.match(request);

    if (!response) {
      const url = new URL(request.url);
      const object = await env.ASSETS.get(url.pathname.slice(1));
      if (!object) return new Response('Not Found', { status: 404 });

      response = new Response(object.body, {
        headers: {
          'Cache-Control': 'public, max-age=2592000',
          'Content-Type': object.httpMetadata?.contentType || 'application/octet-stream',
        },
      });
      ctx.waitUntil(cache.put(request, response.clone()));
    }
    return response;
  },
};
```

**Detection**:
- `[STATIC]`: Public domain/r2.dev enabled without Cache Rules in zone
- `[STATIC]`: No Worker in front of public R2
- `[LIVE-VALIDATED]`: R2 Class B operations match visitor count (no caching)

**Guardian Rule**: `R2002`

**Pattern Reference**: See `@skills/patterns/r2-cdn-cache.md`

---

#### TRAP-R2-006: Uncached R2.get() on Hot Path (MEDIUM) - NEW v1.5.0

**Pattern**: Worker endpoint calls `R2.get()` without checking `caches.default` first. Each request triggers billable operation.

```typescript
// EXPENSIVE: Direct R2 hit every request
app.get('/files/:id', async (c) => {
  const file = await c.env.FILES.get(c.req.param('id'));
  if (!file) return c.notFound();
  return new Response(file.body);
});
// Cost: 1 Class B op per request ($0.36/M)

// OPTIMIZED: Cache-first with R2 fallback
app.get('/files/:id', async (c) => {
  const cache = caches.default;
  const cacheKey = new Request(c.req.url);

  // Check edge cache first (FREE)
  let response = await cache.match(cacheKey);
  if (response) return response;

  // Cache miss: fetch from R2 (Class B op)
  const file = await c.env.FILES.get(c.req.param('id'));
  if (!file) return c.notFound();

  response = new Response(file.body, {
    headers: {
      'Content-Type': file.httpMetadata?.contentType || 'application/octet-stream',
      'Cache-Control': 'public, max-age=86400',
      'ETag': file.etag,
    },
  });

  // Populate cache for next request
  c.executionCtx.waitUntil(cache.put(cacheKey, response.clone()));
  return response;
});
// 95% cache hit = 95% cost reduction
```

**Detection**:
- `[STATIC]`: `R2.get()` without `cache.match()` in same handler
- `[STATIC]`: Route handler with `env.*.get()` but no `caches.default` import
- `[LIVE-VALIDATED]`: R2 Class B ops ≈ request count (should be << with caching)

**Guardian Rule**: `R2002`

---

## Durable Objects

### Pricing Model (2026)

| Resource | Cost | Free Tier |
|----------|------|-----------|
| Requests | $0.15 per million | 1M/month |
| Duration | $12.50 per million GB-seconds | None |
| Storage | $0.20 per GB/month | 1GB |

### Cost Traps

#### TRAP-DO-001: Overusing Durable Objects (HIGH)

**Pattern**: Using Durable Objects for simple key-value storage.

```typescript
// EXPENSIVE: Durable Object for simple counter
export class CounterDO {
  async fetch(request: Request) {
    const count = await this.state.storage.get('count') || 0;
    await this.state.storage.put('count', count + 1);
    return new Response(String(count + 1));
  }
}
// Cost: $0.15/M requests + duration charges + storage

// OPTIMIZED: Use KV or D1 for simple storage
await env.KV.put('counter', String(count + 1));
// Cost: $5/M writes (cheaper for non-coordinated access)
```

**When to use Durable Objects**:
- Real-time coordination (chat, collaboration)
- Strong consistency requirements
- WebSocket management
- Rate limiting with atomic counters
- Distributed locks

**Detection**:
- `[STATIC]`: Check if DO is used for simple CRUD without coordination needs
- `[LIVE-VALIDATED]`: Compare request patterns to storage operations

**Guardian Rule**: `BUDGET001`

---

#### TRAP-DO-002: Not Using Hibernation (MEDIUM)

**Pattern**: Keeping Durable Objects active when idle.

```typescript
// EXPENSIVE: Object stays active
export class ChatRoom {
  async fetch(request: Request) {
    // Handle request
    return new Response('OK');
  }
}

// OPTIMIZED: Use hibernation for WebSocket connections
export class ChatRoom {
  async webSocketMessage(ws: WebSocket, message: string) {
    // Handle message - object hibernates between messages
  }
}
```

**Detection**:
- `[STATIC]`: Check for WebSocket handlers vs hibernation API usage

---

## KV (Key-Value Store)

### Pricing Model (2026)

| Operation | Cost | Free Tier |
|-----------|------|-----------|
| Reads | $0.50 per million | 100K/day |
| Writes | $5.00 per million | 1K/day |
| Storage | $0.50 per GB/month | 1GB |

### Cost Traps

#### TRAP-KV-001: Write-Heavy Patterns (HIGH)

**Pattern**: Using KV for write-heavy workloads.

```typescript
// EXPENSIVE: Frequent KV writes
app.post('/events', async (c) => {
  await c.env.KV.put(`event:${Date.now()}`, JSON.stringify(event));
});
// Cost: 1M events = $5

// OPTIMIZED: Use D1 or R2 for write-heavy
await c.env.DB.prepare('INSERT INTO events ...').run();
// Cost: 1M events = $1 (D1 writes)
// Or use Analytics Engine (essentially free)
```

**Detection**:
- `[STATIC]`: Count `.put()` calls in request handlers
- `[LIVE-VALIDATED]`: Check write operation frequency

**Guardian Rule**: `BUDGET005`

---

## Queues

### Pricing Model (2026)

| Operation | Cost | Free Tier |
|-----------|------|-----------|
| Messages | $0.40 per million | 1M/month |

### Cost Traps

#### TRAP-QUEUE-001: High Retry Counts (HIGH)

**Pattern**: Setting high max_retries multiplies message costs.

```jsonc
// EXPENSIVE: 5 retries = up to 6x message cost
{
  "queues": {
    "consumers": [{
      "queue": "my-queue",
      "max_retries": 5  // Each retry = another message charge
    }]
  }
}

// OPTIMIZED: Low retries + DLQ for inspection
{
  "queues": {
    "consumers": [{
      "queue": "my-queue",
      "max_retries": 1,
      "dead_letter_queue": "my-queue-dlq"
    }]
  }
}
```

**Detection**:
- `[STATIC]`: Check wrangler config for `max_retries > 2`
- `[LIVE-VALIDATED]`: Compare message count to delivery attempts

**Guardian Rule**: `COST001`

---

## Workers AI

### Pricing Model (2026)

| Model Size | Cost | Notes |
|------------|------|-------|
| Small (<3B) | ~$0.01/1K neurons | Efficient for simple tasks |
| Medium (3-8B) | ~$0.05/1K neurons | Good balance |
| Large (>8B) | ~$0.68/M tokens | Expensive at scale |

### Cost Traps

#### TRAP-AI-001: Large Models for Simple Tasks (HIGH)

**Pattern**: Using Llama 70B for tasks a smaller model handles.

```typescript
// EXPENSIVE: Large model for classification
const result = await env.AI.run('@cf/meta/llama-3-70b-instruct', {
  prompt: 'Is this spam? ' + message
});

// OPTIMIZED: Small model or fine-tuned classifier
const result = await env.AI.run('@cf/huggingface/distilbert-sst-2-int8', {
  text: message
});
// Or use embeddings + cosine similarity for classification
```

**Detection**:
- `[STATIC]`: Check model names in code for >8B models
- `[LIVE-VALIDATED]`: Check AI Gateway logs for model usage

**Guardian Rule**: `BUDGET004`

---

#### TRAP-AI-002: No Prompt Caching (MEDIUM)

**Pattern**: Identical prompts not cached via AI Gateway.

```typescript
// EXPENSIVE: Same prompt, full inference each time
const result = await env.AI.run(model, { prompt: systemPrompt + userInput });

// OPTIMIZED: Use AI Gateway with caching
// Configure in AI Gateway dashboard:
// - Enable caching for identical requests
// - Set appropriate TTL
```

**Detection**:
- `[STATIC]`: Check for AI Gateway configuration
- `[LIVE-VALIDATED]`: Check cache hit rate in AI Gateway logs

**Guardian Rule**: `COST003`

---

## Vectorize

### Pricing Model (2026)

| Resource | Cost | Limit |
|----------|------|-------|
| Queries | $0.01 per million | N/A |
| Stored Vectors | $0.05 per 100M dimension-vectors | 5M vectors/index |

### Cost Traps

#### TRAP-VEC-001: Approaching Vector Limits (INFO)

**Pattern**: Not planning for vector index limits.

**Detection**:
- `[STATIC]`: Check expected vector count in design docs
- `[LIVE-VALIDATED]`: Query current vector count

**Guardian Rule**: `BUDGET006`

---

## Log Privacy Violations (NEW v1.5.0)

**CRITICAL**: Logging sensitive data to external services (Axiom, Better Stack, etc.) creates compliance liability and potential data breach exposure. Privacy violations often compound costs through:
1. Regulatory fines (GDPR, CCPA)
2. Incident response costs
3. Customer notification requirements
4. Reputation damage

### TRAP-PRIVACY-001: Logging Authorization Headers (CRITICAL)

**Pattern**: Logging request headers without redacting Authorization, API keys, or tokens.

```typescript
// DANGEROUS: Logs bearer tokens, API keys
app.use('*', async (c, next) => {
  console.log('Request headers:', Object.fromEntries(c.req.raw.headers));
  await next();
});
// If exported to Axiom/Better Stack:
// - Bearer tokens visible in logs
// - API keys exposed to log viewers
// - Session tokens compromised

// SAFE: Redact sensitive headers
const SENSITIVE_HEADERS = ['authorization', 'x-api-key', 'cookie', 'cf-access-client-secret'];

app.use('*', async (c, next) => {
  const safeHeaders = Object.fromEntries(
    [...c.req.raw.headers.entries()].map(([key, value]) =>
      SENSITIVE_HEADERS.includes(key.toLowerCase())
        ? [key, '[REDACTED]']
        : [key, value]
    )
  );
  console.log('Request headers:', safeHeaders);
  await next();
});
```

**Detection**:
- `[STATIC]`: `console.log.*headers` without redaction
- `[STATIC]`: Logger call with `request.headers` as argument
- `[LIVE-VALIDATED]`: Logs contain "Bearer", "Authorization:", "x-api-key"

**Guardian Rule**: `PRIV001`

---

### TRAP-PRIVACY-002: Logging PII (HIGH)

**Pattern**: Logging user data containing email addresses, phone numbers, or other personally identifiable information.

```typescript
// DANGEROUS: User object with PII goes to logs
app.post('/api/users', async (c) => {
  const user = await c.req.json();
  console.log('Creating user:', user);  // Contains email, phone, etc.
  await db.createUser(user);
});

// SAFE: Log only non-PII identifiers
app.post('/api/users', async (c) => {
  const user = await c.req.json();
  console.log('Creating user:', { id: user.id, role: user.role });
  await db.createUser(user);
});

// SAFE: Use sanitization utility
import { sanitizeLogs } from './utils/log-sanitizer';

console.log('User data:', sanitizeLogs(JSON.stringify(user)));
// Output: "User data: {\"email\":\"[EMAIL]\",\"phone\":\"[PHONE]\"}"
```

**Detection**:
- `[STATIC]`: `console.log` with user object variables
- `[STATIC]`: Logger calls with request body
- `[LIVE-VALIDATED]`: Logs contain email patterns, phone patterns

**Guardian Rule**: `PRIV002`

**Pattern Reference**: See `@commands/cf-logs.md` Privacy Filters section

---

### TRAP-PRIVACY-003: Logging Financial Data (CRITICAL)

**Pattern**: Credit card numbers, bank accounts, or financial identifiers in logs.

```typescript
// DANGEROUS: Payment data in logs
app.post('/api/checkout', async (c) => {
  const payment = await c.req.json();
  console.log('Processing payment:', payment);  // Contains card number!
  // ...
});

// SAFE: Never log payment data
app.post('/api/checkout', async (c) => {
  const payment = await c.req.json();
  console.log('Processing payment for order:', payment.orderId);
  // Card data never touches console.log
});

// SAFE: Hash/mask if audit trail needed
const maskedCard = payment.cardNumber.replace(/\d(?=\d{4})/g, '*');
console.log('Card ending:', maskedCard.slice(-4));  // "****1234"
```

**Detection**:
- `[STATIC]`: Variables named `card`, `payment`, `credit`, `account` in log statements
- `[STATIC]`: 16-digit number patterns in console output
- `[LIVE-VALIDATED]`: Logs contain credit card regex patterns

**Guardian Rule**: `PRIV003`

---

## Provenance Tagging Reference

When citing this document in warnings:

| Tag | Usage |
|-----|-------|
| `[STATIC:COST_WATCHLIST]` | Warning based on code pattern matching |
| `[LIVE-VALIDATED:COST_WATCHLIST]` | Warning confirmed by observability data |
| `[REFUTED:COST_WATCHLIST]` | Pattern exists but not hitting thresholds |

### Example Warning Format

```
[STATIC:COST_WATCHLIST] TRAP-D1-001 detected in src/handlers/import.ts:45
Per-row INSERT in loop may cause high D1 write costs.
Estimated impact: 10,000 items × $0.001 = $10/batch
Recommendation: Use db.batch() for bulk inserts.
See: COST_SENSITIVE_RESOURCES.md#trap-d1-001-per-row-inserts-critical
```

---

## Loop-Induced Cost Traps (Billing Safety)

**CRITICAL**: Infinite loops, recursion, and runaway processes are the #1 cause of unexpected cloud bills. In serverless, a loop isn't frozen UI—it's a **billing multiplier**.

### TRAP-LOOP-001: Worker Self-Recursion (CRITICAL)

**Pattern**: Worker calls itself via `fetch()` creating infinite request chain.

```typescript
// DISASTER: Each iteration is a new Worker invocation
app.post('/webhook', async (c) => {
  // If this webhook triggers itself...
  const response = await fetch(request.url, {
    method: 'POST',
    body: processedData,
  });
  // ...infinite loop at $0.30/M requests
});
// Cost: Unbounded - can hit rate limits or exhaust budget

// SAFE: Recursion depth tracking
const DEPTH_HEADER = 'X-Recursion-Depth';
const MAX_DEPTH = 3;

app.post('/webhook', async (c) => {
  const depth = parseInt(c.req.header(DEPTH_HEADER) || '0');
  if (depth > MAX_DEPTH) {
    return c.json({ error: 'Recursion limit' }, 508);
  }

  const headers = new Headers();
  headers.set(DEPTH_HEADER, (depth + 1).toString());
  // Now safe to call
});
```

**Detection**:
- `[STATIC]`: Pattern `fetch(request.url)` or `fetch(c.req.url)`
- `[LIVE-VALIDATED]`: Sudden spike in request count from same origin

**Guardian Rules**: `LOOP005`
**Pre-deploy Hook**: Detects and blocks on CRITICAL

---

### TRAP-LOOP-002: Queue Retry Storm (HIGH)

**Pattern**: Permanent bug causes infinite retries until DLQ (or forever if no DLQ).

```jsonc
// EXPENSIVE: 5 retries × message cost
{
  "queues": {
    "consumers": [{
      "queue": "events",
      "max_retries": 5  // Each retry = $0.40/M
    }]
  }
}
// 1M messages with permanent failure = 6M × $0.40 = $2.40
// Without DLQ: retries forever

// SAFE: Low retries + DLQ
{
  "queues": {
    "consumers": [{
      "queue": "events",
      "max_retries": 1,
      "dead_letter_queue": "events-dlq"  // Breaks the loop
    }]
  }
}
```

**Detection**:
- `[STATIC]`: `max_retries > 2` without DLQ
- `[LIVE-VALIDATED]`: DLQ depth increasing, high retry rate

**Guardian Rules**: `LOOP006`, `LOOP008`, `COST001`

---

### TRAP-LOOP-003: Durable Object Wake Loop (HIGH)

**Pattern**: `setInterval` in DO keeps object active and billing for duration.

```typescript
// EXPENSIVE: DO stays awake billing wall time
export class BadDO {
  constructor(state: DurableObjectState) {
    // This runs FOREVER
    setInterval(() => this.checkSomething(), 1000);
    // Duration billing: $12.50/M GB-seconds
    // 1 hour = 3600 seconds = ~$0.045 per DO per hour
  }
}

// SAFE: Alarm-based with hibernation
export class GoodDO {
  async alarm() {
    await this.checkSomething();
    // Only reschedule if still needed
    if (await this.shouldContinue()) {
      await this.state.storage.setAlarm(Date.now() + 1000);
    }
    // Otherwise hibernates - no duration billing
  }
}
```

**Detection**:
- `[STATIC]`: `setInterval` in DO class without `clearInterval`
- `[LIVE-VALIDATED]`: DO duration charges without corresponding activity

**Guardian Rules**: `LOOP004`

---

### TRAP-LOOP-004: N+1 Query Loop (CRITICAL)

**Pattern**: Database query inside loop causes N+1 operations.

```typescript
// DISASTER: 1000 users = 1000 D1 queries
for (const user of users) {
  const orders = await db
    .prepare('SELECT * FROM orders WHERE user_id = ?')
    .bind(user.id)
    .all();
}
// Cost: 1000 × read operations + CPU time

// SAFE: Single batch query
const userIds = users.map(u => u.id);
const placeholders = userIds.map(() => '?').join(',');
const orders = await db
  .prepare(`SELECT * FROM orders WHERE user_id IN (${placeholders})`)
  .bind(...userIds)
  .all();
// Cost: 1 query regardless of user count
```

**Detection**:
- `[STATIC]`: SQL operations inside `for`, `while`, `forEach`, `.map()`
- `[LIVE-VALIDATED]`: D1 query count >> logical operation count

**Guardian Rules**: `LOOP002`, `BUDGET003`

---

### TRAP-LOOP-005: R2 Write Flood (HIGH)

**Pattern**: R2 Class A operations inside high-frequency loop.

```typescript
// EXPENSIVE: Each iteration = Class A operation ($4.50/M)
for (const log of logs) {
  await bucket.put(`log/${log.id}.json`, JSON.stringify(log));
}
// 1M logs = $4.50

// SAFE: Buffer and batch
const buffer = logs.map(l => JSON.stringify(l)).join('\n');
await bucket.put(`logs/${Date.now()}.jsonl`, buffer);
// 1 batch = $0.0000045
```

**Detection**:
- `[STATIC]`: `.put()` inside loops
- `[LIVE-VALIDATED]`: Class A ops >> object count

**Guardian Rules**: `LOOP003`, `BUDGET002`

---

### CPU Limit as Circuit Breaker

The `limits.cpu_ms` setting is your billing safety circuit breaker:

| Use Case | Recommended cpu_ms | Rationale |
|----------|-------------------|-----------|
| API endpoint | 50-100ms | Fails fast on loops |
| DB operations | 100-200ms | Query + serialize time |
| AI inference | 500-1000ms | Model loading |
| Batch processing | 5000-10000ms | Legitimate heavy work |

```jsonc
{
  "limits": {
    "cpu_ms": 100  // Kill process if CPU churns >100ms
  }
}
```

**Without this setting**: A tight `while(true)` burns 30s of CPU (paid tier limit) before failing.

---

## Adding New Cost Traps

When adding new Cloudflare services or discovering new cost patterns:

1. Add entry under appropriate service section
2. Include:
   - Trap ID (TRAP-{SERVICE}-{NUMBER})
   - Severity (CRITICAL/HIGH/MEDIUM/INFO)
   - Code examples (expensive vs optimized)
   - Detection methods ([STATIC] and [LIVE-VALIDATED])
   - Associated Guardian rule ID
3. Update guardian skill with new BUDGET/COST rule
4. Add detection logic to pre-deploy hook if applicable
5. Update agents to reference new trap

---

## Quick Reference Card

| Service | Top Cost Trap | Guardian Rule | Detection |
|---------|---------------|---------------|-----------|
| D1 | Per-row inserts | BUDGET003 | `for.*\.run\(` pattern |
| D1 | Row read explosion | BUDGET007 | Unindexed SELECT on high traffic |
| R2 | Frequent small writes | BUDGET002 | `.put()` in loops |
| R2 | Class B accumulation | BUDGET008 | Public bucket without cache |
| R2 | IA minimum billing | BUDGET009 | `.get()` on IA bucket |
| DO | Overuse for simple KV | BUDGET001 | DO without coordination |
| KV | Write-heavy patterns | BUDGET005 | High `.put()` frequency |
| Queues | High retries | COST001 | `max_retries > 2` |
| AI | Large models | BUDGET004 | Model name contains `70b` |
| Vectorize | Approaching limits | BUDGET006 | Vector count monitoring |
| Privacy | Auth header logging | PRIV001 | `console.log.*headers` |
| Privacy | PII in logs | PRIV002 | User objects in log calls |
| Privacy | Financial data logs | PRIV003 | Card patterns in logs |

### Loop Safety Quick Reference

| Loop Type | Trap ID | Guardian Rule | Detection |
|-----------|---------|---------------|-----------|
| Worker self-fetch | TRAP-LOOP-001 | LOOP005 | `fetch(request.url)` |
| Queue retry storm | TRAP-LOOP-002 | LOOP006, LOOP008 | No DLQ, high retries |
| DO setInterval | TRAP-LOOP-003 | LOOP004 | `setInterval` in DO |
| N+1 queries | TRAP-LOOP-004 | LOOP002 | SQL in loop |
| R2 write flood | TRAP-LOOP-005 | LOOP003 | `.put()` in loop |
| Missing cpu_ms | - | LOOP001 | No limits config |
| Unbounded while | - | LOOP007 | `while(true)` |

### v1.4.0 New Cost Traps

| Trap ID | Service | Severity | Description |
|---------|---------|----------|-------------|
| TRAP-D1-004 | D1 | CRITICAL | Row read explosion from unindexed queries |
| TRAP-R2-003 | R2 | MEDIUM | Class B ops without edge caching |
| TRAP-R2-004 | R2 | CRITICAL | IA storage with read operations ($9 minimum) |

### v1.5.0 New Cost Traps

| Trap ID | Service | Severity | Description |
|---------|---------|----------|-------------|
| TRAP-D1-005 | D1 | HIGH | Unbounded SELECT * without LIMIT |
| TRAP-D1-006 | D1 | MEDIUM | Drizzle findMany without limit option |
| TRAP-R2-005 | R2 | HIGH | Public bucket without CDN/Cache Rules |
| TRAP-R2-006 | R2 | MEDIUM | Uncached R2.get() on hot path |
| TRAP-PRIVACY-001 | Privacy | CRITICAL | Logging Authorization headers |
| TRAP-PRIVACY-002 | Privacy | HIGH | Logging PII (email, phone) |
| TRAP-PRIVACY-003 | Privacy | CRITICAL | Logging financial data (cards) |

---

*Last updated: 2026-01-18 (v1.5.0 - Query Optimization + External Logging + Privacy)*
