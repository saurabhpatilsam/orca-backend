# Duplicate Configuration Detection

## Overview
This system automatically detects when the same trading strategy configuration is used multiple times. It separates identifying fields from the full configuration for efficient comparison and duplicate detection.

## What Makes a Configuration a Duplicate?

A configuration is considered a duplicate when ALL of these **strategy-identifying fields** match:

```python
{
    "instrument_name": "NQ",           # Trading instrument
    "way": "LONG",                     # Trading direction (LONG/SHORT)
    "point_type": "BUY",              # Point type
    "point_strategy_key": "15_7_5_2", # Point strategy
    "point_position": "INSIDE",       # Position type
    "exit_strategy_key": "15_15"      # Exit strategy
}
```

Other fields like `start_time`, `end_time`, `quantity`, `accounts_ids`, `notes`, and `user` do NOT affect duplicate detection.

## How It Works

### 1. Dual Storage Structure
Each run configuration is stored with two JSON objects:

- **`config`**: Complete configuration with all fields
- **`strategy_config`**: Only the 6 identifying fields (for fast comparison)

This design makes duplicate detection efficient and explicit.

### 2. Automatic Detection
When `run_orca_system` is called:

1. **Extract** strategy config from the full config
2. **Check** for active duplicates in the database
3. **Log** a warning if duplicates are found
4. **Store** both full config and strategy config
5. **Return** duplicate information in the response

### 3. Database Schema
```sql
CREATE TABLE run_configs (
    id BIGSERIAL PRIMARY KEY,
    config JSONB NOT NULL,              -- Full configuration
    strategy_config JSONB NOT NULL,     -- Identifying fields only
    created_by TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ
);

-- GIN index for fast JSONB comparison
CREATE INDEX idx_run_configs_strategy_config 
ON run_configs USING GIN (strategy_config);
```

## API Endpoints

### 1. Check for Duplicates Before Running
```http
POST /run-bot/configs/check-duplicate
Content-Type: application/json

{
  "instrument_name": "NQ",
  "way": "LONG",
  "point_type": "BUY",
  "point_strategy_key": "15_7_5_2",
  "point_position": "INSIDE",
  "exit_strategy_key": "15_15"
}
```

**Response:**
```json
{
  "has_active_duplicate": true,
  "active_duplicates": [
    {
      "id": 123,
      "strategy_config": {...},
      "created_by": "john_doe",
      "status": "running",
      "created_at": "2025-10-21T12:00:00Z"
    }
  ],
  "active_count": 1,
  "all_duplicates": [...],
  "total_count": 5,
  "strategy_config": {...}
}
```

### 2. Find Duplicates of a Specific Run
```http
GET /run-bot/configs/{run_id}/duplicates
```

**Response:**
```json
{
  "run_id": 123,
  "strategy_config": {...},
  "duplicates": [
    {
      "id": 456,
      "status": "completed",
      "created_at": "2025-10-20T10:00:00Z"
    }
  ],
  "count": 1
}
```

### 3. Run Bot (with duplicate detection)
```http
POST /run-bot/max
```

The response now includes duplicate information:
```json
{
  "status": "success",
  "run_id": 789,
  "is_duplicate": true,
  "duplicate_run_ids": [123, 456]
}
```

## Example Usage

### Scenario 1: Prevent Running Duplicates

```python
import requests

# Check for duplicates first
strategy = {
    "instrument_name": "NQ",
    "way": "LONG",
    "point_type": "BUY",
    "point_strategy_key": "15_7_5_2",
    "point_position": "INSIDE",
    "exit_strategy_key": "15_15"
}

response = requests.post(
    "http://localhost:8000/run-bot/configs/check-duplicate",
    json=strategy
)

result = response.json()

if result["has_active_duplicate"]:
    print(f"⚠️  Warning: {result['active_count']} active duplicate(s) found!")
    print(f"Active runs: {[d['id'] for d in result['active_duplicates']]}")
    
    # Option 1: Stop the old run first
    for duplicate in result["active_duplicates"]:
        requests.patch(
            f"http://localhost:8000/run-bot/configs/{duplicate['id']}/status",
            json={"status": "stopped"}
        )
    
    # Option 2: Don't run if duplicates exist
    # exit(1)
else:
    print("✓ No duplicates found. Safe to proceed.")
```

