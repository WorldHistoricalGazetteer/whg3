## Find all files containing given text

### Case-sensitive
```bash
find ./ -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" \) ! -path "./whg/static/*" ! -path "./static/*" -exec grep -lz -P "Grossner" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```

### Non-case-sensitive
```bash
find ./ -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" \) ! -path "./whg/static/*" ! -path "./static/*" -exec grep -lzi -P "grossner" {} + | xargs -0 -I {} echo {} | sort -u | sed "s|^./||"
```

## Running Docker in Windows

### Open WSL in Console
- Run PowerShell as Administrator (right-click)
- Switch to WSL as root user
```sh
wsl -u root
```
- Switch to local WHG directory
```sh
cd /mnt/i/workspace/whg3
```

## SSL Certificates
- Certification is automated using the `python3-certbot-dns-digitalocean` plugin, which allows Certbot to automatically manage DNS-01 challenges by updating DNS records on DigitalOcean.
- The domain must first be set up on DigitalOcean.
- To generate a new certificate:
```sh
sudo certbot certonly --dns-digitalocean --dns-digitalocean-credentials /etc/letsencrypt/digitalocean.ini -d <domain.com>
```
- The certificate and key will be stored locally and updated automatically when necessary.
