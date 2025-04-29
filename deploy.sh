#!/bin/bash

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y python3-pip python3-venv nginx

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create systemd service file
sudo tee /etc/systemd/system/social-scraper.service << EOF
[Unit]
Description=Social Scraper API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/social-scrapper-api
Environment="PATH=/home/ubuntu/social-scrapper-api/venv/bin"
ExecStart=/home/ubuntu/social-scrapper-api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create Nginx configuration
sudo tee /etc/nginx/sites-available/social-scraper << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/social-scraper /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Restart services
sudo systemctl daemon-reload
sudo systemctl enable social-scraper
sudo systemctl start social-scraper
sudo systemctl restart nginx 