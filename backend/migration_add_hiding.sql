-- Migration: Add job hiding and source toggle features
-- Run this SQL in your Supabase SQL editor to update your existing database

-- Add new columns to sources table
ALTER TABLE sources
ADD COLUMN IF NOT EXISTS enabled boolean NOT NULL DEFAULT true,
ADD COLUMN IF NOT EXISTS last_error text,
ADD COLUMN IF NOT EXISTS jobs_found_last_scan int DEFAULT 0;

-- Add new columns to jobs table
ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS hidden boolean NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS hidden_at timestamptz;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS jobs_hidden_idx ON jobs (hidden);
CREATE INDEX IF NOT EXISTS sources_enabled_idx ON sources (enabled);

-- Update existing rows to have default values
UPDATE sources SET enabled = true WHERE enabled IS NULL;
UPDATE jobs SET hidden = false WHERE hidden IS NULL;

-- Verify changes
SELECT 'Migration completed successfully!' as status;
