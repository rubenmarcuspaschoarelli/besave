# Usuário do worker (BSV-12). Sem console e sem access key aqui: o dono gera no console, fora do git.
resource "aws_iam_user" "worker" {
  name = "besave-worker"
}

resource "aws_iam_user_policy" "worker" {
  name = "besave-worker-publicacao"
  user = aws_iam_user.worker.name
  policy = jsonencode({
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
  })
}
