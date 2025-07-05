import asyncio
import os
from fastapi import FastAPI, HTTPException, Header
import aiohttp
import praw
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import json
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import random
import brotli
import ssl
import tweepy

load_dotenv()

app = FastAPI()

# Cache for Twitter results
twitter_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

class SearchQuery(BaseModel):
    platform: str  # 'twitter' or 'reddit'
    query: str
    limit: Optional[int] = 20
    subreddit: Optional[str] = "all"  # Reddit-specific
    sort: Optional[str] = "relevance"  # Reddit: relevance, hot, top, new, comments
    product: Optional[str] = "Latest"  # Twitter: Top, Latest, Media

class DirectMessageRequest(BaseModel):
    platform: str  # 'twitter' or 'reddit'
    recipient_id: str  # Twitter user ID or Reddit username of the recipient
    message: str  # The message to send
    media_ids: Optional[List[str]] = None  # Optional media IDs to attach (Twitter only)
    subject: Optional[str] = None  # Optional subject for Reddit messages

def init_twitter_v1_api(bearer_token: str, access_token: str = None, access_token_secret: str = None):
    """
    Initialize Twitter API v1 client for DM functionality
    Requires both Bearer Token and User Access Tokens for DM operations
    """
    try:
        # For DM operations, we need user access tokens (not just bearer token)
        if not access_token or not access_token_secret:
            raise ValueError("User Access Token and Secret are required for DM operations")
        
        # Create API v1.1 client
        auth = tweepy.OAuthHandler(
            consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET")
        )
        auth.set_access_token(access_token, access_token_secret)
        
        api = tweepy.API(auth, wait_on_rate_limit=True)
        return api
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Twitter API: {str(e)}")

async def search_tweepy(query: str, limit: int = 100, bearer_token: str = None):
    if not bearer_token:
        raise HTTPException(status_code=401, detail="Missing Twitter Bearer Token in X-API-KEY header.")
    client = tweepy.Client(bearer_token=bearer_token)
    try:
        tweets = client.search_recent_tweets(
            query=query,
            max_results=min(limit, 100),  # Twitter API max is 100 per request
            tweet_fields=["created_at", "author_id", "public_metrics"],
            expansions=["author_id"]
        )
        results = []
        if tweets.data:
            user_map = {u.id: u.username for u in tweets.includes['users']} if 'users' in tweets.includes else {}
            for tweet in tweets.data:
                results.append({
                    "platform": "twitter",
                    "id": tweet.id,
                    "author": user_map.get(tweet.author_id, tweet.author_id),
                    "author_id": tweet.author_id,  # This is the recipient_id you need for DMs
                    "content": tweet.text,
                    "created": tweet.created_at.isoformat() if tweet.created_at else None,
                    "likes": tweet.public_metrics.get("like_count", 0),
                    "retweets": tweet.public_metrics.get("retweet_count", 0),
                    "url": f"https://twitter.com/{user_map.get(tweet.author_id, tweet.author_id)}/status/{tweet.id}"
                })
        return results
    except tweepy.errors.Unauthorized as e:
        raise HTTPException(status_code=401, detail="Invalid Twitter Bearer Token.")
    except tweepy.TooManyRequests as e:
        raise HTTPException(status_code=429, detail="Twitter API rate limit exceeded. Please try again later.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tweepy error: {str(e)}")

async def get_user_by_username(username: str, bearer_token: str = None):
    """
    Get user information by username using Twitter API v2
    """
    if not bearer_token:
        raise HTTPException(status_code=401, detail="Missing Twitter Bearer Token in X-API-KEY header.")
    
    client = tweepy.Client(bearer_token=bearer_token)
    try:
        user = client.get_user(username=username, user_fields=["id", "username", "name", "description", "profile_image_url"])
        if user.data:
            return {
                "id": user.data.id,  # This is the recipient_id for DMs
                "username": user.data.username,
                "name": user.data.name,
                "description": user.data.description,
                "profile_image_url": user.data.profile_image_url
            }
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except tweepy.errors.Unauthorized as e:
        raise HTTPException(status_code=401, detail="Invalid Twitter Bearer Token.")
    except tweepy.errors.NotFound as e:
        raise HTTPException(status_code=404, detail="User not found")
    except tweepy.errors.TooManyRequests as e:
        raise HTTPException(status_code=429, detail="Twitter API rate limit exceeded. Please try again later.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tweepy error: {str(e)}")

