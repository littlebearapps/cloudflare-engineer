# Architecture Templates

Pre-built architecture patterns for common Cloudflare use cases.

## Template 1: API Gateway

**Use Case**: REST/GraphQL API with database backend

```mermaid
graph LR
    subgraph "Edge"
        W[Worker<br/>Hono Router]
    end
    subgraph "Storage"
        D1[(D1<br/>Primary DB)]
        KV[(KV<br/>Cache)]
    end
    subgraph "Auth"
        Access[CF Access]
    end

    Client --> Access --> W
    W --> KV
    KV -.->|miss| D1
    W --> D1
```

**Wrangler Config**:
```jsonc
{
  "name": "api-gateway",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",
  "placement": { "mode": "smart" },
  "observability": { "logs": { "enabled": true } },
  "d1_databases": [
    { "binding": "DB", "database_name": "api-db", "database_id": "..." }
  ],
  "kv_namespaces": [
    { "binding": "CACHE", "id": "..." }
  ],
  "routes": [
    { "pattern": "api.example.com/*", "zone_name": "example.com" }
  ]
}
```

---

## Template 2: Event Pipeline

**Use Case**: Ingest events, process async, store results

```mermaid
graph LR
    subgraph "Ingest"
        I[Ingest Worker]
    end
    subgraph "Processing"
        Q1[Queue]
        P[Processor]
        DLQ[Dead Letter]
    end
    subgraph "Storage"
        D1[(D1)]
        R2[(R2<br/>Raw Data)]
        AE[Analytics Engine]
    end

    Client --> I
    I --> Q1 --> P
    P --> D1
    P --> R2
    P --> AE
    P -.->|failed| DLQ
```

**Wrangler Config**:
```jsonc
{
  "name": "event-pipeline",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",
  "observability": { "logs": { "enabled": true } },
  "d1_databases": [
    { "binding": "DB", "database_name": "events-db", "database_id": "..." }
  ],
  "r2_buckets": [
    { "binding": "RAW_DATA", "bucket_name": "events-raw" }
  ],
  "analytics_engine_datasets": [
    { "binding": "METRICS", "dataset": "event_metrics" }
  ],
  "queues": {
    "producers": [
      { "binding": "EVENTS_QUEUE", "queue": "events" }
    ],
    "consumers": [
      {
        "queue": "events",
        "max_batch_size": 100,
        "max_retries": 1,
        "dead_letter_queue": "events-dlq",
        "max_concurrency": 10
      }
    ]
  }
}
```

---

## Template 3: AI Application

**Use Case**: LLM-powered application with RAG

```mermaid
graph LR
    subgraph "Edge"
        W[Worker]
    end
    subgraph "AI"
        GW[AI Gateway]
        WAI[Workers AI]
    end
    subgraph "Storage"
        V[(Vectorize)]
        KV[(KV<br/>Prompt Cache)]
        D1[(D1<br/>Conversations)]
    end

    Client --> W
    W --> KV
    W --> V
    W --> GW --> WAI
    W --> D1
```

**Wrangler Config**:
```jsonc
{
  "name": "ai-app",
  "main": "src/index.ts",
  "compatibility_date": "2025-01-01",
  "placement": { "mode": "smart" },
  "observability": { "logs": { "enabled": true } },
  "ai": { "binding": "AI" },
  "vectorize": [
    { "binding": "VECTORS", "index_name": "knowledge-base" }
  ],
  "kv_namespaces": [
    { "binding": "PROMPT_CACHE", "id": "..." }
  ],
  "d1_databases": [
    { "binding": "DB", "database_name": "conversations", "database_id": "..." }
  ],
  "vars": {
    "AI_GATEWAY_SLUG": "ai-app-gateway"
  }
}
```

---

## Template 4: Fullstack App (Workers + Assets)

**Use Case**: Fullstack SPA with API backend (React, Vue, Svelte, etc.)

```mermaid
graph LR
    subgraph "Single Worker"
        Assets[Assets<br/>./dist]
        API[API Routes<br/>./src]
    end
    subgraph "Storage"
        D1[(D1)]
        KV[(KV Cache)]
    end

    Client -->|/*| Assets
    Client -->|/api/*| API
    API --> D1
    API --> KV
```

**Wrangler Config** (Modern `[assets]` block):
```jsonc
{
  "name": "fullstack-app",
  "main": "src/worker.ts",
  "compatibility_date": "2025-01-01",

  // NEW: Unified assets serving (replaces [site] and Pages)
  "assets": {
    "directory": "./dist",              // Vite/Next.js/SvelteKit output
    "binding": "ASSETS",                // Optional: access in Worker code
    "html_handling": "auto-trailing-slash",
    "not_found_handling": "single-page-application"  // 404 → index.html for SPA routing
  },

  "d1_databases": [
    { "binding": "DB", "database_name": "app-db", "database_id": "..." }
  ],
  "kv_namespaces": [
    { "binding": "CACHE", "id": "..." }
  ],
  "routes": [
    { "pattern": "example.com/*", "zone_name": "example.com" }
  ]
}
```

**Worker Implementation:**
```typescript
// src/worker.ts
import { Hono } from 'hono';
import { apiRoutes } from './routes/api';

const app = new Hono<{ Bindings: Env }>();

// API routes
app.route('/api', apiRoutes);

// Health check
app.get('/health', (c) => c.json({ status: 'ok' }));

// All other routes serve static assets automatically
// (handled by assets binding)

export default app;
```

> **Note**: This replaces the legacy `[site]` and `pages_build_output_dir` configurations. See `workers-assets.md` for migration guide.

---

## Mermaid Diagram Patterns

### Basic Worker Flow
```mermaid
graph LR
    A[Client] --> B[Worker]
    B --> C[(D1)]
    B --> D[(KV)]
```

### Queue Processing
```mermaid
graph LR
    A[Producer] --> B[Queue]
    B --> C[Consumer]
    C --> D[(Storage)]
    C -.->|failed| E[DLQ]
```

### Service Bindings
```mermaid
graph LR
    A[Gateway Worker] -->|RPC| B[Auth Worker]
    A -->|RPC| C[Data Worker]
    B --> D[(KV)]
    C --> E[(D1)]
```

### Multi-Region
```mermaid
graph TB
    subgraph "Region A"
        WA[Worker A]
        DA[(D1 Primary)]
    end
    subgraph "Region B"
        WB[Worker B]
        DB[(D1 Replica)]
    end
    WA --> DA
    WB --> DB
    DA -.->|sync| DB
```
