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

## Code Templates

### Entry Point (src/index.ts)

```typescript
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { timing } from 'hono/timing';
import { errorHandler } from './middleware/errors';
import { apiRoutes } from './routes/api';
import { healthRoutes } from './routes/health';
import type { Bindings } from './types';

const app = new Hono<{ Bindings: Bindings }>();

// Middleware
app.use('*', timing());
app.use('*', logger());
app.use('*', cors());
app.onError(errorHandler);

// Routes
app.route('/health', healthRoutes);
app.route('/api', apiRoutes);

// 404 handler
app.notFound((c) => c.json({ error: 'Not found' }, 404));

export default app;
```

### Type Definitions (src/types.ts)

```typescript
export interface Bindings {
  // D1 Database
  DB: D1Database;

  // KV Namespace
  CACHE: KVNamespace;

  // R2 Bucket
  STORAGE: R2Bucket;

  // Queue Producer
  QUEUE: Queue<QueueMessage>;

  // AI
  AI: Ai;

  // Environment variables
  ENVIRONMENT: 'development' | 'staging' | 'production';
}

export interface QueueMessage {
  type: string;
  payload: unknown;
  timestamp: number;
}

// Hono context helper
export type AppContext = Context<{ Bindings: Bindings }>;
```

### Drizzle Schema (src/db/schema.ts)

```typescript
import { sqliteTable, text, integer, real } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

export const users = sqliteTable('users', {
  id: text('id').primaryKey(),
  email: text('email').notNull().unique(),
  name: text('name'),
  createdAt: text('created_at')
    .notNull()
    .default(sql`CURRENT_TIMESTAMP`),
  updatedAt: text('updated_at')
    .notNull()
    .default(sql`CURRENT_TIMESTAMP`),
});

export const projects = sqliteTable('projects', {
  id: text('id').primaryKey(),
  userId: text('user_id')
    .notNull()
    .references(() => users.id),
  title: text('title').notNull(),
  status: text('status', { enum: ['draft', 'active', 'archived'] })
    .notNull()
    .default('draft'),
  metadata: text('metadata', { mode: 'json' }).$type<Record<string, unknown>>(),
  createdAt: text('created_at')
    .notNull()
    .default(sql`CURRENT_TIMESTAMP`),
});

// Type exports for queries
export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;
export type Project = typeof projects.$inferSelect;
export type NewProject = typeof projects.$inferInsert;
```

### Drizzle Config (drizzle.config.ts)

```typescript
import type { Config } from 'drizzle-kit';

export default {
  schema: './src/db/schema.ts',
  out: './migrations',
  dialect: 'sqlite',
} satisfies Config;
```

### Database Queries (src/db/queries.ts)

```typescript
import { drizzle } from 'drizzle-orm/d1';
import { eq, desc, and, sql } from 'drizzle-orm';
import * as schema from './schema';

export function getDb(d1: D1Database) {
  return drizzle(d1, { schema });
}

export async function getUserById(db: D1Database, id: string) {
  const d = getDb(db);
  return d.query.users.findFirst({
    where: eq(schema.users.id, id),
  });
}

export async function createUser(db: D1Database, user: schema.NewUser) {
  const d = getDb(db);
  return d.insert(schema.users).values(user).returning().get();
}

export async function getProjectsByUser(
  db: D1Database,
  userId: string,
  options: { limit?: number; offset?: number } = {}
) {
  const d = getDb(db);
  const { limit = 20, offset = 0 } = options;

  return d.query.projects.findMany({
    where: eq(schema.projects.userId, userId),
    orderBy: desc(schema.projects.createdAt),
    limit,
    offset,
  });
}

// Batch insert pattern (≤1000 rows)
export async function batchInsertProjects(
  db: D1Database,
  projects: schema.NewProject[]
) {
  const d = getDb(db);
  const BATCH_SIZE = 1000;

  for (let i = 0; i < projects.length; i += BATCH_SIZE) {
    const batch = projects.slice(i, i + BATCH_SIZE);
    await d.insert(schema.projects).values(batch);
  }
}
```

