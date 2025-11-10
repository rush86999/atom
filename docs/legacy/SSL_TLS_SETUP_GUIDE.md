# SSL/TLS Setup Guide for Production

## Certificate Options

### 1. Let's Encrypt (Recommended - Free)
```bash
# Install certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d YOUR_DOMAIN.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 2. Commercial Certificate
- Purchase from providers like DigiCert, Comodo, etc.
- Generate CSR and submit to certificate authority
- Install issued certificate

## NGINX Configuration
Create `/etc/nginx/sites-available/atom`:

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name YOUR_DOMAIN.com;

    ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5058;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Verification
```bash
# Test SSL configuration
openssl s_client -connect YOUR_DOMAIN.com:443

# Check certificate
openssl x509 -in /path/to/certificate.crt -text -noout
```

Generated: 2025-11-01 12:29:48
