# Contributing to Cloudflare Engineer Plugin

Thank you for your interest in contributing! This guide will help you get started.

## Quick Start

1. Fork the repository
2. Clone your fork locally
3. Make changes in a feature branch
4. Test your changes
5. Submit a pull request

## Development Setup

### Prerequisites

- Claude Code v2.0.12 or higher
- Python 3.8+ (for hook development)
- Access to a Cloudflare account (for testing)

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/cloudflare-engineer.git
cd cloudflare-engineer

# Install as local plugin for testing
claude plugin install ./

# Or add as local marketplace
/plugin marketplace add ./
```

### Testing Changes

```bash
# Validate plugin structure
claude plugin validate .

# Test pre-deploy hook manually
echo '{"tool_name":"Bash","tool_input":{"command":"npx wrangler deploy"}}' | \
  python3 hooks/pre-deploy-check.py

# Test in a real project
cd /path/to/cloudflare-worker
/cf-audit --validate
```

## Adding Components

### New Skill

1. Create directory: `skills/your-skill/`
2. Create `SKILL.md` with YAML frontmatter:

```markdown
---
description: Brief description for auto-discovery
triggers:
  - "keyword patterns that activate this skill"
---

# Skill Name

Your skill content here...
```

### New Agent

Create `agents/your-agent.md`:

```markdown
---
name: your-agent
description: What the agent does
model: sonnet
color: blue
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - mcp__cloudflare-bindings__*
---

# Agent System Prompt

Your agent instructions here...
```

### New Command

Create `commands/cf-yourcommand.md`:

```markdown
---
description: Command description
allowed-tools:
  - Read
  - Glob
  - Bash
argument-hints: "[--flag] [arg]"
---

# Command Instructions

Your command logic here...
```

### New Hook Rule

1. Add validation logic to `hooks/pre-deploy-check.py`
2. Follow the pattern:

```python
def check_your_rule(config: dict, issues: list) -> None:
    """YOUR001: Description of what this checks."""
    if condition_violated:
        issues.append({
            "id": "YOUR001",
            "severity": "HIGH",  # CRITICAL, HIGH, MEDIUM, LOW
            "message": "What's wrong",
            "recommendation": "How to fix it"
        })
```

3. Register in `run_checks()` function

### New Architecture Pattern

1. Create `skills/patterns/your-pattern.md`
2. Follow the template structure:
   - Problem statement
   - Symptoms
   - Before/after code
   - Implementation steps
   - Trade-offs
   - When NOT to apply

## Pull Request Guidelines

### Before Submitting

- [ ] Run `claude plugin validate .` successfully
- [ ] Test with a real Cloudflare project
- [ ] Update CHANGELOG.md
- [ ] Add/update documentation as needed

### PR Title Format

Use conventional commits:
- `feat: add new D1 sharding pattern`
- `fix: correct queue DLQ detection`
- `docs: improve cost calculation examples`
- `refactor: simplify hook JSONC parser`

### PR Description

Include:
- What changed and why
- Testing performed
- Screenshots/output if applicable
- Breaking changes (if any)

## Code Style

### Markdown (Skills/Agents/Commands)

- Use ATX-style headers (`#`, `##`, `###`)
- Include YAML frontmatter for all components
- Use fenced code blocks with language identifiers
- Keep lines under 100 characters where practical

### Python (Hooks)

- Follow PEP 8
- Add docstrings to functions
- Use type hints where helpful
- Keep functions focused and testable

## Validation Rules

When adding new validation rules to the pre-deploy hook:

| Prefix | Category | Example |
|--------|----------|---------|
| SEC | Security | SEC001 - Plaintext secrets |
| RES | Resilience | RES001 - Missing DLQ |
| COST | Cost | COST001 - High retry count |
| PERF | Performance | PERF001 - Smart Placement |
| BUDGET | Budget enforcement | BUDGET001 - DO usage warning |
| PRIV | Privacy | PRIV001 - PII in logs |
| ZT | Zero Trust | ZT001 - Staging without Access |
| LOOP | Loop Safety (Billing) | LOOP001 - Missing cpu_ms limit |

