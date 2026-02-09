# =============================================================================
# Secrets Manager Secrets for Manga Video Pipeline
# =============================================================================
# Creates placeholder secrets that must be manually populated with actual values
# IMPORTANT: Never commit actual secret values to version control
# =============================================================================

# =============================================================================
# DeepInfra API Key Secret
# =============================================================================
# Used by script_generator Lambda for LLM API calls

resource "aws_secretsmanager_secret" "deepinfra_api_key" {
  name        = var.deepinfra_api_key_secret_name
  description = "DeepInfra API key for LLM script generation"

  # Recovery window for accidental deletion (minimum 7 days, 0 = immediate)
  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name      = "deepinfra-api-key"
      Component = "secrets"
      Usage     = "script-generator-lambda"
    }
  )
}

resource "aws_secretsmanager_secret_version" "deepinfra_api_key" {
  secret_id = aws_secretsmanager_secret.deepinfra_api_key.id

  # Placeholder value - must be replaced manually via AWS Console or CLI
  # aws secretsmanager put-secret-value --secret-id manga-pipeline/deepinfra-api-key --secret-string "your-api-key"
  secret_string = jsonencode({
    api_key = "REPLACE_WITH_ACTUAL_DEEPINFRA_API_KEY"
  })

  lifecycle {
    # Ignore changes to secret_string after initial creation
    # This prevents Terraform from overwriting manually updated values
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# YouTube OAuth Credentials Secret
# =============================================================================
# Used by EC2 renderer for YouTube uploads

resource "aws_secretsmanager_secret" "youtube_oauth" {
  name        = var.youtube_credentials_secret_name
  description = "YouTube OAuth2 credentials for video uploads"

  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name      = "youtube-oauth"
      Component = "secrets"
      Usage     = "ec2-renderer-uploader"
    }
  )
}

resource "aws_secretsmanager_secret_version" "youtube_oauth" {
  secret_id = aws_secretsmanager_secret.youtube_oauth.id

  # Placeholder OAuth token structure
  # Must be populated with actual OAuth tokens from YouTube API setup
  # See: https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps
  secret_string = jsonencode({
    client_id     = "REPLACE_WITH_YOUTUBE_CLIENT_ID"
    client_secret = "REPLACE_WITH_YOUTUBE_CLIENT_SECRET"
    access_token  = "REPLACE_WITH_ACCESS_TOKEN"
    refresh_token = "REPLACE_WITH_REFRESH_TOKEN"
    token_uri     = "https://oauth2.googleapis.com/token"
    expiry        = "2024-01-01T00:00:00Z"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# Admin Dashboard Credentials Secret
# =============================================================================
# Used by dashboard EC2 instance for admin authentication

resource "aws_secretsmanager_secret" "admin_credentials" {
  name        = var.admin_credentials_secret_name
  description = "Admin dashboard login credentials"

  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name      = "admin-credentials"
      Component = "secrets"
      Usage     = "dashboard-auth"
    }
  )
}

resource "aws_secretsmanager_secret_version" "admin_credentials" {
  secret_id = aws_secretsmanager_secret.admin_credentials.id

  # Placeholder admin credentials
  # password_hash should be bcrypt hash of the password
  # Generate with: python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
  secret_string = jsonencode({
    username      = "admin"
    password_hash = "REPLACE_WITH_BCRYPT_HASH"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# JWT Signing Key Secret
# =============================================================================
# Used by dashboard for signing/verifying JWT tokens

resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "${var.project_name}/jwt-secret"
  description = "JWT signing key for dashboard session management"

  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name      = "jwt-secret"
      Component = "secrets"
      Usage     = "dashboard-jwt"
    }
  )
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id

  # Placeholder JWT secret
  # Generate a secure random secret: openssl rand -base64 32
  secret_string = jsonencode({
    secret_key = "REPLACE_WITH_RANDOM_JWT_SECRET_KEY"
    algorithm  = "HS256"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# MangaDex Credentials Secret (Optional)
# =============================================================================
# Only needed if MangaDex requires authentication in the future

resource "aws_secretsmanager_secret" "mangadex" {
  count = var.mangadex_secret_name != "" ? 1 : 0

  name        = var.mangadex_secret_name
  description = "MangaDex API credentials (optional, for authenticated access)"

  recovery_window_in_days = 7

  tags = merge(
    local.common_tags,
    {
      Name      = "mangadex-credentials"
      Component = "secrets"
      Usage     = "manga-fetcher-lambda"
    }
  )
}

resource "aws_secretsmanager_secret_version" "mangadex" {
  count = var.mangadex_secret_name != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.mangadex[0].id

  secret_string = jsonencode({
    username = "OPTIONAL_MANGADEX_USERNAME"
    password = "OPTIONAL_MANGADEX_PASSWORD"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
