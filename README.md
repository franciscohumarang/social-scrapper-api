# Social Scraper API

A unified API for scraping social media content from Twitter and Reddit.

## Deployment to EC2

### Prerequisites
- AWS EC2 instance (Ubuntu recommended)
- SSH access to the instance
- Git installed on your local machine

### Deployment Steps

1. **Connect to your EC2 instance**
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

2. **Clone the repository**
```bash
git clone https://github.com/your-username/social-scrapper-api.git
cd social-scrapper-api
```

3. **Make the deployment script executable**
```bash
chmod +x deploy.sh
```

4. **Run the deployment script**
```bash
./deploy.sh
```

5. **Set up environment variables**
```bash
# Create .env file
nano .env

# Add the following variables:
API_KEY=your_api_key
X_USERNAME=your_twitter_username
X_PASSWORD=your_twitter_password
X_EMAIL=your_twitter_email
X_EMAIL_PASSWORD=your_twitter_email_password
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_reddit_user_agent
```

6. **Restart the service**
```bash
sudo systemctl restart social-scraper
```

### Verifying the Deployment

1. **Check service status**
```bash
sudo systemctl status social-scraper
```

2. **Check Nginx status**
```bash
sudo systemctl status nginx
```

3. **Test the API**
```bash
curl -X POST "http://your-ec2-ip/search" \
     -H "X-API-KEY: your_api_key" \
     -H "Content-Type: application/json" \
     -d '{"platform": "reddit", "query": "test"}'
```

### Troubleshooting

1. **Check service logs**
```bash
sudo journalctl -u social-scraper -f
```

2. **Check Nginx logs**
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

3. **Common issues**:
   - If the service fails to start, check the logs
   - If Nginx returns 502, ensure the service is running
   - If you can't connect, check security group settings

### Security Considerations

1. **Update security group**:
   - Allow inbound traffic on port 80 (HTTP)
   - Allow inbound traffic on port 443 (HTTPS, if using SSL)
   - Allow inbound traffic on port 22 (SSH)

2. **Set up SSL** (recommended):
   - Install Certbot
   - Obtain SSL certificate
   - Configure Nginx for HTTPS

3. **Regular maintenance**:
   - Keep system updated
   - Monitor logs
   - Backup database regularly 