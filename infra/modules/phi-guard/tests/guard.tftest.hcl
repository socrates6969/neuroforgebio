# `tofu test` (CI-only; tofu is not installed on the dev PC): the guard needs no provider.
# Run: tofu -chdir=infra/modules/phi-guard init -backend=false && tofu -chdir=infra/modules/phi-guard test

run "phi_tenant_on_non_listed_services_fails" {
  command = plan

  variables {
    phi          = true
    modules_used = ["bucket", "postgres", "container-service"]
  }

  expect_failures = [terraform_data.guard]
}

run "phi_tenant_on_listed_services_only_plans" {
  command = plan

  variables {
    phi            = true
    modules_used   = ["bucket"]
    extra_services = ["aws_timestream", "aws_sagemaker_ai"]
  }

  assert {
    condition     = length(output.not_listed) == 0
    error_message = "S3, Timestream and SageMaker AI are the BAA-listed services."
  }
}

run "non_phi_environment_is_not_restricted" {
  command = plan

  variables {
    phi          = false
    modules_used = ["bucket", "kms", "network", "postgres", "container-service"]
  }

  assert {
    condition     = contains(output.not_listed, "aws_rds_postgres")
    error_message = "The guard still reports what would block phi = true."
  }
}

run "unmapped_module_fails_closed" {
  command = plan

  variables {
    phi          = false
    modules_used = ["some-new-module"]
  }

  expect_failures = [terraform_data.guard]
}
