# GitHub + Google Cloud Run Deployment Guide

This guide shows you how to deploy your Social Scrapper API using GitHub with Google Cloud Run and Cloud Build for automatic deployments.

## 🚀 GitHub Integration Overview

Your project is already configured for GitHub deployment with:
- ✅ `cloudbuild.yaml` - Cloud Build configuration
- ✅ `Dockerfile` - Container configuration  
- ✅ `.dockerignore` - Optimized builds
- ✅ Environment variable templates

## Step 1: Push to GitHub

1. **Initialize Git** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Social Scrapper API with Cloud Run support"
   ```

2. **Create GitHub repository**:
   - Go to https://github.com/new
   - Name: `social-scrapper-api` (or your preferred name)
   - Make it **Private** (recommended for API keys)
   - Don't initialize with README (you already have files)

3. **Connect and push**:
   ```bash
   git remote add origin https://github.com/yourusername/social-scrapper-api.git
   git branch -M main
   git push -u origin main
   ```

## Step 2: Set Up Google Cloud Build

1. **Enable Cloud Build API**:
   ```bash
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   ```

2. **Connect GitHub to Cloud Build**:
   - Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
   - Click "Create Trigger"
   - Choose "GitHub (Cloud Build GitHub App)"
   - Authenticate with GitHub
   - Select your repository: `yourusername/social-scrapper-api`

3. **Configure the trigger**:
   - **Name**: `social-scrapper-api-deploy`
   - **Description**: `Deploy Social Scrapper API to Cloud Run`
   - **Event**: Push to a branch
   - **Branch**: `^main$` (deploys on main branch pushes)
   - **Configuration**: Cloud Build configuration file
   - **Location**: `/cloudbuild.yaml`

4. **Set substitution variables**:
   - `_SUPABASE_URL`: Your Supabase project URL
   - `_SUPABASE_ANON_KEY`: Your Supabase anon key

## Step 3: Configure Environment Variables

### Option A: Using Cloud Build Substitution Variables (Recommended)

In your Cloud Build trigger settings, add these substitution variables:

```
_SUPABASE_URL = https://your-project.supabase.co
_SUPABASE_ANON_KEY = your-supabase-anon-key
```

### Option B: Using Secret Manager (More Secure)

1. **Create secrets in Secret Manager**:
   ```bash
   # Create secrets
   echo -n "your-supabase-url" | gcloud secrets create supabase-url --data-file=-
   echo -n "your-supabase-anon-key" | gcloud secrets create supabase-anon-key --data-file=-
   echo -n "your-twitter-api-key" | gcloud secrets create twitter-api-key --data-file=-
   # ... add other secrets
   ```

2. **Update cloudbuild.yaml** to use secrets:
   ```yaml
   # Add this step before the deploy step
   - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
     entrypoint: 'bash'
     args:
       - '-c'
       - |
         # Get secrets
         SUPABASE_URL=$$(gcloud secrets versions access latest --secret="supabase-url")
         SUPABASE_ANON_KEY=$$(gcloud secrets versions access latest --secret="supabase-anon-key")
         
         # Deploy with secrets
         gcloud run deploy social-scrapper-api \
           --image gcr.io/$PROJECT_ID/social-scrapper-api:$COMMIT_SHA \
           --region us-central1 \
           --platform managed \
           --allow-unauthenticated \
           --port 8080 \
           --memory 1Gi \
           --cpu 1 \
           --min-instances 0 \
           --max-instances 10 \
           --concurrency 100 \
           --timeout 300 \
           --set-env-vars "SUPABASE_URL=$$SUPABASE_URL,SUPABASE_ANON_KEY=$$SUPABASE_ANON_KEY"
   ```

## Step 4: Test Automatic Deployment

1. **Make a small change** to your code:
   ```bash
   # Edit main.py or any file
   echo "# Updated $(date)" >> main.py
   ```

2. **Commit and push**:
   ```bash
   git add .
   git commit -m "Test automatic deployment"
   git push origin main
   ```

3. **Watch the deployment**:
   - Go to [Cloud Build History](https://console.cloud.google.com/cloud-build/builds)
   - You should see a new build triggered by your push
   - Click on it to watch the build progress

4. **Check your service**:
   ```bash
   gcloud run services list --region us-central1
   ```

## Step 5: Set Up Additional Environment Variables

After the first deployment, you'll need to add all your API keys:

1. **Go to Cloud Run Console**: https://console.cloud.google.com/run
2. **Click on your service**: `social-scrapper-api`
3. **Click "Edit & Deploy New Revision"**
4. **Go to "Variables & Secrets" tab**
5. **Add all your environment variables**:

```
# Supabase (already set via Cloud Build)
SUPABASE_URL = https://your-project.supabase.co
SUPABASE_ANON_KEY = your-supabase-anon-key

