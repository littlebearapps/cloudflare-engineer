# Cloudflare Tunnel Configuration

Cloudflare Tunnel creates secure outbound-only connections from your infrastructure to Cloudflare, eliminating the need for public IPs or open firewall ports.

## Quick Start with cloudflared

### 1. Install cloudflared

```bash
# macOS
brew install cloudflared

# Linux (Debian/Ubuntu)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Docker
docker pull cloudflare/cloudflared:latest
```

### 2. Authenticate

```bash
cloudflared tunnel login
# Opens browser for Cloudflare authentication
```

### 3. Create Tunnel

```bash
cloudflared tunnel create my-tunnel
# Creates tunnel and credentials file at ~/.cloudflared/<TUNNEL_ID>.json
```

### 4. Configure Tunnel

Create `~/.cloudflared/config.yml`:

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

### 5. Run Tunnel

```bash
# Foreground (testing)
cloudflared tunnel run my-tunnel

# As systemd service (production)
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## Tunnel Patterns

| Pattern | Use Case | Config |
|---------|----------|--------|
| **Single Service** | Expose one internal app | Single ingress rule |
| **Multi-Service** | Route by hostname | Multiple ingress rules |
| **Bastion** | SSH/RDP access | `ssh://` or `rdp://` service |
| **Load Balanced** | HA across origins | Multiple replicas running cloudflared |
| **Private Network** | Route CIDR blocks | `warp-routing.enabled: true` |

## Tunnel + Access Integration

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

## Private Network Routing

Enable WARP-to-Tunnel routing for private IP access:

```yaml
# config.yml
tunnel: <TUNNEL_ID>
credentials-file: /path/to/creds.json

warp-routing:
  enabled: true

ingress:
  - service: http_status:404
```

Then configure private network routes in Cloudflare dashboard:
1. Go to Zero Trust > Networks > Tunnels
2. Select your tunnel
3. Add private network routes (e.g., `10.0.0.0/8`)

## Docker Deployment

```yaml
# docker-compose.yml
version: '3'
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --config /etc/cloudflared/config.yml run
    volumes:
      - ./cloudflared:/etc/cloudflared
    restart: unless-stopped

  app:
    image: my-app:latest
    ports:
      - "3000:3000"
```

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared
spec:
  replicas: 2  # HA
  selector:
    matchLabels:
      app: cloudflared
  template:
    metadata:
      labels:
        app: cloudflared
    spec:
      containers:
      - name: cloudflared
        image: cloudflare/cloudflared:latest
        args:
        - tunnel
        - --config
        - /etc/cloudflared/config.yml
        - run
        volumeMounts:
        - name: config
          mountPath: /etc/cloudflared
          readOnly: true
        - name: creds
          mountPath: /etc/cloudflared/creds
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: cloudflared-config
      - name: creds
        secret:
          secretName: cloudflared-creds
```

## Tunnel Troubleshooting

| Issue | Check |
|-------|-------|
| Connection refused | Verify origin service is running on configured port |
| 502 Bad Gateway | Check `originRequest.noTLSVerify` for self-signed certs |
| DNS not resolving | Verify CNAME record points to `<TUNNEL_ID>.cfargotunnel.com` |
| Auth failures | Check credentials file path and permissions |
| Tunnel disconnects | Check cloudflared logs, verify network stability |

```bash
# Debug mode
cloudflared tunnel --loglevel debug run my-tunnel

# Check tunnel status
cloudflared tunnel info my-tunnel

# List all tunnels
cloudflared tunnel list
```
