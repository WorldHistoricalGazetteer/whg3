### Enable/Disable Sites

#### Sites Available
```bash
ls /etc/nginx/sites-available/
```

#### Sites Enabled
```bash
ls /etc/nginx/sites-enabled/
```

#### Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/<example.com> /etc/nginx/sites-enabled/
```

#### Disable Site
```bash
sudo rm /etc/nginx/sites-available/<example.com>
```

#### Test Configuration
```bash
sudo nginx -t
```

#### Reload Nginx
```bash
sudo systemctl reload nginx
```

---

### Configuration Files

#### Edit Site Configuration
```bash
 sudo nano /etc/nginx/sites-available/<example.com>
```

#### Reload Nginx
```bash
sudo systemctl reload nginx
```

#### Sample Configuration
```
# dev.whgazetteer.org
# run with gunicorn -b :8004 --env DJANGO_SETTINGS_MODULE=whg.settings whg.wsgi 2 &

server {
    server_name dev.whgazetteer.org;

    # Redirect HTTP to HTTPS
    listen 80;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name dev.whgazetteer.org;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/dev.whgazetteer.org/fullchain.pem; # Managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/dev.whgazetteer.org/privkey.pem; # Managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # Managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # Managed by Certbot

    location / {
        # CORS Settings
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'authorization,x-csrftoken,DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
        if ($request_method = 'POST') {
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'authorization,x-csrftoken,DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
        }
        if ($request_method = 'GET') {
            add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'authorization,x-csrftoken,DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
        }

        # Proxy settings
        proxy_pass http://localhost:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static content and media files
    location /data_dumps/ {
        alias /home/whgadmin/sites/data_dumps/;
        autoindex off;  # Disable directory listing
    }

    location /media/ {
        root /home/whgadmin/sites/dev-whgazetteer-org/media/;
    }

    location /static/ {
        alias /home/whgadmin/sites/dev-whgazetteer-org/static/;
    }
}

```
