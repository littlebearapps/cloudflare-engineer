# Hono v4+ Patterns for Cloudflare Workers

## Entry Point (src/index.ts)

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

## Type Definitions (src/types.ts)

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

## Route Handler (src/routes/api.ts)

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

## Error Middleware (src/middleware/errors.ts)

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

## Auth Middleware (src/middleware/auth.ts)

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

## Health Check (src/routes/health.ts)

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

## Error Handling Pattern

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
