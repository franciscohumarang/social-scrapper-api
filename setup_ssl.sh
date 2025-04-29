#!/bin/bash

# Install Certbot and Nginx plugin
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# Stop Nginx temporarily
sudo systemctl stop nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Update Nginx configuration
sudo tee /etc/nginx/sites-available/social-scraper << EOF
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Restart Nginx
sudo systemctl start nginx
sudo systemctl restart nginx

# Set up automatic renewal
echo "0 0 * * * root certbot renew --quiet" | sudo tee -a /etc/crontab > /dev/null 