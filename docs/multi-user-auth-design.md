# Cloudflare Tunnel Multi-User Authentication Design

> Date: 2026-05-29
> Scope: openbb-app backend + finanalyzer-app frontend

---

## 1. Architecture Overview

```
User ── HTTPS ──> Cloudflare Tunnel ──> cloudflared ──> Local Backend (FastAPI)
                     │                        │
                     ├── domain.com (SPA)      │
                     ├── domain.com/api/*      │
                     └── domain.com/auth/*     │
                                               │
                    Cloudflare Access (OIDC) ──┘
                    Google / GitHub / Email OTP
```

### Key Principles

| Principle | Rationale |
|-----------|-----------|
| **Tunnel as gateway** | Cloudflare Tunnel terminates TLS at edge, all traffic encrypted end-to-end |
| **Access as IdP** | Cloudflare Access provides OAuth/OIDC flows for Google/GitHub/Email |
| **Admin approval gate** | Backend implements a user status check (pending/active/rejected) that gates JWT issuance |
| **Per-user data isolation** | All database queries scoped by `user_id` |
| **Dual auth for OpenBB** | OpenBB Workspace uses per-user API keys; regular users use JWT from Access flow |

---

## 2. Component Design

### 2.1 Cloudflare Tunnel Configuration

```yaml
# config.yml for cloudflared
tunnel: <tunnel-uuid>
credentials-file: /path/to/credentials.json
ingress:
  # Frontend SPA
  - hostname: domain.com
    service: http://localhost:5173   # or :8001 for SPA served by FastAPI
    originRequest:
      noTLSVerify: true

  # Backend API
  - hostname: domain.com
    path: /api/*
    service: http://localhost:8001

  # Auth endpoints (publicly reachable, no Access policy)
  - hostname: domain.com
    path: /auth/register
    service: http://localhost:8001

  # Cloudflare Access callback
  - hostname: domain.com
    path: /auth/callback
    service: http://localhost:8001

  # Static assets
  - hostname: domain.com
    path: /assets/*
    service: http://localhost:5173

  # Default catch-all
  - service: http_status:404
```

**Cloudflare Access Application Setup:**

1. Create an Access Application in Zero Trust Dashboard
2. Application type: **Self-hosted**
3. Application domain: `domain.com`
4. Session duration: 24h
5. **Policies:**
   - `/auth/register`, `/auth/callback`, `/auth/health` → **Bypass** (no auth required)
   - `/api/*` → **Require** JWT validation
   - `/*` → **Require** JWT validation (SPA behind auth wall)
6. **Identity Providers:**
   - Google (one-click OAuth)
   - GitHub (one-click OAuth)
   - Email OTP (one-time PIN sent to email)
7. **OIDC App:** Enable Cloudflare Access as OIDC provider → obtain `client_id` and `client_secret`

### 2.2 Backend Authentication Module

#### New files in `openbb-app/src/openbb_app/core/`:

```
core/
├── auth.py             # Replaced: JWT middleware + Cloudflare token validation
├── auth_routes.py      # NEW: Registration, callback, admin approval endpoints
├── audit.py            # NEW: Audit logging service
├── models.py          # Updated: Add User model
└── database.py        # Updated: Add users table, audit_log table
```

#### User Model

```python
# src/openbb_app/core/models.py (additions)
from enum import Enum

class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"

class UserModel(BaseModel):
    id: str                 # UUID
    email: str              # unique
    name: str
    auth_provider: str      # "google" | "github" | "email"
    status: UserStatus = UserStatus.PENDING
    role: str = "user"      # "user" | "admin"
    api_key: str | None      # per-user API key for OpenBB Workspace
    created_at: str
    approved_at: str | None
    approved_by: str | None
    last_login_at: str | None

class AuditLogEntry(BaseModel):
    id: int
    user_id: str
    action: str             # "register" | "login" | "approve" | "reject"
    detail: dict | None
    ip_address: str
    timestamp: str
```

#### Authentication Flow

**Registration:**

```
POST /auth/register
{
    "email": "user@example.com",
    "name": "User Name",
    "auth_provider": "google"  // or "github" or "email"
}
→ 201 { "status": "pending", "message": "Registration submitted. Awaiting admin approval." }
```

**Callback (Cloudflare Access OIDC):**

```
GET /auth/callback?code=...&state=...
1. Validate authorization code with Cloudflare Access (/cdn-cgi/access/callback)
2. Extract user identity (email, name) from Cloudflare JWT
3. Look up user in database
4. If user.status == "active" → generate session JWT, redirect to SPA
5. If user.status == "pending" → redirect to "awaiting approval" page
6. If user.status == "rejected" → redirect to "access denied" page
```

