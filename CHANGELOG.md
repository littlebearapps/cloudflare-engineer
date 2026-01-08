# Changelog

All notable changes to the Cloudflare Engineer plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