async def get_reddit_user_by_username(username: str):
    """
    Get Reddit user information by username using PRAW
    """
    try:
        reddit = init_praw()
        redditor = reddit.redditor(username)
        
        # Try to access some basic info to verify the user exists
        # Note: Reddit API doesn't provide much public info about users
        return {
            "username": username,
            "id": username,  # For Reddit, the username is the ID
            "name": username,
            "description": "Reddit user",
            "platform": "reddit"
        }
        
    except praw.exceptions.APIException as e:
        if "USER_DOESNT_EXIST" in str(e):
            raise HTTPException(status_code=404, detail="Reddit user not found.")
        else:
            raise HTTPException(status_code=400, detail=f"Reddit API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Reddit user: {str(e)}")

async def send_direct_message(recipient_id: str, message: str, media_ids: List[str] = None, 
                            bearer_token: str = None, access_token: str = None, access_token_secret: str = None):
    """
    Send a direct message using Twitter API v1.1
    """
    if not bearer_token:
        raise HTTPException(status_code=401, detail="Missing Twitter Bearer Token in X-API-KEY header.")
    
    if not access_token or not access_token_secret:
        raise HTTPException(status_code=401, detail="Missing User Access Token and Secret for DM operations.")
    
    try:
        # Initialize Twitter API v1.1
        api = init_twitter_v1_api(bearer_token, access_token, access_token_secret)
        
        # Send the direct message
        dm = api.send_direct_message(
            recipient_id=recipient_id,
            text=message,
            media_id=media_ids[0] if media_ids else None  # Twitter v1.1 only supports one media per DM
        )
        
        return {
            "success": True,
            "message_id": dm.id,
            "recipient_id": recipient_id,
            "message": message,
            "created_at": dm.created_timestamp,
            "media_ids": media_ids
        }
        
    except tweepy.errors.Unauthorized as e:
        raise HTTPException(status_code=401, detail="Invalid Twitter credentials.")
    except tweepy.errors.Forbidden as e:
        raise HTTPException(status_code=403, detail="Cannot send DM to this user. They may not follow you or have DMs disabled.")
    except tweepy.errors.NotFound as e:
        raise HTTPException(status_code=404, detail="Recipient user not found.")
    except tweepy.errors.TooManyRequests as e:
        raise HTTPException(status_code=429, detail="Twitter API rate limit exceeded. Please try again later.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send DM: {str(e)}")

async def send_reddit_direct_message(recipient_username: str, message: str, subject: str = None, 
                                   sender_username: str = None, sender_password: str = None):
    """
    Send a direct message to a Reddit user using PRAW with script authentication
    Requires sender_username and sender_password (no fallback to environment variables)
    """
    try:
        # Validate that sender credentials are provided
        if not sender_username or not sender_password:
            raise ValueError("Reddit username and password are required for DM operations")
        
        # Get app credentials from environment
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT")
        
        if not all([client_id, client_secret, user_agent]):
            raise ValueError("Missing Reddit app credentials in environment variables")
        
        # Initialize PRAW with provided user credentials
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=sender_username,
            password=sender_password
        )
        
        # Verify the recipient user exists
        recipient = reddit.redditor(recipient_username)
        
        # Send the message using PRAW's message method
        reddit.message(
            recipient=recipient_username,
            subject=subject or "Message from Social Scraper API",
            message=message
        )
        
        return {
            "success": True,
            "recipient_username": recipient_username,
            "sender_username": sender_username,
            "message": message,
            "subject": subject or "Message from Social Scraper API",
            "platform": "reddit"
        }
        
    except praw.exceptions.APIException as e:
        if "USER_DOESNT_EXIST" in str(e):
            raise HTTPException(status_code=404, detail="Reddit user not found.")
        elif "RATELIMIT" in str(e):
            raise HTTPException(status_code=429, detail="Reddit API rate limit exceeded. Please try again later.")
        elif "INVALID_USER" in str(e):
            raise HTTPException(status_code=404, detail="Invalid Reddit username.")
        elif "FORBIDDEN" in str(e):
            raise HTTPException(status_code=403, detail="Cannot send DM to this user. They may have DMs disabled.")
        else:
            raise HTTPException(status_code=400, detail=f"Reddit API error: {str(e)}")
    except praw.exceptions.InvalidImplicitAuth as e:
        raise HTTPException(status_code=401, detail="Invalid Reddit credentials. Check username and password.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send Reddit DM: {str(e)}")

