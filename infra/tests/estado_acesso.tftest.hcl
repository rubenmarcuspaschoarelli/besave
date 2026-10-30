mock_provider "aws" {
  source = "./tests/mocks"
}

variables {
  regiao          = "us-east-1"
  dominio         = "besave.com.br"
  bucket_site     = "besave-site"
  bucket_logs     = "besave-logs"
  ativar_dominios = false
  classe_preco    = "PriceClass_All"
  dominios_curtos = ["besave.io", "besave.me"]
  ativar_curto    = false
}

# BSV-53: só o administrador do dono acessa o bucket do state. Lê o documento de cada policy (o nome do
# bucket é literal, igual ao do backend e ao da raiz estado/), sem depender de mock com ARN igual (lição 11).
run "ninguem_de_servico_acessa_o_estado" {
  command = apply # mock_provider: nada é criado

  assert {
    condition = alltrue([for p in [
      aws_iam_user_policy.worker.policy,
      aws_iam_user_policy.backup.policy,
      aws_iam_role_policy.site_deploy.policy,
      aws_iam_role_policy.vigia.policy,
      aws_iam_role_policy.vigia_agenda.policy,
    ] : !strcontains(p, "besave-tfstate")])
    error_message = "nenhuma policy de serviço pode citar o bucket do state (besave-tfstate)"
  }

  # Statement Allow com ação "*" ou s3:*: Resource não pode ser "*" nem ter curinga no nome do bucket
  # (arn:aws:s3:::*, arn:aws:s3:::besave-*, arn:aws:s3:::*/x). Curinga depois da "/" do objeto é permitido.
  assert {
    condition = alltrue(flatten([for p in [
      aws_iam_user_policy.worker.policy,
      aws_iam_user_policy.backup.policy,
      aws_iam_role_policy.site_deploy.policy,
      aws_iam_role_policy.vigia.policy,
      aws_iam_role_policy.vigia_agenda.policy,
      ] : [for s in jsondecode(p).Statement :
      s.Effect != "Allow"
      || !anytrue([for a in flatten([s.Action]) : a == "*" || startswith(a, "s3")])
      || alltrue([for r in flatten([s.Resource]) :
        r != "*" && !strcontains(split("/", replace(r, "arn:aws:s3:::", ""))[0], "*")
      ])
    ]]))
    error_message = "Allow com ação * ou s3:* não pode ter Resource \"*\" nem curinga no nome do bucket"
  }
}
