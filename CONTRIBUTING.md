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

Severity levels:
- **CRITICAL**: Blocks deploy, security risk
- **HIGH**: Should fix before deploy
- **MEDIUM**: Recommended improvement
- **LOW**: Nice to have

## Questions?

- Open a [Discussion](https://github.com/littlebearapps/cloudflare-engineer/discussions) for questions
- Check existing [Issues](https://github.com/littlebearapps/cloudflare-engineer/issues) before reporting bugs
- See [SECURITY.md](SECURITY.md) for vulnerability reports

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
