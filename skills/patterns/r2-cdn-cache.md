---
name: r2-cdn-cache
description: R2 Class B cost protection pattern using Cloudflare Cache Rules to serve static assets from edge CDN.
---

# R2 CDN Cache Pattern

## Problem

R2 Class B operations (reads/viewing files) cost $0.36/million. For public buckets serving static assets, every request triggers a Class B operation. High-traffic sites can accumulate significant costs even with the 10M free tier.

More dangerously, **R2 Infrequent Access (IA)** storage has a billing trap: Cloudflare rounds up usage to the next billing unit. A single operation on an IA bucket can trigger a minimum charge of **$9.00** because the minimum billable unit represents ~25 million operations.

## Solution

Use Cloudflare's **Cache Rules** to cache R2 objects at the edge. Once cached, subsequent requests are served from the CDN (free) and don't trigger R2 Class B operations.

For public buckets with static assets:
1. Configure custom domain for R2 bucket
2. Add Cache Rules to cache responses
3. Set appropriate Cache-Control headers

## When to Apply

**Trigger Conditions**:
- Public R2 bucket with custom domain
- Serving static assets (images, CSS, JS, videos)
- High read volume (>1M reads/month)
- Same objects requested repeatedly

**Warning Signs**:
- R2 Class B operations >> unique object count
- Same keys appearing in access logs repeatedly
- Approaching or exceeding 10M free tier

## Implementation

### Step 1: Set Up Custom Domain for R2

```bash
# Create public bucket with custom domain
wrangler r2 bucket create my-assets --location wnam

# Configure custom domain in dashboard or via API
# assets.example.com → my-assets bucket
```

### Step 2: Add Cache-Control Headers

```typescript
// When uploading objects, set cache headers
await bucket.put('image.png', imageData, {
  httpMetadata: {
    contentType: 'image/png',
    cacheControl: 'public, max-age=31536000, immutable'  // 1 year for static assets
  }
});
```

### Step 3: Configure Cache Rules

In Cloudflare Dashboard → Rules → Cache Rules:

```yaml
# Rule 1: Cache all R2 assets
Match:
  Hostname: assets.example.com

Then:
  Cache eligibility: Eligible for cache
  Edge TTL:
    Override origin: 1 year
  Browser TTL:
    Override origin: 1 year
  Cache Key:
    Query string: Ignore (or Include specific params)
```

### Step 4: Worker with Cache API (Alternative)

For more control, use the Cache API in a Worker:

```typescript
// src/index.ts
import { Hono } from 'hono';

const app = new Hono<{ Bindings: Env }>();

app.get('/assets/*', async (c) => {
  const url = new URL(c.req.url);
  const key = url.pathname.replace('/assets/', '');

  // Check cache first
  const cache = caches.default;
  const cacheKey = new Request(url.toString(), c.req.raw);

  let response = await cache.match(cacheKey);
  if (response) {
    // Cache hit - free!
    return response;
  }

  // Cache miss - fetch from R2 (Class B op)
  const object = await c.env.ASSETS.get(key);
  if (!object) {
    return c.notFound();
  }

  // Build response with cache headers
  response = new Response(object.body, {
    headers: {
      'Content-Type': object.httpMetadata?.contentType || 'application/octet-stream',
      'Cache-Control': 'public, max-age=31536000, immutable',
      'ETag': object.etag,
    },
  });

  // Store in cache for next request
  c.executionCtx.waitUntil(cache.put(cacheKey, response.clone()));

  return response;
});

export default app;
```

### Wrangler Configuration

```jsonc
{
  "name": "assets-worker",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",
  "r2_buckets": [
    { "binding": "ASSETS", "bucket_name": "my-assets" }
  ],
  "routes": [
    { "pattern": "assets.example.com/*", "zone_name": "example.com" }
  ]
}
```

## R2 Infrequent Access Warning

**CRITICAL**: If you enable R2 Infrequent Access (IA) storage class:

| Action | Cost | Minimum |
|--------|------|---------|
| IA Retrieval | $0.36/GB | - |
| IA Data Retrieval Ops | Different pricing | **$9.00 minimum** |

The minimum charge exists because Cloudflare bills in units, and a single operation rounds up to the minimum billable unit.

**Recommendation**:
- NEVER use IA for buckets with any read operations
- IA is ONLY for true cold storage (backups, archives)
- If IA is needed, ensure objects are large (>100MB) to amortize retrieval costs

```typescript
// WARNING: This can trigger $9 minimum charge
const object = await iaStorageBucket.get('small-file.txt');
// Even for a 1KB file!

// SAFE: Only use IA for large cold storage
const backup = await iaStorageBucket.get('database-backup-500GB.sql');
// 500GB retrieval cost is reasonable
```

## Cost Comparison

| Scenario | Without Cache | With CDN Cache | Savings |
|----------|---------------|----------------|---------|
| 1M reads/month | $0.36 | ~$0.01 (origin) | 97% |
| 10M reads/month | $3.60 | ~$0.05 (origin) | 99% |
| 100M reads/month | $36.00 | ~$0.50 (origin) | 99% |

*Origin requests are the cache misses that hit R2; typically <5% with good caching*

## Trade-offs

| Benefit | Cost |
|---------|------|
| Dramatically reduced Class B ops | Setup complexity |
| Lower latency (edge cache) | Cache invalidation needed for updates |
| Works at massive scale | Custom domain required |

## Cache Invalidation

### For Updated Objects

```typescript
// Option 1: Versioned URLs (recommended)
const url = `/assets/image-v${version}.png`;

// Option 2: Purge cache via API
await fetch('https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${API_TOKEN}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    files: ['https://assets.example.com/image.png']
  })
});
```

## Related Patterns

- `kv-cache-first` - For caching D1 reads

## Guardian Rules

- `BUDGET008` - Flags R2 Class B without caching
- `BUDGET009` - Warns about R2 IA minimum charges
- `TRAP-R2-003` - Class B operation accumulation
- `TRAP-R2-004` - IA minimum billing trap

---

*Added in v1.4.0*
