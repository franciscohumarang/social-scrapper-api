"""
Rate limiting utilities using Supabase for persistent storage
"""
from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

# Plan-based limits
PLAN_LIMITS = {
    "free": {
        "searches_per_month": 250,  # 25 qualified leads × 10 searches/lead
        "searches_per_day": 15,     # Spread evenly with buffer
        "searches_per_hour": 5,     # Prevent abuse
        "dm_per_day": 10,           # Conservative for free users
        "dm_per_hour": 3
    },
    "scout": {
        "searches_per_month": 3000,  # 300 qualified leads × 10 searches/lead
        "searches_per_day": 120,     # 3000/30 = 100, with buffer
        "searches_per_hour": 20,     # Allow concentrated work sessions
        "dm_per_day": 100,           # ~3 DMs per lead
        "dm_per_hour": 15
    },
    "hunter": {
        "searches_per_month": 10000, # 1000 qualified leads × 10 searches/lead
        "searches_per_day": 400,     # 10000/30 ≈ 333, with buffer
        "searches_per_hour": 50,     # High-volume users need flexibility
        "dm_per_day": 300,           # ~3 DMs per lead
        "dm_per_hour": 25
    }
}

logger = logging.getLogger(__name__)

class RateLimiter:
    """Database-backed rate limiter for user plans"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    async def check_and_increment_limit(
        self,
        user_id: str,
        user_plan: str,
        action_type: str,  # 'search' or 'dm'
        endpoint: str = "",
        platform: str = ""
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Check rate limits and increment counters if allowed
        
        Args:
            user_id: User UUID
            user_plan: User's subscription plan (free, scout, hunter)
            action_type: Type of action ('search' or 'dm')
            endpoint: API endpoint name
            platform: Platform name (twitter, reddit)
            
        Returns:
            Tuple of (allowed: bool, error_message: str, current_usage: dict)
        """
        try:
            # Normalize plan name
            plan = user_plan.lower() if user_plan else "free"
            if plan not in PLAN_LIMITS:
                plan = "free"
            
            # Get current usage stats
            usage_stats = await self._get_user_usage_stats(user_id)
            
            # Check limits based on action type
            limits = PLAN_LIMITS[plan]
            
            if action_type == "search":
                # Check monthly limit
                if usage_stats["searches_month"] >= limits["searches_per_month"]:
                    return False, f"Monthly search limit exceeded ({limits['searches_per_month']} searches). Upgrade your plan to continue.", usage_stats
                
                # Check daily limit
                if usage_stats["searches_day"] >= limits["searches_per_day"]:
                    return False, f"Daily search limit exceeded ({limits['searches_per_day']} searches). Try again tomorrow.", usage_stats
                
                # Check hourly limit
                if usage_stats["searches_hour"] >= limits["searches_per_hour"]:
                    return False, f"Hourly search limit exceeded ({limits['searches_per_hour']} searches). Try again in an hour.", usage_stats
            
            elif action_type == "dm":
                # Check daily limit
                if usage_stats["dms_day"] >= limits["dm_per_day"]:
                    return False, f"Daily DM limit exceeded ({limits['dm_per_day']} DMs). Try again tomorrow.", usage_stats
                
                # Check hourly limit  
                if usage_stats["dms_hour"] >= limits["dm_per_hour"]:
                    return False, f"Hourly DM limit exceeded ({limits['dm_per_hour']} DMs). Try again in an hour.", usage_stats
            
            # All checks passed - increment counter
            success = await self._increment_usage_counter(user_id, action_type, endpoint, platform)
            
            if not success:
                return False, "Failed to record usage. Please try again.", usage_stats
            
            # Get updated stats
            updated_stats = await self._get_user_usage_stats(user_id)
            
            return True, "", updated_stats
            
        except Exception as e:
            logger.error(f"Rate limiting error for user {user_id}: {e}")
            # In case of database error, allow the request but log the issue
            return True, "", {}
    
    async def _get_user_usage_stats(self, user_id: str) -> Dict[str, int]:
        """Get current usage statistics for a user"""
        try:
            # Call the Supabase function to get usage stats with automatic resets
            # user_id is already a UUID string from the JWT token
            result = self.supabase.rpc('get_user_usage_stats', {'p_user_id': user_id}).execute()
            
            if result.data and len(result.data) > 0:
                stats = result.data[0]
                return {
                    "searches_month": stats.get("searches_month", 0),
                    "searches_day": stats.get("searches_day", 0),
                    "searches_hour": stats.get("searches_hour", 0),
                    "dms_month": stats.get("dms_month", 0),
                    "dms_day": stats.get("dms_day", 0),
                    "dms_hour": stats.get("dms_hour", 0)
                }
            else:
                # Return zeros if no stats found
                return {
                    "searches_month": 0,
                    "searches_day": 0,
                    "searches_hour": 0,
                    "dms_month": 0,
                    "dms_day": 0,
                    "dms_hour": 0
                }
                
        except Exception as e:
            logger.error(f"Error getting usage stats for user {user_id}: {e}")
            return {}
    
    async def _increment_usage_counter(
        self,
        user_id: str,
        action_type: str,
        endpoint: str = "",
        platform: str = ""
    ) -> bool:
        """Increment usage counter using Supabase function"""
        try:
            # user_id is already a UUID string from the JWT token
            result = self.supabase.rpc('increment_usage_counter', {
                'p_user_id': user_id,
                'p_action_type': action_type,
                'p_endpoint': endpoint,
                'p_platform': platform
            }).execute()
            
            return result.data is not None
            
        except Exception as e:
            logger.error(f"Error incrementing usage counter for user {user_id}: {e}")
            return False
    
    def get_plan_limits(self, user_plan: str) -> Dict[str, int]:
        """Get rate limits for a specific plan"""
        plan = user_plan.lower() if user_plan else "free"
        if plan not in PLAN_LIMITS:
            plan = "free"
        return PLAN_LIMITS[plan]
    
    async def get_usage_summary(self, user_id: str, user_plan: str) -> Dict:
        """Get usage summary with limits and remaining quotas"""
        try:
            usage_stats = await self._get_user_usage_stats(user_id)
            plan_limits = self.get_plan_limits(user_plan)
            
            return {
                "plan": user_plan.lower() if user_plan else "free",
                "current_usage": usage_stats,
                "limits": plan_limits,
                "remaining": {
                    "searches_month": max(0, plan_limits["searches_per_month"] - usage_stats.get("searches_month", 0)),
                    "searches_day": max(0, plan_limits["searches_per_day"] - usage_stats.get("searches_day", 0)),
                    "searches_hour": max(0, plan_limits["searches_per_hour"] - usage_stats.get("searches_hour", 0)),
                    "dms_day": max(0, plan_limits["dm_per_day"] - usage_stats.get("dms_day", 0)),
                    "dms_hour": max(0, plan_limits["dm_per_hour"] - usage_stats.get("dms_hour", 0))
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting usage summary for user {user_id}: {e}")
            return {}