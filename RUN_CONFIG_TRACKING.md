# Run Config Tracking System

## Overview
This system tracks all `run_orca_system` calls by storing configuration data in Supabase, including who created each run, when it was created, and its current status.

## Setup

### 1. Create Supabase Table
Run the SQL script in your Supabase dashboard:
```bash
# The SQL script is available in: supabase_setup.sql
```

Go to your Supabase project → SQL Editor → paste and run the script.

### 2. Table Schema
The `run_configs` table stores:
- **id**: Auto-incrementing primary key
- **config**: JSONB object containing the complete run configuration
- **strategy_config**: JSONB object with identifying fields for duplicate detection (instrument_name, way, point_type, point_strategy_key, point_position, exit_strategy_key)
- **created_by**: Username/identifier (defaults to "system")
- **status**: Current status - `running`, `completed`, `failed`, or `stopped`
- **created_at**: Timestamp when the run was initiated
- **updated_at**: Timestamp when status was last updated

**Note**: See [DUPLICATE_DETECTION.md](DUPLICATE_DETECTION.md) for details on duplicate configuration detection.

## Features

### Automatic Tracking
Every time the `/run-bot/max` endpoint is called, the system automatically:
1. Stores the run configuration in Supabase
2. Tracks it as "running"
3. Updates status to "completed" on success
4. Updates status to "failed" on error

### API Endpoints

#### 1. Get All Run Configs
```http
GET /run-bot/configs?status=running
```

**Query Parameters:**
- `status` (optional): Filter by status (`running`, `completed`, `failed`, `stopped`)

**Response:**
```json
{
  "configs": [
    {
      "id": 1,
      "config": {...},
      "created_by": "john_doe",
      "status": "running",
      "created_at": "2025-10-19T16:30:00Z",
      "updated_at": null
    }
  ],
  "count": 1
}
```

#### 2. Get Active Configs Only
```http
GET /run-bot/configs/active
```

Returns only configs with status = "running".

**Response:**
```json
{
  "configs": [...],
  "count": 3
}
```

#### 3. Update Config Status
```http
PATCH /run-bot/configs/{run_id}/status
Content-Type: application/json

{
  "status": "stopped"
}
```

**Valid status values:**
- `running` - Currently executing
- `completed` - Finished successfully
- `failed` - Ended with an error
- `stopped` - Manually stopped

#### 4. Check for Duplicate Configurations
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

See [DUPLICATE_DETECTION.md](DUPLICATE_DETECTION.md) for complete documentation.

#### 5. Get Duplicates of a Specific Run
```http
GET /run-bot/configs/{run_id}/duplicates
```

## Usage Examples

### Starting a Run with User Tracking
When calling the `/run-bot/max` endpoint, include the `user` parameter:

```javascript
const formData = new FormData();
formData.append('accountName', 'APEX_136189');
formData.append('contract', 'NQ');
formData.append('user', 'john_doe'); // Track who started this run
// ... other parameters

fetch('/run-bot/max', {
  method: 'POST',
  body: formData
});
```

### Viewing All Active Runs
```bash
curl -X GET "http://localhost:8000/run-bot/configs/active"
```

### Stopping a Running Config
```bash
curl -X PATCH "http://localhost:8000/run-bot/configs/123/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "stopped"}'
```

## Code Changes Summary

### 1. Supabase Handler (`app/services/orca_supabase/orca_supabase.py`)
Added functions:
- `insert_run_config()` - Store new run configuration
- `update_run_config_status()` - Update run status
- `get_all_run_configs()` - Retrieve configs with optional filtering
- `get_active_run_configs()` - Get only running configs

### 2. Run Orca System (`app/api/v1/endpoints/max_live.py`)
Modified `run_orca_system()` to:
- Store config on startup (status: "running")
- Update to "completed" on success
- Update to "failed" on error
- Handle serialization of non-JSON objects

### 3. API Router (`app/api/v1/orca_max_router.py`)
Added:
- `user` parameter to `/max` endpoint
- `GET /configs` - View all configs
- `GET /configs/active` - View active configs
- `PATCH /configs/{run_id}/status` - Update status

## Notes

- If no user is specified, it defaults to "system"
- Config data is automatically serialized (datetime objects converted to strings)
- Status updates are timestamped automatically
- The system tracks both manual and automatic status changes
