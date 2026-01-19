# R2 Asset Serving with CDN Caching

For public R2 buckets serving static assets, ALWAYS implement edge caching to avoid Class B operation costs ($0.36/M).

## Worker with Cache API

```typescript
// src/routes/assets.ts
import { Hono } from 'hono';
import type { Bindings } from '../types';

const assets = new Hono<{ Bindings: Bindings }>();

// Cache TTLs by content type
const CACHE_TTLS: Record<string, number> = {
  'image/': 31536000,    // 1 year for images
  'font/': 31536000,     // 1 year for fonts
  'text/css': 2592000,   // 30 days for CSS
  'application/javascript': 2592000, // 30 days for JS
  'default': 86400,      // 1 day default
};

function getCacheTTL(contentType: string): number {
  for (const [prefix, ttl] of Object.entries(CACHE_TTLS)) {
    if (contentType.startsWith(prefix)) return ttl;
  }
  return CACHE_TTLS.default;
}

assets.get('/:key{.+}', async (c) => {
  const key = c.req.param('key');
  const url = new URL(c.req.url);

  // Step 1: Check edge cache first (FREE)
  const cache = caches.default;
  const cacheKey = new Request(url.toString());

  let response = await cache.match(cacheKey);
  if (response) {
    // Cache HIT - no R2 cost
    return new Response(response.body, {
      headers: {
        ...Object.fromEntries(response.headers),
        'X-Cache': 'HIT',
      },
    });
  }

  // Step 2: Cache MISS - fetch from R2 (Class B operation)
  const object = await c.env.ASSETS.get(key);
  if (!object) {
    return c.notFound();
  }

  const contentType = object.httpMetadata?.contentType || 'application/octet-stream';
  const ttl = getCacheTTL(contentType);

  // Step 3: Build response with cache headers
  response = new Response(object.body, {
    headers: {
      'Content-Type': contentType,
      'Cache-Control': `public, max-age=${ttl}, immutable`,
      'ETag': object.etag,
      'X-Cache': 'MISS',
    },
  });

  // Step 4: Store in cache for next request
  c.executionCtx.waitUntil(cache.put(cacheKey, response.clone()));

  return response;
});

export { assets as assetsRoutes };
```

## R2 Upload with Proper Headers

```typescript
// When uploading, set cache-friendly headers
async function uploadAsset(
  bucket: R2Bucket,
  key: string,
  data: ArrayBuffer | ReadableStream,
  contentType: string
) {
  await bucket.put(key, data, {
    httpMetadata: {
      contentType,
      // These headers are returned when object is fetched
      cacheControl: 'public, max-age=31536000, immutable',
    },
    // Optional: Use standard storage (NOT Infrequent Access for public assets)
    // storageClass: 'Standard',  // Default, but explicit for clarity
  });
}
```

## Wrangler Configuration for Assets

```jsonc
{
  "name": "assets-worker",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",
  "r2_buckets": [
    {
      "binding": "ASSETS",
      "bucket_name": "my-assets"
      // NOTE: Do NOT use preview_bucket_name for production assets
    }
  ],
  // Use routes to serve on custom domain
  "routes": [
    { "pattern": "assets.example.com/*", "zone_name": "example.com" }
  ],
  // Optional: Add transform rules in Cloudflare dashboard for
  // automatic Cache Rules instead of Worker-based caching
}
```

## R2 Infrequent Access Warning

**CRITICAL**: Never use R2 Infrequent Access for assets that will be read.

```typescript
// DANGEROUS: IA bucket with reads = $9.00 minimum charge per operation
await iaBucket.get('user-avatar.png');

// SAFE: Standard storage for any readable content
await standardBucket.get('user-avatar.png');

// SAFE: IA only for true cold storage (backups never read)
await iaBucket.put('backup-2025-01-17.sql', backupData);
```

## Cost Comparison

| Pattern | R2 Reads/Month | Cost |
|---------|----------------|------|
| No caching | 1,000,000 | $360 |
| Edge caching (90% hit) | 100,000 | $36 |
| Edge caching (99% hit) | 10,000 | $3.60 |

**Always implement edge caching for public assets.**
