# Queue Safety Patterns (Loop Protection)

**IMPORTANT**: Queue consumers MUST implement idempotency to prevent duplicate processing during retries. This is critical for preventing "retry loops" that multiply costs.

## Queue Consumer with Idempotency (src/queue.ts)

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
```

## Queue Configuration (wrangler.jsonc)

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

## DLQ Consumer (src/dlq-handler.ts)

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

## Queue Publishing Pattern

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

## Idempotency Key Selection

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

## Retry Budget Pattern

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

## Circuit Breaker for Queue Consumers

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
