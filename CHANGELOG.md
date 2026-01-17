# Changelog

All notable changes to the Cloudflare Engineer plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-01-17

### Added
- **Cost Awareness Upgrade** - Comprehensive protection for primary billing dangers:
  - **D1 Row Read Protection** (BUDGET007) - Detects unindexed queries causing millions of reads
  - **R2 Class B Caching** (BUDGET008) - Flags public bucket reads without CDN cache
  - **R2 Infrequent Access Trap** (BUDGET009) - Warns about $9 minimum charge on IA bucket reads
  - New `kv-cache-first` pattern for caching D1 reads with KV
  - New `r2-cdn-cache` pattern for edge caching R2 public assets
  - TRAP-D1-004: Row read explosion cost trap
  - TRAP-R2-003: Class B operation accumulation cost trap
  - TRAP-R2-004: IA minimum billing trap
- **Workers + Assets Architecture** - Unified frontend + backend:
  - Default scaffolding now uses `[assets]` block instead of Pages
  - ARCH001 validation rule for deprecated `[site]` and `pages_build_output_dir`
  - Updated Template 4 for fullstack SPA architecture
  - Migration guide from legacy configurations
- **Workload Router: Isolates vs Containers** - Decision tree in architect skill:
  - Comparison table for Workers vs Containers (Beta)
  - Container configuration templates
  - Hybrid Worker + Container architecture patterns
  - Cloudflare alternatives for native dependencies
- **Observability Export** - Log retention beyond 3-7 days:
  - Axiom integration via Logpush (500GB/month free)
  - Better Stack / Logtail SDK setup
  - OpenTelemetry native export patterns
  - Structured logging with request IDs

### Changed
- Guardian skill includes D1 Row Read Explosion check and R2 IA warning
- Architect skill includes Workload Router and Workers + Assets sections
- Implement skill includes R2 CDN Caching and Observability Export sections
- Patterns skill now includes 5 patterns (added kv-cache-first, r2-cdn-cache)
- Pre-deploy hook checks for deprecated [site] configuration
- Pre-deploy hook detects R2 buckets with IA-suggesting names
- Updated Cloudflare Service Coverage to include Containers (Beta)
- Updated all documentation for v1.4.0

### Fixed
- Pattern Selection Guide now includes D1 read cost optimization path

## [1.3.0] - 2026-01-17

### Added
- **Loop Protection** - Comprehensive billing safety against infinite loops and runaway processes:
  - New `loop-breaker` skill with recursion guards, idempotency patterns, and DO hibernation
  - Recursion depth middleware (X-Recursion-Depth header tracking, HTTP 508 responses)
  - Service Binding recursion guards with context-passing pattern
  - Queue idempotency patterns using KV for deduplication
  - Durable Object hibernation patterns (alarm-based instead of setInterval)
  - D1 QueryBatcher for N+1 query prevention
- **Loop-Sensitive Resource Audit** in guardian skill:
  - New audit rules: LOOP001-LOOP008
  - Detects D1 queries in loops, R2 writes in loops, setInterval in DOs
  - Flags Worker self-fetch patterns and unbounded while loops
  - Checks for missing cpu_ms limits and DLQ configuration
- **Billing Safety Limits** in architect skill:
  - CPU time caps section with recommended limits by use case
  - Subrequest limits and fan-out protection guidance
  - Architecture checklist for billing safety
- **Queue Safety Patterns** in implement skill:
  - Queue Consumer with Idempotency template
  - DLQ Consumer pattern for failed message inspection
  - Retry Budget pattern for message lifecycle limits
  - Circuit Breaker for queue consumers
- **Loop Detection** in pre-deploy hook:
  - Source code scanning for loop-sensitive patterns
  - Detects D1/R2 operations in loops, setInterval, self-fetch, unbounded loops
  - LOOP001-LOOP008 validation rules (CRITICAL/HIGH/MEDIUM)
- **Cost Simulation** in pre-deploy hook:
  - Estimates potential cost impact of detected loop patterns
  - Shows cost formula and daily/monthly projections
- **Loop Cost Traps** in COST_SENSITIVE_RESOURCES.md:
  - TRAP-LOOP-001: Worker Self-Recursion
  - TRAP-LOOP-002: Queue Retry Storm
  - TRAP-LOOP-003: Durable Object Wake Loop
  - TRAP-LOOP-004: N+1 Query Loop
  - TRAP-LOOP-005: R2 Write Flood
  - CPU limit as circuit breaker documentation

