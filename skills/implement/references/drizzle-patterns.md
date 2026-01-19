# Drizzle ORM Patterns for D1

## Drizzle Schema (src/db/schema.ts)

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

## Drizzle Config (drizzle.config.ts)

```typescript
import type { Config } from 'drizzle-kit';

export default {
  schema: './src/db/schema.ts',
  out: './migrations',
  dialect: 'sqlite',
} satisfies Config;
```

## Database Queries (src/db/queries.ts)

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

// Batch insert pattern (<=1000 rows)
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

## Migration Template (migrations/0001_initial.sql)

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

## D1 Query Best Practices

### Batch Inserts

```typescript
// GOOD: Batch inserts
const BATCH_SIZE = 1000;
for (let i = 0; i < items.length; i += BATCH_SIZE) {
  await db.insert(table).values(items.slice(i, i + BATCH_SIZE));
}

// BAD: Per-row inserts
for (const item of items) {
  await db.insert(table).values(item); // N statements = N x cost
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

## Migration Commands

```bash
# Generate migration from schema changes
npm run db:generate

# Apply migrations locally
npm run db:migrate:local

# Apply migrations to remote D1
npm run db:migrate
```
