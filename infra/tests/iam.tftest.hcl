mock_provider "aws" {
  source = "./tests/mocks"
}

run "iam_e_outputs" {
  command = apply # mock_provider: nada é criado

  # IAM-01
  assert {
    condition     = aws_iam_user.worker.name == "besave-worker"
    error_message = "usuário do worker deve ser besave-worker"
  }

  # IAM-02 + IAM-03: exatamente estas ações, só nestes recursos
  assert {
    condition = jsondecode(aws_iam_user_policy.worker.policy) == {
      Version = "2012-10-17"
      Statement = [
        {
          Sid      = "ObjetosDoSite"
          Effect   = "Allow"
          Action   = ["s3:PutObject", "s3:DeleteObject", "s3:GetObject"]
          Resource = "${aws_s3_bucket.site.arn}/*"
        },
        {
          Sid      = "ListarSite"
          Effect   = "Allow"
          Action   = "s3:ListBucket"
          Resource = aws_s3_bucket.site.arn
        },
        {
          Sid    = "Redirects"
          Effect = "Allow"
          Action = [
            "cloudfront-keyvaluestore:DescribeKeyValueStore",
            "cloudfront-keyvaluestore:PutKey",
            "cloudfront-keyvaluestore:DeleteKey",
            "cloudfront-keyvaluestore:ListKeys",
          ]
          Resource = aws_cloudfront_key_value_store.redirects.arn
        },
        {
          Sid      = "Invalidar"
          Effect   = "Allow"
          Action   = "cloudfront:CreateInvalidation"
          Resource = aws_cloudfront_distribution.site.arn
        },
      ]
    }
    error_message = "policy do worker difere do mínimo da spec"
  }
  assert {
    condition     = aws_iam_user_policy.worker.user == aws_iam_user.worker.name
    error_message = "policy deve estar no usuário do worker"
  }

  # OPS-01
  assert {
    condition = (output.bucket_site == "besave-site" &&
      output.dominio_distribuicao == aws_cloudfront_distribution.site.domain_name &&
      output.arn_kvs == aws_cloudfront_key_value_store.redirects.arn &&
    output.arn_distribuicao == aws_cloudfront_distribution.site.arn)
    error_message = "outputs: bucket, domínio CF, ARN KVS, ARN distribuição"
  }

  # OPS-02: nada aponta para o bucket do protótipo
  assert {
    condition     = !contains([aws_s3_bucket.site.bucket, aws_s3_bucket.logs.bucket], "besave.com.br")
    error_message = "o bucket besave.com.br (protótipo) não pode ser gerenciado aqui"
  }
}
