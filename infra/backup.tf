# Cópia diária do banco na AWS (BSV-49). O dump sai da instância 2 da OCI; aqui só há o destino.
resource "aws_s3_bucket" "backup" {
  bucket = var.bucket_backup
}

resource "aws_s3_bucket_public_access_block" "backup" {
  bucket                  = aws_s3_bucket.backup.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versionamento: sobrescrever um dump no mesmo nome não perde o anterior.
resource "aws_s3_bucket_versioning" "backup" {
  bucket = aws_s3_bucket.backup.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Retenção de 30 dias é só aqui: o usuário de backup não apaga nada.
resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    id     = "db-30-dias"
    status = "Enabled"

    filter {
      prefix = "db/"
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }

  depends_on = [aws_s3_bucket_versioning.backup]
}

resource "aws_s3_bucket_policy" "backup" {
  bucket = aws_s3_bucket.backup.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "SoTls"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.backup.arn, "${aws_s3_bucket.backup.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.backup]
}

# Usuário da instância 2. Sem console e sem access key aqui: o dono gera no console, fora do git.
resource "aws_iam_user" "backup" {
  name = "besave-backup"
}

resource "aws_iam_user_policy" "backup" {
  name = "besave-backup-db"
  user = aws_iam_user.backup.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "GravarELer"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload"]
        Resource = "${aws_s3_bucket.backup.arn}/db/*"
      },
      {
        Sid       = "ListarDb"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.backup.arn
        Condition = { StringLike = { "s3:prefix" = "db/*" } }
      },
      {
        Sid      = "NuncaApagar"
        Effect   = "Deny"
        Action   = ["s3:DeleteObject", "s3:DeleteObjectVersion", "s3:DeleteBucket"]
        Resource = [aws_s3_bucket.backup.arn, "${aws_s3_bucket.backup.arn}/*"]
      },
    ]
  })
}
