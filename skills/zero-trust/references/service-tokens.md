# Service Tokens and Admin Protection

## Service Token Overview

Service tokens provide machine-to-machine authentication for Cloudflare Access without user identity. Use for:
- CI/CD pipelines
- Cron jobs and scheduled tasks
- Worker-to-Worker communication
- Monitoring and health checks

## Creating Service Tokens

### Via Dashboard
1. Zero Trust > Access > Service Auth > Service Tokens
2. Create Service Token
3. Copy Client ID and Client Secret (shown once only)

### Via Terraform
```hcl
resource "cloudflare_access_service_token" "ci_token" {
  zone_id = var.zone_id
  name    = "CI/CD Pipeline"
}

# Store in secrets manager
output "ci_client_id" {
  value     = cloudflare_access_service_token.ci_token.client_id
  sensitive = true
}

output "ci_client_secret" {
  value     = cloudflare_access_service_token.ci_token.client_secret
  sensitive = true
}
```

## Using Service Tokens

### HTTP Request Headers
```bash
curl https://api.example.com/internal \
  -H "CF-Access-Client-Id: <CLIENT_ID>" \
  -H "CF-Access-Client-Secret: <CLIENT_SECRET>"
```

### GitHub Actions
```yaml
jobs:
  deploy:
    steps:
      - name: Trigger deploy
        run: |
          curl -X POST https://api.example.com/deploy \
            -H "CF-Access-Client-Id: ${{ secrets.CF_CLIENT_ID }}" \
            -H "CF-Access-Client-Secret: ${{ secrets.CF_CLIENT_SECRET }}"
```

### Worker Fetch
```typescript
async function callInternalAPI(env: Env) {
  const response = await fetch('https://internal.example.com/api', {
    headers: {
      'CF-Access-Client-Id': env.SERVICE_TOKEN_ID,
      'CF-Access-Client-Secret': env.SERVICE_TOKEN_SECRET,
    },
  });
  return response.json();
}
```

## Admin Panel Protection Checklist

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

## Extended Validation Rules

### ZT009: Jobs Route Without Service Token

**Pattern**: Scheduled job endpoints accessible without machine auth.

**Detection**:
- Routes matching `/jobs/*`, `/cron/*`, `/scheduled/*`
- No `CF-Access-Client-Id` header validation
- No Access application with service token policy

**Risk**: Attackers can trigger jobs, potentially causing data corruption or resource exhaustion.

**Fix**: Add Access application with service token policy.

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

## Service Token Best Practices

| Practice | Recommendation |
|----------|----------------|
| **Naming** | Descriptive names: `ci-deploy-prod`, `monitoring-healthcheck` |
| **Rotation** | Quarterly rotation; automate with Terraform |
| **Scoping** | One token per use case, not shared across services |
| **Storage** | Secrets manager (AWS Secrets Manager, HashiCorp Vault, Bitwarden) |
| **Logging** | Never log token values; redact in error messages |
| **Expiration** | Set token expiration for temporary access |

## Token Rotation Strategy

```hcl
# Create new token
resource "cloudflare_access_service_token" "api_v2" {
  zone_id = var.zone_id
  name    = "API Service Token v2"
}

# Update Access policy to accept both old and new
resource "cloudflare_access_policy" "api_service" {
  application_id = cloudflare_access_application.api.id
  zone_id        = var.zone_id
  name           = "Service Token Access"
  precedence     = 1
  decision       = "non_identity"

  include {
    service_token = [
      cloudflare_access_service_token.api_v1.id,  # Old (to be removed)
      cloudflare_access_service_token.api_v2.id,  # New
    ]
  }
}

# After all clients migrated, remove old token
# resource "cloudflare_access_service_token" "api_v1" { ... }
```