**Admin Approval:**

```
POST /auth/admin/approve  (admin-auth required)
{
    "user_id": "uuid",
    "action": "approve"  // or "reject"
}
→ 200 { "status": "active" }
```

#### JWT Session Token

```python
# Generated after successful Cloudflare OIDC callback
jwt_payload = {
    "sub": user.id,
    "email": user.email,
    "name": user.name,
    "role": user.role,
    "iat": int(time.time()),
    "exp": int(time.time()) + 86400,  # 24h
}
token = jwt.encode(jwt_payload, JWT_SECRET, algorithm="HS256")
```

#### Middleware

```python
# FastAPI middleware: extracts user from JWT or API key
async def authenticate_request(request: Request, call_next):
    # Priority 1: API key (for OpenBB Workspace)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = get_user_by_api_key(api_key)
        if user and user.status == "active":
            request.state.user = user
            return await call_next(request)

    # Priority 2: Session JWT (for SPA users)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user = get_user_by_id(payload["sub"])
            if user and user.status == "active":
                request.state.user = user
                return await call_next(request)
        except jwt.ExpiredSignatureError:
            pass

    # Catch: Cloudflare Access JWT (alternative, direct JWT from Cf)
    cf_jwt = request.headers.get("Cf-Access-Jwt-Id-Token")
    if cf_jwt:
        payload = validate_cf_jwt(cf_jwt, CF_ACCESS_AUDIENCE)
        user = get_user_by_email(payload["email"])
        if user and user.status == "active":
            request.state.user = user
            return await call_next(request)

    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
```

### 2.3 Database Schema Additions

```sql
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    auth_provider TEXT NOT NULL,        -- 'google' | 'github' | 'email'
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'active' | 'rejected'
    role TEXT NOT NULL DEFAULT 'user',    -- 'user' | 'admin'
    api_key TEXT UNIQUE,                  -- per-user API key (for OpenBB)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    approved_by TEXT,
    last_login_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,                -- 'register' | 'login' | 'approve' | 'reject' | 'api_key_issue'
    detail TEXT,                         -- JSON blob with extra info
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- All existing tables get user_id column added
ALTER TABLE portfolio_stocks ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE transactions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE dashboards ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default';
```

### 2.4 Admin Approval Workflow

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│ User submits │ ──> │ Admin receives │ ──> │ Admin logs in │
│ registration │     │ notification   │     │ (SSO)         │
└─────────────┘     └───────────────┘     └──────────────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ Review user   │
                                          │ details       │
                                          └──────┬───────┘
                                                 │
                                    ┌────────────┴────────────┐
                                    ▼                         ▼
                            ┌────────────┐           ┌──────────────┐
                            │ Approve    │           │ Reject       │
                            │ status=active│         │ status=rejected│
                            │ Log audit   │           │ Log audit     │
                            │ Notify user |           │ Notify user   │
                            └────────────┘           └──────────────┘
```

**Admin endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/admin/users` | GET | admin | List all users with status, filterable |
| `/auth/admin/users/{id}` | GET | admin | User details + audit history |
| `/auth/admin/users/{id}/approve` | POST | admin | Approve user |
| `/auth/admin/users/{id}/reject` | POST | admin | Reject user |
| `/auth/admin/audit-log` | GET | admin | Full audit log with filters |

### 2.5 OpenBB Workspace Compatibility

OpenBB Workspace expects to authenticate via its own auth mechanism. We provide a **bridge**:

**Per-user API Key:**

```python
# Generated automatically when admin approves user
import secrets
api_key = "fina_" + secrets.token_urlsafe(32)

# Stored in users.api_key
```

**OpenBB Workspace Configuration:**

User configures in OpenBB Workspace:
- **Backend URL:** `https://domain.com`
- **API Key:** `fina_<user-specific-key>`

