# Deploy do site pelo GitHub Actions (BSV-17): OIDC, sem chave guardada. O bucket é compartilhado com o
# worker; a policy só alcança os prefixos do site (deploy-site/prefixos.json, também lido pelo script).
locals {
  # Formato imutável do "sub" do GitHub (use_immutable_subject: dono@ID/repo@ID): um repositório
  # recriado com o mesmo nome não herda o acesso. IDs públicos, não segredo.
  site_deploy_repo     = "rubenmarcuspaschoarelli@51489817/besave@1371919473"
  site_deploy_prefixos = jsondecode(file("${path.module}/deploy-site/prefixos.json"))
}

# thumbprint_list omitido: opcional no provedor; a AWS valida o GitHub pela CA.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

resource "aws_iam_role" "site_deploy" {
  name                 = "besave-site-deploy"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:${local.site_deploy_repo}:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "site_deploy" {
  name = "besave-site-deploy-minimo"
  role = aws_iam_role.site_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PublicarSite"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = [for p in local.site_deploy_prefixos : "${aws_s3_bucket.site.arn}/${p}"]
      },
      {
        Sid       = "ListarSite"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.site.arn
        Condition = { StringLike = { "s3:prefix" = local.site_deploy_prefixos } }
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
