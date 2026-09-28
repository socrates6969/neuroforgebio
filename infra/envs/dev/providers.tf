# Credentials are NEVER configured in code or tfvars. An owner-run shell supplies them
# (AWS SSO / environment) when the owner decides to plan or apply against a real account.
provider "aws" {
  region = var.region
  default_tags {
    tags = {
      project     = "nf-platform"
      environment = "dev"
      managed_by  = "opentofu"
      data_class  = "synthetic-only" # BLUEPRINT §7: no real human neural data in dev
    }
  }
}
