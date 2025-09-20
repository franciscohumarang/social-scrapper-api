# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server locally
python main.py
# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# For production deployment on EC2
chmod +x deploy.sh
./deploy.sh
```

### Testing the API
```bash
# Test search endpoint (requires authentication via Supabase JWT)
curl -X POST "http://localhost:8000/search" \
     -H "Authorization: Bearer <supabase_jwt_token>" \
     -H "Content-Type: application/json" \
     -d '{"platform": "reddit", "query": "test"}'

# Test DM endpoint (requires authentication via Supabase JWT)
curl -X POST "http://localhost:8000/send-dm" \
     -H "Authorization: Bearer <supabase_jwt_token>" \
     -H "Content-Type: application/json" \
     -d '{"platform": "reddit", "recipient_id": "username", "message": "Hello!", "subject": "Test"}'
```

### Service Management (Production)
```bash
# Check service status
sudo systemctl status social-scraper

# View logs
sudo journalctl -u social-scraper -f

# Restart service after code changes
sudo systemctl restart social-scraper

# Check Nginx status
sudo systemctl status nginx
```

## Architecture Overview

### Core Components

**FastAPI Application** (`main.py`): 
- Main API server with Supabase JWT authentication
- Unified endpoints for Twitter and Reddit operations
- Built-in rate limiting and usage tracking
- CORS-enabled for web client integration

**Authentication System**:
- Uses Supabase JWT tokens for all endpoint authentication
- `get_current_user()` dependency extracts user data and settings
- No API key headers for basic endpoints - all auth via Bearer tokens

**Rate Limiting** (`rate_limiter.py`):
- Database-backed rate limiting using Supabase functions
- Plan-based limits (free, scout, hunter) for searches and DMs
- Automatic usage tracking and reset cycles
- Integrated with all API endpoints

**Credential Management** (`decrypt_credentials.py`):
- Server-side AES-256-GCM encryption for sensitive credentials
- Deterministic key derivation from JWT user data
- Compatible with client-side TypeScript encryption
- Handles Twitter/Reddit API credentials securely

### Data Flow

1. **Authentication**: All requests require Supabase JWT in Authorization header
2. **User Resolution**: JWT decoded to get user ID and fetch settings from database
3. **Rate Limiting**: Usage checked against plan limits before processing
4. **Credential Decryption**: User's encrypted API credentials decrypted using JWT-derived keys
5. **Platform Integration**: Request forwarded to Twitter/Reddit APIs using decrypted credentials
6. **Usage Tracking**: Successful requests increment usage counters in database

### Platform Integrations

**Twitter Integration**:
- Uses TwitterAPI.io for search functionality
- Direct messaging via TwitterAPI.io with login cookie authentication
- User lookup via Twitter API v2 with Bearer tokens
- Credentials: username, email, password (encrypted), API keys

**Reddit Integration**:
- asyncpraw for async Reddit API operations
- Search across subreddits and comments
- Direct messaging using script application credentials
- Credentials: client_id, client_secret, username, password (encrypted)

### Database Schema

**Users Table**: Stores user profiles and subscription plans
**Settings Table**: Stores encrypted API credentials and user preferences
**Usage Stats**: Tracks API usage with automatic reset cycles (handled by Supabase functions)

Rate limiting functions:
- `get_user_usage_stats()`: Gets current usage with automatic resets
- `increment_usage_counter()`: Records API usage events

### Security Model

- All credentials encrypted at rest using AES-256-GCM
- Key derivation based on user JWT data (deterministic, no stored keys)
- Rate limiting prevents abuse and ensures fair usage
- Supabase RLS (Row Level Security) enforces data isolation
- No plaintext credentials in environment variables for user-specific operations

### API Endpoints

**POST /search**: Search Twitter or Reddit (requires JWT auth)
**POST /send-dm**: Send direct messages (requires JWT auth)  
**GET /user/{platform}/{username}**: Get user info for DMs (requires JWT auth)
**GET /usage**: Get current usage statistics (requires JWT auth)

All endpoints use Supabase JWT authentication and return structured JSON responses with proper error handling.

### Environment Variables

Required for server operation:
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `TWITTER_CONSUMER_KEY`: Twitter app consumer key
- `TWITTER_CONSUMER_SECRET`: Twitter app consumer secret
- `TWITTER_API_IO_KEY`: TwitterAPI.io service key
- `TWITTER_PROXY`: Proxy for Twitter operations
- `REDDIT_CLIENT_ID`: Reddit app client ID
- `REDDIT_CLIENT_SECRET`: Reddit app client secret
- `REDDIT_USER_AGENT`: Reddit API user agent string

User-specific credentials are stored encrypted in the database, not in environment variables.