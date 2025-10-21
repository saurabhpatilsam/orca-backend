# Duplicate Configuration Detection - Implementation Summary

## What Was Implemented

A complete duplicate configuration detection system that:
1. **Separates identifying fields** from full configuration
2. **Automatically detects** duplicate runs
3. **Provides API endpoints** for checking duplicates
4. **Logs warnings** when duplicates are found
5. **Maintains backward compatibility** with existing code

---

## Files Modified

### 1. Database Schema
**File**: `supabase_setup.sql`
- Added `strategy_config` JSONB column
- Added GIN index for fast duplicate lookups
- Fixed `user` → `created_by` (reserved keyword issue)

### 2. Supabase Handler
**File**: `app/services/orca_supabase/orca_supabase.py`
- Updated `insert_run_config()` to accept `strategy_config` parameter
- Added `find_duplicate_configs()` - Find all matching configurations
- Added `has_active_duplicate()` - Check for active duplicates
- Changed `user` parameter to `created_by`

### 3. Config Utilities (NEW)
**File**: `app/services/orca_supabase/config_utils.py`
- `STRATEGY_IDENTIFYING_FIELDS` - List of fields that define a duplicate
- `extract_strategy_config()` - Extract identifying fields from full config
- `normalize_strategy_config()` - Normalize for consistent comparison

### 4. Run Orca System
**File**: `app/api/v1/endpoints/max_live.py`
- Import duplicate detection functions
- Extract strategy config before running
- Check for active duplicates
- Log warning if duplicates found
- Store both full config and strategy config
- Return duplicate information in response
- Fixed parameter from `user` to `created_by`

### 5. API Router
**File**: `app/api/v1/orca_max_router.py`
- Import duplicate detection utilities
- Added `POST /configs/check-duplicate` endpoint
- Added `GET /configs/{run_id}/duplicates` endpoint
- Fixed parameter from `user` to `created_by`

### 6. Documentation (NEW)
- **`DUPLICATE_DETECTION.md`**: Complete feature documentation
- **`RUN_CONFIG_TRACKING.md`**: Updated with new endpoints
- **`IMPLEMENTATION_SUMMARY.md`**: This file

---

## The 6 Identifying Fields

A configuration is a **duplicate** when these fields match:

```python
{
    "instrument_name": "NQ",           # Contract (NQ, ES, etc.)
    "way": "LONG",                     # Direction (LONG/SHORT)
    "point_type": "BUY",              # Point type
    "point_strategy_key": "15_7_5_2", # Point strategy
    "point_position": "INSIDE",       # Position (INSIDE/OUTSIDE)
    "exit_strategy_key": "15_15"      # Exit strategy
}
```

