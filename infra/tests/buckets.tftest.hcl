mock_provider "aws" {}

run "buckets" {
  command = apply # mock_provider: nada é criado; valores computados viram falsos conhecidos

  # S3-01
  assert {
    condition     = aws_s3_bucket.site.bucket == "besave-site"
    error_message = "bucket do site deve ser besave-site"
  }
  assert {
    condition = alltrue([for b in [aws_s3_bucket_public_access_block.site, aws_s3_bucket_public_access_block.logs] :
    b.block_public_acls && b.block_public_policy && b.ignore_public_acls && b.restrict_public_buckets])
    error_message = "Block Public Access deve ter os 4 flags nos dois buckets"
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.site.bucket == aws_s3_bucket.site.id && aws_s3_bucket_public_access_block.logs.bucket == aws_s3_bucket.logs.id
    error_message = "BPA deve apontar para os buckets certos"
  }

  # S3-02
  assert {
    condition = alltrue([for p in ["data/chunks/", "data/busca/"] :
      length([for r in aws_s3_bucket_lifecycle_configuration.site.rule : r
    if r.status == "Enabled" && r.filter[0].prefix == p && r.expiration[0].days == 7]) == 1])
    error_message = "data/chunks/ e data/busca/ devem expirar em 7 dias"
  }
  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.site.rule) == 2
    error_message = "lifecycle do site deve ter só as 2 regras"
  }

  # S3-04
  assert {
    condition     = aws_s3_bucket.logs.bucket == "besave-logs"
    error_message = "bucket de logs deve ser besave-logs"
  }
  assert {
    condition     = aws_s3_bucket_ownership_controls.logs.rule[0].object_ownership == "BucketOwnerPreferred"
    error_message = "logs do CloudFront exigem ACL: ownership BucketOwnerPreferred"
  }
}
