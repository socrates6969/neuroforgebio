variable "region" {
  type        = string
  default     = "us-east-1"
  description = "One US region at launch (ADR 0004)"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "name" {
  type    = string
  default = "nf-dev"
}

variable "bucket_prefix" {
  type        = string
  default     = "nf-dev-example"
  description = "S3 names are global: the owner picks a unique prefix before any apply"
}

variable "tenant_ids" {
  type        = set(string)
  default     = []
  description = "Tenant UUIDs that get a KMS KEK; add a tenant here and apply BEFORE its first upload (infra/README.md \"Tenant keys\")"
}

variable "tenant_alias_prefix" {
  type        = string
  default     = "alias/"
  description = "Prefix of the tenant KEK aliases; passed to the platform as NF_KMS_KEY_ALIAS_PREFIX"
}

variable "platform_image" {
  type        = string
  description = "Digest-pinned platform image. Placeholder until M2 builds one."
  default     = "ghcr.io/example/platform@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.platform_image))
    error_message = "platform_image must be pinned by digest (…@sha256:<64 hex>)."
  }
}

variable "enable_interface_endpoints" {
  type    = bool
  default = true
}

variable "phi" {
  type        = bool
  default     = false
  description = "PHI tenants in this environment (5.7). dev holds synthetic data only (BLUEPRINT §7)."
  validation {
    condition     = var.phi == false
    error_message = "dev holds synthetic data only: phi must stay false."
  }
}
