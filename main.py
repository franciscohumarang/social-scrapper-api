import asyncio
import os
from fastapi import FastAPI, HTTPException, Header
from twscrape import API, gather
import praw
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

class SearchQuery(BaseModel):
    platform: str  # 'twitter' or 'reddit'
    query: str
    limit: Optional[int] = 20
    subreddit: Optional[str] = "all"  # Reddit-specific
    sort: Optional[str] = "relevance"  # Reddit: relevance, hot, top, new, comments
    product: Optional[str] = "Latest"  # Twitter: Top, Latest, Media

async def init_twscrape():
    api = API()
    username = os.getenv("X_USERNAME")
    password = os.getenv("X_PASSWORD")
    email = os.getenv("X_EMAIL")
    email_password = os.getenv("X_EMAIL_PASSWORD")
    if not all([username, password, email, email_password]):
        raise ValueError("Missing X account credentials")
    
    # Add account if not exists
    await api.pool.add_account(username, password, email, email_password)
    # Login all accounts
    await api.pool.login_all()
    return api

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
            api = await init_twscrape()
            results = []
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
            return {"results": results}

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