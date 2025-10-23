#!/bin/bash

# Social Scraper API - VPS Deployment Script
# This script automates the deployment process on a VPS

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="social-scrapper-api"
APP_DIR="/opt/social-scrapper-api"
COMPOSE_FILE="docker-compose.yml"
PROD_COMPOSE_FILE="docker-compose.prod.yml"

echo -e "${GREEN}🚀 Starting Social Scraper API Deployment${NC}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create application directory if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    print_status "Creating application directory: $APP_DIR"
    sudo mkdir -p "$APP_DIR"
    sudo chown $USER:$USER "$APP_DIR"
fi

# Navigate to application directory
cd "$APP_DIR"

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found!"
    if [ -f "env.example" ]; then
        print_status "Copying env.example to .env"
        cp env.example .env
        print_warning "Please edit .env file with your actual configuration values"
        print_warning "Run: nano .env"
        exit 1
    else
        print_error "No env.example file found. Please create a .env file with required environment variables."
        exit 1
    fi
fi

# Validate required environment variables
print_status "Validating environment variables..."
source .env

required_vars=("SUPABASE_URL" "SUPABASE_ANON_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" = "your_${var,,}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    print_error "Missing or invalid environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    print_error "Please update your .env file with valid values"
    exit 1
fi

print_status "Environment variables validated successfully"

# Choose deployment mode
echo ""
echo "Choose deployment mode:"
echo "1) Development (docker-compose.yml)"
echo "2) Production (docker-compose.prod.yml with Redis and Nginx)"
read -p "Enter your choice (1 or 2): " choice

case $choice in
    1)
        COMPOSE_FILE_TO_USE="$COMPOSE_FILE"
        print_status "Using development configuration"
        ;;
    2)
        COMPOSE_FILE_TO_USE="$PROD_COMPOSE_FILE"
        print_status "Using production configuration"
        ;;
    *)
        print_error "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE_TO_USE" ]; then
    print_error "Compose file $COMPOSE_FILE_TO_USE not found!"
    exit 1
fi

# Stop existing containers
print_status "Stopping existing containers..."
docker-compose -f "$COMPOSE_FILE_TO_USE" down 2>/dev/null || true

# Pull latest changes if it's a git repository
if [ -d ".git" ]; then
    print_status "Pulling latest changes from git..."
    git pull origin main 2>/dev/null || print_warning "Could not pull latest changes"
fi

# Build and start containers
print_status "Building and starting containers..."
docker-compose -f "$COMPOSE_FILE_TO_USE" build --no-cache
docker-compose -f "$COMPOSE_FILE_TO_USE" up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check if services are running
print_status "Checking service status..."
if docker-compose -f "$COMPOSE_FILE_TO_USE" ps | grep -q "Up"; then
    print_status "✅ Services are running successfully!"
else
    print_error "❌ Some services failed to start"
    print_status "Checking logs..."
    docker-compose -f "$COMPOSE_FILE_TO_USE" logs
    exit 1
fi

# Test health endpoint
print_status "Testing health endpoint..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_status "✅ Health check passed!"
else
    print_warning "⚠️  Health check failed, but services might still be starting"
fi

# Display service information
echo ""
print_status "🎉 Deployment completed successfully!"
echo ""
echo "Service Information:"
echo "==================="
echo "Application URL: http://localhost:8000"
echo "Health Check: http://localhost:8000/health"
echo ""

if [ "$COMPOSE_FILE_TO_USE" = "$PROD_COMPOSE_FILE" ]; then
    echo "Production Services:"
    echo "- API: http://localhost:8000"
    echo "- Redis: localhost:6379"
    echo "- Nginx: http://localhost:80 (redirects to HTTPS)"
    echo ""
    print_warning "Note: SSL certificates need to be configured for HTTPS"
fi

echo "Useful Commands:"
echo "================"
echo "View logs: docker-compose -f $COMPOSE_FILE_TO_USE logs -f"
echo "Stop services: docker-compose -f $COMPOSE_FILE_TO_USE down"
echo "Restart services: docker-compose -f $COMPOSE_FILE_TO_USE restart"
echo "Update services: docker-compose -f $COMPOSE_FILE_TO_USE pull && docker-compose -f $COMPOSE_FILE_TO_USE up -d"
echo ""

print_status "Deployment script completed!"