### Scenario 2: Monitor Duplicate Runs

```python
# Get all active configs
response = requests.get("http://localhost:8000/run-bot/configs/active")
active_runs = response.json()["configs"]

# Check each for duplicates
for run in active_runs:
    dup_response = requests.get(
        f"http://localhost:8000/run-bot/configs/{run['id']}/duplicates"
    )
    duplicates = dup_response.json()
    
    if duplicates["count"] > 0:
        print(f"Run {run['id']} has {duplicates['count']} duplicate(s)")
```

## Logging

When a duplicate is detected, the system logs a clear warning:

```
⚠️  DUPLICATE CONFIGURATION DETECTED!
   Active duplicate run(s) found: [123, 456]
   Strategy config: {'instrument_name': 'NQ', 'way': 'LONG', ...}
   Consider stopping the existing run before starting a new one.
```

## Future Enhancements (Ideas)

You can extend this system with:

1. **Auto-stop duplicates**: Automatically stop old runs when a new one starts
2. **Require confirmation**: Reject duplicate runs unless explicitly confirmed
3. **Duplicate limits**: Allow max N duplicates per strategy
4. **Smart merging**: Combine duplicate runs into a single execution
5. **Alerts**: Send notifications when duplicates are detected
6. **Dashboard**: Visual display of duplicate configurations

## Implementation Details

### Key Files

1. **`supabase_setup.sql`**: Database schema with `strategy_config` column
2. **`app/services/orca_supabase/config_utils.py`**: Helper functions for extracting/normalizing strategy config
3. **`app/services/orca_supabase/orca_supabase.py`**: Duplicate detection functions
4. **`app/api/v1/endpoints/max_live.py`**: Automatic duplicate checking in `run_orca_system`
5. **`app/api/v1/orca_max_router.py`**: API endpoints for duplicate checking

### Helper Functions

**Extract Strategy Config:**
```python
from app.services.orca_supabase.config_utils import extract_strategy_config

strategy = extract_strategy_config(full_config)
# Returns only the 6 identifying fields
```

**Check for Active Duplicates:**
```python
from app.services.orca_supabase.orca_supabase import has_active_duplicate

has_dup, duplicates = has_active_duplicate(strategy_config)
if has_dup:
    print(f"Found {len(duplicates)} active duplicate(s)")
```

**Find All Duplicates:**
```python
from app.services.orca_supabase.orca_supabase import find_duplicate_configs

# All duplicates (any status)
all_dups = find_duplicate_configs(strategy_config)

# Only running duplicates
running_dups = find_duplicate_configs(strategy_config, status_filter="running")
```

## Database Migration

If you already have a `run_configs` table without `strategy_config`:

```sql
-- Add the new column
ALTER TABLE run_configs ADD COLUMN strategy_config JSONB;

-- Create the index
CREATE INDEX idx_run_configs_strategy_config 
ON run_configs USING GIN (strategy_config);

-- Note: Existing rows will have NULL strategy_config
-- You may need to backfill or mark them as legacy
```

## Testing

Run the SQL setup script first:
```bash
# In Supabase SQL Editor, run: supabase_setup.sql
```

Then test duplicate detection:
```bash
# Start first run
curl -X POST http://localhost:8000/run-bot/max \
  -F "contract=NQ" \
  -F "trading_mode=LONG" \
  -F "trading_side=BUY" \
  # ... other params

# Start duplicate run (same strategy)
curl -X POST http://localhost:8000/run-bot/max \
  -F "contract=NQ" \
  -F "trading_mode=LONG" \
  -F "trading_side=BUY" \
  # ... same strategy params

# Check logs for duplicate warning
```

## Notes

- Duplicate detection is **non-blocking** by default (warns but allows execution)
- You can add blocking logic in `run_orca_system` if needed
- The `strategy_config` is automatically normalized for consistent comparison
- Enum values are converted to strings before comparison
