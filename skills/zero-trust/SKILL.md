---
name: zero-trust
description: Identify and remediate Zero Trust security gaps in Cloudflare deployments. Use this skill when auditing Access policies, checking staging/dev environment protection, detecting unprotected admin routes, or implementing mTLS and service tokens for machine-to-machine auth.
---

# Cloudflare Zero Trust Skill

Audit and implement Zero Trust security policies using Cloudflare Access, service tokens, and mTLS. Ensure all environments (production, staging, dev) have appropriate access controls.

## Environment Protection Matrix

### Risk Assessment by Environment

| Environment | Expected Protection | Common Gap | Risk Level |
|-------------|--------------------|-----------| -----------|
| Production | CF Access + WAF + Rate Limiting | Usually protected | LOW |
| Staging | CF Access (should mirror prod) | Often missing Access | HIGH |
| Development | CF Access or IP restrictions | Frequently exposed | CRITICAL |
| Preview (PR deploys) | CF Access or time-limited | Often public | HIGH |
| Admin/Internal APIs | Service Tokens + mTLS | Basic auth only | CRITICAL |

## Zero Trust Audit Workflow

### Step 1: Environment Discovery

```
1. List all Workers in account via MCP
2. Identify environment patterns:
   - *-staging, *-dev, *-preview
   - staging.*, dev.*, preview.*
   - Feature branch deployments
3. Check route configurations
```

### Step 2: Access Policy Verification

For each environment, verify:

```javascript
// Query Access applications
mcp__cloudflare-access__list_applications()

// For each route/hostname, check if Access policy exists:
// - Authentication requirement
// - Allow/Block rules
// - Session duration
// - Geographic restrictions
```

### Step 3: Audit Findings