Severity levels:
- **CRITICAL**: Blocks deploy, security risk, or billing explosion risk (includes LOOP* critical)
- **HIGH**: Should fix before deploy
- **MEDIUM**: Recommended improvement
- **LOW**: Nice to have
- **INFO**: Informational (Budget warnings)

## Adding New Cloudflare Products to Guardrails

When Cloudflare releases new services or you identify new cost/security patterns, follow this process to add guardrail logic:

### 1. Update Cost Watchlist

Add new cost traps to `COST_SENSITIVE_RESOURCES.md`:

```markdown
## New Service Name

### Pricing Model (Year)

| Operation | Cost | Free Tier |
|-----------|------|-----------|
| ... | ... | ... |

### Cost Traps

#### TRAP-SVC-001: Description (Severity)

**Pattern**: What causes the high cost

\`\`\`typescript
// EXPENSIVE: Anti-pattern
...

// OPTIMIZED: Correct pattern
...
\`\`\`

**Detection**:
- `[STATIC]`: How to detect via code analysis
- `[LIVE-VALIDATED]`: How to confirm via observability

**Guardian Rule**: `BUDGETXXX`
```

### 2. Add Guardian Skill Rules

Update `skills/guardian/SKILL.md`:

1. Add to Budget Enforcement Triggers table
2. Add audit rule to Budget Audit Rules table with ID (BUDGET007+)
3. Add detection logic description to Budget Whisperer section

### 3. Add Pre-Deploy Hook Checks (if applicable)

If the trap can be detected statically from wrangler config:

```python
# hooks/pre-deploy-check.py

def check_new_service_trap(config: dict) -> list[dict]:
    """Check for new service cost traps."""
    issues = []

    # Check bindings
    if "new_service" in config:
        # Detection logic
        issues.append({
            "id": "BUDGETXXX",
            "severity": "MEDIUM",
            "message": "Description of issue",
            "fix": "How to fix it",
        })

    return issues
```

### 4. Update Agents for Provenance Tagging

Ensure agents cite the Cost Watchlist when giving cost advice:

```markdown
# In agent system prompts

When discussing costs for [Service]:
1. Reference COST_SENSITIVE_RESOURCES.md
2. Tag warnings with `[STATIC:COST_WATCHLIST]` or `[LIVE-VALIDATED:COST_WATCHLIST]`
3. Cite specific TRAP-XXX-NNN identifiers
```

### 5. Update Documentation

- Add service to README.md "Supported Cloudflare Services" list
- Update CLAUDE.md "Cloudflare Service Coverage" table
- Add to CHANGELOG.md under appropriate version

### Example: Adding Hyperdrive Guardrails

```markdown
# COST_SENSITIVE_RESOURCES.md

## Hyperdrive (Connection Pooling)

### Pricing Model (2026)

| Resource | Cost | Free Tier |
|----------|------|-----------|
| Connections | $0.01 per 1M queries | 5M/month |

### Cost Traps

#### TRAP-HD-001: Connection per Request (HIGH)

**Pattern**: Creating new connection for each request instead of pooling.

\`\`\`typescript
// EXPENSIVE: New connection per request
app.get('/data', async (c) => {
  const client = new Client(c.env.DATABASE_URL);
  await client.connect();
  // ...
});

// OPTIMIZED: Use Hyperdrive connection
app.get('/data', async (c) => {
  // Hyperdrive manages connection pooling
  const result = await c.env.HYPERDRIVE.query('SELECT ...');
});
\`\`\`

**Detection**:
- `[STATIC]`: Check for `new Client()` in request handlers
- `[LIVE-VALIDATED]`: Connection count in observability

**Guardian Rule**: `BUDGET007`
```

## Questions?

- Open a [Discussion](https://github.com/littlebearapps/cloudflare-engineer/discussions) for questions
- Check existing [Issues](https://github.com/littlebearapps/cloudflare-engineer/issues) before reporting bugs
- See [SECURITY.md](SECURITY.md) for vulnerability reports

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
