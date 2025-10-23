# Social Scraper API

A unified API for scraping social media content from Twitter and Reddit, with direct messaging capabilities.

## Features

- **Search**: Search tweets and Reddit posts/comments
- **Direct Messaging**: Send direct messages to Twitter users
- **Caching**: Built-in caching for Twitter search results
- **Rate Limiting**: Automatic rate limit handling

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
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
TWITTER_CONSUMER_KEY=your_twitter_consumer_key
TWITTER_CONSUMER_SECRET=your_twitter_consumer_secret
TWITTER_API_IO_KEY=your_twitterapi_io_key
TWITTER_PROXY=your_proxy_url
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
# Test search endpoint (requires Supabase JWT authentication)
curl -X POST "http://your-ec2-ip/search" \
     -H "Authorization: Bearer your_supabase_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"platform": "reddit", "query": "test", "limit": 10}'

# Test DM endpoint (requires Supabase JWT authentication)
curl -X POST "http://your-ec2-ip/send-dm" \
     -H "Authorization: Bearer your_supabase_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"platform": "titter", "recipient_id": "123456789", "message": "Hello from API!"}'
```

**Note**: All endpoints now require Supabase JWT authentication. User credentials (Twitter/Reddit) are stored encrypted in the database and retrieved automatically based on the authenticated user.

## API Endpoints
w
### POST /search
Search for content on Twitter or Reddit.

**Headers:**
- `Authorization`: Bearer token (Supabase JWT token - required for all requests)

**Body:**
```json
{
  "platform": "twitter|reddit",
  "query": "search term",
  "limit": 20,
  "subreddit": "all",
  "sort": "relevance",
  "product": "Latest"
}
```

**Twitter Response includes:**
```json
{
  "results": [
    {
      "platform": "twitter",
      "id": "tweet_id",
      "author": "username",
      "author_id": "123456789",  // This is the recipient_id for DMs
      "content": "tweet content",
      "created": "2023-01-01T00:00:00Z",
      "likes": 10,
      "retweets": 5,
      "url": "https://twitter.com/username/status/tweet_id"
    }
  ],
  "source": "api"
}
```

**Reddit Response includes:**
```json
{
  "results": [
    {
      "platform": "reddit",
      "type": "submission|comment",
      "id": "post_id",
      "author": "username",
      "author_id": "username",  // This is the recipient_id for DMs
      "content": "post content",
      "created": 1640995200,
      "score": 100,
      "num_comments": 25,  // For submissions only
      "url": "https://reddit.com/r/subreddit/comments/post_id"
    }
  ]
}
```

### GET /user/{username}
Get Twitter user information by username (useful for getting recipient_id for DMs).

**Headers:**
- `Authorization`: Bearer token (Supabase JWT token - required)

**Response:**
```json
{
  "id": "123456789",  // This is the recipient_id for DMs
  "username": "username",
  "name": "Display Name",
  "description": "User bio",
  "profile_image_url": "https://pbs.twimg.com/profile_images/..."
}
```

### GET /user/{platform}/{username}
Get user information by username for a specific platform.

**Headers:**
- `Authorization`: Bearer token (Supabase JWT token - required)

**Twitter Response:**
```json
{
  "id": "123456789",  // This is the recipient_id for DMs
  "username": "username",
  "name": "Display Name",
  "description": "User bio",
  "profile_image_url": "https://pbs.twimg.com/profile_images/..."
}
```

**Reddit Response:**
```json
{
  "id": "username",  // This is the recipient_id for DMs
  "username": "username",
  "name": "username",
  "description": "Reddit user",
  "platform": "reddit"
}
```

### POST /send-dm
Send a direct message to a Twitter or Reddit user.

**Headers:**
- `Authorization`: Bearer token (Supabase JWT token - required)

**Note**: User credentials (Twitter username/email/password or Reddit username/password) are stored encrypted in the database and retrieved automatically based on the authenticated user.

**Body:**
```json
{
  "platform": "twitter|reddit",
  "recipient_id": "123456789",  // Twitter user ID or Reddit username
  "message": "Your message here",
  "media_ids": ["media_id_1"],  // Optional, Twitter only
  "subject": "Message subject"  // Optional, Reddit only
}
```

**Response:**

**Twitter DM Response:**
```json
{
  "success": true,
  "recipient_id": "123456789",
  "message": "Your message here",
  "media_ids": ["media_id_1"],
  "response": {
    // TwitterAPI.io response data
  }
}
```

**Reddit DM Response:**
```json
{
  "success": true,
  "recipient_username": "username",
  "sender_username": "your_username",
  "message": "Your message here",
  "subject": "Message subject",
  "platform": "reddit"
}
```

**Authentication:**
All requests now use Supabase JWT authentication. User credentials are stored encrypted in the database and retrieved automatically based on the authenticated user.

## How to Get recipient_id for DMs

There are two ways to get the `recipient_id` needed for sending direct messages:

### Method 1: From Search Results
When you search for content, each result includes the `author_id`:

```bash
# Search for tweets
curl -X POST "http://your-server/search" \
     -H "Authorization: Bearer your_supabase_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"platform": "twitter", "query": "python", "limit": 5}'

# Search for Reddit posts
curl -X POST "http://your-server/search" \
     -H "Authorization: Bearer your_supabase_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"platform": "reddit", "query": "python", "limit": 5}'

# Use the author_id from the response as recipient_id
```

### Method 2: Get User by Username
Use the `/user/{platform}/{username}` endpoint to get user information:

```bash
# Get Twitter user info by username
curl -X GET "http://your-server/user/twitter/elonmusk" \
     -H "Authorization: Bearer your_supabase_jwt_token"

