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

---

## Cloudflare Tunnel Configuration (NEW v1.5.0)

### Quick Start with cloudflared

Cloudflare Tunnel creates secure outbound-only connections from your infrastructure to Cloudflare, eliminating the need for public IPs or open firewall ports.

**1. Install cloudflared**:
```bash
# macOS
brew install cloudflared

# Linux (Debian/Ubuntu)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Docker
docker pull cloudflare/cloudflared:latest
```

**2. Authenticate**:
```bash
cloudflared tunnel login
# Opens browser for Cloudflare authentication
```

**3. Create Tunnel**:
```bash
cloudflared tunnel create my-tunnel
# Creates tunnel and credentials file at ~/.cloudflared/<TUNNEL_ID>.json
```

**4. Configure Tunnel** (`~/.cloudflared/config.yml`):
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/user/.cloudflared/<TUNNEL_ID>.json

ingress:
  # Internal admin panel (protected by Access)
  - hostname: admin.example.com
    service: http://localhost:3000
    originRequest:
      noTLSVerify: true

  # Internal API (service token auth)
  - hostname: api-internal.example.com
    service: http://localhost:8080

  # Development server
  - hostname: dev.example.com
    service: http://localhost:5173

  # Catch-all (required)
  - service: http_status:404
```

**5. Run Tunnel**:
```bash
# Foreground (testing)
cloudflared tunnel run my-tunnel

# As systemd service (production)
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Tunnel Patterns

| Pattern | Use Case | Config |
|---------|----------|--------|
| **Single Service** | Expose one internal app | Single ingress rule |
| **Multi-Service** | Route by hostname | Multiple ingress rules |
| **Bastion** | SSH/RDP access | `ssh://` or `rdp://` service |
| **Load Balanced** | HA across origins | Multiple replicas running cloudflared |
| **Private Network** | Route CIDR blocks | `warp-routing.enabled: true` |

### Tunnel + Access Integration

```yaml
# config.yml with Access requirements
tunnel: <TUNNEL_ID>
credentials-file: /path/to/creds.json

ingress:
  - hostname: admin.example.com
    service: http://localhost:3000
    originRequest:
      # Access validates JWT before traffic reaches origin
      # No additional auth needed in application
      access:
        required: true
        teamName: my-team
  - service: http_status:404
```

---

## Access Policy Generator (NEW v1.5.0)

### Admin Route Protection (Email OTP)

Protect admin panels with email-based one-time passwords.

**Terraform**:
```hcl
resource "cloudflare_access_application" "admin" {
  zone_id          = var.zone_id
  name             = "Admin Panel"
  domain           = "admin.example.com"
  type             = "self_hosted"
  session_duration = "4h"  # Short for admin access

  # Require fresh auth for sensitive actions
  allowed_idps = ["email"]  # Force email OTP only
}

resource "cloudflare_access_policy" "admin_email_otp" {
  application_id = cloudflare_access_application.admin.id
  zone_id        = var.zone_id
  name           = "Admin Email OTP"
  precedence     = 1
  decision       = "allow"

  include {
    email = [
      "admin@company.com",
      "cto@company.com"
    ]
  }

  require {
    # Force email OTP verification
    login_method = { id = "otp" }
  }
}
```

### Jobs/Cron Route Protection (Service Token)

Protect scheduled job endpoints with service tokens for machine-to-machine auth.

**Terraform**:
```hcl
resource "cloudflare_access_application" "jobs" {
  zone_id          = var.zone_id
  name             = "Job Runner"
  domain           = "jobs.example.com"
  type             = "self_hosted"
  session_duration = "24h"
}

resource "cloudflare_access_service_token" "jobs_token" {
  zone_id = var.zone_id
  name    = "Job Runner Service Token"
}

resource "cloudflare_access_policy" "jobs_service_token" {
  application_id = cloudflare_access_application.jobs.id
  zone_id        = var.zone_id
  name           = "Service Token Access"
  precedence     = 1
  decision       = "non_identity"  # Machine auth, no user identity

  include {
    service_token = [cloudflare_access_service_token.jobs_token.id]
  }
}

# Output credentials for CI/CD
output "job_runner_client_id" {
  value     = cloudflare_access_service_token.jobs_token.client_id
  sensitive = true
}

output "job_runner_client_secret" {
  value     = cloudflare_access_service_token.jobs_token.client_secret
  sensitive = true
}
```

**CI/CD Usage**:
```bash
# GitHub Actions example
curl -X POST https://jobs.example.com/run \
  -H "CF-Access-Client-Id: ${{ secrets.JOB_CLIENT_ID }}" \
  -H "CF-Access-Client-Secret: ${{ secrets.JOB_CLIENT_SECRET }}" \
  -H "Content-Type: application/json" \
  -d '{"job": "nightly-backup"}'
```

