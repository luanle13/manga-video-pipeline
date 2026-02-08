terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "manga-video-pipeline"
      Owner       = "DevOps"
    }
  }
}

# Additional provider for ACM certificates in us-east-1 (required for CloudFront)
provider "aws" {
  alias  = "us-east-1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "manga-video-pipeline"
      Owner       = "DevOps"
    }
  }
}

# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# Data source for AWS region
data "aws_region" "current" {}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}