### Route Handler (src/routes/api.ts)

```typescript
import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import type { Bindings } from '../types';
import * as queries from '../db/queries';

const api = new Hono<{ Bindings: Bindings }>();

// Validation schemas
const createUserSchema = z.object({
  email: z.string().email(),
  name: z.string().optional(),
});

const paginationSchema = z.object({
  limit: z.coerce.number().min(1).max(100).default(20),
  offset: z.coerce.number().min(0).default(0),
});

// GET /api/users/:id
api.get('/users/:id', async (c) => {
  const id = c.req.param('id');
  const user = await queries.getUserById(c.env.DB, id);

  if (!user) {
    return c.json({ error: 'User not found' }, 404);
  }

  return c.json(user);
});

// POST /api/users
api.post('/users', zValidator('json', createUserSchema), async (c) => {
  const data = c.req.valid('json');
  const id = crypto.randomUUID();

  const user = await queries.createUser(c.env.DB, {
    id,
    ...data,
  });

  return c.json(user, 201);
});

// GET /api/users/:id/projects
api.get(
  '/users/:id/projects',
  zValidator('query', paginationSchema),
  async (c) => {
    const userId = c.req.param('id');
    const { limit, offset } = c.req.valid('query');

    const projects = await queries.getProjectsByUser(c.env.DB, userId, {
      limit,
      offset,
    });

    return c.json({ projects, limit, offset });
  }
);

export { api as apiRoutes };
```

### Error Middleware (src/middleware/errors.ts)

```typescript
import type { ErrorHandler } from 'hono';
import type { Bindings } from '../types';

export const errorHandler: ErrorHandler<{ Bindings: Bindings }> = (
  err,
  c
) => {
  console.error('Unhandled error:', err);

  // Don't leak internal errors in production
  if (c.env.ENVIRONMENT === 'production') {
    return c.json({ error: 'Internal server error' }, 500);
  }

  return c.json(
    {
      error: err.message,
      stack: err.stack,
    },
    500
  );
};
```

### Auth Middleware (src/middleware/auth.ts)

```typescript
import { createMiddleware } from 'hono/factory';
import type { Bindings } from '../types';

interface AuthVariables {
  userId: string;
}

export const requireAuth = createMiddleware<{
  Bindings: Bindings;
  Variables: AuthVariables;
}>(async (c, next) => {
  const authHeader = c.req.header('Authorization');

  if (!authHeader?.startsWith('Bearer ')) {
    return c.json({ error: 'Missing authorization' }, 401);
  }

  const token = authHeader.slice(7);

  // Validate token (replace with your auth logic)
  try {
    const userId = await validateToken(token, c.env);
    c.set('userId', userId);
    await next();
  } catch {
    return c.json({ error: 'Invalid token' }, 401);
  }
});

async function validateToken(token: string, env: Bindings): Promise<string> {
  // Implement your token validation
  // e.g., JWT verification, database lookup, etc.
  throw new Error('Not implemented');
}
```

### Queue Consumer with Idempotency (src/queue.ts)

**IMPORTANT**: Queue consumers MUST implement idempotency to prevent duplicate processing during retries. This is critical for preventing "retry loops" that multiply costs.

