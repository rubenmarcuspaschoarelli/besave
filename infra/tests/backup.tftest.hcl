mock_provider "aws" {
  source = "./tests/mocks"
}

# Valores que este arquivo assume; independem do terraform.tfvars local.
variables {
  regiao          = "us-east-1"
  dominio         = "besave.com.br"
  bucket_site     = "besave-site"
  bucket_logs     = "besave-logs"
  bucket_backup   = "besave-backup"
  ativar_dominios = false
  classe_preco    = "PriceClass_All"
  dominios_curtos = ["besave.io", "besave.me"]
  ativar_curto    = false
}

run "bucket_de_backup" {
  command = apply # mock_provider: nada é criado

  # BKP-01
  assert {
    condition     = aws_s3_bucket.backup.bucket == "besave-backup"
    error_message = "bucket de backup deve ser besave-backup"
  }
  # BKP-02
  assert {
    condition = (aws_s3_bucket_public_access_block.backup.bucket == aws_s3_bucket.backup.id
      && aws_s3_bucket_public_access_block.backup.block_public_acls
      && aws_s3_bucket_public_access_block.backup.block_public_policy
      && aws_s3_bucket_public_access_block.backup.ignore_public_acls
    && aws_s3_bucket_public_access_block.backup.restrict_public_buckets)
    error_message = "Block Public Access deve ter os 4 flags no bucket de backup"
  }
  # BKP-03
  assert {
    condition     = one([for r in aws_s3_bucket_server_side_encryption_configuration.backup.rule : one(r.apply_server_side_encryption_by_default).sse_algorithm]) == "AES256"
    error_message = "criptografia padrão deve ser AES256"
  }
  # BKP-04
  assert {
    condition     = aws_s3_bucket_versioning.backup.versioning_configuration[0].status == "Enabled"
    error_message = "versionamento deve estar ligado"
  }
  # BKP-05
  assert {
    condition = one([for r in aws_s3_bucket_lifecycle_configuration.backup.rule :
      r.status == "Enabled" && one(r.filter).prefix == "db/" && one(r.expiration).days == 30
    ]) == true
    error_message = "ciclo de vida: db/ expira em 30 dias"
  }
  # BKP-06
  assert {
    condition = jsondecode(aws_s3_bucket_policy.backup.policy).Statement[0] == {
      Sid       = "SoTls"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.backup.arn, "${aws_s3_bucket.backup.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }
    error_message = "bucket deve negar acesso sem TLS"
  }
}

run "usuario_so_grava_e_le" {
  command = apply

  # BKP-07
  assert {
    condition     = aws_iam_user.backup.name == "besave-backup"
    error_message = "usuário deve ser besave-backup"
  }
  # BKP-08: exatamente estas permissões, só neste prefixo
  assert {
    condition = jsondecode(aws_iam_user_policy.backup.policy) == {
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
    }
    error_message = "policy do backup deve ser só gravar/ler em db/, listar db/ e negar apagar"
  }
  # BKP-09: apagar é negado — nenhum Allow tem ação de remoção e o Deny cobre objeto, versão e bucket
  assert {
    condition = alltrue([
      for s in jsondecode(aws_iam_user_policy.backup.policy).Statement :
      s.Effect == "Deny" || !anytrue([for a in flatten([s.Action]) : can(regex("(?i)delete|s3:[*]|Put(Bucket|Lifecycle)", a))])
    ])
    error_message = "nenhum Allow pode conter ação de apagar ou de administração do bucket"
  }
  assert {
    condition = alltrue([for a in ["s3:DeleteObject", "s3:DeleteObjectVersion", "s3:DeleteBucket"] :
    contains(flatten([for s in jsondecode(aws_iam_user_policy.backup.policy).Statement : s.Action if s.Effect == "Deny"]), a)])
    error_message = "Deny deve cobrir DeleteObject, DeleteObjectVersion e DeleteBucket"
  }
}
