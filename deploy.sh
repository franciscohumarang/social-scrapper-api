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
User=root
WorkingDirectory=/root/social-scrapper-api
Environment="PATH=/root/social-scrapper-api/venv/bin"
ExecStart=/root/social-scrapper-api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
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

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    sudo tee .env << EOF
# API Key for authentication
API_KEY=your_api_key_here

# Reddit API credentials
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_reddit_user_agent
EOF
    echo "Please update the .env file with your actual credentials"
fi

# Create twitter_accounts.json if it doesn't exist
if [ ! -f twitter_accounts.json ]; then
    echo "Creating twitter_accounts.json file..."
    sudo tee twitter_accounts.json << EOF
[
    {
        "username": "account1",
        "password": "password1",
        "email": "email1@example.com",
        "email_password": "email_password1"
    }
]
EOF
    echo "Please update the twitter_accounts.json file with your actual Twitter accounts"
fi

# Set proper permissions
sudo chown -R root:root /root/social-scrapper-api
sudo chmod -R 755 /root/social-scrapper-api
sudo chmod 600 .env
sudo chmod 600 twitter_accounts.json

# Restart services
sudo systemctl daemon-reload
sudo systemctl enable social-scraper
sudo systemctl start social-scraper
sudo systemctl restart nginx

# Print status
echo "Deployment completed. Checking service status..."
sudo systemctl status social-scraper
sudo systemctl status nginx

# Print instructions
echo "
Deployment completed! Here's what you need to do next:

1. Edit the .env file with your actual credentials:
   sudo nano .env

2. Edit the twitter_accounts.json file with your Twitter accounts:
   sudo nano twitter_accounts.json

3. Restart the service after updating credentials:
   sudo systemctl restart social-scraper

4. Check the logs if needed:
   sudo journalctl -u social-scraper -f

5. Test the API:
   curl -X POST http://localhost:8000/search \\
        -H \"X-API-KEY: your_api_key\" \\
        -H \"Content-Type: application/json\" \\
        -d '{\"platform\": \"twitter\", \"query\": \"test\"}'
" 