```typescript
import type { Bindings, QueueMessage } from './types';

/**
 * Idempotency guard - prevents duplicate message processing
 * Uses KV to track processed message IDs
 */
async function ensureIdempotent(
  messageId: string,
  kv: KVNamespace,
  ttlSeconds = 86400 // 24 hours
): Promise<{ alreadyProcessed: boolean; markProcessed: () => Promise<void> }> {
  const key = `processed:${messageId}`;
  const existing = await kv.get(key);

  if (existing) {
    return { alreadyProcessed: true, markProcessed: async () => {} };
  }

  return {
    alreadyProcessed: false,
    markProcessed: async () => {
      await kv.put(key, Date.now().toString(), { expirationTtl: ttlSeconds });
    },
  };
}

export default {
  async queue(
    batch: MessageBatch<QueueMessage>,
    env: Bindings
  ): Promise<void> {
    // Process in batches for efficiency
    const messages = batch.messages;

    for (const msg of messages) {
      // Check idempotency FIRST to avoid duplicate work
      const { alreadyProcessed, markProcessed } = await ensureIdempotent(
        msg.id,
        env.IDEMPOTENCY_KV
      );

      if (alreadyProcessed) {
        console.log(`Skipping duplicate message: ${msg.id}`);
        msg.ack(); // Don't retry - already processed
        continue;
      }

      try {
        await processMessage(msg.body, env);
        await markProcessed(); // Only mark after successful processing
        msg.ack();
      } catch (error) {
        console.error('Failed to process message:', error);
        // Will retry or go to DLQ based on wrangler config
        // DO NOT mark as processed - allow retry
        msg.retry();
      }
    }
  },
};

async function processMessage(
  message: QueueMessage,
  env: Bindings
): Promise<void> {
  switch (message.type) {
    case 'user.created':
      await handleUserCreated(message.payload, env);
      break;
    case 'project.updated':
      await handleProjectUpdated(message.payload, env);
      break;
    default:
      console.warn('Unknown message type:', message.type);
  }
}

async function handleUserCreated(payload: unknown, env: Bindings) {
  // Process user creation event
}

async function handleProjectUpdated(payload: unknown, env: Bindings) {
  // Process project update event
}
```

### Queue Configuration (wrangler.jsonc)

**CRITICAL**: Always configure Dead Letter Queues (DLQ) to break retry loops.

```jsonc
{
  "queues": {
    "producers": [
      { "binding": "EVENTS_QUEUE", "queue": "events" }
    ],
    "consumers": [
      {
        "queue": "events",
        "max_batch_size": 100,
        "max_retries": 1,           // LOW retries - each retry = cost
        "dead_letter_queue": "events-dlq",  // REQUIRED: breaks retry loops
        "max_concurrency": 10       // Prevents overload
      }
    ]
  },
  // KV for idempotency tracking
  "kv_namespaces": [
    { "binding": "IDEMPOTENCY_KV", "id": "your-kv-namespace-id" }
  ]
}
```

### DLQ Consumer (src/dlq-handler.ts)

Create a separate handler to inspect failed messages:

```typescript
import type { Bindings, QueueMessage } from './types';

export default {
  async queue(
    batch: MessageBatch<QueueMessage>,
    env: Bindings
  ): Promise<void> {
    for (const msg of batch.messages) {
      // Log failed message for debugging
      console.error('DLQ message:', {
        id: msg.id,
        body: msg.body,
        timestamp: msg.timestamp,
        attempts: msg.attempts,
      });

      // Optionally store in R2 for later analysis
      await env.DLQ_BUCKET.put(
        `failed/${msg.id}.json`,
        JSON.stringify({
          message: msg.body,
          timestamp: msg.timestamp,
          attempts: msg.attempts,
          receivedAt: new Date().toISOString(),
        })
      );

      msg.ack(); // Always ack DLQ messages
    }
  },
}
```

### Health Check (src/routes/health.ts)

```typescript
import { Hono } from 'hono';
import type { Bindings } from '../types';

const health = new Hono<{ Bindings: Bindings }>();

health.get('/', async (c) => {
  const checks: Record<string, 'ok' | 'error'> = {};

  // Check D1
  try {
    await c.env.DB.prepare('SELECT 1').first();
    checks.d1 = 'ok';
  } catch {
    checks.d1 = 'error';
  }

  // Check KV
  try {
    await c.env.CACHE.get('health-check');
    checks.kv = 'ok';
  } catch {
    checks.kv = 'error';
  }

  const healthy = Object.values(checks).every((v) => v === 'ok');

  return c.json(
    {
      status: healthy ? 'healthy' : 'degraded',
      checks,
      timestamp: new Date().toISOString(),
    },
    healthy ? 200 : 503
  );
});

export { health as healthRoutes };
```

