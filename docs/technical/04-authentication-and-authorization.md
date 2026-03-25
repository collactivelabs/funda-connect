# 04 — Authentication & Authorization

> **Status:** Draft  
> **Last Updated:** 2026-03-25

---

## 1. Overview

FundaConnect uses a **JWT-based authentication** system with access and refresh tokens. The system supports email/password registration and Google OAuth 2.0 social login. Role-based access control (RBAC) governs endpoint permissions.

---

## 2. Authentication Strategy

### 2.1 Token Architecture

| Token | Purpose | Lifetime | Storage (Client) |
|-------|---------|----------|-------------------|
| Access Token | API request authentication | 30 minutes | Memory (JS variable) |
| Refresh Token | Obtain new access tokens | 7 days | HttpOnly cookie (web) / secure storage (mobile) |

**Access Token Payload (JWT Claims):**
```json
{
  "sub": "user-uuid",
  "email": "sipho@example.co.za",
  "role": "parent",
  "email_verified": true,
  "iat": 1711360000,
  "exp": 1711361800,
  "jti": "unique-token-id"
}
```

**Refresh Token:** Opaque token stored in Redis with user association. Supports rotation — each refresh invalidates the previous token and issues a new pair.

### 2.2 Token Refresh Flow

```
Client                          API                         Redis
  │                              │                            │
  │  Request with expired AT     │                            │
  │ ───────────────────────────► │                            │
  │  401 Unauthorized            │                            │
  │ ◄─────────────────────────── │                            │
  │                              │                            │
  │  POST /auth/refresh          │                            │
  │  Cookie: refresh_token=RT1   │                            │
  │ ───────────────────────────► │                            │
  │                              │  Validate RT1              │
  │                              │ ──────────────────────────►│
  │                              │  Valid + user_id           │
  │                              │ ◄──────────────────────────│
  │                              │  Delete RT1, Store RT2     │
  │                              │ ──────────────────────────►│
  │                              │                            │
  │  200: new AT2 + RT2 cookie   │                            │
  │ ◄─────────────────────────── │                            │
```

### 2.3 Refresh Token Rotation & Reuse Detection

When a refresh token is used, it is immediately invalidated and a new one is issued. If an already-invalidated refresh token is presented (reuse detection), all tokens for that user are revoked, forcing re-authentication.

```python
# Pseudocode for reuse detection
async def refresh_token(token: str):
    stored = await redis.get(f"refresh:{token}")
    if stored is None:
        # Token not found — could be reuse of invalidated token
        if await redis.get(f"refresh:used:{token}"):
            # REUSE DETECTED — revoke all user tokens
            await revoke_all_user_tokens(user_id)
            raise SecurityException("Token reuse detected")
        raise InvalidTokenException()
    
    user_id = stored["user_id"]
    await redis.delete(f"refresh:{token}")
    await redis.set(f"refresh:used:{token}", "1", ex=86400 * 7)
    
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    return new_access, new_refresh
```

---

## 3. Registration Flow

### 3.1 Email/Password Registration

```
1. User submits: email, password, first_name, last_name, phone, role
2. Server validates:
   - Email format and uniqueness
   - Password strength (min 8 chars, 1 uppercase, 1 number, 1 special)
   - Phone format (SA mobile: +27 XX XXX XXXX)
3. Server creates user record (email_verified = false)
4. Server generates email verification token (UUID, stored in Redis, 24hr expiry)
5. Server sends verification email with link: https://fundaconnect.co.za/verify?token=xxx
6. Server returns 201 with user data (no tokens yet)
7. User clicks verification link
8. Server validates token, sets email_verified = true
9. User can now log in
```

### 3.2 Google OAuth 2.0

```
1. Client redirects to Google OAuth consent screen
2. User grants consent → Google redirects back with auth code
3. Client sends auth code to POST /auth/google
4. Server exchanges code for Google tokens
5. Server fetches Google user profile (email, name, avatar)
6. Server checks if email exists:
   - Yes: Link Google account, issue tokens
   - No: Create new user, issue tokens
7. Server returns access + refresh tokens
```

---

## 4. Password Management

### 4.1 Password Hashing
- Algorithm: **bcrypt** (via `passlib`)
- Work factor: 12 rounds
- Pepper: Application-level secret prepended before hashing

### 4.2 Password Reset Flow
```
1. POST /auth/forgot-password { email }
2. Server generates reset token (UUID, Redis, 1hr expiry)
3. Server sends reset email with link
4. User clicks link, enters new password
5. POST /auth/reset-password { token, new_password }
6. Server validates token, hashes new password, updates user
7. Server revokes all existing refresh tokens for that user
8. Server returns success; user must log in with new password
```

### 4.3 Password Requirements
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character
- Not in a common password list (top 10,000)
- Not the same as email or name

---

## 5. Role-Based Access Control (RBAC)

### 5.1 Roles

| Role | Description |
|------|-------------|
| `parent` | Homeschooling parent/guardian. Can manage learners, book lessons, leave reviews. |
| `teacher` | Educator offering lessons. Can manage profile, availability, view bookings, log lessons. |
| `admin` | Platform administrator. Full access to all resources, verification management, reporting. |

### 5.2 Permission Matrix

| Resource | Parent | Teacher | Admin |
|----------|--------|---------|-------|
| Browse teachers | ✅ | ✅ | ✅ |
| View teacher profile | ✅ | ✅ | ✅ |
| Edit own user profile | ✅ (own) | ✅ (own) | ✅ (any) |
| Manage teacher profile | ❌ | ✅ (own) | ✅ (any) |
| Upload verification docs | ❌ | ✅ (own) | ❌ |
| Review verification docs | ❌ | ❌ | ✅ |
| Manage learners | ✅ (own) | ❌ | ✅ (any) |
| Create bookings | ✅ | ❌ | ✅ |
| View bookings | ✅ (own) | ✅ (own) | ✅ (any) |
| Cancel bookings | ✅ (own) | ✅ (own) | ✅ (any) |
| Complete lessons | ❌ | ✅ (own) | ✅ |
| Leave reviews | ✅ | ❌ | ❌ |
| Reply to reviews | ❌ | ✅ (own) | ✅ |
| View payment history | ✅ (own) | ✅ (own) | ✅ (any) |
| View earnings/payouts | ❌ | ✅ (own) | ✅ (any) |
| Admin dashboard | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ✅ |

### 5.3 Implementation

```python
from functools import wraps
from fastapi import Depends, HTTPException, status

def require_role(*roles: str):
    """Dependency that checks the current user has one of the required roles."""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

# Usage in route:
@router.get("/admin/dashboard")
async def admin_dashboard(user: User = Depends(require_role("admin"))):
    ...

@router.post("/bookings")
async def create_booking(user: User = Depends(require_role("parent", "admin"))):
    ...
```

### 5.4 Resource-Level Authorization

Beyond role checks, endpoints enforce ownership:
- Parents can only access their own learners, bookings, and payment history
- Teachers can only access their own profile, bookings, and earnings
- Implemented via query-level filtering (e.g., `WHERE parent_id = current_user.parent_profile.id`)

---

## 6. Security Headers & Middleware

```python
# Applied globally via middleware
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; ...",
}
```

---

## 7. Session Management

- Access tokens are stateless (validated by signature)
- Refresh tokens are stateful (stored in Redis with user association)
- Active session listing: Users can see all active sessions (device, location, last used)
- Session revocation: Users can revoke individual sessions or all sessions
- Admin forced logout: Admins can force-logout any user by clearing their refresh tokens
