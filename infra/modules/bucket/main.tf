# S3 bucket: private, KMS-encrypted, versioned, TLS-only. Optional object lock (WORM) for the
# audit log (BLUEPRINT §6). No real human neural data in dev (BLUEPRINT §7).
terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

variable "bucket_name" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "object_lock" {
  type        = bool
  default     = false
  description = "Enable object lock (GOVERNANCE mode default retention) for WORM audit data"
}

variable "object_lock_days" {
  type    = number
  default = 365
}

variable "force_destroy" {
  type    = bool
  default = false
}

resource "aws_s3_bucket" "this" {
  bucket              = var.bucket_name
  force_destroy       = var.force_destroy
  object_lock_enabled = var.object_lock
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.this]
}

resource "aws_s3_bucket_object_lock_configuration" "this" {
  count  = var.object_lock ? 1 : 0
  bucket = aws_s3_bucket.this.id
  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.object_lock_days
    }
  }
  depends_on = [aws_s3_bucket_versioning.this]
}

output "bucket_name" {
  value = aws_s3_bucket.this.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "blocks_public_access" {
  value = alltrue([
    aws_s3_bucket_public_access_block.this.block_public_acls,
    aws_s3_bucket_public_access_block.this.block_public_policy,
    aws_s3_bucket_public_access_block.this.ignore_public_acls,
    aws_s3_bucket_public_access_block.this.restrict_public_buckets,
  ])
}