### Migration Template (migrations/0001_initial.sql)

```sql
-- Migration: Initial schema
-- Created: YYYY-MM-DD

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'active', 'archived')),
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Always create indexes for WHERE and ORDER BY columns
CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_user_status ON projects(user_id, status);
CREATE INDEX idx_projects_created_at ON projects(created_at DESC);
```

### Package.json Template

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

### TSConfig Template

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

## Best Practices

### D1 Query Patterns

```typescript
// GOOD: Batch inserts
const BATCH_SIZE = 1000;
for (let i = 0; i < items.length; i += BATCH_SIZE) {
  await db.insert(table).values(items.slice(i, i + BATCH_SIZE));
}

// BAD: Per-row inserts
for (const item of items) {
  await db.insert(table).values(item); // N statements = N × cost
}
```

### KV Caching Pattern

```typescript
async function getCached<T>(
  kv: KVNamespace,
  key: string,
  fetcher: () => Promise<T>,
  ttl: number = 3600
): Promise<T> {
  const cached = await kv.get(key, 'json');
  if (cached) return cached as T;

  const fresh = await fetcher();
  await kv.put(key, JSON.stringify(fresh), { expirationTtl: ttl });
  return fresh;
}
```

### Queue Publishing Pattern

```typescript
// Publish to queue with type safety
async function enqueue<T extends QueueMessage['type']>(
  queue: Queue<QueueMessage>,
  type: T,
  payload: Extract<QueueMessage, { type: T }>['payload']
) {
  await queue.send({
    type,
    payload,
    timestamp: Date.now(),
  });
}
```

### Error Handling Pattern

```typescript
// Custom error classes
class NotFoundError extends Error {
  status = 404;
}

class ValidationError extends Error {
  status = 400;
}

// Error handler catches and formats
const errorHandler: ErrorHandler = (err, c) => {
  const status = 'status' in err ? (err.status as number) : 500;
  return c.json({ error: err.message }, status);
};
```

## Service Bindings RPC

For Worker-to-Worker calls, use Service Bindings instead of HTTP:

```typescript
// In wrangler.jsonc
{
  "services": [
    { "binding": "AUTH_SERVICE", "service": "auth-worker" }
  ]
}

// In code
interface AuthService {
  validateToken(token: string): Promise<{ userId: string }>;
}

// Call via RPC (no HTTP overhead)
const result = await c.env.AUTH_SERVICE.validateToken(token);
```

## R2 Asset Serving with CDN Caching (NEW v1.4.0)

For public R2 buckets serving static assets, ALWAYS implement edge caching to avoid Class B operation costs ($0.36/M).

### Worker with Cache API

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

### R2 Upload with Proper Headers

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

### Wrangler Configuration for Assets

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

### R2 Infrequent Access Warning

**CRITICAL**: Never use R2 Infrequent Access for assets that will be read.

```typescript
// ❌ DANGEROUS: IA bucket with reads = $9.00 minimum charge per operation
await iaBucket.get('user-avatar.png');

// ✅ SAFE: Standard storage for any readable content
await standardBucket.get('user-avatar.png');

// ✅ SAFE: IA only for true cold storage (backups never read)
await iaBucket.put('backup-2025-01-17.sql', backupData);
```

## Queue Safety Patterns (Loop Protection)

### Idempotency Key Selection

Choose idempotency keys carefully to prevent both duplicates AND false positives:

```typescript
// Option 1: Message ID (provided by Cloudflare)
const idempotencyKey = msg.id;

// Option 2: Content-based hash (for deduplication across producers)
const contentHash = await crypto.subtle.digest(
  'SHA-256',
  new TextEncoder().encode(JSON.stringify(msg.body))
);
const idempotencyKey = btoa(String.fromCharCode(...new Uint8Array(contentHash)));

// Option 3: Business key (e.g., order ID)
const idempotencyKey = `order:${msg.body.orderId}`;
```

### Retry Budget Pattern

Limit total processing attempts across the entire message lifecycle:

```typescript
interface MessageWithRetryBudget {
  data: unknown;
  retryBudget: number;  // Decrements on each retry
  firstAttempt: number; // Timestamp
}

async function processWithBudget(msg: Message<MessageWithRetryBudget>, env: Bindings) {
  const { data, retryBudget, firstAttempt } = msg.body;

  // Hard timeout - don't process ancient messages
  const ageMs = Date.now() - firstAttempt;
  if (ageMs > 3600000) { // 1 hour
    console.error('Message too old, sending to DLQ');
    msg.ack(); // Let it go to DLQ naturally
    return;
  }

  if (retryBudget <= 0) {
    console.error('Retry budget exhausted');
    msg.ack();
    return;
  }

  try {
    await processData(data, env);
    msg.ack();
  } catch (error) {
    // Decrement budget for next retry
    // Note: This requires republishing with updated budget
    msg.retry();
  }
}
```

### Circuit Breaker for Queue Consumers

Prevent cascading failures when downstream services are unhealthy:

```typescript
// src/utils/circuit-breaker.ts
class CircuitBreaker {
  private failures = 0;
  private lastFailure = 0;
  private state: 'closed' | 'open' | 'half-open' = 'closed';

  constructor(
    private threshold = 5,
    private resetTimeMs = 30000
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailure > this.resetTimeMs) {
        this.state = 'half-open';
      } else {
        throw new Error('Circuit breaker is open');
      }
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() {
    this.failures = 0;
    this.state = 'closed';
  }

  private onFailure() {
    this.failures++;
    this.lastFailure = Date.now();
    if (this.failures >= this.threshold) {
      this.state = 'open';
    }
  }

  isOpen(): boolean {
    return this.state === 'open';
  }
}

// Usage in queue consumer
const dbCircuit = new CircuitBreaker(5, 30000);

async function processMessage(msg: QueueMessage, env: Bindings) {
  if (dbCircuit.isOpen()) {
    // Don't even try - circuit is open
    // This prevents burning retries on a known-down service
    throw new Error('Database circuit breaker open');
  }

  await dbCircuit.execute(async () => {
    await saveToDatabase(msg, env);
  });
}
```

## Observability Export (NEW v1.4.0)

Native Cloudflare log retention is short (3-7 days). For production-grade applications, export OpenTelemetry (OTel) data to third-party tools for long-term debugging and analysis.

### Wrangler Observability Configuration

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

### Export to Axiom (Recommended Free Tier)

Axiom offers 500GB/month free ingest - excellent for solo developers.

**Step 1: Wrangler Configuration**

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

**Step 2: Set Up Axiom Logpush (Dashboard)**

1. Go to Cloudflare Dashboard → Analytics & Logs → Logpush
2. Create a job for Workers trace events
3. Select Axiom as destination
4. Enter your Axiom API token and dataset name

**Step 3: Structured Logging in Code**

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

  // console.log outputs to Workers logs → Axiom via Logpush
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

### Export to Better Stack (Logtail)

Better Stack offers real-time log viewing with free tier.

**Step 1: Install Logtail SDK**

```bash
npm install @logtail/js
```

**Step 2: Configure Logger**

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

**Wrangler Configuration:**

```jsonc
{
  "name": "my-worker",
  "vars": {
    "LOGTAIL_TOKEN": ""  // Set via: wrangler secret put LOGTAIL_TOKEN
  }
}
```

### OpenTelemetry Native Export (Advanced)

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

### Observability Best Practices

| Practice | Recommendation |
|----------|----------------|
| **Sampling** | Use 10-20% sampling for high-volume endpoints |
| **Structured Logs** | Always use JSON format with consistent fields |
| **Request IDs** | Use `cf-ray` header or generate UUID |
| **Error Context** | Include stack traces only in development |
| **PII Redaction** | Never log passwords, tokens, or user PII |
| **Retention** | Export to Axiom/Better Stack for >7 day retention |

### Wrangler Config Template (Full Observability)

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
