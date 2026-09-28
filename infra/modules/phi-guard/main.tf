# PHI placement guard (BUILD-GUIDE 5.7, BLUEPRINT §8.5). CODE ONLY: never applied by agents.
# A phi = true environment may only use services listed as BAA-covered in
# infra/policy/phi-services.json (the same file the platform's placement check reads:
# services/platform/nf_platform/placement.py). The plan fails when phi = true and any service the
# environment uses is not listed, or when a module has no service mapping (fail closed).
# DRAFT readiness pack: no provider BAA is signed (owner action); nothing here claims compliance.

variable "phi" {
  type        = bool
  default     = false
  description = "true when this environment holds PHI tenants"
}

variable "modules_used" {
  type        = list(string)
  description = "Names of the infra/modules this environment instantiates (mapped to services via iac_modules)"
}

variable "extra_services" {
  type        = list(string)
  default     = []
  description = "Service ids used outside the modules (catalog ids in phi-services.json)"
}

variable "policy_file" {
  type        = string
  default     = ""
  description = "Override for tests; default infra/policy/phi-services.json"
}

locals {
  policy     = jsondecode(file(var.policy_file != "" ? var.policy_file : "${path.module}/../../policy/phi-services.json"))
  covered    = [for s in local.policy.baa_covered : s.id]
  unmapped   = [for m in var.modules_used : m if !contains(keys(local.policy.iac_modules), m)]
  services   = sort(distinct(concat(flatten([for m in var.modules_used : local.policy.iac_modules[m] if contains(keys(local.policy.iac_modules), m)]), var.extra_services)))
  unknown    = [for s in local.services : s if !contains(keys(local.policy.catalog), s)]
  not_listed = [for s in local.services : s if !contains(local.covered, s)]
}

resource "terraform_data" "guard" {
  input = {
    phi      = var.phi
    services = local.services
  }

  lifecycle {
    precondition {
      condition     = length(local.unmapped) == 0 && length(local.unknown) == 0
      error_message = "Every module and service needs an entry in infra/policy/phi-services.json (iac_modules / catalog)."
    }
    precondition {
      condition     = !var.phi || length(local.not_listed) == 0
      error_message = "phi = true: this environment uses services that are not BAA-listed in infra/policy/phi-services.json."
    }
  }
}

output "services" {
  value = local.services
}

output "not_listed" {
  description = "Services that would block phi = true (empty = every service is BAA-listed)"
  value       = local.not_listed
}