**Compatibility endpoints required by OpenBB Workspace:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/apps.json` | GET | Available apps - **key required** |
| `/widgets.json` | GET | Widget definitions - **key required** |
| `/agents.json` | GET | AI agents - **key required** |
| `/api/v1/*` | * | All data endpoints - **key or JWT** |

**Flow for OpenBB:**

```
OpenBB Workspace
    │
    ├─ Bearer <api-key> ──> /apps.json
    │                       │
    │                       └─ Middleware matches key → user → passes with user context
    │
    ├─ Bearer <api-key> ──> /widgets.json
    │
    └─ Bearer <api-key> ──> /api/v1/portfolio/stocks
                            │
                            └─ DatabaseManager with user_id scope
```

### 2.6 Frontend (finanalyzer-app) Changes

#### New Components

```
src/components/auth/
├── LoginPage.tsx          # Starting point (redirects to Cloudflare Access)
├── RegisterPage.tsx       # Registration form
├── CallbackHandler.tsx    # Handles OAuth callback, extracts JWT
├── PendingApproval.tsx    # "Awaiting admin approval" page
├── AdminUserList.tsx      # Admin panel: list + approve/reject users
├── useAuth.ts             # Auth context hook
└── authStore.ts           # Zustand store for auth state
```

**SPA Auth Flow:**

```typescript
// 1. User visits domain.com → check for session cookie / localStorage token
// 2. No token → redirect to /auth/login → which redirects to Cloudflare Access
// 3. Cloudflare Access authenticates via Google/GitHub/Email
// 4. Callback → backend validates → checks user status
// 5. Active user → get JWT → store in localStorage + cookie → redirect to SPA
// 6. All API calls include `Authorization: Bearer <jwt>`
```

**Protected Routes:**

```typescript
// Route guard component
function ProtectedRoute({ children }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <Loading />;
  if (!user) return <Navigate to="/auth/login" />;
  if (user.status === 'pending') return <Navigate to="/auth/pending" />;
  return children;
}
```

**Admin Routes:**

```typescript
function AdminRoute({ children }) {
  const { user } = useAuth();
  if (!user || user.role !== 'admin') return <Navigate to="/" />;
  return children;
}
```

---

## 3. Configuration Files

### 3.1 `.env` Additions

```bash
# === Cloudflare Access ===
CF_ACCESS_AUDIENCE=<audience-tag-from-access-application>
CF_ACCESS_CLIENT_ID=<oidc-client-id>
CF_ACCESS_CLIENT_SECRET=<oidc-client-secret>
CF_ACCESS_CALLBACK_URL=https://domain.com/auth/callback

# === JWT ===
JWT_SECRET=<strong-random-secret>
JWT_EXPIRY_HOURS=24

# === Admin ===
ADMIN_EMAILS=roger@example.com,admin@example.com  # comma-separated

# === Allowed Registrations ===
# Restrict to specific email domains or individual emails (regex)
ALLOWED_EMAIL_PATTERN=.*@example\.com|.*@gmail\.com
```

### 3.2 Cloudflare Access Application Settings

Navigate to **Zero Trust Dashboard → Access → Applications**:

| Setting | Value |
|---------|-------|
| Application Name | Finanalyzer |
| Domain | `domain.com` |
| Session Duration | 24h |
| App URL | `https://domain.com` |

**Add Policies:**

1. **`/auth/*` bypass policy:**
   - Rule: `Include → Everyone`
   - Action: **Bypass**

2. **`/api/*` auth policy:**
   - Rule: `Include → Email → *`
   - Action: **Allow**

3. **Root policy:**
   - Rule: `Include → Email → *`
   - Action: **Allow**

**Identity Providers:**

| Provider | Configured? | Notes |
|----------|-------------|-------|
| Google | Yes | One-click OAuth |
| GitHub | Yes | One-click OAuth |
| Email OTP | Yes | One-time PIN to email |

---

## 4. Security Considerations

| Concern | Mitigation |
|---------|-----------|
| JWT theft | Short expiry (24h) + refresh rotation; stored in httpOnly cookie |
| CSRF | SameSite=Strict on auth cookies; anti-CSRF token on admin endpoints |
| API key leak | Per-user keys can be revoked individually; rate-limit API endpoints |
| Unapproved access | Middleware checks `user.status == "active"` before every request |
| Audit trail | All auth actions logged with user_id, action, IP, user_agent |
| Email spoofing | Cloudflare Email OTP verified at edge |
| Tunnel security | `cloudflared` uses mutual TLS; no open ports on server |
| Data encryption | JWT signed with HS256; API keys stored as bcrypt hash; all traffic over HTTPS |

**Rate Limiting:**

```python
# Using slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/register")
@limiter.limit("5/hour")  # Max 5 registration attempts per IP per hour
async def register(...):
    pass
```

---

## 5. Implementation Phases

### Phase 1: Foundation (2-3 days)
| Step | Task | Files |
|------|------|-------|
| 1.1 | Set up Cloudflare Tunnel + config | `cloudflared/config.yml` |
| 1.2 | Configure Cloudflare Access application | Zero Trust Dashboard |
| 1.3 | Add `users` table + `audit_log` table | `core/models.py`, `core/database.py` |
| 1.4 | Implement JWT middleware | `core/auth.py` (rewrite) |

### Phase 2: Auth Flow (2-3 days)
| Step | Task | Files |
|------|------|-------|
| 2.1 | Registration endpoint | `core/auth_routes.py` |
| 2.2 | Cloudflare OIDC callback handler | `core/auth_routes.py` |
| 2.3 | Admin approval endpoints | `core/auth_routes.py` |
| 2.4 | Audit logging service | `core/audit.py` |
| 2.5 | Frontend auth components | `src/components/auth/*` |

### Phase 3: Data Isolation (1-2 days)
| Step | Task | Files |
|------|------|-------|
| 3.1 | Add `user_id` to all data tables | migration script |
| 3.2 | Update `DatabaseManager` for user scoping | `core/database.py` |
| 3.3 | Update route handlers to pass user context | `routes/portfolio.py`, `routes/dashboard.py` |

### Phase 4: OpenBB Workspace Integration (1 day)
| Step | Task | Files |
|------|------|-------|
| 4.1 | Per-user API key generation | `core/auth_routes.py` |
| 4.2 | API key middleware | `core/auth.py` |
| 4.3 | OpenBB Workspace auth test | Integration test |

### Phase 5: Testing & Docs (1-2 days)

| Test Case | Type |
|-----------|------|
| Registration with email | Functional |
| Registration with Google OAuth | Functional |
| Registration with GitHub OAuth | Functional |
| Admin approval flow | Functional |
| Rejected user login attempt | Edge case |
| Pending user login attempt | Edge case |
| JWT expiry / refresh | Edge case |
| OpenBB Workspace API key access | Integration |
| Per-user data isolation (user A cannot see user B's data) | Security |
| Rate limit exceeded | Error handling |
| Audit log completeness | Verification |
| Tunnel routing correctness | Integration |

---

## 6. Configuration Quick-Start

### Step 1: Install and Authenticate cloudflared

```bash
# Install
brew install cloudflared

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create finanalyzer

# Route DNS
cloudflared tunnel route dns finanalyzer domain.com
```

### Step 2: Configure Cloudflare Access

1. Go to **Zero Trust → Access → Applications → Add an application**
2. Select **Self-hosted**
3. Domain: `domain.com`
4. Enable **OIDC** → note the **Client ID** and **Client Secret**
5. Add Identity Providers: Google, GitHub, Email OTP
6. Add bypass policy for `/auth/*`
7. Add auth policy for `/*`

### Step 3: Start Cloudflare Tunnel

```bash
cloudflared tunnel run finanalyzer
```

### Step 4: Update Backend `.env`

```bash
CF_ACCESS_AUDIENCE=your-audience-tag
CF_ACCESS_CLIENT_ID=your-client-id
CF_ACCESS_CLIENT_SECRET=your-client-secret
CF_ACCESS_CALLBACK_URL=https://domain.com/auth/callback
JWT_SECRET=your-random-secret-min-32-chars
ADMIN_EMAILS=roger@example.com
ALLOWED_EMAIL_PATTERN=.*@example\.com|.*@gmail\.com
```

### Step 5: Start Backend

```bash
cd openbb-app && uv run openbb-app
```

---

## 7. Architecture Decision Records

### ADR-1: Cloudflare Access as IdP vs Self-managed Auth

**Decision:** Use Cloudflare Access as the OIDC provider.

**Rationale:**
- Zero additional login UI — Google/GitHub/Email OTP built-in
- Client ID/Secret integration matches user requirements
- No password storage liability
- Tunnel + Access share same dashboard
- Already using Cloudflare for DNS

**Trade-off:** Admin approval requires a custom database layer (cannot be done in Access alone). Mitigated by the hybrid approach: Access handles OAuth, backend handles approval gating.

### ADR-2: Per-User API Keys for OpenBB Workspace

**Decision:** Generate `fina_<token>` style API keys per approved user.

**Rationale:**
- OpenBB Workspace expects static API key in its config
- Per-user keys enable individual revocations and audit
- Keys map to user_id for data isolation

**Trade-off:** User must copy API key from profile page to OpenBB Workspace config. Acceptable as a one-time setup.

### ADR-3: Same DB with `user_id` vs Per-User DB files

**Decision:** Same SQLite database with `user_id` column.

**Rationale:**
- Simpler migration path (add columns, not split files)
- Admin can query across all users
- No need to manage per-user file lifecycle
- Compatible with future PostgreSQL migration

**Trade-off:** SQLite WAL mode needed for concurrency. If user count exceeds ~50 concurrent, consider migrating to PostgreSQL.
