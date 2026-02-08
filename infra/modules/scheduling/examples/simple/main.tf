# Simple example showing just the EventBridge scheduling module

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# Assume Step Functions state machine already exists
data "aws_sfn_state_machine" "existing" {
  name = "manga-pipeline"
}

# Use the scheduling module
module "pipeline_scheduling" {
  source = "../../"

  state_machine_arn = data.aws_sfn_state_machine.existing.arn
  environment       = "prod"
}

# Outputs
output "eventbridge_rule_name" {
  value = module.pipeline_scheduling.eventbridge_rule_name
}

output "schedule_expression" {
  value = module.pipeline_scheduling.schedule_expression
}
