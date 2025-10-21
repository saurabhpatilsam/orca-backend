-- SQL Script to create run_configs table in Supabase
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS run_configs (
    id BIGSERIAL PRIMARY KEY,
    config JSONB NOT NULL,
    strategy_config JSONB NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT valid_status CHECK (status IN ('queued', 'running', 'completed', 'failed', 'stopped'))
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_run_configs_status ON run_configs(status);
CREATE INDEX IF NOT EXISTS idx_run_configs_created_by ON run_configs(created_by);
CREATE INDEX IF NOT EXISTS idx_run_configs_created_at ON run_configs(created_at DESC);
-- Index for duplicate detection - GIN index for JSONB equality comparisons
CREATE INDEX IF NOT EXISTS idx_run_configs_strategy_config ON run_configs USING GIN (strategy_config);

-- Enable Row Level Security (RLS) if needed
-- ALTER TABLE run_configs ENABLE ROW LEVEL SECURITY;

-- Optional: Create a policy to allow all operations (adjust based on your security needs)
-- CREATE POLICY "Enable all operations for authenticated users" 
-- ON run_configs FOR ALL 
-- USING (true);

-- Add a comment to the table
COMMENT ON TABLE run_configs IS 'Stores Orca trading system run configurations with tracking information';
COMMENT ON COLUMN run_configs.config IS 'JSON object containing the complete run configuration';
COMMENT ON COLUMN run_configs.strategy_config IS 'JSON object containing only the identifying fields (instrument_name, way, point_type, point_strategy_key, point_position, exit_strategy_key) for duplicate detection';
COMMENT ON COLUMN run_configs.created_by IS 'Username or identifier of who initiated the run';
COMMENT ON COLUMN run_configs.status IS 'Current status: queued, running, completed, failed, or stopped';
COMMENT ON COLUMN run_configs.created_at IS 'Timestamp when the run was initiated';
COMMENT ON COLUMN run_configs.updated_at IS 'Timestamp when the status was last updated';
