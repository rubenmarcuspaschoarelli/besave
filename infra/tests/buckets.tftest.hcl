mock_provider "aws" {
  source = "./tests/mocks"
}

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

run "sem_expiracao_no_site" {
  command = plan
  module {
    source = "./tests/inspecao"
  }

  # S3-02 (revisão do dono): só a limpeza de órfãos do worker remove chunks
  assert {
    condition     = contains(output.recursos, "aws_s3_bucket.site")
    error_message = "inspeção deve enxergar os recursos da raiz"
  }
  assert {
    condition     = output.expiracao_no_site == []
    error_message = "besave-site não pode ter lifecycle com expiração"
  }
}
