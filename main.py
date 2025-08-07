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
    limit: Optional[int] = 100
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

async def search_twitterapi_io(query: str, limit: int = 5, product: str = "Latest", api_key: str = None):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing TwitterAPI.io API Key in X-API-KEY header.")
    
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Map product type to queryType
    query_type = "Latest" if product == "Latest" else "Top"
    
    params = {
        "query": query,
        "queryType": query_type,
        "cursor": ""
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 401:
                    raise HTTPException(status_code=401, detail="Invalid TwitterAPI.io API Key.")
                elif response.status == 429:
                    raise HTTPException(status_code=429, detail="TwitterAPI.io rate limit exceeded. Please try again later.")
                elif response.status != 200:
                    raise HTTPException(status_code=response.status, detail=f"TwitterAPI.io error: {response.status}")
                
                data = await response.json()
                results = []
                
                if "tweets" in data and data["tweets"]:
                    tweet_count = 0
                    for tweet in data["tweets"]:
                        if tweet_count >= limit:
                            break
                        
                        # Extract author information
                        author_info = tweet.get("author", {})
                        author_username = author_info.get("username", "unknown")
                        author_id = author_info.get("id", "unknown")
                        
                        # Extract engagement metrics
                        public_metrics = tweet.get("public_metrics", {})
                        
                        results.append({
                            "platform": "twitter",
                            "id": tweet.get("id", ""),
                            "author": author_username,
                            "author_id": author_id,
                            "content": tweet.get("text", ""),
                            "created": tweet.get("created_at"),
                            "likes": public_metrics.get("like_count", 0),
                            "retweets": public_metrics.get("retweet_count", 0),
                            "url": tweet.get("url", f"https://twitter.com/{author_username}/status/{tweet.get('id', '')}")
                        })
                        tweet_count += 1
                
                return results
                
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"TwitterAPI.io connection error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TwitterAPI.io error: {str(e)}")

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

async def get_login_cookie(username: str, email: str, password: str):
    """
    Get login cookie from twitterapi.io for DM operations
    """
    api_key = os.getenv("TWITTER_API_IO_KEY")
    proxy = os.getenv("TWITTER_PROXY")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing TWITTER_API_IO_KEY in environment variables.")
    if not proxy:
        raise HTTPException(status_code=500, detail="Missing TWITTER_PROXY in environment variables.")
    
    url = "https://api.twitterapi.io/twitter/user_login_v2"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "user_name": username,
        "email": email,
        "password": password,
        "totp_secret": "",  # Empty if no 2FA
        "proxy": proxy
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 401:
                    raise HTTPException(status_code=401, detail="Invalid TwitterAPI.io API Key.")
                elif response.status == 429:
                    raise HTTPException(status_code=429, detail="TwitterAPI.io rate limit exceeded. Please try again later.")
                elif response.status != 200:
                    raise HTTPException(status_code=response.status, detail=f"TwitterAPI.io login error: {response.status}")
                
                data = await response.json()
                if data.get("login_cookie"):
                    return data["login_cookie"]
                else:
                    raise HTTPException(status_code=400, detail=f"Login failed: {data.get('msg', 'Unknown error')}")
                    
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"TwitterAPI.io connection error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TwitterAPI.io login error: {str(e)}")

