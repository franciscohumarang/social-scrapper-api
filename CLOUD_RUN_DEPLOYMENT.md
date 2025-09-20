# Google Cloud Run Deployment Guide

This guide will help you deploy your Social Scrapper API to Google Cloud Run.

## Prerequisites

1. **Google Cloud Account**: You need a Google Cloud account with billing enabled
2. **Google Cloud CLI**: Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
3. **Docker**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
4. **Git**: For version control (optional but recommended)

## Project Structure

Your project now includes the following files for Cloud Run deployment:

```
social-scrapper-api/
├── Dockerfile                 # Container configuration
├── .dockerignore             # Docker build exclusions
├── cloudbuild.yaml           # Cloud Build configuration
├── deploy-cloud-run.sh       # Bash deployment script
├── deploy-cloud-run.ps1      # PowerShell deployment script
├── env.cloudrun.template     # Environment variables template
├── requirements.txt          # Python dependencies
└── main.py                   # Your FastAPI application
```

## Step 1: Set Up Google Cloud Project

1. **Create a new project** (or use existing):
   ```bash
   gcloud projects create your-project-id --name="Social Scrapper API"
   ```

2. **Set your project ID**:
   ```bash
   gcloud config set project your-project-id
   ```

3. **Enable billing** for your project in the [Google Cloud Console](https://console.cloud.google.com/)

## Step 2: Configure Environment Variables

1. **Copy the environment template**:
   ```bash
   cp env.cloudrun.template .env
   ```

2. **Edit the `.env` file** with your actual credentials:
   ```bash
   # Required
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-supabase-anon-key
   
   # Twitter API (get from https://developer.twitter.com/)
   TWITTER_CONSUMER_KEY=your-consumer-key
   TWITTER_CONSUMER_SECRET=your-consumer-secret
   TWITTER_BEARER_TOKEN=your-bearer-token
   TWITTER_API_IO_KEY=your-twitterapi-io-key
   TWITTER_PROXY=your-proxy-url
   
   # Reddit API (get from https://www.reddit.com/prefs/apps/)
   REDDIT_CLIENT_ID=your-reddit-client-id
   REDDIT_CLIENT_SECRET=your-reddit-client-secret
   REDDIT_USER_AGENT=your-app-name/1.0
   REDDIT_USERNAME=your-reddit-username
   REDDIT_PASSWORD=your-reddit-password
   ```

## Step 3: Deploy to Cloud Run

### Option A: Using the Deployment Script (Recommended)

#### For Windows (PowerShell):
```powershell
# Set your project ID
$env:PROJECT_ID = "your-project-id"

# Set environment variables
$env:SUPABASE_URL = "your-supabase-url"
$env:SUPABASE_ANON_KEY = "your-supabase-anon-key"

# Run deployment
.\deploy-cloud-run.ps1 -ProjectId "your-project-id"
```

#### For Linux/Mac (Bash):
```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export SUPABASE_URL="your-supabase-url"
export SUPABASE_ANON_KEY="your-supabase-anon-key"

# Make script executable and run
chmod +x deploy-cloud-run.sh
./deploy-cloud-run.sh
```

### Option B: Manual Deployment

1. **Build the Docker image**:
   ```bash
   docker build -t gcr.io/your-project-id/social-scrapper-api .
   ```

2. **Push to Container Registry**:
   ```bash
   gcloud auth configure-docker
   docker push gcr.io/your-project-id/social-scrapper-api
   ```

3. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy social-scrapper-api \
     --image gcr.io/your-project-id/social-scrapper-api \
     --region us-central1 \
     --platform managed \
     --allow-unauthenticated \
     --port 8080 \
     --memory 1Gi \
     --cpu 1 \
     --min-instances 0 \
     --max-instances 10 \
     --concurrency 100 \
     --timeout 300
   ```

4. **Set environment variables**:
   ```bash
   gcloud run services update social-scrapper-api \
     --region us-central1 \
     --set-env-vars "SUPABASE_URL=your-supabase-url,SUPABASE_ANON_KEY=your-supabase-anon-key"
   ```

## Step 4: Configure Environment Variables in Cloud Run

After deployment, you need to set all your environment variables:

1. **Go to Cloud Run Console**: https://console.cloud.google.com/run
2. **Click on your service**: `social-scrapper-api`
3. **Click "Edit & Deploy New Revision"**
4. **Go to "Variables & Secrets" tab**
5. **Add all environment variables** from your `.env` file
6. **Click "Deploy"**

## Step 5: Test Your Deployment

1. **Get your service URL**:
   ```bash
   gcloud run services describe social-scrapper-api --region us-central1 --format="value(status.url)"
   ```

2. **Test the health endpoint**:
   ```bash
   curl https://your-service-url/health
   ```

3. **Test authentication** (replace with your actual JWT token):
   ```bash
   curl -X GET "https://your-service-url/usage" \
     -H "Authorization: Bearer your-jwt-token"
   ```

## Step 6: Configure Custom Domain (Optional)

1. **Map a custom domain**:
   ```bash
   gcloud run domain-mappings create \
     --service social-scrapper-api \
     --domain api.yourdomain.com \
     --region us-central1
   ```

2. **Follow the DNS configuration instructions** provided by Google Cloud

## Step 7: Set Up Monitoring and Logging

1. **View logs**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=social-scrapper-api" --limit 50
   ```

2. **Set up alerts** in the [Cloud Monitoring Console](https://console.cloud.google.com/monitoring)

## Step 8: Continuous Deployment (Optional)

To set up automatic deployments when you push to your repository:

1. **Create a Cloud Build trigger**:
   ```bash
   gcloud builds triggers create github \
     --repo-name=your-repo-name \
     --repo-owner=your-github-username \
     --branch-pattern="^main$" \
     --build-config=cloudbuild.yaml
   ```

2. **Set substitution variables** in the trigger:
   - `_SUPABASE_URL`: Your Supabase URL
   - `_SUPABASE_ANON_KEY`: Your Supabase anon key

## Troubleshooting

### Common Issues:

1. **Build fails**: Check that all dependencies are in `requirements.txt`
2. **Service won't start**: Check environment variables are set correctly
3. **Health check fails**: Verify the `/health` endpoint is working
4. **Authentication errors**: Check Supabase configuration

### View Logs:
```bash
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=social-scrapper-api" --limit 100 --format="table(timestamp,severity,textPayload)"
```

### Debug Locally:
```bash
# Build and run locally
docker build -t social-scrapper-api .
docker run -p 8080:8080 --env-file .env social-scrapper-api
```

## Cost Optimization

- **Min instances**: Set to 0 to avoid costs when not in use
- **Max instances**: Adjust based on your traffic
- **Memory/CPU**: Start with 1Gi/1 CPU, adjust as needed
- **Concurrency**: Higher values = fewer instances needed

## Security Best Practices

1. **Use Secret Manager** for sensitive environment variables
2. **Enable IAM** for fine-grained access control
3. **Set up VPC** if you need private networking
4. **Enable Cloud Armor** for DDoS protection
5. **Use HTTPS** (enabled by default on Cloud Run)

## Next Steps

1. **Set up monitoring** and alerting
2. **Configure custom domain** if needed
3. **Set up CI/CD** pipeline
4. **Implement rate limiting** (already included in your app)
5. **Add API documentation** (FastAPI auto-generates this)

## Support

- **Google Cloud Run Documentation**: https://cloud.google.com/run/docs
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Supabase Documentation**: https://supabase.com/docs

Your Social Scrapper API is now ready for production on Google Cloud Run! 🚀
