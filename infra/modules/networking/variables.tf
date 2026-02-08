# =============================================================================
# Networking Module - Input Variables
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

# =============================================================================
# Security Configuration
# =============================================================================

variable "admin_ip" {
  description = "Admin IP address or CIDR block for dashboard access"
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_ip, 0))
    error_message = "Admin IP must be a valid CIDR block (e.g., 203.0.113.0/32)."
  }
}

variable "allowed_ip_ranges" {
  description = "Additional IP CIDR blocks allowed to access the dashboard"
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_ip_ranges : can(cidrhost(cidr, 0))])
    error_message = "All allowed IP ranges must be valid CIDR blocks."
  }
}

# =============================================================================
# Feature Flags
# =============================================================================

variable "enable_ssh_access" {
  description = "Enable SSH access to dashboard instance (for debugging only)"
  type        = bool
  default     = false
}

variable "enable_http_redirect" {
  description = "Enable HTTP (port 80) for redirect to HTTPS"
  type        = bool
  default     = true
}

# =============================================================================
# Additional Tags
# =============================================================================

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