async def send_direct_message(recipient_id: str, message: str, media_ids: List[str] = None, 
                            username: str = None, email: str = None, password: str = None):
    """
    Send a direct message using TwitterAPI.io
    """
    api_key = os.getenv("TWITTER_API_IO_KEY")
    proxy = os.getenv("TWITTER_PROXY")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing TWITTER_API_IO_KEY in environment variables.")
    if not proxy:
        raise HTTPException(status_code=500, detail="Missing TWITTER_PROXY in environment variables.")
    if not username or not email or not password:
        raise HTTPException(status_code=401, detail="Missing Twitter account credentials for DM operations.")
    
    try:
        # Get login cookie
        login_cookie = await get_login_cookie(username, email, password)
        
        # Send the direct message
        url = "https://api.twitterapi.io/twitter/send_dm_to_user"
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "login_cookie": login_cookie,
            "user_id": recipient_id,
            "text": message,
            "proxy": proxy
        }
        
        # Add media_ids if provided
        if media_ids:
            payload["media_ids"] = media_ids
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 401:
                    raise HTTPException(status_code=401, detail="Invalid TwitterAPI.io API Key.")
                elif response.status == 403:
                    raise HTTPException(status_code=403, detail="Cannot send DM to this user. They may not follow you or have DMs disabled.")
                elif response.status == 404:
                    raise HTTPException(status_code=404, detail="Recipient user not found.")
                elif response.status == 429:
                    raise HTTPException(status_code=429, detail="TwitterAPI.io rate limit exceeded. Please try again later.")
                elif response.status != 200:
                    raise HTTPException(status_code=response.status, detail=f"TwitterAPI.io DM error: {response.status}")
                
                data = await response.json()
                return {
                    "success": True,
                    "recipient_id": recipient_id,
                    "message": message,
                    "media_ids": media_ids,
                    "response": data
                }
        
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=500, detail=f"TwitterAPI.io connection error: {str(e)}")
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
                                    twitter_username: str = None, twitter_email: str = None, 
                                    twitter_password: str = None, reddit_username: str = None,
                                    reddit_password: str = None):
    """
    Unified function to send direct messages to Twitter or Reddit users
    """
    if platform.lower() == "twitter":
        return await send_direct_message(
            recipient_id=recipient_id,
            message=message,
            media_ids=media_ids,
            username=twitter_username,
            email=twitter_email,
            password=twitter_password
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
async def search_social(search: SearchQuery):
    # For Twitter, use TwitterAPI.io API Key from environment
    if search.platform.lower() == "twitter":
        api_key = os.getenv("TWITTER_API_IO_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing TWITTER_API_IO_KEY in environment variables. Required for Twitter searches.")
        # Check cache first
        cached_results = get_cached_twitter_results(search.query, search.limit)
        if cached_results:
            return {"results": cached_results, "source": "cache"}
        # Search using TwitterAPI.io
        results = await search_twitterapi_io(search.query, search.limit, product=search.product, api_key=api_key)
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
    twitter_username: str = Header(None, alias="X-TWITTER-USERNAME"),
    twitter_email: str = Header(None, alias="X-TWITTER-EMAIL"),
    twitter_password: str = Header(None, alias="X-TWITTER-PASSWORD"),
    reddit_username: str = Header(None, alias="X-REDDIT-USERNAME"),
    reddit_password: str = Header(None, alias="X-REDDIT-PASSWORD")
):
    """
    Send a direct message to a Twitter or Reddit user
    
    Headers required based on platform:
    
    For Twitter:
    - X-TWITTER-USERNAME: Twitter username (required)
    - X-TWITTER-EMAIL: Twitter email (required)
    - X-TWITTER-PASSWORD: Twitter password (required)
    
    For Reddit:
    - X-REDDIT-USERNAME: Reddit username (required)
    - X-REDDIT-PASSWORD: Reddit password (required)
    
    Body:
    - platform: 'twitter' or 'reddit'
    - recipient_id: Twitter user ID or Reddit username of the recipient
    - message: The message to send
    - media_ids: Optional list of media IDs to attach (Twitter only)
    - subject: Optional subject for Reddit messages
    
    Environment variables required for Twitter:
    - TWITTER_API_IO_KEY: TwitterAPI.io API Key
    - TWITTER_PROXY: Proxy URL for login operations
    """
    
    # Validate platform-specific headers
    if dm_request.platform.lower() == "twitter":
        if not twitter_username:
            raise HTTPException(status_code=401, detail="Missing X-TWITTER-USERNAME header. Required for Twitter DMs.")
        if not twitter_email:
            raise HTTPException(status_code=401, detail="Missing X-TWITTER-EMAIL header. Required for Twitter DMs.")
        if not twitter_password:
            raise HTTPException(status_code=401, detail="Missing X-TWITTER-PASSWORD header. Required for Twitter DMs.")
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
        twitter_username=twitter_username,
        twitter_email=twitter_email,
        twitter_password=twitter_password,
        reddit_username=reddit_username,
        reddit_password=reddit_password
    )

@app.get("/user/{username}")
async def get_user_info(username: str):
    """
    Get user information by username
    
    Environment variables required:
    - TWITTER_BEARER_TOKEN: Twitter Bearer Token
    
    Returns user information including the user ID (recipient_id for DMs)
    """
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        raise HTTPException(status_code=500, detail="Missing TWITTER_BEARER_TOKEN in environment variables.")
    return await get_user_by_username(username, bearer_token)

@app.get("/user/{platform}/{username}")
async def get_user_info_platform(platform: str, username: str):
    """
    Get user information by username for a specific platform
    
    Environment variables required for Twitter:
    - TWITTER_BEARER_TOKEN: Twitter Bearer Token
    
    Returns user information including the user ID (recipient_id for DMs)
    """
    if platform.lower() == "twitter":
        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer_token:
            raise HTTPException(status_code=500, detail="Missing TWITTER_BEARER_TOKEN in environment variables.")
        return await get_user_by_username(username, bearer_token)
    elif platform.lower() == "reddit":
        return await get_reddit_user_by_username(username)
    else:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'twitter' or 'reddit'.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 