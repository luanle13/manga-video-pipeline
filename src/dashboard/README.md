# Admin Dashboard Authentication

Secure JWT-based authentication module for the admin dashboard using httpOnly cookies.

## Features

- 🔐 **Bcrypt password hashing**: Industry-standard password security
- 🎫 **JWT tokens**: Stateless authentication with expiration
- 🍪 **httpOnly cookies**: Protection against XSS attacks
- 🛡️ **CSRF protection**: SameSite=Strict cookie attribute
- 🔒 **Secure by default**: HTTPS-only cookies in production
- 🚪 **Middleware protection**: Automatic authentication checks
- ⏱️ **Token expiration**: Configurable token lifetime

## Installation

Dependencies are listed in `requirements.txt`:

```bash
pip install python-jose[cryptography]>=3.3 bcrypt>=4.0 python-multipart>=0.0.6
```

## Quick Start

### 1. Generate Secret Key

Generate a secure random secret key for JWT signing:

```python
import secrets

# Generate 32 random bytes, encode as hex
secret_key = secrets.token_hex(32)
print(secret_key)
# Example: 'a1b2c3d4e5f6...' (64 characters)
```

**Production**: Store in AWS Secrets Manager:

```python
from src.common.secrets import SecretsClient

secrets_client = SecretsClient(region="us-east-1")
secrets_client.create_secret(
    secret_name="manga-pipeline/jwt-secret",
    secret_value={"jwt_secret_key": secret_key}
)
```

### 2. Hash Initial Admin Password

```python
from src.dashboard.auth import hash_password

# Hash password
hashed = hash_password("your-secure-password")
print(hashed)

# Store in Secrets Manager or DynamoDB
```

### 3. Set Up FastAPI Application

```python
from fastapi import FastAPI, Depends
from src.dashboard.auth import AuthMiddleware, get_current_user

app = FastAPI()

# Load JWT secret from Secrets Manager
secret_key = "your-secret-key-from-secrets-manager"

# Store in app state for get_current_user dependency
app.state.jwt_secret_key = secret_key

# Add authentication middleware
app.add_middleware(AuthMiddleware, secret_key=secret_key)

# Protected route
@app.get("/dashboard")
async def dashboard(username: str = Depends(get_current_user)):
    return {"message": f"Welcome {username}"}
```

### 4. Implement Login Endpoint

```python
from fastapi import HTTPException, Response
from src.dashboard.auth import verify_password, create_access_token, set_auth_cookie

@app.post("/api/auth/login")
async def login(username: str, password: str, response: Response):
    # Load user from database/secrets
    stored_hash = load_user_password_hash(username)

    # Verify password
    if not verify_password(password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create JWT token
    token = create_access_token(
        username=username,
        secret_key=app.state.jwt_secret_key,
        expires_hours=24
    )

    # Set httpOnly cookie
    set_auth_cookie(response, token, max_age=86400, secure=True)

    return {"message": "Login successful"}
```

### 5. Implement Logout Endpoint

```python
from src.dashboard.auth import clear_auth_cookie

@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}
```

## API Reference

### Password Functions

#### `hash_password(plain_password: str) -> str`

Hash a password using bcrypt with automatic salt generation.

```python
from src.dashboard.auth import hash_password

hashed = hash_password("secure-password-123")
# '$2b$12$...' (60 characters)
```

**Returns**: Bcrypt hash as string (safe to store in database)

#### `verify_password(plain_password: str, hashed_password: str) -> bool`

Verify a password against a bcrypt hash.

```python
from src.dashboard.auth import verify_password

is_valid = verify_password("user-input", stored_hash)
if is_valid:
    print("Password correct!")
```

**Returns**: `True` if password matches, `False` otherwise

**Note**: Always returns `False` for invalid hashes (no exceptions)

### JWT Token Functions

#### `create_access_token(username: str, secret_key: str, expires_hours: int = 24) -> str`

Create a signed JWT access token.

```python
from src.dashboard.auth import create_access_token

token = create_access_token(
    username="admin",
    secret_key=app.state.jwt_secret_key,
    expires_hours=24  # Token valid for 24 hours
)
```

