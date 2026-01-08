# Changelog

All notable changes to the Cloudflare Engineer plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
