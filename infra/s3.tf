# Origem do site: privado, sem website hosting, lido só pela distribuição (OAC).
resource "aws_s3_bucket" "site" {
  bucket = var.bucket_site
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Só órfãos vivem tanto: o manifest atual sempre aponta para arquivos recentes.
resource "aws_s3_bucket_lifecycle_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  dynamic "rule" {
    for_each = toset(["data/chunks/", "data/busca/"])
    content {
      id     = "expira-${trimsuffix(replace(rule.value, "/", "-"), "-")}"
      status = "Enabled"
      filter {
        prefix = rule.value
      }
      expiration {
        days = 7
      }
    }
  }
}

# Logs padrão do CloudFront exigem ACL no bucket.
resource "aws_s3_bucket" "logs" {
  bucket = var.bucket_logs
}

resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket                  = aws_s3_bucket.logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
