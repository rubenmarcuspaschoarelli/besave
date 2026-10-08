mock_provider "aws" {
  source = "./tests/mocks"
}

# Lista literal da spec (BSV-17 §2), independente de deploy-site/prefixos.json.
variables {
  prefixos_spec = [
    "_app/*", "index.html", "404.html", "favicon.*", "desejos/*", "assets/besave.css", "assets/fontes/*",
    "tech/*", "players/*", "meu-lar/*", "elas/*", "eles/*", "cultura/*", "familia/*", "pets/*",
    "esporte-vida/*", "outros/*",
  ]
}

run "site_deploy" {
  command = apply # mock_provider: nada é criado

  # OIDC-01
  assert {
    condition = (aws_iam_openid_connect_provider.github.url == "https://token.actions.githubusercontent.com" &&
    aws_iam_openid_connect_provider.github.client_id_list == toset(["sts.amazonaws.com"]))
    error_message = "provedor OIDC do GitHub com client_id_list = [sts.amazonaws.com]"
  }

  # OIDC-02
  assert {
    condition     = aws_iam_role.site_deploy.name == "besave-site-deploy" && aws_iam_role.site_deploy.max_session_duration == 3600
    error_message = "papel besave-site-deploy com sessão de no máximo 1 h"
  }
  assert {
    condition = jsondecode(aws_iam_role.site_deploy.assume_role_policy) == {
      Version = "2012-10-17"
      Statement = [{
        Effect    = "Allow"
        Principal = { Federated = "arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com" }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:rubenmarcuspaschoarelli@51489817/besave@1371919473:ref:refs/heads/main"
          }
        }
      }]
    }
    error_message = "confiança só no provedor OIDC, aud sts.amazonaws.com e main deste repositório"
  }

  # OIDC-03
  assert {
    condition     = output.arn_papel_site_deploy == "arn:aws:iam::111111111111:role/besave-site-deploy" && output.id_distribuicao == aws_cloudfront_distribution.site.id
    error_message = "outputs arn_papel_site_deploy e id_distribuicao"
  }

  # POL-01..03: exatamente estas ações, só nestes recursos
  assert {
    condition = jsondecode(aws_iam_role_policy.site_deploy.policy) == {
      Version = "2012-10-17"
      Statement = [
        {
          Sid      = "PublicarSite"
          Effect   = "Allow"
          Action   = ["s3:PutObject", "s3:DeleteObject"]
          Resource = [for p in var.prefixos_spec : "${aws_s3_bucket.site.arn}/${p}"]
        },
        {
          Sid       = "ListarSite"
          Effect    = "Allow"
          Action    = "s3:ListBucket"
          Resource  = aws_s3_bucket.site.arn
          Condition = { StringLike = { "s3:prefix" = var.prefixos_spec } }
        },
        {
          Sid      = "Invalidar"
          Effect   = "Allow"
          Action   = "cloudfront:CreateInvalidation"
          Resource = "arn:aws:cloudfront::111111111111:distribution/EEXEMPLO000000"
        },
      ]
    }
    error_message = "policy do deploy do site difere do mínimo da spec"
  }
  assert {
    condition     = aws_iam_role_policy.site_deploy.role == aws_iam_role.site_deploy.id
    error_message = "policy deve estar no papel besave-site-deploy"
  }

  # POL-04: nenhum prefixo do worker, nem o bucket inteiro (objetos e listagem)
  assert {
    condition = alltrue([
      for p in concat(
        [for r in jsondecode(aws_iam_role_policy.site_deploy.policy).Statement[0].Resource : trimprefix(r, "${aws_s3_bucket.site.arn}/")],
        jsondecode(aws_iam_role_policy.site_deploy.policy).Statement[1].Condition.StringLike["s3:prefix"],
      ) : length(regexall("^(\\*|data/|oferta/|img/|manifest|sitemap|robots\\.txt|_estado/)", p)) == 0
    ])
    error_message = "nada em data/, oferta/, img/, manifest*, sitemap*, robots.txt, _estado/ nem no bucket inteiro"
  }
}
