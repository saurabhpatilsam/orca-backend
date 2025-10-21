# Backend Authentication Setup

This guide explains the backend-based authentication system for the Orca Trading Platform.

## Architecture

**Backend (FastAPI + Python):**
- JWT-based authentication
- Password hashing with bcrypt
- Session management in Supabase
- User confirmation workflow
- Multi-tenancy support

**Frontend communicates via API only** - No direct database access

---

## Setup Steps

### 1. Install Dependencies

```bash
cd orca-backend
poetry install
```

### 2. Run Database Migrations

Execute the `auth_schema.sql` file in your Supabase SQL Editor:

```bash
# Copy the contents of auth_schema.sql and run it in Supabase Dashboard → SQL Editor
```

This creates:
- `users` table (with `confirmed` field)
- `sessions` table
- `organizations` table
- `organization_members` table
- `user_permissions` table
- `verification_tokens` table

### 3. Configure Environment Variables

Update your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# JWT Configuration
JWT_SECRET_KEY=your_super_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# API Configuration
PORT=8090
API_KEY=your_api_key
```

**Generate JWT_SECRET_KEY:**
```bash
openssl rand -hex 32
```

### 4. Start the Backend Server

```bash
poetry run python -m app.server
```

The API will be available at `http://localhost:8090`

---

## API Endpoints

Base URL: `http://localhost:8090/api/v1`

### Authentication Endpoints

#### 1. **Sign Up** (Create Account)
```http
POST /api/v1/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "name": "John Doe"
}
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "confirmed": false,
  "is_active": true,
  "created_at": "2025-01-21T14:30:00Z",
  "last_login": null
}
```

**Note:** User is created but NOT confirmed. Admin must confirm before signin.

---

#### 2. **Sign In** (Login)
```http
POST /api/v1/auth/signin
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "confirmed": true,
    "is_active": true,
    "created_at": "2025-01-21T14:30:00Z",
    "last_login": "2025-01-21T15:00:00Z"
  }
}
```

**Error Cases:**
- `401`: Invalid credentials
- `401`: Account not confirmed
- `401`: Account deactivated

---

#### 3. **Sign Out** (Logout)
```http
POST /api/v1/auth/signout
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Successfully signed out"
}
```

---

#### 4. **Get Current User**
```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "confirmed": true,
  "is_active": true,
  "created_at": "2025-01-21T14:30:00Z",
  "last_login": "2025-01-21T15:00:00Z"
}
```

---

#### 5. **Get All Users** (Admin)
```http
GET /api/v1/auth/users
Authorization: Bearer <access_token>
```

**Response:**
```json
[
  {
    "id": "uuid",
    "email": "user1@example.com",
    "name": "User One",
    "confirmed": true,
    "is_active": true,
    "created_at": "2025-01-21T14:30:00Z",
    "last_login": "2025-01-21T15:00:00Z"
  },
  {
    "id": "uuid2",
    "email": "user2@example.com",
    "name": "User Two",
    "confirmed": false,
    "is_active": true,
    "created_at": "2025-01-21T14:35:00Z",
    "last_login": null
  }
]
```

---

#### 6. **Confirm User** (Admin)
```http
POST /api/v1/auth/users/{user_id}/confirm
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "confirmed": true,
  "is_active": true,
  "created_at": "2025-01-21T14:30:00Z",
  "last_login": null
}
```

---

#### 7. **Get User Permissions**
```http
GET /api/v1/auth/users/{user_id}/permissions
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "user_id": "uuid",
  "permissions": ["account1", "account2", "admin"]
}
```

---

## User Confirmation Workflow

1. **User signs up** → Account created with `confirmed = false`
2. **Admin views unconfirmed users** → `GET /api/v1/auth/users` (filter by `confirmed = false`)
3. **Admin confirms user** → `POST /api/v1/auth/users/{user_id}/confirm`
4. **User can now sign in** → `POST /api/v1/auth/signin`

---

## Security Features

### ✅ Password Security
- Passwords hashed with bcrypt (passlib)
- Minimum 8 characters required
- Never stored in plain text

### ✅ JWT Tokens
- Signed with HS256 algorithm
- 24-hour expiration (configurable)
- Stored as hash in sessions table

### ✅ Session Management
- Each login creates a session record
- Tokens validated against active sessions
- Sessions expire after 24 hours
- Sign out invalidates session

### ✅ User Confirmation
- New users require admin confirmation
- `confirmed` field prevents unauthorized access
- Protects against automated registration attacks

### ✅ CORS Protection
- Configured for specific frontend origins
- Credentials support enabled
- Prevents unauthorized cross-origin requests

---

## Database Schema

### Users Table
- `id` (UUID, Primary Key)
- `email` (Unique, Email validation)
- `password_hash` (Bcrypt hashed)
- `name` (Optional)
- **`confirmed` (Boolean, Default: false)** ← Admin must set to true
- `is_active` (Boolean, Default: true)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)
- `last_login` (Timestamp, Nullable)

### Sessions Table
- `id` (UUID)
- `user_id` (Foreign Key → users)
- `token_hash` (SHA256 of JWT)
- `ip_address` (Optional)
- `user_agent` (Optional)
- `expires_at` (Timestamp)
- `created_at` (Timestamp)

---

## Testing the API

### Using curl:

**Sign Up:**
```bash
curl -X POST http://localhost:8090/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","name":"Test User"}'
```

**Sign In:**
```bash
curl -X POST http://localhost:8090/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

**Get Current User:**
```bash
curl -X GET http://localhost:8090/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## Frontend Integration

The frontend should:
1. **Store JWT token** in memory or httpOnly cookie
2. **Include token in headers** for authenticated requests
3. **Handle 401 errors** by redirecting to login
4. **Never access database directly**

Example frontend request:
```javascript
const response = await fetch('http://localhost:8090/api/v1/auth/me', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

---

## Next Steps

1. ✅ Run `auth_schema.sql` in Supabase
2. ✅ Install dependencies: `poetry install`
3. ✅ Configure environment variables
4. ✅ Start backend server
5. ⏭️ Update frontend to use backend API
6. ⏭️ Test authentication flow
7. ⏭️ Implement admin user confirmation UI

---

## API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8090/docs`
- **ReDoc**: `http://localhost:8090/redoc`

---

## Troubleshooting

**"Account not confirmed" error:**
- Admin needs to confirm the user via `/api/v1/auth/users/{user_id}/confirm`

**Token expired:**
- Token lasts 24 hours by default
- User needs to sign in again

**Database connection error:**
- Check SUPABASE_URL and SUPABASE_KEY in `.env`
- Ensure Supabase project is active

**Import errors:**
- Run `poetry install` to install all dependencies
- Ensure you're in the orca-backend directory

---

Need help? Check the `/docs` endpoint for interactive API documentation!
