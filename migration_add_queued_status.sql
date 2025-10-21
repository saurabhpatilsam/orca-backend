-- Migration to add 'queued' status to existing run_configs table
-- Run this in Supabase SQL Editor if you already have the table

-- Drop the old constraint
ALTER TABLE run_configs DROP CONSTRAINT IF EXISTS valid_status;

-- Add new constraint with 'queued' status
ALTER TABLE run_configs 
ADD CONSTRAINT valid_status 
CHECK (status IN ('queued', 'running', 'completed', 'failed', 'stopped'));

-- Update default status to 'queued'
ALTER TABLE run_configs 
ALTER COLUMN status SET DEFAULT 'queued';

-- Update comment
COMMENT ON COLUMN run_configs.status IS 'Current status: queued, running, completed, failed, or stopped';
