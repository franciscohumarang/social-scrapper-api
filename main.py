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

async def search_tweepy(query: str, limit: int = 20, bearer_token: str = None):
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

@app.post("/search")
async def search_social(search: SearchQuery, api_key: str = Header(None, alias="X-API-KEY")):
    # For Twitter, use api_key as the Bearer Token
    if search.platform.lower() == "twitter":
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing Twitter Bearer Token in X-API-KEY header.")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 