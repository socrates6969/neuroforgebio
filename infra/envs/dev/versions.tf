terraform {
  # OpenTofu >= 1.8 for provider mocking in `tofu test` (tests/plan.tftest.hcl).
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # Remote state is an owner decision (needs an account). Until then state is local and never
  # committed (.gitignore: *.tfstate). When enabled: encrypted S3 bucket + DynamoDB lock, e.g.
  # backend "s3" {
  #   bucket         = "<owner-created state bucket>"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "<lock table>"
  # }
}
