# KV-Cache-First Pattern

## Problem

D1 row reads are the primary billing danger for solo developers. Unoptimized queries (missing indexes) can trigger millions of reads per page view. The free tier limit of 5 billion rows/month (~166M/day) can be exhausted in hours with a single high-traffic endpoint.

**Real-world example**: One developer hit the 5 million daily read limit just by browsing their own site during development—each page load triggered a full table scan.

## Solution

Place a KV read **before** every D1 query on high-traffic endpoints. KV reads cost $0.50/M (vs D1's $0.25/B = effectively more expensive at scale without caching), but the real savings come from **not hitting D1 at all** on cache hits.

## When to Apply

**Trigger Conditions**:
- Endpoint receives >100 requests/minute
- D1 query returns relatively static data (changes < once/minute)
- Query involves table scans (no WHERE or unindexed WHERE)
- Query returns lists or collections (not single-record lookups by ID)

**Detection** (static):
```javascript
// Anti-pattern: Direct D1 on every request
app.get('/products', async (c) => {
  return c.json(await db.prepare('SELECT * FROM products').all());
});
```

**Detection** (live):
- D1 read count >> expected page views
- High latency on list endpoints
- D1 billing approaching limits

## Implementation

### Before: Direct D1 (Expensive)

```typescript
// Each request reads ALL rows
app.get('/api/products', async (c) => {
  const { results } = await c.env.DB
    .prepare('SELECT * FROM products WHERE category = ?')
    .bind(category)
    .all();
  return c.json(results);
});
// Cost: 10K products × 1K req/hour = 10M rows/hour = $2.50/hour
```

### After: KV-Cache-First (Optimized)

```typescript
// src/utils/cache.ts
export async function getCached<T>(
  kv: KVNamespace,
  key: string,
  fetcher: () => Promise<T>,
  ttl: number = 60
): Promise<T> {
  // Try KV first
  const cached = await kv.get(key, 'json');
  if (cached !== null) {
    return cached as T;
  }

  // Cache miss: fetch from D1
  const fresh = await fetcher();

  // Store in KV for next request
  await kv.put(key, JSON.stringify(fresh), { expirationTtl: ttl });

  return fresh;
}

// src/routes/products.ts
import { getCached } from '../utils/cache';

app.get('/api/products', async (c) => {
  const category = c.req.query('category') || 'all';

  const products = await getCached(
    c.env.CACHE,
    `products:${category}`,
    async () => {
      const { results } = await c.env.DB
        .prepare('SELECT id, name, price FROM products WHERE category = ? LIMIT 100')
        .bind(category)
        .all();
      return results;
    },
    60 // 1 minute TTL
  );

  return c.json(products);
});
// Cost: 1 D1 read/minute + KV reads
// 1K req/hour: 60 D1 reads + 1K KV reads = $0.0005/hour (99.98% savings)
```

### Wrangler Configuration

```jsonc
{
  "name": "my-api",
  "kv_namespaces": [
    { "binding": "CACHE", "id": "your-kv-namespace-id" }
  ],
  "d1_databases": [
    { "binding": "DB", "database_name": "my-db", "database_id": "..." }
  ]
}
```

## Cache Key Strategies

### Simple Key (Single Parameter)
```typescript
const key = `products:${category}`;
```

### Composite Key (Multiple Parameters)
```typescript
const key = `products:${category}:${sortBy}:${page}`;
```

### Hash Key (Complex Queries)
```typescript
const queryHash = await crypto.subtle.digest(
  'SHA-256',
  new TextEncoder().encode(JSON.stringify({ category, filters, sort }))
);
const key = `products:${btoa(String.fromCharCode(...new Uint8Array(queryHash)))}`;
```

## Cache Invalidation Patterns

### Time-Based (Simple)
```typescript
await kv.put(key, data, { expirationTtl: 60 }); // Auto-expire in 60s
```

### Write-Through (Consistent)
```typescript
// On update, invalidate cache
app.put('/api/products/:id', async (c) => {
  await c.env.DB.prepare('UPDATE products SET ...').run();

  // Invalidate all product caches
  await c.env.CACHE.delete(`products:${category}`);

  return c.json({ success: true });
});
```

### Tag-Based (Advanced)
```typescript
// Store cache keys by tag
await kv.put(`tag:products`, JSON.stringify([key1, key2, key3]));

// Invalidate by tag
async function invalidateTag(kv: KVNamespace, tag: string) {
  const keys = await kv.get(`tag:${tag}`, 'json') as string[];
  await Promise.all(keys.map(k => kv.delete(k)));
  await kv.delete(`tag:${tag}`);
}
```

## Cost Comparison

| Scenario | Direct D1 | KV-Cache-First | Savings |
|----------|-----------|----------------|---------|
| 1K req/hour, 10K rows | $2.50/hour | $0.0005/hour | 99.98% |
| 10K req/hour, 100K rows | $250/hour | $0.005/hour | 99.998% |
| 100K req/day, 10K rows | $25/day | $0.05/day | 99.8% |

## Trade-offs

| Benefit | Cost |
|---------|------|
| Dramatic D1 cost reduction | Data staleness (TTL-bounded) |
| Lower latency (KV is faster) | Additional KV write cost |
| Reduced D1 connection pressure | Cache invalidation complexity |
| Works at any scale | Memory for cache keys |

## When NOT to Use

- Single-record lookups by indexed primary key (D1 is efficient)
- Data that changes on every request (TTL=0 defeats purpose)
- Personalized data per user (cache key explosion)
- Writes (use write-through, not read cache)

## Related Patterns

- `d1-batching` - For optimizing writes
- `circuit-breaker` - For external API resilience

## Guardian Rules

- `BUDGET007` - Flags D1 row read explosion
- `TRAP-D1-004` - Row read explosion cost trap

---

*Added in v1.4.0*
