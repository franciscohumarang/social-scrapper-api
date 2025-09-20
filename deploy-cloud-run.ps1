# Google Cloud Run Deployment Script for Social Scrapper API (PowerShell)
# This script builds and deploys the application to Google Cloud Run

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [string]$Region = "us-central1",
    [string]$ServiceName = "social-scrapper-api"
)

# Configuration
$ImageName = "gcr.io/$ProjectId/$ServiceName"

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

Write-Status "Starting deployment to Google Cloud Run..."
Write-Status "Project ID: $ProjectId"
Write-Status "Region: $Region"
Write-Status "Service Name: $ServiceName"

# Check if gcloud is installed and authenticated
try {
    $gcloudVersion = gcloud version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud CLI not found"
    }
} catch {
    Write-Error "gcloud CLI is not installed or not in PATH. Please install it first."
    Write-Host "Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
}

# Check if user is authenticated
$activeAccount = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null
if (-not $activeAccount) {
    Write-Error "Not authenticated with gcloud. Please run 'gcloud auth login' first."
    exit 1
}

# Set the project
Write-Status "Setting project to $ProjectId..."
gcloud config set project $ProjectId

# Enable required APIs
Write-Status "Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build the Docker image
Write-Status "Building Docker image..."
docker build -t $ImageName .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed!"
    exit 1
}

# Configure Docker to use gcloud as a credential helper
Write-Status "Configuring Docker authentication..."
gcloud auth configure-docker

# Push the image to Container Registry
Write-Status "Pushing image to Container Registry..."
docker push $ImageName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker push failed!"
    exit 1
}

# Deploy to Cloud Run
Write-Status "Deploying to Cloud Run..."
gcloud run deploy $ServiceName `
    --image $ImageName `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 10 `
    --concurrency 100 `
    --timeout 300 `
    --set-env-vars "SUPABASE_URL=$env:SUPABASE_URL,SUPABASE_ANON_KEY=$env:SUPABASE_ANON_KEY" `
    --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Run deployment failed!"
    exit 1
}

# Get the service URL
$ServiceUrl = gcloud run services describe $ServiceName --region=$Region --format="value(status.url)"

Write-Status "Deployment completed successfully!"
Write-Status "Service URL: $ServiceUrl"
Write-Status "Health check: $ServiceUrl/health"

# Test the health endpoint
Write-Status "Testing health endpoint..."
try {
    $response = Invoke-WebRequest -Uri "$ServiceUrl/health" -Method GET -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Status "✅ Health check passed!"
    } else {
        Write-Warning "⚠️  Health check returned status code: $($response.StatusCode)"
    }
} catch {
    Write-Warning "⚠️  Health check failed. Check the service logs."
    Write-Host "Error: $($_.Exception.Message)"
}

Write-Status "Deployment script completed!"
Write-Host ""
Write-Status "Next steps:"
Write-Host "1. Set up your environment variables in Cloud Run console"
Write-Host "2. Configure your domain (optional)"
Write-Host "3. Set up monitoring and alerting"
Write-Host "4. Test your API endpoints"
