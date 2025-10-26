# 🔐 JWT Authentication Guide for Orca Trading API

## Overview

All trading bot API endpoints are now **protected with JWT authentication**. You must include a valid JWT token in the Authorization header to access these endpoints.

---

## 🚫 Public Endpoints (No Auth Required)

These endpoints do NOT require authentication:

### Health Check
```http
GET /health
```
Used for monitoring and health checks.

### Authentication Endpoints
```http
POST /api/v1/auth/signup
POST /api/v1/auth/signin
POST /api/v1/auth/signout
```

### Root
```http
GET /
```
Returns API information and documentation link.

---

## 🔒 Protected Endpoints (Auth Required)

All other endpoints require JWT authentication:

### Trading Bot Endpoints
```http
POST   /api/v1/run-bot/max                    # Create trading bot
POST   /api/v1/run-bot/max-backtest           # Run backtest
GET    /api/v1/run-bot/configs                # Get all configs
GET    /api/v1/run-bot/configs/{run_id}       # Get specific config
GET    /api/v1/run-bot/configs/active         # Get active configs
PATCH  /api/v1/run-bot/configs/{run_id}/status # Update config status
POST   /api/v1/run-bot/configs/check-duplicate # Check duplicates
GET    /api/v1/run-bot/configs/{run_id}/duplicates # Get duplicates
```

All these require a valid JWT token!

---

## 🎯 How to Use JWT Authentication

### Step 1: Get Your Token

Sign in to get your JWT token:

```bash
curl -X POST http://localhost:8090/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your@email.com",
    "password": "yourpassword"
  }'
```

**Response:**
```json
{
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "your@email.com",
    "name": "Your Name",
    "confirmed": true
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Save the `access_token`!** You'll need it for all API calls.

---

### Step 2: Use Token in API Calls

Include the token in the Authorization header:

```bash
curl -X POST http://localhost:8090/api/v1/run-bot/max \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -F "accountName=APEX_123456" \
  -F "contract=NQ" \
  -F "trading_mode=long" \
  -F "trading_side=high" \
  # ... other parameters
```

**Important:** Replace `YOUR_ACCESS_TOKEN_HERE` with your actual token!

---

## 📱 Frontend Integration

### JavaScript/TypeScript Example

```typescript
// 1. Sign in and get token
const signIn = async (email: string, password: string) => {
  const response = await fetch('http://localhost:8090/api/v1/auth/signin', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  
  const data = await response.json();
  
  // Store token in localStorage
  localStorage.setItem('access_token', data.access_token);
  
  return data;
};

// 2. Use token in protected API calls
const createTradingBot = async (config: any) => {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    throw new Error('Not authenticated');
  }
  
  const formData = new FormData();
  formData.append('accountName', config.accountName);
  formData.append('contract', config.contract);
  // ... add other fields
  
  const response = await fetch('http://localhost:8090/api/v1/run-bot/max', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,  // Include token!
    },
    body: formData,
  });
  
  if (response.status === 401) {
    // Token expired or invalid
    localStorage.removeItem('access_token');
    throw new Error('Authentication failed. Please sign in again.');
  }
  
  return await response.json();
};

// 3. Create an API client with automatic token handling
class ApiClient {
  private baseURL = 'http://localhost:8090';
  private token: string | null = null;
  
  constructor() {
    this.token = localStorage.getItem('access_token');
  }
  
  setToken(token: string) {
    this.token = token;
    localStorage.setItem('access_token', token);
  }
  
  clearToken() {
    this.token = null;
    localStorage.removeItem('access_token');
  }
  
  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {};
    
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    
    return headers;
  }
  
  async get(endpoint: string) {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });
    
    if (response.status === 401) {
      this.clearToken();
      throw new Error('Unauthorized');
    }
    
    return await response.json();
  }
  
  async post(endpoint: string, body: any) {
    const headers = this.getHeaders();
    
    // Handle FormData vs JSON
    if (!(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'POST',
      headers,
      body,
    });
    
    if (response.status === 401) {
      this.clearToken();
      throw new Error('Unauthorized');
    }
    
    return await response.json();
  }
}

// Usage:
const api = new ApiClient();

// Sign in
const { access_token } = await api.post('/api/v1/auth/signin', {
  email: 'user@example.com',
  password: 'password123'
});
api.setToken(access_token);

// Now all API calls include the token automatically
const configs = await api.get('/api/v1/run-bot/configs');
const newBot = await api.post('/api/v1/run-bot/max', formData);
```

---

## 🔄 Token Expiration

### Token Lifetime
- Default: **24 hours** (1440 minutes)
- Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` env variable

### Handling Expired Tokens

When a token expires, the API returns:
```json
{
  "detail": "Could not validate credentials"
}
```
**Status Code:** `401 Unauthorized`

**What to do:**
1. Clear the stored token
2. Redirect user to sign in
3. Get a new token

### Auto-Refresh Pattern

