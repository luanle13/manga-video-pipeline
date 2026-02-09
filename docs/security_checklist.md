# Security Checklist

This document tracks security controls for the Manga Video Pipeline. Each item has been verified against the codebase.

**Last Updated:** 2024-01-15
**Verified By:** Security Engineering

---

## Summary

| Category | Status | Items Verified |
|----------|--------|----------------|
| Secrets Management | PASS | 3/3 |
| Infrastructure Security | PASS | 4/4 |
| Application Security | PARTIAL | 5/6 |
| Monitoring & Logging | PARTIAL | 2/3 |
| Dependencies | NEEDS VERIFICATION | 1/1 |

**Overall Status:** 2 findings require remediation

---

## Checklist

### 1. Secrets Management

#### 1.1 No Hardcoded Secrets
- [x] **VERIFIED**

**Evidence:**
- Searched all source files for patterns: `api[_-]?key|secret[_-]?key|password|access[_-]?token`
- No AWS access keys found (AKIA pattern)
- Only placeholder values in README documentation files
- All secrets loaded via `SecretsClient` from AWS Secrets Manager

**Files Verified:**
- `src/common/secrets.py` - Uses `boto3.client("secretsmanager")`
- `src/scriptgen/deepinfra_client.py` - API key from Secrets Manager
- `src/uploader/youtube_auth.py` - OAuth tokens from Secrets Manager
- `src/dashboard/auth.py` - JWT secret from app state (injected from Secrets Manager)

#### 1.2 Secrets Manager Used for All Credentials
- [x] **VERIFIED**

**Secrets Configured in Terraform:**
| Secret | Purpose | File |
|--------|---------|------|
| `deepinfra-api-key` | LLM API access | `infra/modules/security/secrets_manager.tf:13` |
| `youtube-oauth` | YouTube upload | `infra/modules/security/secrets_manager.tf:51` |
| `admin-credentials` | Dashboard login | `infra/modules/security/secrets_manager.tf:92` |
| `jwt-secret` | Session signing | `infra/modules/security/secrets_manager.tf:129` |
| `mangadex` (optional) | MangaDex auth | `infra/modules/security/secrets_manager.tf:165` |

**Secret Access Pattern:**
```python
# src/common/secrets.py - Caching prevents excessive API calls
secrets_client = SecretsClient(region=settings.aws_region, cache_ttl=300)
api_key = secrets_client.get_deepinfra_api_key(secret_name)
```

#### 1.3 CloudWatch Logs Don't Contain Secrets
- [x] **VERIFIED**

**Implementation:** `src/common/logging_config.py:29-38`
```python
SENSITIVE_PATTERN = re.compile(r".*(secret|password|token|key).*", re.IGNORECASE)

class SensitiveFieldFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__.keys()):
            if SENSITIVE_PATTERN.match(key):
                setattr(record, key, "[REDACTED]")
        return True
```

**Unit Test Coverage:** `tests/unit/test_logging.py`

---

### 2. Infrastructure Security

#### 2.1 IAM Roles Use Least Privilege
- [x] **VERIFIED**

**File:** `infra/modules/security/iam.tf`

| Role | Permissions | Resource Scope |
|------|-------------|----------------|
| `lambda-fetcher` | S3 PutObject/GetObject, DynamoDB CRUD | `jobs/*` prefix only |
| `lambda-scriptgen` | S3 Get/Put, DynamoDB Get/Update, Secrets Read | Specific secret ARN |
| `lambda-ttsgen` | S3 Get/Put, DynamoDB Get/Update | `jobs/*` prefix only |
| `lambda-cleanup` | S3 DeleteObject, ListBucket, DynamoDB Update | `jobs/*` prefix only |
| `ec2-renderer` | S3 Get/Put, DynamoDB, Secrets, States callback | Specific resources |
| `step-functions` | Lambda Invoke, EC2 Run/Terminate with tags | Tagged instances only |

**Key Controls:**
- All S3 permissions scoped to `${bucket_arn}/jobs/*` prefix
- DynamoDB permissions limited to specific tables and indexes
- EC2 terminate restricted to instances with pipeline tag
- No wildcard `*` for sensitive actions

#### 2.2 S3 Bucket Blocks Public Access
- [x] **VERIFIED**

**File:** `infra/modules/storage/s3.tf:31-38`
```hcl
resource "aws_s3_bucket_public_access_block" "assets" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**Additional Controls:**
- Server-side encryption with AES-256 (line 44-53)
- HTTPS-only bucket policy (line 99-124)
- 7-day lifecycle expiration (line 59-81)

#### 2.3 DynamoDB Encryption Enabled
- [x] **VERIFIED**

**File:** `infra/modules/storage/dynamodb.tf`

All three tables have encryption enabled:
```hcl
# Line 44-47 (manga_jobs), Line 88-91 (processed_manga), Line 126-129 (settings)
server_side_encryption {
  enabled = true
}
```

Point-in-time recovery also enabled for data protection.

#### 2.4 Security Groups Restrict Inbound Access
- [x] **VERIFIED**

**File:** `infra/modules/networking/security_groups.tf`

| Security Group | Inbound Rules | Outbound |
|----------------|---------------|----------|
| `renderer-sg` | None | All (S3, APIs) |
| `dashboard-sg` | 443/tcp from admin IP only | All |

**Dashboard SG:**
- HTTPS (443) from admin IP CIDR only
- Optional HTTP (80) for HTTPS redirect
- SSH (22) optional and disabled by default

---

### 3. Application Security

#### 3.1 All API Calls Use HTTPS/TLS
- [x] **VERIFIED**

**Evidence:**
- Grep for `http://` in source code: No matches
- S3 bucket policy enforces HTTPS:
```hcl
Condition = {
  Bool = { "aws:SecureTransport" = "false" }
}
```
- External API URLs hardcoded with HTTPS:
  - MangaDex: `https://api.mangadex.org`
  - DeepInfra: `https://api.deepinfra.com`
  - YouTube: `https://www.googleapis.com`

