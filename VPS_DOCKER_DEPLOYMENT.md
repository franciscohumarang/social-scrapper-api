# VPS Docker Deployment Guide

This guide covers deploying the Social Scraper API to a VPS using Docker.

## Prerequisites

- VPS with Ubuntu 20.04+ or similar Linux distribution
- SSH access to your VPS
- Domain name (optional, for SSL)
- Basic knowledge of Linux commands

## VPS Setup

### 1. Connect to Your VPS

```bash
ssh root@your-vps-ip
# or
ssh username@your-vps-ip
```

### 2. Update System Packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (optional)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 4. Install Additional Tools

```bash
# Install Git
sudo apt install git -y

# Install Nginx (for reverse proxy)
sudo apt install nginx -y

# Install Certbot (for SSL certificates)
sudo apt install certbot python3-certbot-nginx -y
```

## Application Deployment

### 1. Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/social-scrapper-api
cd /opt/social-scrapper-api

# Clone repository
sudo git clone https://github.com/your-username/social-scrapper-api.git .

# Set proper permissions
sudo chown -R $USER:$USER /opt/social-scrapper-api
```

### 2. Create Environment File

```bash
# Copy the example environment file
cp env.example .env

# Edit the environment file
nano .env
```

The `env.example` file contains all required environment variables with placeholders. Update them with your actual values:

```bash
# REQUIRED: Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Twitter Configuration
TWITTER_CONSUMER_KEY=your_twitter_consumer_key
TWITTER_CONSUMER_SECRET=your_twitter_consumer_secret
TWITTER_API_IO_KEY=your_twitterapi_io_key
TWITTER_PROXY=your_proxy_url
TWITTER_BEARER_TOKEN=your_twitter_bearer_token

# Reddit Configuration
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_reddit_user_agent
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password

# Application Configuration
PORT=8000
PYTHONUNBUFFERED=1
```

### 3. Create Docker Compose File

```bash
nano docker-compose.yml
```

Add the following configuration:

```yaml
version: '3.8'

services:
  social-scrapper-api:
    build: .
    container_name: social-scrapper-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - TWITTER_CONSUMER_KEY=${TWITTER_CONSUMER_KEY}
      - TWITTER_CONSUMER_SECRET=${TWITTER_CONSUMER_SECRET}
      - TWITTER_API_IO_KEY=${TWITTER_API_IO_KEY}
      - TWITTER_PROXY=${TWITTER_PROXY}
      - REDDIT_CLIENT_ID=${REDDIT_CLIENT_ID}
      - REDDIT_CLIENT_SECRET=${REDDIT_CLIENT_SECRET}
      - REDDIT_USER_AGENT=${REDDIT_USER_AGENT}
    volumes:
      - ./logs:/app/logs
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

### 4. Deploy Application

#### Option A: Automated Deployment (Recommended)

```bash
# Make the deployment script executable
chmod +x deploy-vps.sh

# Run the deployment script
./deploy-vps.sh
```

The deployment script will:
- Validate your environment variables
- Choose between development or production mode
- Build and start the containers
- Perform health checks
- Display service information

#### Option B: Manual Deployment

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up -d

# Check if container is running
docker-compose ps

# View logs
docker-compose logs -f
```

#### Production Deployment

For production deployment with Redis caching and Nginx reverse proxy:

```bash
# Use the production compose file
docker-compose -f docker-compose.prod.yml up -d

# Or use the deployment script and choose option 2
./deploy-vps.sh
```

## Nginx Configuration

### 1. Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/social-scrapper-api
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location / {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
```

### 2. Enable Site

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/social-scrapper-api /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

## SSL Certificate Setup

### 1. Obtain SSL Certificate

```bash
# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### 2. Set Up Automatic Renewal

```bash
# Add to crontab
sudo crontab -e

# Add this line
0 12 * * * /usr/bin/certbot renew --quiet
```

## Firewall Configuration

### 1. Configure UFW Firewall

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'

# Allow specific port (if not using Nginx)
sudo ufw allow 8000

# Check status
sudo ufw status
```

## Monitoring and Logs

