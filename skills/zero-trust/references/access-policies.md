# Access Policy Patterns

## Pattern 1: Environment-Based Access

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

## Pattern 2: Service Token for Machine Auth

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

## Pattern 3: mTLS for High-Security APIs

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

## Access Policy Generator

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