### Combined Admin + Service Token Pattern

```hcl
# Single application with multiple policies
resource "cloudflare_access_application" "api_admin" {
  zone_id          = var.zone_id
  name             = "API Admin Routes"
  domain           = "api.example.com/admin/*"
  type             = "self_hosted"
  session_duration = "4h"
}

# Policy 1: Human admin access (email OTP)
resource "cloudflare_access_policy" "admin_humans" {
  application_id = cloudflare_access_application.api_admin.id
  zone_id        = var.zone_id
  name           = "Admin Humans"
  precedence     = 1
  decision       = "allow"

  include {
    email_domain = ["company.com"]
  }

  require {
    login_method = { id = "otp" }
  }
}

# Policy 2: Automated tools (service token)
resource "cloudflare_access_policy" "admin_automation" {
  application_id = cloudflare_access_application.api_admin.id
  zone_id        = var.zone_id
  name           = "Admin Automation"
  precedence     = 2
  decision       = "non_identity"

  include {
    service_token = [cloudflare_access_service_token.admin_automation.id]
  }
}
```

---

## Admin Panel Protection Checklist (NEW v1.5.0)

Use this checklist when auditing admin routes:

### Authentication
- [ ] Access application exists for admin routes
- [ ] Short session duration (≤4h for admin, ≤1h for super-admin)
- [ ] MFA/OTP required (not just email domain)
- [ ] Service tokens used for automation (not hardcoded creds)

### Authorization
- [ ] Least privilege: separate policies for different admin roles
- [ ] IP restrictions for super-admin actions (optional)
- [ ] Geographic restrictions if applicable

### Audit & Monitoring
- [ ] Access logs enabled
- [ ] Alerts configured for failed auth attempts
- [ ] Regular access review (quarterly)
- [ ] Service token rotation schedule

### Code-Level Checks
- [ ] No hardcoded credentials in source
- [ ] Service token IDs/secrets in environment variables only
- [ ] Admin routes not exposed on public API documentation
- [ ] Rate limiting on admin endpoints

---

## Extended Validation Rules (NEW v1.5.0)

| ID | Severity | Check |
|----|----------|-------|
| ZT001 | CRITICAL | Staging without Access |
| ZT002 | CRITICAL | Dev environment exposed |
| ZT003 | HIGH | Preview deploys public |
| ZT004 | CRITICAL | Admin routes unprotected |
| ZT005 | HIGH | Internal APIs no service token |
| ZT006 | MEDIUM | Weak session duration |
| ZT007 | LOW | No geographic restriction |
| ZT008 | MEDIUM | Missing bypass audit |
| **ZT009** | **CRITICAL** | /jobs/* route without service token auth |
| **ZT010** | **HIGH** | Admin uses password-only (no OTP/MFA) |
| **ZT011** | **CRITICAL** | Service token credentials hardcoded |
| **ZT012** | **MEDIUM** | Admin session > 4h |

### ZT009: Jobs Route Without Service Token

**Pattern**: Scheduled job endpoints accessible without machine auth.

**Detection**:
- Routes matching `/jobs/*`, `/cron/*`, `/scheduled/*`
- No `CF-Access-Client-Id` header validation
- No Access application with service token policy

**Risk**: Attackers can trigger jobs, potentially causing data corruption or resource exhaustion.

**Fix**: Add Access application with service token policy (see generator above).

### ZT010: Admin Without MFA

**Pattern**: Admin routes protected only by email domain, no OTP/MFA requirement.

**Detection**:
- Access policy with `email_domain` include but no `login_method` require
- Admin routes without Access (falls back to app-level password auth)

**Risk**: Compromised email = full admin access.

**Fix**: Add `require { login_method = { id = "otp" } }` to policy.

### ZT011: Hardcoded Service Token Credentials

**Pattern**: Service token client ID/secret in source code.

**Detection**:
```bash
# Grep patterns
grep -r "CF-Access-Client-Id.*[a-f0-9]{32}" .
grep -r "CF-Access-Client-Secret.*[a-f0-9]{64}" .
```

**Risk**: Credentials in git history, exposed in logs.

**Fix**: Move to environment variables, use secrets manager.

### ZT012: Long Admin Sessions

**Pattern**: Admin Access application with `session_duration > 4h`.

**Detection**: Check Access application configuration.

**Risk**: Longer sessions = longer window for session hijacking.

**Fix**: Set `session_duration = "4h"` or shorter for admin apps.

---

## Related Skills

- **architect**: Overall architecture including Access integration
- **guardian**: Security auditing across all Cloudflare services
- **loop-breaker**: Preventing service token abuse in loops

---

*Extended in v1.5.0 - Tunnel Config, Access Policy Generator, Admin Protection*
