---
name: patterns
description: Cloudflare architecture patterns for common problems. Reference when decomposing monolithic Workers, optimizing D1 writes, or adding external API resilience.
triggers:
  - monolithic Worker
  - subrequest limits
  - D1 write costs
  - batch inserts
  - external API failures
  - circuit breaker
  - resilience patterns
  - decomposing Workers
---

# Cloudflare Architecture Patterns

Proven patterns for solving common Cloudflare architecture challenges. Each pattern includes symptoms (when to apply), detection methods, implementation steps, and trade-offs.

## Pattern Catalog

| Pattern | Problem | Solution | Effort |
|---------|---------|----------|--------|
| [service-bindings](#service-bindings) | Monolithic Worker hitting subrequest limits | Decompose with RPC | Medium |
| [d1-batching](#d1-batching) | High D1 write costs from per-row inserts | Batch writes | Low |
| [circuit-breaker](#circuit-breaker) | External API failures cascading | Fail-fast with fallback | Medium |
| [kv-cache-first](#kv-cache-first) | D1 row read explosion on high-traffic endpoints | KV cache before D1 | Low |
| [r2-cdn-cache](#r2-cdn-cache) | R2 Class B operation costs on public buckets | Edge cache via Cache Rules | Low |

---

## When to Apply Patterns

### Service Bindings Pattern

**Trigger Conditions**:
- Subrequest count approaching 1,000/request limit
- Single Worker handling unrelated domains (auth, data, notifications)
- HTTP `fetch()` between internal Workers
- Worker file > 1MB after bundling
- Multiple teams need to deploy independently

**Detection** (static):
```javascript
// Anti-pattern: HTTP fetch to internal service
const response = await fetch(`${AUTH_SERVICE_URL}/validate`, {
  headers: { Authorization: token }
});
```

**Detection** (live):
- Check observability for high subrequest counts
- Look for latency patterns indicating network hops

### D1 Batching Pattern

**Trigger Conditions**:
- D1 writes represent > 80% of costs
- Per-row INSERT in loops detected in code
- Cron jobs with unbatched writes
- Webhook handlers inserting one record at a time

**Detection** (static):
```javascript
// Anti-pattern: Per-row inserts in loop
for (const item of items) {
  await db.run('INSERT INTO items (name) VALUES (?)', [item.name]);
}
```

**Detection** (live):
- D1 write count >> expected record count
- High write costs relative to data volume

### Circuit Breaker Pattern

**Trigger Conditions**:
- External API calls without timeout
- No fallback for third-party failures
- Error rate spikes correlating with upstream issues
- User-facing errors caused by backend service outages

**Detection** (static):
```javascript
// Anti-pattern: Unbounded external fetch
const data = await fetch('https://external-api.com/data');
// No timeout, no fallback, no retry logic
```

**Detection** (live):
- Error rate spikes in observability
- Latency P99 >> P50 (indicating timeouts)
- Correlation between external service status and Worker errors

### KV-Cache-First Pattern (NEW v1.4.0)

**Trigger Conditions**:
- D1 query returns list/collection data
- Endpoint receives >100 requests/minute
- Query uses unindexed columns in WHERE clause
- Same data requested by multiple users
- D1 row reads approaching free tier limits

**Detection** (static):
```javascript
// Anti-pattern: Direct D1 read on high-traffic endpoint
app.get('/products', async (c) => {
  return c.json(await db.prepare('SELECT * FROM products').all());
});
// 1K req/hour × 10K rows = 10M rows/hour = blowing free tier
```

**Detection** (live):
- D1 read count >> expected request count
- High read latency on list endpoints
- Approaching 5B rows/month free tier limit

### R2 CDN Cache Pattern (NEW v1.4.0)

**Trigger Conditions**:
- Public R2 bucket serving static assets
- High Class B operation counts
- Same objects requested repeatedly
- No Cache-Control headers configured

**Detection** (static):
```javascript
// Anti-pattern: Public R2 without caching
app.get('/assets/:key', async (c) => {
  const obj = await c.env.BUCKET.get(c.req.param('key'));
  return new Response(obj.body);
  // Every request = Class B op ($0.36/M)
});
```

**Detection** (live):
- R2 Class B operations >> unique object count
- Same keys appearing repeatedly in logs

---

## Pattern Details

Detailed implementation guides are in separate files:

- @service-bindings.md - Decompose monolithic Workers into service-bound microservices
- @d1-batching.md - Optimize D1 write costs with batch operations
- @circuit-breaker.md - Add resilience for external API dependencies
- @kv-cache-first.md - Cache D1 reads with KV for high-traffic endpoints (NEW v1.4.0)
- @r2-cdn-cache.md - Cache R2 objects at the edge for public buckets (NEW v1.4.0)

---

## Pattern Selection Guide

```
Is your Worker > 500 lines or hitting subrequest limits?
├─ Yes → Consider SERVICE-BINDINGS pattern
└─ No
   │
   Are D1 READS your primary cost driver?
   ├─ Yes → Apply KV-CACHE-FIRST pattern
   │        (For high-traffic endpoints with relatively static data)
   └─ No
      │
      Are D1 WRITES your primary cost driver (>50%)?
      ├─ Yes → Apply D1-BATCHING pattern
      └─ No
         │
         Do you have a public R2 bucket with many reads?
         ├─ Yes → Apply R2-CDN-CACHE pattern
         └─ No
            │
            Do you call external APIs?
            ├─ Yes → Apply CIRCUIT-BREAKER pattern
            └─ No → Review other optimization opportunities
```

---

## Combining Patterns

Patterns can be combined. Common combinations:

1. **Service Bindings + D1 Batching**: Decompose monolith AND optimize data layer
2. **Circuit Breaker + Service Bindings**: Each microservice has its own resilience
3. **All Three**: Large applications benefit from all patterns

**Implementation Order** (recommended):
1. Circuit Breaker first (lowest risk, immediate resilience benefit)
2. D1 Batching second (cost savings without architecture change)
3. Service Bindings last (largest change, needs careful planning)

---

## Pattern Anti-Patterns

Things to avoid when implementing patterns:

| Pattern | Anti-Pattern | Why It's Bad |
|---------|--------------|--------------|
| Service Bindings | Too many small Workers | Complexity overhead exceeds benefit |
| Service Bindings | Circular dependencies | Deadlock risk, hard to reason about |
| D1 Batching | Batches too large | Memory pressure, timeout risk |
| D1 Batching | No error handling per batch | One bad record fails entire batch |
| Circuit Breaker | Circuit never closes | Permanent degraded mode |
| Circuit Breaker | No fallback defined | Fail-fast with no alternative |

---

## Future Patterns (Roadmap)

Patterns to be added:

- **read-replication**: Durable Objects for regional caching
- **event-sourcing**: Queues + D1 for audit trails
- **rate-limiting**: KV-based distributed rate limiting
- **edge-caching**: Cache API patterns for dynamic content