### Changed
- Architect skill now includes Billing Safety Limits section
- Guardian skill now includes Loop-Sensitive Resource Audit category
- Implement skill now includes Queue Safety patterns section
- Pre-deploy hook groups loop issues in dedicated "LOOP SAFETY" output section
- Anti-patterns table in architect skill expanded with loop-related patterns
- Skill count increased from 10 to 11

### Fixed
- Pre-deploy hook now properly handles LOOP* rules in severity counting
- Loop critical issues now show specific warning about billing explosion risk

## [1.2.0] - 2026-01-08

### Added
- **Vibecoder Proactive Safeguards** - Guardian skill now proactively warns about:
  - Budget impacts (Durable Objects, R2 writes, D1 writes, large AI models, KV writes)
  - Privacy concerns (PII in logs, user data in KV keys, AI prompts without redaction)
  - New audit rules: BUDGET001-006, PRIV001-005
- **Resource Discovery Mode** for `/cf-audit`:
  - Default behavior now includes resource discovery
  - Finds unused KV namespaces, R2 buckets, D1 databases
  - Identifies dangling references and orphaned Workers
  - New `--discover` flag for explicit discovery-only mode
  - New `--category=resources` option
- **Edge-Native Constraints** in architect skill:
  - Node.js API compatibility matrix
  - Common library compatibility guide (express, axios, bcrypt, sharp, etc.)
  - Cloudflare alternatives for incompatible packages
  - Runtime limits reference (Free vs Standard vs Unbound)
  - Example migration patterns from Node.js to Edge
- **Performance Budgeter** in pre-deploy hook:
  - Bundle size estimation against tier limits (1MB Free, 10MB Standard)
  - Heavy dependency detection (moment, lodash, aws-sdk, sharp)
  - New validation rules: PERF005 (bundle size), PERF006 (native packages)
  - Enhanced DLQ checks with RES002 (max_concurrency)
- **New skill: zero-trust** - Cloudflare Access policy auditing:
  - Environment protection matrix (prod/staging/dev/preview)
  - Access policy verification workflow
  - Service token and mTLS patterns
  - Audit rules ZT001-ZT008
- **New skill: custom-hostnames** - SSL for SaaS management:
  - Custom hostname lifecycle management
  - Multi-tenant routing patterns
  - SSL certificate validation methods
  - Hostname webhook handling
  - CAA record requirements
- **New skill: media-streaming** - Cloudflare Stream and Images:
  - Video upload with signed URLs
  - HLS.js player integration
  - Stream webhook handling
  - Image transformation patterns
  - Named variants and responsive images
  - Live streaming architecture

### Changed
- Plugin now positioned as **Platform Architect** (upgraded from Senior Developer)
- Guardian skill now includes Budget and Privacy audit categories
- Architect skill validates Workers runtime compatibility by default
- `/cf-audit` command now performs resource discovery by default
- Pre-deploy hook includes Performance Budgeter checks
- Updated README with Vibecoder Proactive Safeguards section
- Skill count increased from 7 to 10

### Fixed
- Improved DLQ check includes max_concurrency validation
- Better JSONC parsing for wrangler configs with comments

## [1.1.0] - 2025-01-07

### Added
- **Live validation mode** (`--validate`) for commands - validates configurations against live Cloudflare data via MCP tools
- **Provenance tagging system** - outputs tagged as `[STATIC]`, `[LIVE-VALIDATED]`, `[LIVE-REFUTED]`, or `[INCOMPLETE]`
- **Audit probes skill** (`skills/probes/`) - pre-built MCP queries for D1 indexes, observability metrics, AI Gateway costs, and queue health
- **Pattern catalog skill** (`skills/patterns/`) with 3 architecture patterns:
  - Service Bindings for monolith decomposition
  - D1 Batching for write cost optimization
  - Circuit Breaker for external API resilience
- **New command** `/cf-pattern` - apply architecture patterns to current project

### Changed
- All agents now include MCP availability checks with graceful degradation
- Enhanced cost analysis with 2026 Cloudflare pricing formulas
- Improved pre-deploy hook with better JSONC/TOML parsing

## [1.0.0] - 2024-12-15

### Added
- Initial release
- **5 skills**: architect, guardian, implement, optimize-costs, scale
- **3 agents**: architecture-reviewer, cost-analyzer, security-auditor
- **3 commands**: /cf-costs, /cf-audit, /cf-design
- **1 hook**: pre-deploy validation (SEC001, SEC002, RES001, COST001, PERF001, PERF004)
- Support for Workers, D1, R2, KV, Queues, Vectorize, AI Gateway, Workflows, Durable Objects
