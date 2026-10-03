mock_provider "aws" {
  source = "./tests/mocks"
}

# BSV-16: virada de besave.com.br para a distribuição nova.
run "dominios_desligados" {
  command = apply # mock_provider: nada é criado

  # VIR-02
  assert {
    condition     = length(aws_route53_record.site) == 0
    error_message = "sem ativar_dominios: nenhum A/AAAA do domínio"
  }

  # VIR-04
  assert {
    condition     = aws_lambda_function.vigia.environment[0].variables["URL_MANIFEST"] == "https://${aws_cloudfront_distribution.site.domain_name}/manifest.json"
    error_message = "sem ativar_dominios: vigia lê o manifest pelo *.cloudfront.net"
  }
}

run "dominios_ativos" {
  command = apply

  variables {
    ativar_dominios = true
  }

  # VIR-01
  assert {
    condition = toset([for r in values(aws_route53_record.site) : "${r.name} ${r.type}"]) == toset([
      "besave.com.br A", "besave.com.br AAAA", "www.besave.com.br A", "www.besave.com.br AAAA",
    ])
    error_message = "A e AAAA de besave.com.br e www"
  }
  assert {
    condition = alltrue([for r in values(aws_route53_record.site) :
      r.zone_id == "Z0000000000000EXEMPLO" && r.allow_overwrite && length(r.alias) == 1 &&
      r.alias[0].name == aws_cloudfront_distribution.site.domain_name &&
      r.alias[0].zone_id == aws_cloudfront_distribution.site.hosted_zone_id &&
    !r.alias[0].evaluate_target_health])
    error_message = "registros alias para a distribuição nova, na zona do domínio, com allow_overwrite"
  }

  # VIR-03
  assert {
    condition     = aws_lambda_function.vigia.environment[0].variables["URL_MANIFEST"] == "https://besave.com.br/manifest.json"
    error_message = "com ativar_dominios: vigia lê o manifest pelo domínio (testa DNS e certificado)"
  }
}

run "dominios_protecao" {
  command = plan
  module {
    source = "./tests/inspecao"
  }

  # VIR-05
  assert {
    condition     = output.prevent_destroy["aws_route53_record.site"]
    error_message = "registros de besave.com.br/www com prevent_destroy = true: apply sem ativar_dominios não pode apagá-los"
  }
}
