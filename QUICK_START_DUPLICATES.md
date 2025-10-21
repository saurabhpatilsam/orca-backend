# Quick Start: Duplicate Detection

## Setup (One-Time)

1. **Run SQL in Supabase**
   ```bash
   # Open Supabase → SQL Editor
   # Copy and run: supabase_setup.sql
   ```

2. **Done!** The system is ready to use.

---

## How to Use

### Option 1: Just Run (Automatic Detection)

The system automatically detects duplicates when you call `/run-bot/max`:

```bash
POST /run-bot/max
```

**Response includes:**
```json
{
  "status": "success",
  "run_id": 123,
  "is_duplicate": true,          ← Tells you if it's a duplicate
  "duplicate_run_ids": [101, 102] ← IDs of matching runs
}
```

**Logs will show:**
```
⚠️  DUPLICATE CONFIGURATION DETECTED!
   Active duplicate run(s) found: [101, 102]
```

---

### Option 2: Check Before Running

**Before** starting a run, check if it's a duplicate:

```bash
POST /run-bot/configs/check-duplicate

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
  "active_count": 2,
  "active_duplicates": [...]  ← List of active runs with same config
}
```

**Then decide:**
- ✅ Stop the old runs first
- ✅ Continue anyway
- ✅ Cancel the new run

---

## What Makes a Duplicate?

These 6 fields must **ALL match**:

| Field | Example | 
|-------|---------|
| `instrument_name` | "NQ" |
| `way` | "LONG" |
| `point_type` | "BUY" |
| `point_strategy_key` | "15_7_5_2" |
| `point_position` | "INSIDE" |
| `exit_strategy_key` | "15_15" |

**Everything else is ignored** (dates, quantity, accounts, notes, user, etc.)

---

## Common Scenarios

### Scenario 1: Prevent Duplicates

```python
# Check first
response = requests.post(
    "/run-bot/configs/check-duplicate",
    json=strategy_config
)

if response.json()["has_active_duplicate"]:
    print("❌ Duplicate found! Aborting.")
    exit(1)

# Then run
requests.post("/run-bot/max", data=form_data)
```

### Scenario 2: Auto-Stop Old Duplicates

```python
# Check for duplicates
response = requests.post(
    "/run-bot/configs/check-duplicate",
    json=strategy_config
)

# Stop all active duplicates
for dup in response.json()["active_duplicates"]:
    requests.patch(
        f"/run-bot/configs/{dup['id']}/status",
        json={"status": "stopped"}
    )

# Now run the new one
requests.post("/run-bot/max", data=form_data)
```

### Scenario 3: Just Log and Continue

```python
# Just run - system will warn but continue
response = requests.post("/run-bot/max", data=form_data)

if response.json()["is_duplicate"]:
    print(f"⚠️  Warning: Duplicate of runs {response.json()['duplicate_run_ids']}")
```

---

## API Cheat Sheet

| Endpoint | Purpose |
|----------|---------|
| `POST /run-bot/max` | Run bot (auto-detects duplicates) |
| `POST /configs/check-duplicate` | Check if config is duplicate |
| `GET /configs/active` | List all active runs |
| `GET /configs/{id}/duplicates` | Find duplicates of a run |
| `PATCH /configs/{id}/status` | Stop/update a run |

---

## Current Behavior

- ✅ **Detects** duplicates automatically
- ✅ **Logs** warning when found
- ✅ **Continues** running (non-blocking)
- ✅ **Returns** duplicate info in response

**To change this behavior**, modify `run_orca_system()` in:
```
app/api/v1/endpoints/max_live.py
```

Example - Block duplicates:
```python
if has_duplicate:
    raise HTTPException(
        status_code=409,
        detail=f"Duplicate config! Active runs: {duplicate_ids}"
    )
```

---

## Need More Info?

- **Full Documentation**: `DUPLICATE_DETECTION.md`
- **Config Tracking**: `RUN_CONFIG_TRACKING.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