### 1. View Application Logs

```bash
# View real-time logs
docker-compose logs -f social-scrapper-api

# View last 100 lines
docker-compose logs --tail=100 social-scrapper-api
```

### 2. Monitor Container Status

```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats social-scrapper-api

# Restart container
docker-compose restart social-scrapper-api
```

### 3. Set Up Log Rotation

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/social-scrapper-api
```

Add:

```
/opt/social-scrapper-api/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose restart social-scrapper-api
    endscript
}
```

## Backup and Maintenance

### 1. Create Backup Script

```bash
nano /opt/social-scrapper-api/backup.sh
```

Add:

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/social-scrapper-api"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup application files
tar -czf $BACKUP_DIR/app_$DATE.tar.gz /opt/social-scrapper-api --exclude=logs

# Keep only last 7 days of backups
find $BACKUP_DIR -name "app_*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/app_$DATE.tar.gz"
```

```bash
# Make executable
chmod +x /opt/social-scrapper-api/backup.sh

# Add to crontab for daily backups
crontab -e

# Add this line
0 2 * * * /opt/social-scrapper-api/backup.sh
```

### 2. Update Application

```bash
# Pull latest changes
cd /opt/social-scrapper-api
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### Common Issues

#### 1. Container Won't Start

```bash
# Check logs
docker-compose logs social-scrapper-api

# Check if port is in use
sudo netstat -tulpn | grep :8000

# Kill process using port
sudo kill -9 $(sudo lsof -t -i:8000)
```

#### 2. Permission Issues

```bash
# Fix file permissions
sudo chown -R $USER:$USER /opt/social-scrapper-api

# Fix Docker permissions
sudo chmod 666 /var/run/docker.sock
```

#### 3. Nginx Issues

```bash
# Test Nginx configuration
sudo nginx -t

# Check Nginx status
sudo systemctl status nginx

# Restart Nginx
sudo systemctl restart nginx
```

#### 4. SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate manually
sudo certbot renew --force-renewal
```

### Health Checks

#### 1. Application Health

```bash
# Check if API is responding
curl http://localhost:8000/health

# Check through Nginx
curl http://your-domain.com/health
```

#### 2. Container Health

```bash
# Check container health
docker inspect social-scrapper-api | grep -A 10 "Health"

# Check resource usage
docker stats social-scrapper-api --no-stream
```

## Security Considerations

### 1. Environment Variables

- Never commit `.env` files to version control
- Use strong, unique passwords and API keys
- Regularly rotate API keys and secrets

### 2. Container Security

```bash
# Run container as non-root user (already configured in Dockerfile)
# Use read-only filesystem where possible
# Regularly update base images
```

### 3. Network Security

- Use firewall rules to restrict access
- Enable fail2ban for SSH protection
- Use strong SSH keys instead of passwords

### 4. Monitoring

- Set up log monitoring
- Monitor resource usage
- Set up alerts for service downtime

## Performance Optimization

### 1. Resource Limits

Update `docker-compose.yml`:

```yaml
services:
  social-scrapper-api:
    # ... existing configuration
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
```

### 2. Caching

- Enable Nginx caching for static content
- Use Redis for application-level caching
- Implement database query caching

### 3. Load Balancing

For high-traffic scenarios, consider:
- Multiple container instances
- Load balancer (HAProxy, Nginx)
- Database connection pooling

## Maintenance Commands

### Daily Operations

```bash
# Check service status
docker-compose ps
sudo systemctl status nginx

# View recent logs
docker-compose logs --tail=50 social-scrapper-api

# Check disk space
df -h
```

### Weekly Operations

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean Docker images
docker system prune -f

# Check SSL certificate expiry
sudo certbot certificates
```

### Monthly Operations

```bash
# Review logs for errors
grep -i error /opt/social-scrapper-api/logs/*.log

# Update application
git pull origin main
docker-compose down && docker-compose up -d

# Security audit
sudo apt audit
```

This guide provides a complete setup for deploying your Social Scraper API on a VPS with Docker, including security, monitoring, and maintenance considerations.