**Non-identifying fields** (these DON'T affect duplicates):
- `start_time`, `end_time` - Different time ranges
- `quantity` - Different position sizes
- `accounts_ids` - Different accounts
- `notes` - Different notes
- `user` - Different users
- `environment` - Dev/production

---

## API Endpoints

### Check Before Running
```bash
POST /run-bot/configs/check-duplicate
```
Check if a strategy configuration already exists.

### Find Duplicates of a Run
```bash
GET /run-bot/configs/{run_id}/duplicates
```
Get all configurations that match a specific run.

### Get All Configs
```bash
GET /run-bot/configs?status=running
```
List all run configs (with optional status filter).

### Get Active Configs
```bash
GET /run-bot/configs/active
```
List only running configurations.

### Update Status
```bash
PATCH /run-bot/configs/{run_id}/status
```
Update a configuration's status.

---

## How Duplicate Detection Works

### Automatic Flow

When `/run-bot/max` is called:

```
1. Extract strategy_config from run_config
   ├─ Only 6 identifying fields
   └─ Normalized to strings

2. Check Supabase for matching strategy_config
   ├─ Query: WHERE strategy_config = {...} AND status = 'running'
   └─ Uses GIN index for fast lookup

3. If duplicates found:
   ├─ Log warning with duplicate IDs
   ├─ Continue running (non-blocking)
   └─ Return is_duplicate: true

4. Store in database:
   ├─ config: Full configuration
   ├─ strategy_config: Identifying fields only
   └─ created_by, status, timestamps

5. Return response:
   {
     "status": "success",
     "run_id": 123,
     "is_duplicate": true,
     "duplicate_run_ids": [456, 789]
   }
```

### Database Structure

```
run_configs table:
┌────┬─────────────┬──────────────────┬────────────┬──────────┐
│ id │   config    │ strategy_config  │ created_by │  status  │
├────┼─────────────┼──────────────────┼────────────┼──────────┤
│ 1  │ {full JSON} │ {6 fields only}  │ john_doe   │ running  │
│ 2  │ {full JSON} │ {6 fields only}  │ jane_doe   │ completed│
│ 3  │ {full JSON} │ {SAME 6 fields}  │ john_doe   │ running  │ ← Duplicate!
└────┴─────────────┴──────────────────┴────────────┴──────────┘
                        ↑
                    GIN Index
              (fast JSONB equality)
```

---

## Example Responses

### Response from `/run-bot/max`

**No Duplicate:**
```json
{
  "status": "success",
  "run_id": 123,
  "is_duplicate": false,
  "duplicate_run_ids": []
}
```

**With Duplicate:**
```json
{
  "status": "success",
  "run_id": 124,
  "is_duplicate": true,
  "duplicate_run_ids": [123]
}
```

### Response from `/configs/check-duplicate`

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

---

## Log Output

When a duplicate is detected:

```log
WARNING - ⚠️  DUPLICATE CONFIGURATION DETECTED!
WARNING -    Active duplicate run(s) found: [123, 456]
WARNING -    Strategy config: {'instrument_name': 'NQ', 'way': 'LONG', ...}
WARNING -    Consider stopping the existing run before starting a new one.
INFO - Run config stored in Supabase with ID: 789
INFO - This run (ID: 789) is a duplicate of: [123, 456]
```

---

## Migration Steps

### If You Already Have Data

**Option 1: Fresh Start**
```sql
DROP TABLE IF EXISTS run_configs;
-- Then run supabase_setup.sql
```

**Option 2: Migration**
```sql
-- Add new column to existing table
ALTER TABLE run_configs ADD COLUMN strategy_config JSONB;
CREATE INDEX idx_run_configs_strategy_config 
ON run_configs USING GIN (strategy_config);

-- Existing records will have NULL strategy_config
-- New runs will populate it automatically
```

### If Starting Fresh
```bash
# Just run the SQL script in Supabase
# File: supabase_setup.sql
```

---

## Testing the Feature

### Test 1: Run Same Config Twice

```bash
# First run
curl -X POST http://localhost:8000/run-bot/max \
  -F "contract=NQ" \
  -F "trading_mode=LONG" \
  -F "trading_side=BUY" \
  -F "point_strategy_key=15_7_5_2" \
  -F "point_position=INSIDE" \
  -F "exit_strategy_key=15_15" \
  -F "user=test_user"

# Response: "is_duplicate": false

# Second run (same strategy)
curl -X POST http://localhost:8000/run-bot/max \
  -F "contract=NQ" \
  -F "trading_mode=LONG" \
  -F "trading_side=BUY" \
  -F "point_strategy_key=15_7_5_2" \
  -F "point_position=INSIDE" \
  -F "exit_strategy_key=15_15" \
  -F "user=test_user"

# Response: "is_duplicate": true, "duplicate_run_ids": [...]
```

### Test 2: Check for Duplicates

```bash
curl -X POST http://localhost:8000/run-bot/configs/check-duplicate \
  -H "Content-Type: application/json" \
  -d '{
    "instrument_name": "NQ",
    "way": "LONG",
    "point_type": "BUY",
    "point_strategy_key": "15_7_5_2",
    "point_position": "INSIDE",
    "exit_strategy_key": "15_15"
  }'
```

### Test 3: Get Active Duplicates

```bash
curl http://localhost:8000/run-bot/configs/active
```

---

## Future Enhancement Ideas

Based on your needs, you could:

1. **Block duplicates** - Raise an error instead of warning
2. **Auto-stop old runs** - Stop previous runs when starting a duplicate
3. **Require confirmation** - Force user to acknowledge duplicates
4. **Duplicate limits** - Allow max N concurrent duplicates
5. **Strategy groups** - Tag related strategies
6. **Performance tracking** - Compare performance across duplicate runs

---

## Key Benefits

✅ **Separated concerns** - Identifying fields vs. full config  
✅ **Fast lookups** - GIN index on strategy_config  
✅ **Non-intrusive** - Warns but doesn't block by default  
✅ **Flexible** - Easy to add blocking/auto-stop logic later  
✅ **Trackable** - Full history of duplicate runs  
✅ **API-first** - Check duplicates programmatically  

---

## Need Help?

- **Duplicate Detection**: See `DUPLICATE_DETECTION.md`
- **Config Tracking**: See `RUN_CONFIG_TRACKING.md`
- **Database Setup**: See `supabase_setup.sql`
- **Code Examples**: See documentation files above
