# =============================================================================
# AWS Budgets for Manga Video Pipeline
# =============================================================================
# Monthly cost budget with email notifications at configurable thresholds
# Default thresholds: 65% ($80), 100% ($120), 120% ($145)
# =============================================================================

resource "aws_budgets_budget" "monthly_budget" {
  count = var.create_budget ? 1 : 0

  name         = "${var.project_name}-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_limit)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Include all cost types
  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_support            = true
    include_tax                = true
    include_upfront            = true
    use_amortized              = false
    use_blended                = false
  }

  # Dynamic notification blocks for each threshold
  dynamic "notification" {
    for_each = var.budget_alert_thresholds
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Also add forecasted notifications for early warning
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alarm_email]
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-monthly-budget"
      Component = "budgets"
    }
  )
}

# =============================================================================
# Budget for EC2 Spot Instances (separate tracking)
# =============================================================================

resource "aws_budgets_budget" "ec2_spot_budget" {
  count = var.create_budget ? 1 : 0

  name         = "${var.project_name}-ec2-spot-budget"
  budget_type  = "COST"
  limit_amount = "50" # $50/month for EC2 Spot
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Filter to EC2 Spot only
  cost_filter {
    name   = "Service"
    values = ["Amazon Elastic Compute Cloud - Compute"]
  }

  cost_filter {
    name   = "PurchaseType"
    values = ["Spot Instances"]
  }

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = false
    include_recurring          = true
    include_refund             = false
    include_subscription       = false
    include_support            = false
    include_tax                = true
    include_upfront            = false
    use_amortized              = false
    use_blended                = false
  }

  # Alert at 80% of EC2 Spot budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }

  # Alert when exceeding EC2 Spot budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-ec2-spot-budget"
      Component = "budgets"
    }
  )
}

# =============================================================================
# Budget for Lambda Functions
# =============================================================================

resource "aws_budgets_budget" "lambda_budget" {
  count = var.create_budget ? 1 : 0

  name         = "${var.project_name}-lambda-budget"
  budget_type  = "COST"
  limit_amount = "20" # $20/month for Lambda
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Filter to Lambda only
  cost_filter {
    name   = "Service"
    values = ["AWS Lambda"]
  }

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = false
    include_recurring          = true
    include_refund             = false
    include_subscription       = false
    include_support            = false
    include_tax                = true
    include_upfront            = false
    use_amortized              = false
    use_blended                = false
  }

  # Alert at 80% of Lambda budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }

  tags = merge(
    local.common_tags,
    {
      Name      = "${var.project_name}-lambda-budget"
      Component = "budgets"
    }
  )
}
