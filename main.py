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

# List of Nitter instances (updated with most reliable ones from https://github.com/zedeus/nitter/wiki/Instances)
NITTER_INSTANCES = [
    "https://nitter.net",  # Official instance
    "https://xcancel.com",
    "https://nitter.poast.org",
    "https://nitter.privacyredirect.com",
    "https://lightbrd.com",
    "https://nitter.space",
    "https://nitter.tiekoetter.com"
]

class SearchQuery(BaseModel):
    platform: str  # 'twitter' or 'reddit'
    query: str
    limit: Optional[int] = 20
    subreddit: Optional[str] = "all"  # Reddit-specific
    sort: Optional[str] = "relevance"  # Reddit: relevance, hot, top, new, comments
    product: Optional[str] = "Latest"  # Twitter: Top, Latest, Media

async def search_nitter(query: str, limit: int = 20):
    # Randomize the list of instances
    instances = NITTER_INSTANCES.copy()
    random.shuffle(instances)
    
    for instance in instances:
        try:
            print(f"Trying Nitter instance: {instance}")
            async with aiohttp.ClientSession() as session:
                # Format query for Nitter
                formatted_query = query.replace(" ", "+")
                url = f"{instance}/search?f=tweets&q={formatted_query}"
                print(f"Search URL: {url}")
                
                # Browser-like headers
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                    'TE': 'Trailers',
                    'DNT': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Pragma': 'no-cache'
                }
                
                # Try to get response with SSL verification disabled
                async with session.get(url, headers=headers, ssl=False) as response:
                    if response.status == 200:
                        html = await response.text()
                        print(html)
                        soup = BeautifulSoup(html, 'html.parser')
                        timeline_container = soup.find('div', class_='timeline-container')
                        if not timeline_container:
                            print("No timeline-container found in HTML")
                            return []
                        timeline = timeline_container.find('div', class_='timeline')
                        if not timeline:
                            print("No timeline found in timeline-container")
                            return []
                        tweet_containers = timeline.find_all('div', class_='timeline-item')
                        print(f"Found {len(tweet_containers)} tweet containers")
                        tweets = []
                        for container in tweet_containers[:limit]:
                            try:
                                # Extract tweet data
                                tweet_link = container.find('a', class_='tweet-link')
                                if not tweet_link:
                                    continue
                                    
                                tweet_id = tweet_link['href'].split('/')[-1]
                                username = container.find('a', class_='username').text.strip()
                                content_div = container.find('div', class_='tweet-content')
                                content = content_div.text.strip() if content_div else ""
                                
                                # Extract metrics
                                stats = container.find_all('span', class_='tweet-stat')
                                likes = 0
                                retweets = 0
                                if len(stats) >= 2:
                                    likes = int(stats[0].text.strip().replace(',', '') or 0)
                                    retweets = int(stats[1].text.strip().replace(',', '') or 0)
                                
                                # Extract timestamp
                                timestamp = container.find('span', class_='tweet-date').find('a')['title']
                                try:
                                    created_at = datetime.strptime(timestamp, '%b %d, %Y · %I:%M %p %Z').isoformat()
                                except:
                                    created_at = datetime.now().isoformat()
                                
                                tweet_data = {
                                    "platform": "twitter",
                                    "id": tweet_id,
                                    "author": username,
                                    "content": content,
                                    "created": created_at,
                                    "likes": likes,
                                    "retweets": retweets,
                                    "url": f"https://twitter.com/{username}/status/{tweet_id}"
                                }
                                print(f"Parsed tweet: {tweet_data}")
                                tweets.append(tweet_data)
                            except Exception as e:
                                print(f"Error parsing tweet: {str(e)}")
                                continue
                        
                        if tweets:
                            print(f"Successfully parsed {len(tweets)} tweets from {instance}")
                            return tweets
                        else:
                            print(f"No tweets found in {instance}")
                    else:
                        print(f"Failed to get response from {instance}: {response.status}")
        except Exception as e:
            print(f"Error with {instance}: {str(e)}")
            continue
    
    raise HTTPException(status_code=500, detail="All Nitter instances failed")

async def search_tweepy(query: str, limit: int = 20):
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        raise HTTPException(status_code=500, detail="Missing Twitter Bearer Token in environment variables.")
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
    expected_api_key = os.getenv("API_KEY")
    print(f"Received API key: {api_key}")
    print(f"Expected API key: {expected_api_key}")
    if expected_api_key and api_key != expected_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    try:
        if search.platform.lower() == "twitter":
            # Check cache first
            cached_results = get_cached_twitter_results(search.query, search.limit)
            if cached_results:
                return {"results": cached_results, "source": "cache"}

            # Search using Tweepy (Twitter API)
            results = await search_tweepy(search.query, search.limit)
            # Cache the results
            cache_twitter_results(search.query, search.limit, results)
            return {"results": results, "source": "api"}

        elif search.platform.lower() == "reddit":
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