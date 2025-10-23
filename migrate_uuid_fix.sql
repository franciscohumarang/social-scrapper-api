-- Migration script to fix UUID type mismatch in rate limiting tables
-- Run this in your Supabase SQL Editor to update existing schema

-- First, drop existing functions to avoid conflicts
DROP FUNCTION IF EXISTS get_user_usage_stats(TEXT);
DROP FUNCTION IF EXISTS increment_usage_counter(TEXT, VARCHAR(20), VARCHAR(50), VARCHAR(20));

-- Drop existing policies to avoid conflicts
DROP POLICY IF EXISTS "Users can view own usage tracking" ON usage_tracking;
DROP POLICY IF EXISTS "Users can view own usage stats" ON user_usage_stats;
DROP POLICY IF EXISTS "JWT users can view own usage tracking" ON usage_tracking;
DROP POLICY IF EXISTS "JWT users can view own usage stats" ON user_usage_stats;

-- If tables exist with TEXT user_id, we need to migrate them
-- Note: This will only work if the tables don't have data yet
-- If they have data, you'll need to manually migrate the data

-- Drop and recreate tables with UUID user_id
DROP TABLE IF EXISTS usage_tracking CASCADE;
DROP TABLE IF EXISTS user_usage_stats CASCADE;

-- Recreate tables with correct UUID types
CREATE TABLE usage_tracking (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR(50) NOT NULL, -- 'search' or 'send-dm'
    action_type VARCHAR(20) NOT NULL, -- 'search' or 'dm'
    platform VARCHAR(20), -- 'twitter', 'reddit', etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_usage_stats (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- Current month counters (reset monthly)
    searches_this_month INTEGER DEFAULT 0,
    dms_this_month INTEGER DEFAULT 0,
    
    -- Current day counters (reset daily) 
    searches_today INTEGER DEFAULT 0,
    dms_today INTEGER DEFAULT 0,
    
    -- Current hour counters (reset hourly)
    searches_this_hour INTEGER DEFAULT 0,
    dms_this_hour INTEGER DEFAULT 0,
    
    -- Tracking periods
    month_start DATE DEFAULT CURRENT_DATE,
    day_start DATE DEFAULT CURRENT_DATE,
    hour_start TIMESTAMP DEFAULT DATE_TRUNC('hour', NOW()),
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_user_stats UNIQUE(user_id)
);

-- Recreate the trigger function
CREATE OR REPLACE FUNCTION reset_usage_counters()
RETURNS TRIGGER AS $$
BEGIN
    -- Reset monthly counters if month changed
    IF NEW.month_start < DATE_TRUNC('month', CURRENT_DATE)::DATE THEN
        NEW.searches_this_month = 0;
        NEW.dms_this_month = 0;
        NEW.month_start = DATE_TRUNC('month', CURRENT_DATE)::DATE;
    END IF;
    
    -- Reset daily counters if day changed
    IF NEW.day_start < CURRENT_DATE THEN
        NEW.searches_today = 0;
        NEW.dms_today = 0;
        NEW.day_start = CURRENT_DATE;
    END IF;
    
    -- Reset hourly counters if hour changed
    IF NEW.hour_start < DATE_TRUNC('hour', NOW()) THEN
        NEW.searches_this_hour = 0;
        NEW.dms_this_hour = 0;
        NEW.hour_start = DATE_TRUNC('hour', NOW());
    END IF;
    
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate the trigger
CREATE TRIGGER reset_usage_counters_trigger
    BEFORE UPDATE ON user_usage_stats
    FOR EACH ROW EXECUTE FUNCTION reset_usage_counters();

-- Recreate functions with UUID parameters
CREATE OR REPLACE FUNCTION increment_usage_counter(
    p_user_id UUID,
    p_action_type VARCHAR(20),
    p_endpoint VARCHAR(50) DEFAULT '',
    p_platform VARCHAR(20) DEFAULT ''
) RETURNS BOOLEAN AS $$
DECLARE
    current_hour TIMESTAMP;
BEGIN
    current_hour := DATE_TRUNC('hour', NOW());
    
    -- Insert usage tracking record
    INSERT INTO usage_tracking (user_id, endpoint, action_type, platform)
    VALUES (p_user_id, p_endpoint, p_action_type, p_platform);
    
    -- Update or insert usage stats
    INSERT INTO user_usage_stats (user_id) 
    VALUES (p_user_id)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- Increment counters based on action type
    IF p_action_type = 'search' THEN
        UPDATE user_usage_stats 
        SET 
            searches_this_month = searches_this_month + 1,
            searches_today = searches_today + 1,
            searches_this_hour = searches_this_hour + 1
        WHERE user_id = p_user_id;
    ELSIF p_action_type = 'dm' THEN
        UPDATE user_usage_stats 
        SET 
            dms_this_month = dms_this_month + 1,
            dms_today = dms_today + 1,
            dms_this_hour = dms_this_hour + 1
        WHERE user_id = p_user_id;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_user_usage_stats(p_user_id UUID)
RETURNS TABLE(
    searches_month INTEGER,
    searches_day INTEGER, 
    searches_hour INTEGER,
    dms_month INTEGER,
    dms_day INTEGER,
    dms_hour INTEGER
) AS $$
BEGIN
    -- Ensure user stats record exists
    INSERT INTO user_usage_stats (user_id)
    VALUES (p_user_id)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- Update counters (triggers will reset if needed)
    UPDATE user_usage_stats SET updated_at = NOW() WHERE user_id = p_user_id;
    
    -- Return current stats
    RETURN QUERY
    SELECT 
        searches_this_month,
        searches_today,
        searches_this_hour,
        dms_this_month,
        dms_today,
        dms_this_hour
    FROM user_usage_stats 
    WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Recreate RLS policies
CREATE POLICY "Service role can manage all usage data" ON usage_tracking
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage all usage stats" ON user_usage_stats
    FOR ALL USING (auth.role() = 'service_role');

-- Allow authenticated users to view their own data (if using Supabase auth)
CREATE POLICY "Users can view own usage tracking" ON usage_tracking
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view own usage stats" ON user_usage_stats  
    FOR SELECT USING (auth.uid() = user_id);

-- Alternative: Custom policies for JWT-based authentication
CREATE POLICY "JWT users can view own usage tracking" ON usage_tracking
    FOR SELECT USING (
        user_id = COALESCE(
            (current_setting('request.jwt.claims', true)::json->>'user_id')::uuid,
            (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
        )
    );

CREATE POLICY "JWT users can view own usage stats" ON user_usage_stats  
    FOR SELECT USING (
        user_id = COALESCE(
            (current_setting('request.jwt.claims', true)::json->>'user_id')::uuid,
            (current_setting('request.jwt.claims', true)::json->>'sub')::uuid
        )
    );

-- Recreate indexes for performance
CREATE INDEX IF NOT EXISTS idx_usage_stats_user_id ON user_usage_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_tracking_user_created ON usage_tracking(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_user_endpoint_created ON usage_tracking(user_id, endpoint, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_user_action_created ON usage_tracking(user_id, action_type, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_tracking(created_at);

-- Grant necessary permissions
GRANT SELECT, INSERT ON usage_tracking TO authenticated;
GRANT SELECT, INSERT, UPDATE ON user_usage_stats TO authenticated;
GRANT EXECUTE ON FUNCTION increment_usage_counter TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_usage_stats TO authenticated;

-- Add comments
COMMENT ON TABLE usage_tracking IS 'Tracks all API usage for rate limiting and analytics';
COMMENT ON TABLE user_usage_stats IS 'Optimized counters for quick rate limit checks';
COMMENT ON FUNCTION increment_usage_counter IS 'Safely increment usage counters for a user';
COMMENT ON FUNCTION get_user_usage_stats IS 'Get current usage stats with automatic counter resets';
