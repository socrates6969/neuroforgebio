# dev environment (BUILD-GUIDE 0.7). CODE ONLY: never applied by agents. Applying needs the owner to
# create the AWS account and approve spend (ADR 0004).

module "kms" {
  source              = "../../modules/kms"
  name                = var.name
  tenant_ids          = var.tenant_ids
  tenant_alias_prefix = var.tenant_alias_prefix
}

module "network" {
  source                     = "../../modules/network"
  name                       = var.name
  region                     = var.region
  availability_zones         = var.availability_zones
  enable_interface_endpoints = var.enable_interface_endpoints
}

module "raw_bucket" {
  source      = "../../modules/bucket"
  bucket_name = "${var.bucket_prefix}-raw"
  kms_key_arn = module.kms.key_arn
}

module "audit_bucket" {
  source      = "../../modules/bucket"
  bucket_name = "${var.bucket_prefix}-audit"
  kms_key_arn = module.kms.key_arn
  object_lock = true
}

# The platform's S3ObjectStore uses five logical buckets named "<bucket_prefix>-<logical>"
# (nf_platform.storage.objects.BUCKETS): raw and audit above, the other three here.
module "data_buckets" {
  source      = "../../modules/bucket"
  for_each    = toset(["zarr", "artifacts", "models"])
  bucket_name = "${var.bucket_prefix}-${each.key}"
  kms_key_arn = module.kms.key_arn
}

locals {
  bucket_arns = concat(
    [module.raw_bucket.bucket_arn, module.audit_bucket.bucket_arn],
    [for b in module.data_buckets : b.bucket_arn],
  )
}

module "platform_api" {
  source     = "../../modules/container-service"
  name       = "${var.name}-platform-api"
  region     = var.region
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
  image      = var.platform_image

  # Read by nf_platform (config.Settings.from_env, storage.runtime.storage_from_env). A prod env
  # copies this block with NF_ENVIRONMENT = "prod": the platform then refuses to start unless
  # storage is S3 + AWS KMS (NR-H1). Only "prod" arms that check; "staging" behaves like dev.
  environment = {
    NF_ENVIRONMENT          = "dev"
    NF_S3_BUCKET_PREFIX     = var.bucket_prefix
    NF_KMS_BACKEND          = "aws"
    NF_KMS_KEY_ALIAS_PREFIX = var.tenant_alias_prefix
    AWS_REGION              = var.region
  }
}

# Least privilege for the platform task: its five buckets, the root key (bucket SSE-KMS) and the
# tenant KEKs by alias. No kms:ScheduleKeyDeletion: shredding a tenant key is an owner action.
resource "aws_iam_role_policy" "platform_storage" {
  name = "platform-storage"
  role = module.platform_api.task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "Buckets"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketVersioning"]
        Resource = local.bucket_arns
      },
      {
        Sid    = "Objects"
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:PutObjectRetention",
          "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts",
        ]
        Resource = [for arn in local.bucket_arns : "${arn}/*"]
      },
      {
        Sid      = "BucketEncryption"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = [module.kms.key_arn]
      },
      {
        Sid      = "TenantKeks"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt", "kms:DescribeKey"]
        Resource = "*"
        Condition = {
          "ForAnyValue:StringLike" = { "kms:ResourceAliases" = module.kms.tenant_alias_pattern }
        }
      },
    ]
  })
}

module "postgres" {
  source                     = "../../modules/postgres"
  name                       = "${var.name}-pg"
  vpc_id                     = module.network.vpc_id
  subnet_ids                 = module.network.private_subnet_ids
  allowed_security_group_ids = [module.platform_api.security_group_id]
  kms_key_arn                = module.kms.key_arn
  deletion_protection        = false # dev holds synthetic data only
}

# 5.7 PHI placement guard. modules_used must list every module above (a Python test in
# services/platform/tests/governance/test_gov_phi_placement.py checks this against the module
# blocks). dev holds synthetic data only, so phi stays false; the guard still reports which
# services would block a phi = true environment (output phi_not_listed).
module "phi_guard" {
  source       = "../../modules/phi-guard"
  phi          = var.phi
  modules_used = ["kms", "network", "bucket", "container-service", "postgres"]
}
