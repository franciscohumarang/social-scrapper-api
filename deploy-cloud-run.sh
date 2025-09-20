#!/bin/bash

# Google Cloud Run Deployment Script for Social Scrapper API
# This script builds and deploys the application to Google Cloud Run

set -e  # Exit on any error

# Configuration
PROJECT_ID=""
REGION="us-central1"
SERVICE_NAME="social-scrapper-api"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    print_error "PROJECT_ID is not set. Please set it in this script or as an environment variable."
    echo "Usage: PROJECT_ID=your-project-id ./deploy-cloud-run.sh"
    exit 1
fi

print_status "Starting deployment to Google Cloud Run..."
print_status "Project ID: $PROJECT_ID"
print_status "Region: $REGION"
print_status "Service Name: $SERVICE_NAME"

# Check if gcloud is installed and authenticated
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first."
    echo "Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    print_error "Not authenticated with gcloud. Please run 'gcloud auth login' first."
    exit 1
fi

# Set the project
print_status "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable required APIs
print_status "Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build the Docker image
print_status "Building Docker image..."
docker build -t $IMAGE_NAME .

# Configure Docker to use gcloud as a credential helper
print_status "Configuring Docker authentication..."
gcloud auth configure-docker

# Push the image to Container Registry
print_status "Pushing image to Container Registry..."
docker push $IMAGE_NAME

# Deploy to Cloud Run
print_status "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --concurrency 100 \
    --timeout 300 \
    --set-env-vars "SUPABASE_URL=$SUPABASE_URL,SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" \
    --quiet

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

print_status "Deployment completed successfully!"
print_status "Service URL: $SERVICE_URL"
print_status "Health check: $SERVICE_URL/health"

# Test the health endpoint
print_status "Testing health endpoint..."
if curl -f -s "$SERVICE_URL/health" > /dev/null; then
    print_status "✅ Health check passed!"
else
    print_warning "⚠️  Health check failed. Check the service logs."
fi

print_status "Deployment script completed!"
echo ""
print_status "Next steps:"
echo "1. Set up your environment variables in Cloud Run console"
echo "2. Configure your domain (optional)"
echo "3. Set up monitoring and alerting"
echo "4. Test your API endpoints"
