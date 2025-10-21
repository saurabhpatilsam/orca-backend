# 🚀 Async API - Background Task Processing

## Overview

The trading bot API now runs **asynchronously** using FastAPI's BackgroundTasks. This means:
- ✅ **Frontend gets immediate response** (no waiting)
- ✅ **Backend processes in background**
- ✅ **Poll for status updates**
- ✅ **No timeout issues**

---

## How It Works

### 1. Submit Request
```http
POST /api/v1/run-bot/max
```

**Frontend sends:** Trading configuration  
**Backend returns immediately:** 
```json
{
  "status": "queued",
  "message": "Trading bot queued for execution",
  "run_id": 123,
  "is_duplicate": false,
  "duplicate_run_ids": [],
  "note": "Use GET /api/v1/run-bot/configs/123 to check status"
}
```

**HTTP Status:** `202 Accepted` (not 200)

### 2. Backend Process Flow

```
Request arrives → Store config (status: "queued") → Return run_id
                                    ↓
              Background task starts (status: "running")
                                    ↓
              Trading system executes
                                    ↓
              Update status ("completed" or "failed")
```

### 3. Check Status
```http
GET /api/v1/run-bot/configs/{run_id}
```

**Response:**
```json
{
  "config": {
    "id": 123,
    "status": "running",  // or "queued", "completed", "failed"
    "config": {...},
    "strategy_config": {...},
    "created_by": "user@example.com",
    "created_at": "2025-10-21T20:00:00Z",
    "updated_at": "2025-10-21T20:00:05Z"
  }
}
```

---

## Status Flow

```
queued → running → completed
    ↓       ↓
    └───────→ failed
```

### Status Meanings:

| Status | Description |
|--------|-------------|
| `queued` | Request received, waiting to start |
| `running` | Currently executing trading logic |
| `completed` | Successfully finished |
| `failed` | Error occurred during execution |
| `stopped` | Manually stopped by user |

---

## API Endpoints

### 1. Submit Trading Bot (Async)
```http
POST /api/v1/run-bot/max
Content-Type: multipart/form-data

accountName: APEX_123456
contract: NQ
trading_mode: long
trading_side: high
point_strategy_key: 15_7_5_2
...
```

**Response:** `202 Accepted`
```json
{
  "status": "queued",
  "run_id": 123,
  "message": "Trading bot queued for execution"
}
```

### 2. Get Specific Run Status
```http
GET /api/v1/run-bot/configs/{run_id}
```

**Response:** `200 OK`
```json
{
  "config": {
    "id": 123,
    "status": "running",
    ...
  }
}
```

### 3. Get All Runs (Filtered)
```http
GET /api/v1/run-bot/configs?status=running
GET /api/v1/run-bot/configs?status=queued
GET /api/v1/run-bot/configs  // All statuses
```

**Response:**
```json
{
  "configs": [...],
  "count": 5
}
```

### 4. Get Active Runs
```http
GET /api/v1/run-bot/configs/active
```

Returns all runs with status "running" or "queued"

### 5. Update Status (Manual)
```http
PATCH /api/v1/run-bot/configs/{run_id}/status
Content-Type: application/json

{
  "status": "stopped"
}
```

---

## Frontend Implementation

### React/TypeScript Example

```typescript
// 1. Submit trading bot
async function startTradingBot(config) {
  const response = await fetch('http://localhost:8090/api/v1/run-bot/max', {
    method: 'POST',
    body: formData,
  });
  
  if (response.status === 202) {
    const data = await response.json();
    const runId = data.run_id;
    
    // Store run_id and start polling
    pollStatus(runId);
  }
}

// 2. Poll for status updates
async function pollStatus(runId) {
  const interval = setInterval(async () => {
    const response = await fetch(
      `http://localhost:8090/api/v1/run-bot/configs/${runId}`
    );
    
    const data = await response.json();
    const status = data.config.status;
    
    console.log(`Status: ${status}`);
    
    // Stop polling when done
    if (status === 'completed' || status === 'failed') {
      clearInterval(interval);
      handleCompletion(status);
    }
  }, 2000); // Poll every 2 seconds
}