**Parameters**:
- `username`: Username to encode in token
- `secret_key`: Secret key for signing (keep secure!)
- `expires_hours`: Token lifetime in hours (default: 24)

**Returns**: Encoded JWT token as string

**Token payload**:
```json
{
  "sub": "admin",
  "exp": 1234567890,
  "iat": 1234567800
}
```

#### `verify_token(token: str, secret_key: str) -> str | None`

Verify and decode a JWT token.

```python
from src.dashboard.auth import verify_token

username = verify_token(token, secret_key)
if username:
    print(f"Valid token for: {username}")
else:
    print("Invalid or expired token")
```

**Returns**:
- `str`: Username if token is valid
- `None`: If token is expired, invalid signature, or malformed

### FastAPI Dependency

#### `get_current_user(request: Request) -> str`

FastAPI dependency to get authenticated user from request.

```python
from fastapi import Depends
from src.dashboard.auth import get_current_user

@app.get("/api/jobs")
async def get_jobs(username: str = Depends(get_current_user)):
    # username is extracted from JWT cookie
    return {"jobs": [...], "user": username}
```

**Raises**:
- `HTTPException(401)`: If token is missing or invalid
- `HTTPException(500)`: If JWT secret not configured

**Requires**: `app.state.jwt_secret_key` must be set

### Middleware

#### `AuthMiddleware`

Starlette/FastAPI middleware for automatic authentication checks.

```python
from src.dashboard.auth import AuthMiddleware

app.add_middleware(
    AuthMiddleware,
    secret_key="your-jwt-secret",
    excluded_paths={"/login", "/api/auth/login", "/static", "/health"}
)
```

**Parameters**:
- `secret_key`: JWT secret for token verification
- `excluded_paths`: Set of paths that don't require auth (optional)

**Default excluded paths**:
- `/login` - Login page
- `/api/auth/login` - Login API endpoint
- `/static` - Static files (CSS, JS, images)

**Behavior**:
- Valid token → Continue to handler, set `request.state.username`
- Missing/invalid token → Redirect to `/login` (302)
- Excluded paths → Always allowed

**Example**: Accessing username in handler

```python
@app.get("/dashboard")
async def dashboard(request: Request):
    username = request.state.username  # Set by middleware
    return {"user": username}
```

### Cookie Helpers

#### `set_auth_cookie(response, token: str, max_age: int = 86400, secure: bool = True)`

Set authentication cookie on response with secure defaults.

```python
from src.dashboard.auth import set_auth_cookie

set_auth_cookie(
    response,
    token=jwt_token,
    max_age=86400,  # 24 hours in seconds
    secure=True     # HTTPS only (set False for local dev)
)
```

**Cookie attributes**:
- `httpOnly=True` - JavaScript cannot access (XSS protection)
- `secure=True` - HTTPS only (set False for local dev over HTTP)
- `samesite="strict"` - CSRF protection
- `path="/"` - Cookie valid for entire site
- `max_age` - Cookie lifetime in seconds

#### `clear_auth_cookie(response)`

Delete authentication cookie (for logout).

```python
from src.dashboard.auth import clear_auth_cookie

@app.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}
```

## Security Best Practices

### 1. Secret Key Management

**❌ Never hardcode secret keys**:
```python
# BAD - DO NOT DO THIS
secret_key = "my-secret-key"
```

**✅ Use Secrets Manager**:
```python
from src.common.secrets import SecretsClient

secrets_client = SecretsClient(region="us-east-1")
secret = secrets_client.get_secret("manga-pipeline/jwt-secret")
secret_key = secret["jwt_secret_key"]
```

**✅ Use environment variables** (fallback):
```python
import os

secret_key = os.environ.get("JWT_SECRET_KEY")
if not secret_key:
    raise ValueError("JWT_SECRET_KEY not set")
```

### 2. Password Storage

**❌ Never store plain passwords**:
```python
# BAD - DO NOT DO THIS
user_password = "password123"  # Plain text
```

**✅ Always hash passwords**:
```python
from src.dashboard.auth import hash_password

hashed = hash_password("user-password")
# Store 'hashed' in database, NOT plain password
```