| ID | Name | Severity | Check |
|----|------|----------|-------|
| ZT001 | Staging without Access | CRITICAL | staging.* routes without Access policy |
| ZT002 | Dev environment exposed | CRITICAL | dev.* publicly accessible |
| ZT003 | Preview deploys public | HIGH | *.pages.dev or preview.* without Access |
| ZT004 | Admin routes unprotected | CRITICAL | /admin/* without Access or auth middleware |
| ZT005 | Internal APIs no service token | HIGH | Internal service routes without mTLS/tokens |
| ZT006 | Weak session duration | MEDIUM | Access session > 24h for sensitive routes |
| ZT007 | No geographic restriction | LOW | Admin access from any country |
| ZT008 | Missing bypass audit | MEDIUM | Bypass rules without justification |

## Access Policy Patterns

### Pattern 1: Environment-Based Access

```jsonc
// wrangler.jsonc with Access-protected routes
{
  "routes": [
    {
      "pattern": "api.example.com/*",
      "zone_name": "example.com"
    },
    {
      "pattern": "staging.example.com/*",
      "zone_name": "example.com"
      // Access policy should protect this route
    }
  ]
}
```

**Recommended Access Policy for Staging:**
```json
{
  "name": "Staging Environment",
  "domain": "staging.example.com",
  "type": "self_hosted",
  "session_duration": "12h",
  "policies": [
    {
      "name": "Team Access",
      "decision": "allow",
      "include": [
        { "email_domain": { "domain": "company.com" } }
      ],
      "require": [
        { "login_method": { "id": "google" } }
      ]
    }
  ]
}
```

### Pattern 2: Service Token for Machine Auth

For Worker-to-Worker or CI/CD access:

```typescript
// Verify service token in Worker
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Service token headers set by Cloudflare Access
    const cfAccessClientId = request.headers.get('CF-Access-Client-Id');
    const cfAccessClientSecret = request.headers.get('CF-Access-Client-Secret');

    if (!cfAccessClientId || cfAccessClientId !== env.EXPECTED_CLIENT_ID) {
      return new Response('Unauthorized', { status: 401 });
    }

    // Process authenticated request
    return handleRequest(request, env);
  }
};
```

### Pattern 3: mTLS for High-Security APIs

```jsonc
// wrangler.jsonc with mTLS binding
{
  "mtls_certificates": [
    {
      "binding": "MY_CERT",
      "certificate_id": "..."
    }
  ]
}
```

```typescript
// Verify client certificate
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const tlsClientAuth = request.cf?.tlsClientAuth;

    if (!tlsClientAuth || tlsClientAuth.certVerified !== 'SUCCESS') {
      return new Response('Certificate required', { status: 403 });
    }

    // Additional verification
    if (!tlsClientAuth.certIssuerDN.includes('O=MyCompany')) {
      return new Response('Invalid certificate issuer', { status: 403 });
    }

    return handleRequest(request, env);
  }
};
```

## Environment Detection Heuristics

### Staging/Dev Indicators

```
Hostname patterns:
- staging.*, stage.*, stg.*
- dev.*, development.*
- preview.*, pr-*.*, branch-*.*
- *.pages.dev (Cloudflare Pages previews)
- localhost:*, 127.0.0.1:*

Wrangler config indicators:
- env.staging, env.development
- name: "*-staging", "*-dev"
- vars.ENVIRONMENT: "staging" | "development"
```

### Admin Route Indicators

```
Path patterns requiring protection:
- /admin/*
- /api/admin/*
- /internal/*
- /dashboard/*
- /manage/*
- /config/*
- /_debug/*
- /metrics, /health (depends on sensitivity)
```

## Output Format

```markdown
# Zero Trust Audit Report

**Scope**: [Account/Zone]
**Environments Scanned**: X

## Critical Gaps (Immediate Action Required)

### [ZT001] Staging Environment Exposed
- **Route**: staging.example.com/*
- **Status**: No Access policy detected
- **Risk**: Staging data/functionality exposed to internet
- **Fix**: Create Access application with team email domain restriction
- **Provenance**: `[LIVE-VALIDATED]` via cloudflare-access MCP

### [ZT004] Admin Routes Unprotected
- **Route**: api.example.com/admin/*
- **Status**: No authentication middleware or Access policy
- **Risk**: Admin functions accessible without auth
- **Fix**: Add Access policy OR implement auth middleware
- **Provenance**: `[STATIC]` - code analysis

## High Priority

[List HIGH severity findings]

## Recommendations

1. [ ] Create Access application for `staging.example.com`
2. [ ] Implement service token auth for CI/CD access
3. [ ] Add mTLS for internal service-to-service calls
4. [ ] Review and reduce session durations

## Access Policy Suggestions

[Generated Access policy configurations]
```

## MCP Tools for Zero Trust

```javascript
// List Access applications
mcp__cloudflare-access__list_applications()

// Get application details
mcp__cloudflare-access__get_application({ app_id: "..." })

// List Access policies
mcp__cloudflare-access__list_policies({ app_id: "..." })

// Verify route protection
mcp__cloudflare-bindings__workers_list()
```

## Tips

- **Preview deploys**: Always protect with Access; use time-limited URLs
- **Service tokens**: Rotate quarterly; scope to specific applications
- **mTLS**: Required for PCI-DSS/HIPAA compliance scenarios
- **Session duration**: Shorter for admin (1-4h), longer for general access (24h)
- **Bypass rules**: Document and audit regularly; set expiration
- **Geographic restrictions**: Consider for admin access
- **Device posture**: Enable for high-security environments (requires WARP)

## Quick Fixes

### Add Access to Staging (via Terraform)

```hcl
resource "cloudflare_access_application" "staging" {
  zone_id          = var.zone_id
  name             = "Staging Environment"
  domain           = "staging.example.com"
  type             = "self_hosted"
  session_duration = "12h"
}

resource "cloudflare_access_policy" "staging_team" {
  application_id = cloudflare_access_application.staging.id
  zone_id        = var.zone_id
  name           = "Team Access"
  precedence     = 1
  decision       = "allow"

  include {
    email_domain = ["company.com"]
  }
}
```

### Add Service Token Auth to Worker

```typescript
// middleware/serviceToken.ts
export function requireServiceToken(env: Env) {
  return async (c: Context, next: () => Promise<void>) => {
    const clientId = c.req.header('CF-Access-Client-Id');
    if (clientId !== env.EXPECTED_SERVICE_TOKEN_ID) {
      return c.json({ error: 'Unauthorized' }, 401);
    }
    await next();
  };
}
```