# Get Reddit user info by username
curl -X GET "http://your-server/user/reddit/username" \
     -H "Authorization: Bearer your_supabase_jwt_token"
```

### Example Workflow

**Twitter DM:**
```bash
# 1. Get user ID by username
curl -X GET "http://your-server/user/twitter/elonmusk" \
     -H "Authorization: Bearer your_supabase_jwt_token"

# Response: {"id": "44196397", "username": "elonmusk", ...}

# 2. Send DM using the user ID
curl -X POST "http://your-server/send-dm" \
     -H "Authorization: Bearer your_supabase_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"platform": "twitter", "recipient_id": "44196397", "message": "Hello!"}'
```

**Reddit DM:**
```bash
# 1. Get user info by username
curl -X GET "http://your-server/user/reddit/username" \
     -H "Authorization: Bearer your_supabase_jwt_token"

# Response: {"id": "username", "username": "username", ...}

# 2. Send DM using the username
curl -X POST "http://your-server/send-dm" \
     -H "Authorization: Bearer your_supabase_jwt_token" \
     -H "Content-Type: application/json" \
     -d '{"platform": "reddit", "recipient_id": "username", "message": "Hello!", "subject": "Test message"}'
```

### GET /usage
Get current usage statistics and rate limits for the authenticated user.

**Headers:**
- `Authorization`: Bearer token (Supabase JWT token - required)

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "user_uuid",
    "plan": "free|premium|pro",
    "usage_stats": {
      "search": {
        "twitter": {
          "count": 15,
          "limit": 100,
          "remaining": 85,
          "reset_time": "2023-01-01T00:00:00Z"
        },
        "reddit": {
          "count": 8,
          "limit": 100,
          "remaining": 92,
          "reset_time": "2023-01-01T00:00:00Z"
        }
      },
      "dm": {
        "twitter": {
          "count": 3,
          "limit": 10,
          "remaining": 7,
          "reset_time": "2023-01-01T00:00:00Z"
        },
        "reddit": {
          "count": 1,
          "limit": 10,
          "remaining": 9,
          "reset_time": "2023-01-01T00:00:00Z"
        }
      }
    }
  }
}
```

### GET /health
Health check endpoint for monitoring and load balancers.

**Headers:**
- None required

**Response:**
```json
{
  "status": "healthy",
  "service": "social-scrapper-api",
  "timestamp": "2023-01-01T00:00:00Z"
}
```

## Authentication Setup

The API now uses **Supabase JWT authentication** for all endpoints. User credentials (Twitter/Reddit) are stored encrypted in the database.

### Supabase Setup

1. **Create a Supabase project** at https://supabase.com/
2. **Get your project credentials**:
   - Project URL (`SUPABASE_URL`)
   - Anonymous key (`SUPABASE_ANON_KEY`)
3. **Set up authentication**:
   - Enable email/password authentication in Supabase Auth settings
   - Users will authenticate via Supabase Auth and receive JWT tokens
4. **Database setup**:
   - Create `users` table for user profiles
   - Create `settings` table for encrypted credentials
   - Set up Row Level Security (RLS) policies

### Getting JWT Tokens

Users authenticate through Supabase Auth and receive JWT tokens:

```bash
# Example: User login (handled by your frontend)
curl -X POST "https://your-project.supabase.co/auth/v1/token?grant_type=password" \
     -H "apikey: your_supabase_anon_key" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "password"}'

# Response includes access_token (JWT) to use in API requests
```

## Twitter API Setup

To use the DM functionality, you need:

1. **Twitter Developer Account**: Apply at https://developer.twitter.com/
2. **App Credentials**: Get Consumer Key and Consumer Secret
3. **User Access Tokens**: Generate Access Token and Access Token Secret
4. **Bearer Token**: For search functionality

### Getting Twitter Credentials

1. Go to https://developer.twitter.com/
2. Create a new app
3. Navigate to "Keys and Tokens"
4. Generate:
   - Consumer Key and Secret
   - Access Token and Secret (with Read and Write permissions)
   - Bearer Token

## Reddit API Setup

Reddit API requires different authentication methods for different operations:

### Read-Only Operations (Search)
For searching Reddit content, you need:
1. **Reddit Developer Account**: Go to https://www.reddit.com/prefs/apps
2. **Create a "script" application** (not "web" or "installed")
3. **Get credentials**:
   - Client ID (under the app name)
   - Client Secret (click "secret" to reveal)
   - User Agent (format: `platform:app_name:version:username`)

### DM Operations (Sending Messages)
For sending direct messages, you need a **script application** with:
1. **Script Application**: Same as above, but must be "script" type
2. **Reddit Account Credentials**:
   - Username of the Reddit account
   - Password of the Reddit account
3. **Permissions**: The Reddit account must have permission to send messages

### Getting Reddit Credentials

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in the details:
   - **Name**: Your app name
   - **Type**: Select "script"
   - **Description**: Brief description
   - **About URL**: Can be blank
   - **Redirect URI**: Can be blank
4. Click "Create app"
5. Note down:
   - **Client ID**: The string under your app name
   - **Client Secret**: Click "secret" to reveal
   - **User Agent**: Use format `platform:app_name:version:username`

### Important Notes for Reddit DMs

- **Script Application Required**: Only script applications can send DMs
- **Account Credentials**: You need the username and password of a Reddit account
- **Rate Limits**: Reddit has strict rate limits for messaging
- **User Privacy**: Users can disable DMs from non-friends
- **Two-Factor Authentication**: If your Reddit account has 2FA enabled, you may need to use refresh tokens instead of password authentication

## Troubleshooting

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
   - For DM errors, verify Twitter credentials and permissions

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