### 3. Cookie Security

**Production** (HTTPS):
```python
set_auth_cookie(response, token, secure=True)  # HTTPS only
```

**Local Development** (HTTP):
```python
set_auth_cookie(response, token, secure=False)  # Allow HTTP
```

**Never** set `httpOnly=False` or `samesite="none"` unless absolutely necessary.

### 4. Token Expiration

Choose appropriate token lifetime:
- **Short-lived** (1-2 hours): More secure, requires frequent re-login
- **Long-lived** (24 hours): Better UX, less secure
- **Production recommendation**: 8-12 hours

```python
# 8-hour tokens
token = create_access_token(username, secret_key, expires_hours=8)
set_auth_cookie(response, token, max_age=8*3600)  # Match cookie lifetime
```

### 5. HTTPS in Production

**Always** use HTTPS in production:
```python
# Production
app.add_middleware(
    HTTPSRedirectMiddleware,  # Force HTTPS
)
app.add_middleware(
    AuthMiddleware,
    secret_key=secret_key,
)
```

## Testing

Run the test suite:

```bash
pytest tests/unit/test_dashboard_auth.py -v
```

**Test coverage**:
- ✅ Password hashing and verification
- ✅ JWT token creation and verification
- ✅ Token expiration handling
- ✅ Middleware authentication checks
- ✅ Cookie security settings
- ✅ Excluded path handling
- ✅ Integration flows

## Example: Full Application

```python
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from src.dashboard.auth import (
    AuthMiddleware,
    get_current_user,
    verify_password,
    create_access_token,
    set_auth_cookie,
    clear_auth_cookie,
)
from src.common.secrets import SecretsClient

app = FastAPI()

# Load JWT secret
secrets_client = SecretsClient(region="us-east-1")
secret_data = secrets_client.get_secret("manga-pipeline/jwt-secret")
JWT_SECRET = secret_data["jwt_secret_key"]
ADMIN_HASH = secret_data["admin_password_hash"]

# Configure app
app.state.jwt_secret_key = JWT_SECRET

# Add middleware
app.add_middleware(AuthMiddleware, secret_key=JWT_SECRET)

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

# Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>Manga Pipeline Admin</h1>"

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <form method="post" action="/api/auth/login">
        <input name="username" placeholder="Username">
        <input name="password" type="password" placeholder="Password">
        <button type="submit">Login</button>
    </form>
    """

@app.post("/api/auth/login")
async def login(request: LoginRequest, response: Response):
    # Verify credentials
    if request.username != "admin" or not verify_password(request.password, ADMIN_HASH):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create token
    token = create_access_token(request.username, JWT_SECRET, expires_hours=24)

    # Set cookie
    set_auth_cookie(response, token, max_age=86400, secure=True)

    return {"message": "Login successful"}

@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}

@app.get("/dashboard")
async def dashboard(username: str = Depends(get_current_user)):
    return {"message": f"Welcome to dashboard, {username}"}

@app.get("/api/jobs")
async def get_jobs(username: str = Depends(get_current_user)):
    return {"jobs": [], "user": username}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Troubleshooting

### "Not authenticated" error on protected routes

**Cause**: Token not found in cookie or invalid

**Solution**:
1. Check browser cookies (DevTools → Application → Cookies)
2. Verify cookie name is `access_token`
3. Check token hasn't expired
4. Verify JWT secret matches between login and verification

### "Authentication configuration error"

**Cause**: JWT secret not set in `app.state.jwt_secret_key`

**Solution**:
```python
# Add this before adding middleware
app.state.jwt_secret_key = "your-secret-key"
```

### Middleware redirects even for excluded paths

**Cause**: Path not properly excluded

**Solution**:
```python
# Make sure path starts with /
excluded_paths = {"/login", "/static"}  # ✅ Correct
excluded_paths = {"login", "static"}    # ❌ Wrong
```

### Cookies not working in local development

**Cause**: Secure flag requires HTTPS

**Solution**:
```python
# For local dev over HTTP
set_auth_cookie(response, token, secure=False)
```

## License

See project LICENSE file.