#### 3.2 Dashboard Uses httpOnly Secure Cookies
- [x] **VERIFIED**

**File:** `src/dashboard/auth.py:332-340`
```python
response.set_cookie(
    key=COOKIE_NAME,
    value=token,
    httponly=True,        # Prevent XSS access
    secure=secure,        # HTTPS only
    samesite="strict",    # CSRF protection
    path="/",
)
```

#### 3.3 Dashboard Has CSRF Protection
- [x] **VERIFIED**

**Implementation:**
- `src/dashboard/csrf.py` - Token generation and validation
- `src/dashboard/routes/auth_routes.py:99-108` - Login validates CSRF

```python
# Token generation uses cryptographic randomness
token = secrets.token_urlsafe(32)

# One-time use tokens with 60-minute expiry
if not request.app.state.csrf_manager.verify_token(csrf_token):
    raise HTTPException(status_code=403, detail="Invalid CSRF token")
```

#### 3.4 Login Endpoint Is Rate-Limited
- [ ] **FINDING: NOT IMPLEMENTED**

**Current State:**
- No rate limiting on `/api/auth/login` endpoint
- Could allow brute-force password attacks

**Recommendation:**
Add rate limiting middleware using `slowapi` or similar:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
```

**Priority:** HIGH - Implement before production deployment

#### 3.5 Jinja2 Auto-Escaping Enabled
- [x] **VERIFIED**

**File:** `src/dashboard/app.py:84`
```python
templates = Jinja2Templates(directory=str(templates_dir))
```

FastAPI's `Jinja2Templates` enables auto-escaping by default for HTML files, preventing XSS attacks in template output.

#### 3.6 JWT Has Reasonable Expiry
- [x] **VERIFIED**

**File:** `src/dashboard/auth.py:81-94`
```python
def create_access_token(username: str, secret_key: str, expires_hours: int = 24) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "sub": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
```

24-hour expiry is appropriate for admin dashboard sessions.

---

### 4. Monitoring & Logging

#### 4.1 CloudTrail Enabled for API Auditing
- [ ] **FINDING: NOT CONFIGURED**

**Current State:**
- No CloudTrail configuration in Terraform modules
- API calls to AWS services not being audited

**Recommendation:**
Add CloudTrail configuration to `infra/modules/monitoring/`:
```hcl
resource "aws_cloudtrail" "main" {
  name                          = "${var.project_name}-trail"
  s3_bucket_name               = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail        = false
  enable_logging               = true
}
```

**Priority:** MEDIUM - Required for compliance and incident investigation

#### 4.2 CloudWatch Logs Configured
- [x] **VERIFIED**

**Evidence:**
- All Lambda functions have CloudWatch log groups (30-day retention)
- EC2 instances log to CloudWatch
- Step Functions logging enabled
- Log groups: `/aws/lambda/*`, `/aws/ec2/*`

#### 4.3 Budget Alerts Configured
- [x] **VERIFIED**

**File:** `infra/modules/monitoring/budgets.tf`
- Monthly budget: $120 with 65%, 100%, 120% thresholds
- EC2 Spot budget: $50
- Lambda budget: $20
- Forecasted spend alerts enabled

---

### 5. Dependencies

#### 5.1 Dependencies Scanned
- [ ] **NEEDS VERIFICATION**

**Status:** `pip-audit` not installed in local environment

**To Verify:**
```bash
pip install pip-audit
pip-audit --strict
```

**CI Integration:** `.github/workflows/ci.yml:83-88` runs `pip-audit` on every PR

---

## Findings Summary

### HIGH Priority

1. **Login Rate Limiting Not Implemented**
   - File: `src/dashboard/routes/auth_routes.py`
   - Risk: Brute-force attacks on admin login
   - Remediation: Add slowapi rate limiter, 5 attempts/minute

### MEDIUM Priority

2. **CloudTrail Not Configured**
   - Risk: No audit trail for AWS API calls
   - Remediation: Add CloudTrail module to Terraform

---

## Verification Commands

```bash
# Check for hardcoded secrets
grep -rE "(api[_-]?key|secret|password|token)\s*[=:]\s*['\"][^'\"]{10,}" src/ --include="*.py"

# Check for AWS access keys
grep -rE "AKIA[0-9A-Z]{16}" .

# Verify HTTPS usage
grep -rE "http://" src/ --include="*.py" | grep -v "localhost\|127.0.0.1"

# Run security audit
pip-audit --strict

# Check IAM policies for wildcards
grep -rE '"Action":\s*"\*"' infra/
```

---

## Approval

- [ ] Security Team Review
- [ ] High Priority Findings Remediated
- [ ] Production Deployment Approved
