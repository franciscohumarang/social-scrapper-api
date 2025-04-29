import asyncio
import os
from fastapi import FastAPI, HTTPException, Header
from twscrape import API, gather
import praw
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
import json
import time
from datetime import datetime, timedelta

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

class TwitterAccount(BaseModel):
    username: str
    password: str
    email: str
    email_password: str

def get_twitter_accounts() -> List[TwitterAccount]:
    accounts = []
    try:
        # Try to read from JSON file first
        if os.path.exists('twitter_accounts.json'):
            with open('twitter_accounts.json', 'r') as f:
                accounts_data = json.load(f)
                print(f"Loaded accounts from JSON file: {len(accounts_data)} accounts")
                for account in accounts_data:
                    accounts.append(TwitterAccount(**account))
                return accounts
        
        # Fallback to environment variable
        accounts_json = os.getenv("TWITTER_ACCOUNTS")
        print(f"Raw TWITTER_ACCOUNTS from env: {accounts_json}")
        
        if accounts_json:
            try:
                # Remove any surrounding quotes and whitespace
                accounts_json = accounts_json.strip().strip("'").strip('"')
                print(f"Cleaned accounts JSON: {accounts_json}")
                
                # Try to parse the JSON
                try:
                    accounts_data = json.loads(accounts_json)
                except json.JSONDecodeError:
                    # If that fails, try to fix common JSON formatting issues
                    accounts_json = accounts_json.replace("'", '"')  # Replace single quotes with double quotes
                    accounts_data = json.loads(accounts_json)
                
                print(f"Parsed accounts data: {accounts_data}")
                for account in accounts_data:
                    accounts.append(TwitterAccount(**account))
                print(f"Successfully loaded {len(accounts)} Twitter accounts")
            except Exception as e:
                print(f"Error parsing Twitter accounts: {str(e)}")
                print(f"Error type: {type(e)}")
                print(f"Error details: {e.__dict__}")
        else:
            print("TWITTER_ACCOUNTS environment variable is not set")
    except Exception as e:
        print(f"Error loading Twitter accounts: {str(e)}")
    
    return accounts

async def init_twscrape():
    api = API()
    accounts = get_twitter_accounts()
    
    if not accounts:
        raise ValueError("No Twitter accounts configured")
    
    print(f"Initializing twscrape with {len(accounts)} accounts")
    
    # Add all accounts
    for account in accounts:
        try:
            print(f"Adding account: {account.username}")
            await api.pool.add_account(
                account.username,
                account.password,
                account.email,
                account.email_password
            )
            print(f"Successfully added account: {account.username}")
        except Exception as e:
            print(f"Error adding account {account.username}: {str(e)}")
    
    # Login all accounts
    print("Logging in all accounts...")
    await api.pool.login_all()
    print("All accounts logged in successfully")
    return api

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

            api = await init_twscrape()
            results = []
            
            # Add delay between requests
            delay = 2  # seconds
            count = 0
            
            async for tweet in api.search(search.query, limit=search.limit, kv={"product": search.product}):
                results.append({
                    "platform": "twitter",
                    "id": tweet.id,
                    "author": tweet.user.username,
                    "content": tweet.rawContent,
                    "created": tweet.date.isoformat(),
                    "likes": tweet.likeCount,
                    "retweets": tweet.retweetCount,
                    "url": f"https://x.com/{tweet.user.username}/status/{tweet.id}"
                })
                
                # Add delay every 10 tweets
                count += 1
                if count % 10 == 0:
                    await asyncio.sleep(delay)
            
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