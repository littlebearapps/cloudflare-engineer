---
name: implement
description: Scaffold Cloudflare Workers with Hono, Drizzle ORM, and TypeScript best practices. Use this skill when implementing new Workers, adding endpoints, or setting up database schemas.
---

# Cloudflare Implementation Skill

Scaffold production-ready Cloudflare Workers following modern patterns with Hono, Drizzle ORM, and TypeScript.

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Router | Hono v4+ | Lightweight, fast, TypeScript-first |
| ORM | Drizzle | Type-safe D1 queries, migrations |
| Validation | Zod | Request/response validation |
| Runtime | Workers | Edge compute |

## Project Structure

```
worker/
├── src/
│   ├── index.ts          # Hono app entry
│   ├── routes/           # Route handlers
│   │   ├── api.ts
│   │   └── health.ts
│   ├── middleware/       # Hono middleware
│   │   ├── auth.ts
│   │   └── errors.ts
│   ├── services/         # Business logic
│   │   └── users.ts
│   ├── db/               # Drizzle schema + queries
│   │   ├── schema.ts
│   │   └── queries.ts
│   └── types.ts          # Shared types
├── migrations/           # D1 migrations
│   └── 0001_initial.sql
├── wrangler.jsonc
├── drizzle.config.ts
├── package.json
└── tsconfig.json
```

## Quick Start Templates

### Package.json

```json
{
  "name": "worker-name",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "db:generate": "drizzle-kit generate",
    "db:migrate": "wrangler d1 migrations apply DB",
    "db:migrate:local": "wrangler d1 migrations apply DB --local",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "hono": "^4.0.0",
    "@hono/zod-validator": "^0.2.0",
    "drizzle-orm": "^0.29.0",
    "zod": "^3.22.0"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20240000.0",
    "drizzle-kit": "^0.20.0",
    "typescript": "^5.3.0",
    "wrangler": "^3.0.0"
  }
}
```

### TSConfig

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022"],
    "types": ["@cloudflare/workers-types"],
    "strict": true,
    "skipLibCheck": true,
    "noEmit": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "jsxImportSource": "hono/jsx"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules"]
}
```

## Best Practices Summary

### D1 Queries

```typescript
// GOOD: Batch inserts
const BATCH_SIZE = 1000;
for (let i = 0; i < items.length; i += BATCH_SIZE) {
  await db.insert(table).values(items.slice(i, i + BATCH_SIZE));
}

// BAD: Per-row inserts (N statements = N x cost)
for (const item of items) {
  await db.insert(table).values(item);
}
```

### Queue Safety

**CRITICAL**: Always configure DLQs and implement idempotency:

```jsonc
{
  "queues": {
    "consumers": [{
      "queue": "events",
      "max_retries": 1,           // LOW retries
      "dead_letter_queue": "events-dlq"  // REQUIRED
    }]
  }
}
```

### R2 Asset Caching

Always implement edge caching to avoid $0.36/M Class B costs:

```typescript
// Check cache first
const cached = await caches.default.match(cacheKey);
if (cached) return cached;

// Fetch from R2 and cache
const object = await bucket.get(key);
const response = new Response(object.body, {
  headers: { 'Cache-Control': 'public, max-age=31536000' }
});
ctx.waitUntil(caches.default.put(cacheKey, response.clone()));
```

## Commands

```bash
# Generate migration from schema changes
npm run db:generate

# Apply migrations locally
npm run db:migrate:local

# Apply migrations to remote D1
npm run db:migrate

# Development
npm run dev

# Deploy
npm run deploy
```

## Reference Files

For detailed implementation patterns, consult:

- **`references/hono-patterns.md`** - Hono entry point, routes, middleware, error handling, auth
- **`references/drizzle-patterns.md`** - Schema definitions, queries, migrations, batch patterns
- **`references/queue-safety.md`** - Idempotency, DLQ handlers, circuit breaker, retry budget
- **`references/r2-caching.md`** - CDN caching, upload headers, IA storage warnings
- **`references/observability.md`** - Axiom, Better Stack, OTel export patterns

## Related Skills

- **architect**: Service selection, wrangler.toml generation
- **loop-breaker**: Recursion guards for Worker-to-Worker calls
- **query-optimizer**: D1 query optimization, N+1 detection
- **patterns**: Architecture patterns (service-bindings, circuit-breaker)