```typescript
class AuthenticatedApiClient {
  async callWithRetry(fn: () => Promise<any>) {
    try {
      return await fn();
    } catch (error) {
      if (error.message === 'Unauthorized') {
        // Try to refresh or re-authenticate
        // Then retry the call
        await this.reAuthenticate();
        return await fn();
      }
      throw error;
    }
  }
  
  private async reAuthenticate() {
    // Implement your re-authentication logic
    // e.g., use refresh token or ask user to sign in again
  }
}
```

---

## 🚨 Error Responses

### 401 Unauthorized

**When it happens:**
- No Authorization header
- Invalid token
- Expired token
- Token signature verification failed

**Response:**
```json
{
  "detail": "Could not validate credentials"
}
```

**Solution:** Sign in again to get a new token.

---

### 400 Bad Request

**When it happens:**
- User account not confirmed

**Response:**
```json
{
  "detail": "User account not confirmed. Please contact an administrator."
}
```

**Solution:** Wait for admin to confirm your account in the database.

---

## 🧪 Testing with cURL

### Complete Example

```bash
# 1. Sign in
TOKEN=$(curl -s -X POST http://localhost:8090/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123"}' \
  | jq -r '.access_token')

# 2. Use token in protected endpoint
curl -X GET http://localhost:8090/api/v1/run-bot/configs \
  -H "Authorization: Bearer $TOKEN"

# 3. Create trading bot with token
curl -X POST http://localhost:8090/api/v1/run-bot/max \
  -H "Authorization: Bearer $TOKEN" \
  -F "accountName=APEX_123456" \
  -F "contract=NQ" \
  -F "trading_mode=long" \
  -F "trading_side=high" \
  -F "point_strategy_key=15_7_5_2" \
  -F "point_position=aggressive" \
  -F "exit_strategy_key=15_15" \
  -F "dateFrom=2025-01-01T09:00:00" \
  -F "dateTo=2025-01-01T16:00:00" \
  -F "quantity=1" \
  -F "environment=PROD"
```

---

## 🔍 Testing in Swagger/OpenAPI

When using the interactive API docs at `/docs`:

1. Click the **Authorize** button (🔓 icon)
2. Enter your token in the format: `Bearer YOUR_TOKEN`
3. Click **Authorize**
4. Now all protected endpoints will include your token automatically!

---

## 🛡️ Security Best Practices

### ✅ DO

- Store tokens securely (httpOnly cookies or secure localStorage)
- Use HTTPS in production
- Set appropriate token expiration times
- Clear tokens on sign out
- Handle 401 errors gracefully
- Rotate tokens periodically

### ❌ DON'T

- Store tokens in plain text
- Share tokens between users
- Commit tokens to git
- Use tokens in URL parameters
- Ignore token expiration
- Use same token on multiple devices without refresh mechanism

---

## 📊 Token Structure

Your JWT token contains:

```json
{
  "sub": "user-uuid-here",           // User ID
  "email": "user@example.com",       // User email
  "name": "User Name",               // User name
  "exp": 1736899200,                 // Expiration timestamp
  "iat": 1736812800                  // Issued at timestamp
}
```

**Note:** You can decode the token at https://jwt.io (for debugging only)

---

## 🎯 Quick Reference

| Action | Endpoint | Auth Required? |
|--------|----------|----------------|
| Sign Up | `POST /api/v1/auth/signup` | ❌ No |
| Sign In | `POST /api/v1/auth/signin` | ❌ No |
| Sign Out | `POST /api/v1/auth/signout` | ✅ Yes |
| Health Check | `GET /health` | ❌ No |
| Create Bot | `POST /api/v1/run-bot/max` | ✅ Yes |
| Get Configs | `GET /api/v1/run-bot/configs` | ✅ Yes |
| All other bot endpoints | Various | ✅ Yes |

---

## 🆘 Troubleshooting

### "Could not validate credentials"

**Possible causes:**
1. Token is missing
2. Token is malformed
3. Token has expired
4. Token signature is invalid

**Solution:** Sign in again to get a fresh token.

---

### "User account not confirmed"

**Cause:** Admin hasn't confirmed your account yet.

**Solution:** 
1. Contact admin
2. Or run in Supabase:
```sql
UPDATE users SET confirmed = true WHERE email = 'your@email.com';
```

---

### Token works in Postman but not in browser

**Possible causes:**
1. CORS issues
2. Token not being sent from frontend
3. Token format incorrect (missing "Bearer " prefix)

**Solution:** Check browser console for errors and verify token is included in headers.

---

## 📝 Summary

✅ **Health endpoint:** No auth required  
✅ **Auth endpoints:** No auth required (for signup/signin)  
✅ **All trading bot endpoints:** JWT auth required  
✅ **Token format:** `Authorization: Bearer <token>`  
✅ **Token lifetime:** 24 hours default  
✅ **On 401 error:** Clear token and re-authenticate  

**Your API is now secure! 🔒**
