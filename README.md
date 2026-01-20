# Cloudflare Engineer Plugin

[![Version](https://img.shields.io/badge/version-1.6.0-blue.svg)](https://github.com/littlebearapps/cloudflare-engineer/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-v2.0.12+-purple.svg)](https://claude.com/claude-code)
[![GitHub Issues](https://img.shields.io/github/issues/littlebearapps/cloudflare-engineer)](https://github.com/littlebearapps/cloudflare-engineer/issues)
[![GitHub Discussions](https://img.shields.io/github/discussions/littlebearapps/cloudflare-engineer)](https://github.com/littlebearapps/cloudflare-engineer/discussions)

> **The Platform Architect that protects your wallet.**
> Design, implement, and secure Cloudflare Workers without the billing anxiety.

## Why This Plugin?

Serverless is powerful, but a single infinite loop or unindexed query can cost thousands. **Cloudflare Engineer** acts as your proactive pair programmer, enforcing architectural patterns that scale without bankrupting you.

It doesn't just write code—it **audits** it against a database of known Cloudflare billing traps.

| 🛡️ **Sleep Soundly** | ⚡ **Ship Faster** | 🏗️ **Scale Smart** |
| :--- | :--- | :--- |
| Real-time cost guardrails catch row-read explosions and recursion loops *before* you deploy. | 13 auto-skills handle the boilerplate for Hono, D1, Queues, and Workflows instantly. | Pattern architect suggests the right tool (Workers vs Containers vs Workflows) for the job. |

## Quick Install

```bash
# 1. Add the marketplace
/plugin marketplace add littlebearapps/cloudflare-engineer

# 2. Install the plugin
/plugin install cloudflare-engineer@littlebearapps-cloudflare-engineer
```

To update: `/plugin update cloudflare-engineer@littlebearapps-cloudflare-engineer`

> **Note**: Works fully without setup. For live validation against production metrics, configure the optional [Cloudflare MCP servers](#mcp-tool-integration).

---

## Billing Protection

We detect the specific patterns that cause billing spikes.

| Protection | What It Catches | Rule |
|------------|-----------------|------|
| **D1 Row Read Shield** | `SELECT *` without `LIMIT`, unindexed queries causing millions of reads | QUERY001, BUDGET007 |
| **R2 Cost Shield** | Class B operation abuse, public buckets without CDN caching | BUDGET008, R2002 |
| **Loop Breaker** | Worker self-recursion, infinite retry loops, `setInterval` in DOs | LOOP001-008 |
| **AI Cost Awareness** | Expensive models (Llama 405b, DeepSeek-R1) for simple tasks | AI001, AI002 |
| **Queue Safety** | Missing DLQs, high retry counts, no max_concurrency | RES001, COST001 |

See the full [Cost-Sensitive Resources Watchlist](COST_SENSITIVE_RESOURCES.md) for all billing traps.

## Architecture Skills

Stop guessing which service to use. The plugin provides decision trees for:

| Skill | When It Activates |
|-------|-------------------|
| `architect` | "Design a queue-based pipeline" → Edge-Native Constraints + Billing Safety |
| `workflow-architect` | "Should I use Queues or Workflows?" → Durable execution patterns |
| `query-optimizer` | "Optimize my D1 queries" → N+1 detection, caching decisions |
| `loop-breaker` | "Prevent infinite loops" → Recursion guards, idempotency |
| `guardian` | "Is my worker secure?" → Security + Budget + Privacy audit |
| `zero-trust` | "Protect my staging environment" → Access policies, Tunnel config |
| `implement` | "Scaffold a Hono API with D1" → Code templates + Queue Safety |

All 13 skills activate automatically based on your questions.

---

## Pre-Deploy Validation

Before `wrangler deploy`, our hook validates your config and source code against 30+ rules.

### Severity Levels

| Severity | Blocking? | Example Detection |
|----------|-----------|-------------------|
| 🔴 CRITICAL | **Yes** | `while(true)` without break, D1 query inside `map()` |
| 🟠 HIGH | No | Plaintext secrets, R2 writes in loops |
| 🟡 MEDIUM | No | Missing DLQ, deprecated `[site]` config |
| 🔵 LOW/INFO | No | Smart placement disabled, observability not configured |

### Key Rules

| Rule | Severity | Detection |
|------|----------|-----------|
| SEC001 | 🔴 CRITICAL | Plaintext secrets in config |
| LOOP002 | 🔴 CRITICAL | D1 query in loop (N+1 trap) |
| LOOP005 | 🔴 CRITICAL | Worker self-fetch recursion |
| LOOP007 | 🔴 CRITICAL | Unbounded `while(true)` loop |
| BUDGET007 | 🔴 CRITICAL | D1 row read explosion |
| RES001 | 🟠 HIGH | Queue without dead letter queue |
| BUDGET008 | 🟡 MEDIUM | R2 Class B without edge caching |
| AI001 | 🟠 HIGH | Expensive AI model without cost awareness |

### Suppressing False Positives

**Inline comments** for known-safe patterns:

```typescript
// @pre-deploy-ok LOOP005
async function traverse(node: Node, depth = 0) {
  if (depth > 10) return;  // Has depth limit - safe
  await traverse(child, depth + 1);
}

while (true) { // @pre-deploy-ok LOOP007
  if (shouldStop) break;  // Controlled loop
}
```

**Project-level `.pre-deploy-ignore`** file:

```bash
RES001:my-queue     # Suppress for specific queue
LOOP001             # Allow high cpu_ms for this worker
```

**Emergency bypass** (session-only):

```bash
SKIP_PREDEPLOY_CHECK=1 npx wrangler deploy
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/cf-costs [--validate]` | Cost report with monthly projections |
| `/cf-audit [--validate]` | Full security, performance, and cost audit |
| `/cf-design` | Interactive architecture design wizard |
| `/cf-pattern <name>` | Apply patterns: `circuit-breaker`, `kv-cache-first`, `d1-batching` |
| `/cf-logs` | Configure external logging (Axiom, Better Stack) with privacy filters |

## Pattern Catalog

Apply battle-tested patterns with scaffolding:

| Pattern | Problem | Solution |
|---------|---------|----------|
| `service-bindings` | Monolithic Worker hitting subrequest limits | Decompose with RPC |
| `d1-batching` | High D1 write costs from per-row inserts | Batch INSERT operations |
| `circuit-breaker` | External API cascading failures | Fail-fast with fallback |
| `kv-cache-first` | D1 row read explosion | Cache reads in KV |
| `r2-cdn-cache` | R2 Class B operation costs | Edge cache public assets |

```bash
/cf-pattern kv-cache-first
/cf-pattern circuit-breaker --analyze-only
```

---

## Supported Services

| Category | Services |
|----------|----------|
| **Compute** | Workers, Durable Objects, Containers (Beta) |
| **Storage** | R2, D1 (SQLite), KV, Vectorize |
| **Flow** | Queues, Workflows, Stream |
| **Security** | Access (Zero Trust), AI Gateway, Custom Hostnames |

## MCP Tool Integration

For `--validate` mode, configure these Cloudflare MCP servers:

| MCP Server | Used For |
|------------|----------|
| `cloudflare-observability` | Worker metrics, error rates, latency |
| `cloudflare-ai-gateway` | AI costs, cache hit rates |
| `cloudflare-bindings` | D1 queries, resource inventory |

**Without MCP**: Full static analysis works perfectly. Commands tag findings as `[STATIC]`.

**With MCP**: Live validation confirms findings against production. Tags: `[LIVE-VALIDATED]` or `[LIVE-REFUTED]`.

---

## What's New in v1.6.0

### Session-Aware Hooks

| Hook | When | What It Does |
|------|------|--------------|
| **SessionStart** | Session begins | Detects CF projects, announces bindings (D1, R2, KV, Queues, DO, AI) |
| **PreToolUse** | Before `wrangler deploy` | Validates config and source code (30+ rules) |
| **PostToolUse** | After `wrangler deploy` | Parses deployment output, suggests next steps |

### AI Cost Detection

| Rule | Severity | Detection |
|------|----------|-----------|
| AI001 | 🟠 HIGH | Expensive model usage (llama-3.1-405b, deepseek-r1) without cost awareness |
| AI002 | 🟡 MEDIUM | AI binding without cache wrapper pattern |

### GitHub Integration

- YAML issue templates with structured fields
- GitHub Discussions for community Q&A
- 10 new labels for Cloudflare services and components

---

## Support & Community

| Channel | Purpose |
|---------|---------|
| [GitHub Issues](https://github.com/littlebearapps/cloudflare-engineer/issues) | Bug reports and feature requests |
| [GitHub Discussions](https://github.com/littlebearapps/cloudflare-engineer/discussions) | Questions, ideas, and community chat |
| [Changelog](CHANGELOG.md) | Version history and what's new |

## Requirements

- Claude Code v2.0.12+
- Python 3.8+ (for pre-deploy hook)
- Cloudflare account with Workers enabled

## Contributing

We believe in the power of open source. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

1. Check the [Issue Tracker](https://github.com/littlebearapps/cloudflare-engineer/issues)
2. Read our [Contributing Guide](CONTRIBUTING.md)
3. Submit a PR!

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Links

- [Changelog](CHANGELOG.md)
- [Cost-Sensitive Resources Watchlist](COST_SENSITIVE_RESOURCES.md)
- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

---

<div align="center">
<sub>Made with care by <a href="https://littlebearapps.com">Little Bear Apps</a></sub>
</div>
