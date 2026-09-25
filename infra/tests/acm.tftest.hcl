mock_provider "aws" {
  source = "./tests/mocks"
}

run "acm" {
  command = apply # mock_provider: nada é criado

  # CF-10
  assert {
    condition     = aws_acm_certificate.site.domain_name == "besave.com.br" && tolist(aws_acm_certificate.site.subject_alternative_names) == tolist(["www.besave.com.br"])
    error_message = "certificado deve cobrir besave.com.br e www.besave.com.br"
  }
  assert {
    condition     = aws_acm_certificate.site.validation_method == "DNS"
    error_message = "validação deve ser DNS"
  }
  assert {
    condition = alltrue([for r in values(aws_route53_record.validacao_acm) :
    r.zone_id == "Z0000000000000EXEMPLO" && r.type == "CNAME" && r.allow_overwrite])
    error_message = "registros de validação devem ir para a zona do domínio"
  }
  assert {
    condition = (aws_route53_record.validacao_acm["besave.com.br"].name == "_a.besave.com.br." &&
      tolist(aws_route53_record.validacao_acm["besave.com.br"].records) == tolist(["_x.acm-validations.aws."]) &&
      aws_route53_record.validacao_acm["www.besave.com.br"].name == "_b.www.besave.com.br." &&
    tolist(aws_route53_record.validacao_acm["www.besave.com.br"].records) == tolist(["_y.acm-validations.aws."]))
    error_message = "cada domínio deve ter o registro de validação que o ACM pediu"
  }
  assert {
    condition     = length(aws_acm_certificate_validation.site.validation_record_fqdns) == 2
    error_message = "validação deve esperar os 2 registros"
  }
}
