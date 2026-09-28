# `tofu test` (CI-only): plans the dev environment against a MOCKED aws provider, so no account,
# no credentials and no API calls are needed. Asserts the security baseline.
mock_provider "aws" {}

run "plan_dev_with_mock_provider" {
  command = plan

  assert {
    condition     = output.db_publicly_accessible == false
    error_message = "Postgres must not be publicly accessible."
  }

  assert {
    condition     = output.db_storage_encrypted == true
    error_message = "Postgres storage must be encrypted."
  }

  assert {
    condition     = output.buckets_block_public_access == true
    error_message = "Every bucket must block public access."
  }

  assert {
    condition     = output.service_assign_public_ip == false
    error_message = "Services must not get public IPs."
  }
}

run "tenant_kek_alias_matches_platform" {
  command = plan

  variables {
    tenant_ids = ["00000000-0000-4000-8000-000000000001"]
  }

  assert {
    condition     = output.tenant_kek_aliases["00000000-0000-4000-8000-000000000001"] == "alias/nf/tenant/00000000-0000-4000-8000-000000000001"
    error_message = "Tenant KEK alias must be alias/nf/tenant/<id> (nf_platform storage_from_env)."
  }
}

run "rejects_unpinned_image" {
  command = plan

  variables {
    platform_image = "ghcr.io/example/platform:latest"
  }

  expect_failures = [var.platform_image]
}

run "dev_rejects_phi" {
  command = plan

  variables {
    phi = true
  }

  expect_failures = [var.phi]
}

run "dev_stack_is_not_phi_ready" {
  command = plan

  assert {
    condition     = contains(output.phi_not_listed, "aws_rds_postgres") && !contains(output.phi_not_listed, "aws_s3")
    error_message = "RDS is not BAA-listed in phi-services.json; S3 is."
  }
}