# Twitter API
TWITTER_CONSUMER_KEY = your-twitter-consumer-key
TWITTER_CONSUMER_SECRET = your-twitter-consumer-secret
TWITTER_BEARER_TOKEN = your-twitter-bearer-token
TWITTER_API_IO_KEY = your-twitterapi-io-key
TWITTER_PROXY = your-twitter-proxy

# Reddit API
REDDIT_CLIENT_ID = your-reddit-client-id
REDDIT_CLIENT_SECRET = your-reddit-client-secret
REDDIT_USER_AGENT = your-reddit-user-agent
REDDIT_USERNAME = your-reddit-username
REDDIT_PASSWORD = your-reddit-password
```

6. **Click "Deploy"**

## Step 6: GitHub Actions (Alternative to Cloud Build)

If you prefer GitHub Actions over Cloud Build, create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Google Cloud Run

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Google Auth
      id: auth
      uses: google-github-actions/auth@v1
      with:
        credentials_json: ${{ secrets.GCP_SA_KEY }}
    
    - name: Set up Cloud SDK
      uses: google-github-actions/setup-gcloud@v1
    
    - name: Configure Docker
      run: gcloud auth configure-docker
    
    - name: Build and Push
      run: |
        docker build -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/social-scrapper-api:${{ github.sha }} .
        docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/social-scrapper-api:${{ github.sha }}
    
    - name: Deploy to Cloud Run
      run: |
        gcloud run deploy social-scrapper-api \
          --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/social-scrapper-api:${{ github.sha }} \
          --region us-central1 \
          --platform managed \
          --allow-unauthenticated \
          --port 8080 \
          --memory 1Gi \
          --cpu 1 \
          --min-instances 0 \
          --max-instances 10 \
          --concurrency 100 \
          --timeout 300 \
          --set-env-vars "SUPABASE_URL=${{ secrets.SUPABASE_URL }},SUPABASE_ANON_KEY=${{ secrets.SUPABASE_ANON_KEY }}"
```

## Step 7: Branch Protection and PR Deployments

1. **Set up branch protection**:
   - Go to your GitHub repo → Settings → Branches
   - Add rule for `main` branch
   - Require pull request reviews
   - Require status checks to pass

2. **Deploy from PRs** (optional):
   - Modify your trigger to also deploy from PRs
   - Use different service names for PR deployments
   - Clean up PR deployments automatically

## Step 8: Monitoring and Logs

1. **View build logs**:
   ```bash
   gcloud builds log --stream
   ```

2. **View service logs**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=social-scrapper-api" --limit 50
   ```

3. **Set up monitoring**:
   - Go to [Cloud Monitoring](https://console.cloud.google.com/monitoring)
   - Create alerts for errors, high latency, etc.

## 🔒 Security Best Practices

1. **Use Secret Manager** for sensitive data
2. **Set up IAM** with least privilege
3. **Enable VPC** if you need private networking
4. **Use Cloud Armor** for DDoS protection
5. **Regular security updates** for dependencies

## 🚀 Benefits of This Setup

- **Automatic deployments** on every push to main
- **Rollback capability** through Cloud Run revisions
- **Zero-downtime deployments**
- **Built-in monitoring** and logging
- **Cost-effective** (pay only for usage)
- **Scalable** (auto-scales based on traffic)

## 📝 Next Steps

1. **Test your API** endpoints
2. **Set up custom domain** (optional)
3. **Configure monitoring** alerts
4. **Set up staging environment** (optional)
5. **Add API documentation** (FastAPI auto-generates this)

Your Social Scrapper API is now fully integrated with GitHub and will automatically deploy to Google Cloud Run on every push! 🎉
