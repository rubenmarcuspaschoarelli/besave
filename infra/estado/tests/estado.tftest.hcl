mock_provider "aws" {}

variables {
  regiao = "us-east-1"
}

run "bucket_do_estado" {
  command = apply # mock_provider: nada é criado

  assert {
    condition     = aws_s3_bucket.estado.bucket == "besave-tfstate"
    error_message = "bucket do state deve ser besave-tfstate"
  }

  assert {
    condition     = aws_s3_bucket_versioning.estado.versioning_configuration[0].status == "Enabled"
    error_message = "versionamento deve estar ligado"
  }

  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.estado.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"
    error_message = "SSE-S3 (AES256) deve estar ligado"
  }

  assert {
    condition = (aws_s3_bucket_public_access_block.estado.block_public_acls
      && aws_s3_bucket_public_access_block.estado.block_public_policy
      && aws_s3_bucket_public_access_block.estado.ignore_public_acls
    && aws_s3_bucket_public_access_block.estado.restrict_public_buckets)
    error_message = "Block Public Access deve ter os 4 flags"
  }

  assert {
    condition     = length(jsondecode(aws_s3_bucket_policy.estado.policy).Statement) == 1
    error_message = "a policy deve ter só a negação sem TLS"
  }

  assert {
    condition     = jsondecode(aws_s3_bucket_policy.estado.policy).Statement[0].Effect == "Deny"
    error_message = "a negação sem TLS deve ser Deny"
  }

  assert {
    condition     = jsondecode(aws_s3_bucket_policy.estado.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "a policy deve negar quando aws:SecureTransport = false"
  }

  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.estado.rule) == 1 && one(aws_s3_bucket_lifecycle_configuration.estado.rule).status == "Enabled"
    error_message = "deve haver uma regra de lifecycle ativa"
  }

  assert {
    condition     = one(one(aws_s3_bucket_lifecycle_configuration.estado.rule).noncurrent_version_expiration).noncurrent_days == 90
    error_message = "versões não correntes expiram em 90 dias"
  }

  assert {
    condition     = one(one(aws_s3_bucket_lifecycle_configuration.estado.rule).noncurrent_version_expiration).newer_noncurrent_versions == 30
    error_message = "devem ficar sempre as 30 versões não correntes mais novas"
  }

  assert {
    condition     = one(one(aws_s3_bucket_lifecycle_configuration.estado.rule).abort_incomplete_multipart_upload).days_after_initiation == 7
    error_message = "multipart incompleto é abortado em 7 dias"
  }
}
