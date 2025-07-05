#!/usr/bin/env python3
"""
Test script for the Direct Message endpoints (Twitter and Reddit)
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change to your server URL
TWITTER_BEARER_TOKEN = os.getenv("API_KEY")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def test_search_endpoint():
    """Test the search endpoint"""
    print("Testing search endpoint...")
    
    url = f"{API_BASE_URL}/search"
    headers = {
        "X-API-KEY": TWITTER_BEARER_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "platform": "twitter",
        "query": "python",
        "limit": 5
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Found {len(result.get('results', []))} results")
            print(f"Source: {result.get('source', 'unknown')}")
            
            # Show how to get recipient_id from search results
            if result.get('results'):
                first_result = result['results'][0]
                print(f"\nFirst result:")
                print(f"  Author: @{first_result.get('author')}")
                print(f"  Author ID (recipient_id): {first_result.get('author_id')}")
                print(f"  Content: {first_result.get('content')[:100]}...")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

def test_reddit_search():
    """Test Reddit search endpoint"""
    print("\nTesting Reddit search endpoint...")
    
    url = f"{API_BASE_URL}/search"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "platform": "reddit",
        "query": "python",
        "limit": 5,
        "subreddit": "programming"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Found {len(result.get('results', []))} results")
            
            # Show how to get recipient_id from Reddit search results
            if result.get('results'):
                first_result = result['results'][0]
                print(f"\nFirst result:")
                print(f"  Author: u/{first_result.get('author')}")
                print(f"  Author ID (recipient_id): {first_result.get('author_id')}")
                print(f"  Type: {first_result.get('type')}")
                print(f"  Content: {first_result.get('content')[:100]}...")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

def test_get_user_endpoint():
    """Test the get user endpoint"""
    print("\nTesting get user endpoint...")
    
    # Test with a known username (replace with actual username)
    username = "twitter"  # Example username
    
    url = f"{API_BASE_URL}/user/{username}"
    headers = {
        "X-API-KEY": TWITTER_BEARER_TOKEN
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            user_info = response.json()
            print(f"User found:")
            print(f"  Username: @{user_info.get('username')}")
            print(f"  Name: {user_info.get('name')}")
            print(f"  User ID (recipient_id): {user_info.get('id')}")
            print(f"  Description: {user_info.get('description', 'No description')[:100]}...")
            return user_info.get('id')  # Return the user ID for DM testing
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_get_reddit_user_endpoint():
    """Test the get Reddit user endpoint"""
    print("\nTesting get Reddit user endpoint...")
    
    # Test with a known Reddit username (replace with actual username)
    username = "reddit"  # Example username
    
    url = f"{API_BASE_URL}/user/reddit/{username}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            user_info = response.json()
            print(f"Reddit user found:")
            print(f"  Username: u/{user_info.get('username')}")
            print(f"  User ID (recipient_id): {user_info.get('id')}")
            print(f"  Platform: {user_info.get('platform')}")
            return user_info.get('id')  # Return the username for DM testing
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_dm_endpoint(recipient_id=None, platform="twitter"):
    """Test the direct message endpoint"""
    print(f"\nTesting {platform} DM endpoint...")
    
    if not recipient_id:
        print(f"No recipient_id provided. Skipping {platform} DM test.")
        return
    
    url = f"{API_BASE_URL}/send-dm"
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add platform-specific headers (now required)
    if platform == "twitter":
        headers["X-API-KEY"] = TWITTER_BEARER_TOKEN
        headers["X-ACCESS-TOKEN"] = TWITTER_ACCESS_TOKEN
        headers["X-ACCESS-TOKEN-SECRET"] = TWITTER_ACCESS_TOKEN_SECRET
    elif platform == "reddit":
        # Reddit credentials are now required via headers
        reddit_username = os.getenv("REDDIT_USERNAME")
        reddit_password = os.getenv("REDDIT_PASSWORD")
        
        if reddit_username and reddit_password:
            headers["X-REDDIT-USERNAME"] = reddit_username
            headers["X-REDDIT-PASSWORD"] = reddit_password
            print(f"Using Reddit credentials: {reddit_username}")
        else:
            print("Error: Reddit credentials required but not found in environment")
            print("Set REDDIT_USERNAME and REDDIT_PASSWORD environment variables")
            return
    
    data = {
        "platform": platform,
        "recipient_id": recipient_id,
        "message": f"Hello from the Social Scraper API! This is a test message for {platform}.",
        "media_ids": None,  # Optional: add media IDs if you have them (Twitter only)
        "subject": f"Test message from API - {platform}" if platform == "reddit" else None
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"{platform.capitalize()} DM sent successfully!")
            if platform == "twitter":
                print(f"Message ID: {result.get('message_id')}")
                print(f"Recipient: {result.get('recipient_id')}")
            else:
                print(f"Recipient: {result.get('recipient_username')}")
                print(f"Sender: {result.get('sender_username')}")
                print(f"Subject: {result.get('subject')}")
            print(f"Message: {result.get('message')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

def test_reddit_dm_with_custom_credentials():
    """Test Reddit DM with custom credentials via headers"""
    print("\nTesting Reddit DM with custom credentials...")
    
    # Example recipient (replace with actual Reddit username)
    recipient_username = "test_recipient"
    
    url = f"{API_BASE_URL}/send-dm"
    headers = {
        "Content-Type": "application/json",
        "X-REDDIT-USERNAME": "custom_sender_username",  # Replace with actual username
        "X-REDDIT-PASSWORD": "custom_sender_password"   # Replace with actual password
    }
    
    data = {
        "platform": "reddit",
        "recipient_id": recipient_username,
        "message": "Hello from custom Reddit user!",
        "subject": "Custom sender test"
    }
    
    print("Note: This test uses placeholder credentials.")
    print("Replace 'custom_sender_username' and 'custom_sender_password' with actual values.")
    print("Both X-REDDIT-USERNAME and X-REDDIT-PASSWORD headers are now REQUIRED for Reddit DMs.")
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Reddit DM sent successfully!")
            print(f"Recipient: {result.get('recipient_username')}")
            print(f"Sender: {result.get('sender_username')}")
            print(f"Subject: {result.get('subject')}")
            print(f"Message: {result.get('message')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

def get_user_id_by_username(username, platform="twitter"):
    """Helper function to get user ID by username"""
    print(f"\nGetting {platform} user ID for {username}...")
    
    if platform == "twitter":
        url = f"{API_BASE_URL}/user/{username}"
        headers = {
            "X-API-KEY": TWITTER_BEARER_TOKEN
        }
    else:
        url = f"{API_BASE_URL}/user/{platform}/{username}"
        headers = {}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            user_info = response.json()
            user_id = user_info.get('id')
            if platform == "twitter":
                print(f"Found user: @{user_info.get('username')} (ID: {user_id})")
            else:
                print(f"Found user: u/{user_info.get('username')} (ID: {user_id})")
            return user_id
        else:
            print(f"Could not find user: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

if __name__ == "__main__":
    print("Social Scraper API - DM Test Script (Twitter & Reddit)")
    print("=" * 50)
    
    # Check if required environment variables are set
    if not TWITTER_BEARER_TOKEN:
        print("Error: TWITTER_BEARER_TOKEN not set in environment")
        exit(1)
    
    if not TWITTER_ACCESS_TOKEN or not TWITTER_ACCESS_TOKEN_SECRET:
        print("Error: TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET not set in environment")
        print("These are required for Twitter DM functionality")
        exit(1)
    
    # Check Reddit environment variables
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    reddit_username = os.getenv("REDDIT_USERNAME")
    reddit_password = os.getenv("REDDIT_PASSWORD")
    
    if not all([reddit_client_id, reddit_client_secret, reddit_username, reddit_password]):
        print("Warning: Reddit script application credentials not fully set")
        print("Required: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD")
        print("Reddit DM functionality will not work without these credentials")
    
    # Test search endpoints (shows how to get author_id from search results)
    test_search_endpoint()
    test_reddit_search()
    
    # Test get user endpoints (shows how to get user ID by username)
    twitter_recipient_id = test_get_user_endpoint()
    reddit_recipient_id = test_get_reddit_user_endpoint()
    
    # Test DM endpoints with the user IDs we got
    test_dm_endpoint(twitter_recipient_id, "twitter")
    
    # Only test Reddit DM if credentials are available
    if all([reddit_client_id, reddit_client_secret, reddit_username, reddit_password]):
        test_dm_endpoint(reddit_recipient_id, "reddit")
    else:
        print("\nSkipping Reddit DM test due to missing credentials")
    
    # Test custom Reddit credentials (demonstrates header-based authentication)
    test_reddit_dm_with_custom_credentials()
    
    print("\nTest completed!")
    print("\nSummary:")
    print("1. Search endpoints now return 'author_id' which is the recipient_id for DMs")
    print("2. New /user/{platform}/{username} endpoints get user ID by username")
    print("3. Unified /send-dm endpoint supports both Twitter and Reddit")
    print("4. For Twitter: recipient_id is the numeric user ID")
    print("5. For Reddit: recipient_id is the username")
    print("6. Reddit DMs support both environment variables and header-based credentials")
    print("7. Use X-REDDIT-USERNAME and X-REDDIT-PASSWORD headers for custom Reddit users") 