async def send_direct_message_unified(platform: str, recipient_id: str, message: str, 
                                    media_ids: List[str] = None, subject: str = None,
                                    bearer_token: str = None, access_token: str = None, 
                                    access_token_secret: str = None, reddit_username: str = None,
                                    reddit_password: str = None):
    """
    Unified function to send direct messages to Twitter or Reddit users
    """
    if platform.lower() == "twitter":
        return await send_direct_message(
            recipient_id=recipient_id,
            message=message,
            media_ids=media_ids,
            bearer_token=bearer_token,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
    elif platform.lower() == "reddit":
        return await send_reddit_direct_message(
            recipient_username=recipient_id,  # For Reddit, recipient_id is the username
            message=message,
            subject=subject,
            sender_username=reddit_username,
            sender_password=reddit_password
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'twitter' or 'reddit'.")

def get_cached_twitter_results(query: str, limit: int):
    cache_key = f"{query}_{limit}"
    if cache_key in twitter_cache:
        cache_data = twitter_cache[cache_key]
        if datetime.now().timestamp() - cache_data['timestamp'] < CACHE_DURATION:
            return cache_data['results']
    return None

def cache_twitter_results(query: str, limit: int, results: list):
    cache_key = f"{query}_{limit}"
    twitter_cache[cache_key] = {
        'results': results,
        'timestamp': datetime.now().timestamp()
    }

def init_praw():
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    if not all([client_id, client_secret, user_agent]):
        raise ValueError("Missing Reddit API credentials")
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )

def init_praw_script():
    """
    Initialize PRAW with script application credentials for DM operations
    Requires username and password for script applications
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")
    
    if not all([client_id, client_secret, user_agent, username, password]):
        raise ValueError("Missing Reddit script application credentials (client_id, client_secret, user_agent, username, password)")
    
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        username=username,
        password=password
    )

@app.post("/search")
async def search_social(search: SearchQuery, api_key: str = Header(None, alias="X-API-KEY")):
    # For Twitter, use api_key as the Bearer Token
    if search.platform.lower() == "twitter":
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing Twitter Bearer Token in X-API-KEY header. Required for Twitter searches.")
        # Check cache first
        cached_results = get_cached_twitter_results(search.query, search.limit)
        if cached_results:
            return {"results": cached_results, "source": "cache"}
        # Search using Tweepy (Twitter API)
        results = await search_tweepy(search.query, search.limit, bearer_token=api_key)
        # Cache the results
        cache_twitter_results(search.query, search.limit, results)
        return {"results": results, "source": "api"}
    # Reddit logic remains unchanged
    try:
        if search.platform.lower() == "reddit":
            reddit = init_praw()
            results = []
            subreddit = reddit.subreddit(search.subreddit)
            
            # Search submissions
            for submission in subreddit.search(search.query, sort=search.sort, limit=search.limit):
                results.append({
                    "platform": "reddit",
                    "type": "submission",
                    "id": submission.id,
                    "author": submission.author.name if submission.author else "Unknown",
                    "author_id": submission.author.name if submission.author else "Unknown",  # For Reddit, author_id is the username
                    "content": submission.title,
                    "created": submission.created_utc,
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "url": submission.url
                })
                
                # Search comments in the submission
                submission.comments.replace_more(limit=0)  # Limit comment depth
                for comment in submission.comments.list():
                    if search.query.lower() in comment.body.lower():
                        results.append({
                            "platform": "reddit",
                            "type": "comment",
                            "id": comment.id,
                            "author": comment.author.name if comment.author else "Unknown",
                            "author_id": comment.author.name if comment.author else "Unknown",  # For Reddit, author_id is the username
                            "content": comment.body,
                            "created": comment.created_utc,
                            "score": comment.score,
                            "parent_id": comment.parent_id,
                            "url": f"https://reddit.com{comment.permalink}"
                        })
            
            return {"results": results}

        else:
            raise HTTPException(status_code=400, detail="Invalid platform. Use 'twitter' or 'reddit'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send-dm")
async def send_direct_message_endpoint(
    dm_request: DirectMessageRequest,
    api_key: str = Header(None, alias="X-API-KEY"),
    access_token: str = Header(None, alias="X-ACCESS-TOKEN"),
    access_token_secret: str = Header(None, alias="X-ACCESS-TOKEN-SECRET"),
    reddit_username: str = Header(None, alias="X-REDDIT-USERNAME"),
    reddit_password: str = Header(None, alias="X-REDDIT-PASSWORD")
):
    """
    Send a direct message to a Twitter or Reddit user
    
    Headers required based on platform:
    
    For Twitter:
    - X-API-KEY: Twitter Bearer Token (required)
    - X-ACCESS-TOKEN: User Access Token (required)
    - X-ACCESS-TOKEN-SECRET: User Access Token Secret (required)
    
    For Reddit:
    - X-REDDIT-USERNAME: Reddit username (required)
    - X-REDDIT-PASSWORD: Reddit password (required)
    
    Body:
    - platform: 'twitter' or 'reddit'
    - recipient_id: Twitter user ID or Reddit username of the recipient
    - message: The message to send
    - media_ids: Optional list of media IDs to attach (Twitter only)
    - subject: Optional subject for Reddit messages
    """
    
    # Validate platform-specific headers
    if dm_request.platform.lower() == "twitter":
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-KEY header. Required for Twitter DMs.")
        if not access_token:
            raise HTTPException(status_code=401, detail="Missing X-ACCESS-TOKEN header. Required for Twitter DMs.")
        if not access_token_secret:
            raise HTTPException(status_code=401, detail="Missing X-ACCESS-TOKEN-SECRET header. Required for Twitter DMs.")
    elif dm_request.platform.lower() == "reddit":
        if not reddit_username:
            raise HTTPException(status_code=401, detail="Missing X-REDDIT-USERNAME header. Required for Reddit DMs.")
        if not reddit_password:
            raise HTTPException(status_code=401, detail="Missing X-REDDIT-PASSWORD header. Required for Reddit DMs.")
    else:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'twitter' or 'reddit'.")
    
    return await send_direct_message_unified(
        platform=dm_request.platform,
        recipient_id=dm_request.recipient_id,
        message=dm_request.message,
        media_ids=dm_request.media_ids,
        subject=dm_request.subject,
        bearer_token=api_key,
        access_token=access_token,
        access_token_secret=access_token_secret,
        reddit_username=reddit_username,
        reddit_password=reddit_password
    )

@app.get("/user/{username}")
async def get_user_info(username: str, api_key: str = Header(None, alias="X-API-KEY")):
    """
    Get user information by username
    
    Headers required:
    - X-API-KEY: Twitter Bearer Token
    
    Returns user information including the user ID (recipient_id for DMs)
    """
    return await get_user_by_username(username, api_key)

@app.get("/user/{platform}/{username}")
async def get_user_info_platform(platform: str, username: str, api_key: str = Header(None, alias="X-API-KEY")):
    """
    Get user information by username for a specific platform
    
    Headers required:
    - X-API-KEY: Twitter Bearer Token (required for Twitter) or not needed (for Reddit)
    
    Returns user information including the user ID (recipient_id for DMs)
    """
    if platform.lower() == "twitter":
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-KEY header. Required for Twitter user lookup.")
        return await get_user_by_username(username, api_key)
    elif platform.lower() == "reddit":
        return await get_reddit_user_by_username(username)
    else:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'twitter' or 'reddit'.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 