// 3. Handle completion
function handleCompletion(status) {
  if (status === 'completed') {
    toast.success('Trading bot completed successfully!');
  } else {
    toast.error('Trading bot failed');
  }
}
```

### With React Hook

```typescript
function useTradingBot() {
  const [status, setStatus] = useState('idle');
  const [runId, setRunId] = useState(null);
  
  useEffect(() => {
    if (!runId) return;
    
    const interval = setInterval(async () => {
      const response = await fetch(
        `http://localhost:8090/api/v1/run-bot/configs/${runId}`
      );
      const data = await response.json();
      const newStatus = data.config.status;
      
      setStatus(newStatus);
      
      if (newStatus === 'completed' || newStatus === 'failed') {
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [runId]);
  
  const startBot = async (config) => {
    const response = await fetch('...', { method: 'POST', body: config });
    const data = await response.json();
    setRunId(data.run_id);
    setStatus('queued');
  };
  
  return { status, runId, startBot };
}

// Usage
function TradingDashboard() {
  const { status, startBot } = useTradingBot();
  
  return (
    <div>
      <button onClick={() => startBot(config)}>
        Start Trading Bot
      </button>
      <p>Status: {status}</p>
    </div>
  );
}
```

---

## Benefits

### ✅ No Timeouts
Long-running operations don't timeout the HTTP request

### ✅ Better UX
Users get immediate feedback and can continue using the app

### ✅ Scalability
Server can handle multiple concurrent requests

### ✅ Status Tracking
Full history and current state of all runs

### ✅ Retry Logic
Can retry failed runs easily

---

## Polling Strategy

### Recommended Intervals:

| Phase | Interval |
|-------|----------|
| First 10 seconds | 1 second |
| 10s - 1 minute | 2 seconds |
| After 1 minute | 5 seconds |
| After 5 minutes | 10 seconds |

### Exponential Backoff

```typescript
let pollInterval = 1000; // Start at 1 second

function poll() {
  setTimeout(async () => {
    const status = await checkStatus(runId);
    
    if (status !== 'completed' && status !== 'failed') {
      // Increase interval (max 10 seconds)
      pollInterval = Math.min(pollInterval * 1.5, 10000);
      poll();
    }
  }, pollInterval);
}
```

---

## WebSocket Alternative (Future)

For real-time updates without polling:

```python
# Backend (future enhancement)
@app.websocket("/ws/run/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: int):
    await websocket.accept()
    while True:
        status = get_status(run_id)
        await websocket.send_json({"status": status})
        await asyncio.sleep(1)
```

```typescript
// Frontend
const ws = new WebSocket(`ws://localhost:8090/ws/run/${runId}`);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  setStatus(data.status);
};
```

---

## Testing

### Test Async Flow

```bash
# 1. Start trading bot
curl -X POST http://localhost:8090/api/v1/run-bot/max \
  -F "accountName=APEX_123" \
  -F "contract=NQ" \
  -F "trading_mode=long" \
  -F "trading_side=high" \
  -F "point_strategy_key=15_7_5_2" \
  -F "point_position=aggressive" \
  -F "exit_strategy_key=15_15" \
  -F "dateFrom=2025-01-01T09:00:00" \
  -F "dateTo=2025-01-01T16:00:00" \
  -F "quantity=1" \
  -F "environment=PROD" \
  -F "user=test@example.com"

# Response: {"status":"queued","run_id":123}

# 2. Check status immediately
curl http://localhost:8090/api/v1/run-bot/configs/123
# Response: {"config":{"status":"queued",...}}

# 3. Check again after a few seconds
curl http://localhost:8090/api/v1/run-bot/configs/123
# Response: {"config":{"status":"running",...}}

# 4. Check when completed
curl http://localhost:8090/api/v1/run-bot/configs/123
# Response: {"config":{"status":"completed",...}}
```

---

## Monitoring

### Get All Active Runs
```bash
curl http://localhost:8090/api/v1/run-bot/configs/active
```

### Filter by Status
```bash
curl http://localhost:8090/api/v1/run-bot/configs?status=running
curl http://localhost:8090/api/v1/run-bot/configs?status=failed
```

---

## Database Schema

```sql
CREATE TABLE run_configs (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT valid_status CHECK (
        status IN ('queued', 'running', 'completed', 'failed', 'stopped')
    )
);
```

---

## Error Handling

### Backend Errors
If background task fails:
- Status automatically set to "failed"
- Error logged in backend logs
- Frontend sees "failed" status on next poll

### Frontend Errors
- **Network error during submission:** Retry submission
- **Network error during polling:** Continue polling (exponential backoff)
- **Status stuck on "running":** Show warning after timeout (e.g., 5 minutes)

---

## Migration

If you have existing database:

```sql
-- Run migration_add_queued_status.sql
ALTER TABLE run_configs DROP CONSTRAINT IF EXISTS valid_status;
ALTER TABLE run_configs ADD CONSTRAINT valid_status 
  CHECK (status IN ('queued', 'running', 'completed', 'failed', 'stopped'));
ALTER TABLE run_configs ALTER COLUMN status SET DEFAULT 'queued';
```

---

## Summary

✅ **Submit request → Get run_id immediately**  
✅ **Poll for status updates**  
✅ **No timeouts or blocking**  
✅ **Full status tracking**  
✅ **Scalable and user-friendly**  

The frontend never waits for long-running operations! 🎉
