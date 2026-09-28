output "vpc_id" {
  value = module.network.vpc_id
}

output "db_endpoint" {
  value = module.postgres.endpoint
}

output "db_master_secret_arn" {
  value = module.postgres.master_user_secret_arn
}

output "db_publicly_accessible" {
  value = module.postgres.publicly_accessible
}

output "db_storage_encrypted" {
  value = module.postgres.storage_encrypted
}

output "buckets_block_public_access" {
  value = alltrue(concat(
    [module.raw_bucket.blocks_public_access, module.audit_bucket.blocks_public_access],
    [for b in module.data_buckets : b.blocks_public_access],
  ))
}

output "tenant_kek_aliases" {
  description = "tenant id -> KMS alias of its KEK (what the platform's AwsKms uses)"
  value       = module.kms.tenant_alias_names
}

output "service_assign_public_ip" {
  value = module.platform_api.assign_public_ip
}

output "phi_not_listed" {
  description = "Services of this environment that are not BAA-listed (they block phi = true)"
  value       = module.phi_guard.not_listed
}
