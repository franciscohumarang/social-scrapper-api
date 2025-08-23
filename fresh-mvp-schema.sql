-- Fresh MVP Database Schema
-- Use this if you want to start clean (will lose existing data)

-- Drop existing tables (be careful!)
 DROP TABLE IF EXISTS users CASCADE;
 DROP TABLE IF EXISTS messages CASCADE;
 DROP TABLE IF EXISTS leads CASCADE;
 DROP TABLE IF EXISTS campaigns CASCADE;
 DROP TABLE IF EXISTS accounts CASCADE;

-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    plan TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trial_start TIMESTAMP,
    trial_end TIMESTAMP,
    trial_leads_used INTEGER,
    trial_dms_used INTEGER,
    lemon_squeezy_customer_id TEXT,
    current_day_search_limit INTEGER,
    current_day_search_used INTEGER,
    daily_searches_reset_at TIMESTAMP DEFAULT NOW() + INTERVAL '1 day',
    current_month_leads_used INTEGER,
    current_month_dms_used INTEGER,
    current_month_leads_limit INTEGER,
    current_month_dms_limit INTEGER,
    lemon_squeezy_subscription_id TEXT,
    current_period_end TIMESTAMP.
    status TEXT

    


);


-- Create simplified MVP schema
CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  platform TEXT NOT NULL CHECK (platform IN ('reddit', 'twitter')),
  username TEXT NOT NULL,
  content TEXT NOT NULL, -- Post content that shows pain point
  url TEXT NOT NULL, -- Link to the original post
  score INTEGER NOT NULL CHECK (score >= 1 AND score <= 10), -- AI buying intent score
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  contacted_at TIMESTAMP,
    post_date TIMESTAMP,
  -- Optional fields for search context
  matched_keyword TEXT,
  scrape_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create simplified MVP schema
CREATE TABLE qualified_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  platform TEXT NOT NULL CHECK (platform IN ('reddit', 'twitter')),
  username TEXT NOT NULL,
  content TEXT NOT NULL, -- Post content that shows pain point
  url TEXT NOT NULL, -- Link to the original post
  score INTEGER NOT NULL CHECK (score >= 1 AND score <= 10), -- AI buying intent score
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'replied')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  post_date TIMESTAMP,
  contacted_at TIMESTAMP,
  
  -- Optional fields for search context
  matched_keyword TEXT,
  scrape_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  is_outbound BOOLEAN NOT NULL, -- true = sent by user, false = reply from lead
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'replied')), 
  sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User Settings (simplified) - includes basic profile info for personalized DMs
CREATE TABLE settings (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  
  -- API Credentials
  reddit_client_id TEXT,
  reddit_client_secret TEXT
  reddit_username TEXT,
  twitter_username TEXT,
  x_api_key TEXT,
  dm_schedule JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'saas', 'b2b', 'b2c', 'agency', 'physical'
    description TEXT,
    website_url TEXT,
        
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Archived leads table for storing user's archived leads
CREATE TABLE archived_leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  original_lead_id UUID NOT NULL, -- Reference to original lead ID
  platform TEXT NOT NULL CHECK (platform IN ('reddit', 'twitter')),
  username TEXT NOT NULL,
  content TEXT NOT NULL,
  url TEXT NOT NULL,
  score INTEGER NOT NULL CHECK (score >= 1 AND score <= 10),
  status TEXT NOT NULL CHECK (status IN ('new', 'contacted', 'replied')),
  matched_keyword TEXT,
  scrape_timestamp TIMESTAMP,
  contacted_at TIMESTAMP,
  lead_created_at TIMESTAMP NOT NULL, -- Original lead creation time
  archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  archive_reason TEXT -- Optional reason for archiving
);
-- Create indexes for performance
CREATE INDEX idx_leads_user_id ON leads(user_id);
CREATE INDEX idx_leads_platform ON leads(platform);
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_score ON leads(score);
CREATE INDEX idx_leads_created_at ON leads(created_at);

CREATE INDEX idx_messages_lead_id ON messages(lead_id);
CREATE INDEX idx_messages_is_outbound ON messages(is_outbound);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_sent_at ON messages(sent_at);

CREATE INDEX idx_archived_leads_user_id ON archived_leads(user_id);
CREATE INDEX idx_archived_leads_platform ON archived_leads(platform);
CREATE INDEX idx_archived_leads_score ON archived_leads(score);
CREATE INDEX idx_archived_leads_archived_at ON archived_leads(archived_at);

-- Row Level Security (RLS) policies
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE archived_leads ENABLE ROW LEVEL SECURITY;

-- RLS Policies for leads
CREATE POLICY "Users can view their own leads" ON leads
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own leads" ON leads
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own leads" ON leads
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own leads" ON leads
  FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for messages
CREATE POLICY "Users can view messages for their leads" ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM leads 
      WHERE leads.id = messages.lead_id 
      AND leads.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert messages for their leads" ON messages
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM leads 
      WHERE leads.id = messages.lead_id 
      AND leads.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update messages for their leads" ON messages
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM leads 
      WHERE leads.id = messages.lead_id 
      AND leads.user_id = auth.uid()
    )
  );

-- RLS Policies for settings
CREATE POLICY "Users can manage their own settings" ON settings
  FOR ALL USING (auth.uid() = user_id);

-- RLS Policies for products
CREATE POLICY "Users can view their own products" ON products
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own products" ON products
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own products" ON products
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own products" ON products
  FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for qualified_leads
-- RLS Policies for leads
CREATE POLICY "Users can view their own qualified leads" ON qualified_leads
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own qualified leads" ON qualified_leads
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own qualified leads" ON qualified_leads
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own qualified leads" ON qualified_leads
  FOR DELETE USING (auth.uid() = user_id);