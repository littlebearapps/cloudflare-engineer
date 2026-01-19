# Edge-Native Constraints

**IMPORTANT**: Cloudflare Workers use a V8 isolate runtime, NOT Node.js. Always validate proposed code against these constraints.

## Node.js API Compatibility

Workers supports many Node.js APIs via `node:` prefixed imports when `nodejs_compat` or `nodejs_compat_v2` flag is enabled.

| Node.js Module | Workers Support | Required Flag | Notes |
|----------------|-----------------|---------------|-------|
| `node:assert` | Partial | `nodejs_compat` | Basic assertions |
| `node:async_hooks` | Yes | `nodejs_compat` | AsyncLocalStorage supported |
| `node:buffer` | Yes | `nodejs_compat` | Full Buffer API |
| `node:crypto` | Yes | `nodejs_compat` | Prefer Web Crypto when possible |
| `node:events` | Yes | `nodejs_compat` | EventEmitter |
| `node:path` | Yes | `nodejs_compat` | Path manipulation |
| `node:stream` | Partial | `nodejs_compat` | Web Streams preferred |
| `node:url` | Yes | `nodejs_compat` | URL parsing |
| `node:util` | Partial | `nodejs_compat` | Common utilities |
| `node:zlib` | Yes | `nodejs_compat` | Compression |
| `node:fs` | NO | - | **Use R2 instead** |
| `node:net` | NO | - | **Use TCP sockets (beta)** |
| `node:child_process` | NO | - | **Not available** |
| `node:cluster` | NO | - | **Edge inherently distributed** |
| `node:http` | NO | - | **Use fetch()** |
| `node:https` | NO | - | **Use fetch()** |

## Common Library Compatibility

| Library | Works? | Alternative | Notes |
|---------|--------|-------------|-------|
| `express` | NO | **Hono, itty-router** | Hono is recommended |
| `axios` | Partial | **fetch()** | Native fetch preferred |
| `lodash` | Yes | - | Works, but increases bundle |
| `moment` | Yes | **dayjs, date-fns** | Moment is heavy |
| `uuid` | Yes | **crypto.randomUUID()** | Native is better |
| `bcrypt` | NO | **bcryptjs** | Pure JS version works |
| `sharp` | NO | **Cloudflare Images** | Use Images API |
| `puppeteer` | NO | **Browser Rendering API** | Cloudflare has native |
| `pg` | NO | **Hyperdrive** | Use Hyperdrive for Postgres |
| `mysql2` | NO | **Hyperdrive** | Use Hyperdrive for MySQL |
| `mongodb` | Partial | - | Use fetch to Atlas API |
| `redis` | NO | **KV, Durable Objects** | Use native services |
| `aws-sdk` | Partial | **R2 S3 API** | R2 is S3-compatible |
| `@prisma/client` | Yes | - | D1 adapter available |
| `drizzle-orm` | Yes | - | Recommended for D1 |

## Compatibility Flag Configuration

When using Node.js APIs, add to wrangler config:

```jsonc
{
  "compatibility_flags": ["nodejs_compat_v2"],  // Recommended: latest Node.js compat
  // OR for legacy:
  // "compatibility_flags": ["nodejs_compat"]
}
```

## Edge-Native Validation Workflow

When reviewing proposed architecture or dependencies:

1. Scan package.json for known incompatible libraries
2. Flag any `require('fs')` or `require('net')` patterns
3. Check for `node:` imports without compat flags
4. Suggest Cloudflare-native alternatives:
   - fs → R2
   - net/http → fetch()
   - express → Hono
   - redis → KV/DO
   - postgres → Hyperdrive
   - image processing → Images API
5. Verify wrangler.toml has appropriate compat flags

## Runtime Limits

| Limit | Free | Standard | Unbound |
|-------|------|----------|---------|
| Request timeout | 10ms CPU | 30s wall | 30s wall |
| Memory | 128MB | 128MB | 128MB |
| Bundle size | 1MB | 10MB | 10MB |
| Subrequests | 50 | 1000 | 1000 |
| Environment vars | 64 | 128 | 128 |
| Cron triggers | 3 | 5 | 5 |

## Example: Edge-Native Migration

**Before (Node.js pattern):**
```javascript
const express = require('express');
const fs = require('fs');
const Redis = require('ioredis');

const app = express();
app.get('/file/:id', async (req, res) => {
  const content = fs.readFileSync(`./uploads/${req.params.id}`);
  await redis.set(`cache:${req.params.id}`, content);
  res.send(content);
});
```

**After (Edge-Native):**
```typescript
import { Hono } from 'hono';

const app = new Hono<{ Bindings: Env }>();

app.get('/file/:id', async (c) => {
  const obj = await c.env.R2_BUCKET.get(c.req.param('id'));
  if (!obj) return c.notFound();

  // Cache in KV for fast reads
  await c.env.KV_CACHE.put(`file:${c.req.param('id')}`, await obj.text(), { expirationTtl: 3600 });

  return new Response(obj.body);
});

export default app;
```
