mock_provider "aws" {
  source = "./tests/mocks"
}

# Valores que este arquivo assume; independem do terraform.tfvars local (os `run` sobrescrevem o que testam).
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

# BSV-16: besave.io e besave.me em duas fases (ativar_curto).
run "curto_fase_1" {
  command = apply # mock_provider: nada é criado

  # CUR-01
  assert {
    condition     = toset([for z in values(aws_route53_zone.curto) : z.name]) == toset(["besave.io", "besave.me"])
    error_message = "zonas besave.io e besave.me sempre existem"
  }

  # CUR-02
  assert {
    condition = (toset(keys(output.ns_curtos)) == toset(["besave.io", "besave.me"]) &&
    alltrue([for d, ns in output.ns_curtos : length(ns) == 4 && tolist(ns) == tolist(aws_route53_zone.curto[d].name_servers)]))
    error_message = "output com os 4 NS de cada zona curta"
  }

  # CUR-03
  assert {
    condition = (length(aws_acm_certificate.curto) == 0 && length(aws_route53_record.validacao_curto) == 0 &&
      length(aws_acm_certificate_validation.curto) == 0 && length(aws_cloudfront_function.link_curto) == 0 &&
    length(aws_cloudfront_distribution.curto) == 0 && length(aws_route53_record.curto) == 0)
    error_message = "fase 1: só as zonas, sem certificado, Function, distribuição ou registros"
  }
}

run "curto_fase_2" {
  command = apply

  variables {
    ativar_curto = true
  }

  # CUR-04
  assert {
    condition = (aws_acm_certificate.curto[0].domain_name == "besave.io" &&
      toset(aws_acm_certificate.curto[0].subject_alternative_names) == toset(["www.besave.io", "besave.me", "www.besave.me"]) &&
    aws_acm_certificate.curto[0].validation_method == "DNS")
    error_message = "certificado besave.io + www.besave.io, besave.me, www.besave.me, validação DNS"
  }

  # CUR-05
  assert {
    condition = (toset(keys(aws_route53_record.validacao_curto)) == toset(["besave.io", "www.besave.io", "besave.me", "www.besave.me"]) &&
      aws_route53_record.validacao_curto["besave.io"].zone_id == aws_route53_zone.curto["besave.io"].zone_id &&
      aws_route53_record.validacao_curto["www.besave.io"].zone_id == aws_route53_zone.curto["besave.io"].zone_id &&
      aws_route53_record.validacao_curto["besave.me"].zone_id == aws_route53_zone.curto["besave.me"].zone_id &&
      aws_route53_record.validacao_curto["www.besave.me"].zone_id == aws_route53_zone.curto["besave.me"].zone_id &&
    aws_route53_zone.curto["besave.io"].zone_id != aws_route53_zone.curto["besave.me"].zone_id)
    error_message = "um registro de validação por nome, na zona do domínio dele"
  }
  assert {
    condition = (aws_route53_record.validacao_curto["www.besave.me"].name == "_d.www.besave.me." &&
      aws_route53_record.validacao_curto["www.besave.me"].type == "CNAME" &&
      tolist(aws_route53_record.validacao_curto["www.besave.me"].records) == tolist(["_w.acm-validations.aws."]) &&
    aws_route53_record.validacao_curto["besave.io"].name == "_a.besave.io.")
    error_message = "cada nome recebe o registro que o ACM pediu"
  }
  assert {
    condition     = length(aws_acm_certificate_validation.curto[0].validation_record_fqdns) == 4 && aws_acm_certificate_validation.curto[0].certificate_arn == aws_acm_certificate.curto[0].arn
    error_message = "validação espera os 4 registros"
  }

  # CUR-08
  assert {
    condition = (aws_cloudfront_function.link_curto[0].name == "link-curto" &&
      aws_cloudfront_function.link_curto[0].runtime == "cloudfront-js-2.0" && aws_cloudfront_function.link_curto[0].publish &&
    aws_cloudfront_function.link_curto[0].code == file("${path.module}/functions/link-curto.js"))
    error_message = "link-curto: cloudfront-js-2.0, publicada, código de functions/link-curto.js"
  }

  # CUR-06
  assert {
    condition     = toset(aws_cloudfront_distribution.curto[0].aliases) == toset(["besave.io", "www.besave.io", "besave.me", "www.besave.me"]) && aws_cloudfront_distribution.curto[0].enabled
    error_message = "distribuição curta com os 4 aliases"
  }
  assert {
    condition = (aws_cloudfront_distribution.curto[0].viewer_certificate[0].acm_certificate_arn == aws_acm_certificate_validation.curto[0].certificate_arn &&
      !aws_cloudfront_distribution.curto[0].viewer_certificate[0].cloudfront_default_certificate &&
      aws_cloudfront_distribution.curto[0].viewer_certificate[0].ssl_support_method == "sni-only" &&
    aws_cloudfront_distribution.curto[0].viewer_certificate[0].minimum_protocol_version == "TLSv1.2_2021")
    error_message = "certificado curto validado, sni-only, TLSv1.2_2021"
  }
  assert {
    condition = (length(aws_cloudfront_distribution.curto[0].origin) == 1 &&
      one(aws_cloudfront_distribution.curto[0].origin).domain_name == "besave.com.br" &&
    one(aws_cloudfront_distribution.curto[0].origin).custom_origin_config[0].origin_protocol_policy == "https-only")
    error_message = "origem custom besave.com.br (nunca alcançada)"
  }
  assert {
    condition = (length(aws_cloudfront_distribution.curto[0].ordered_cache_behavior) == 0 &&
      [for f in aws_cloudfront_distribution.curto[0].default_cache_behavior[0].function_association : [f.event_type, f.function_arn]] == [["viewer-request", aws_cloudfront_function.link_curto[0].arn]] &&
    toset(aws_cloudfront_distribution.curto[0].default_cache_behavior[0].allowed_methods) == toset(["GET", "HEAD"]))
    error_message = "behavior único com link-curto em viewer-request"
  }
  assert {
    condition = (aws_cloudfront_distribution.curto[0].logging_config[0].bucket == aws_s3_bucket.logs.bucket_domain_name &&
    aws_cloudfront_distribution.curto[0].logging_config[0].prefix == "curto/")
    error_message = "logs em besave-logs/curto/"
  }

  # CUR-07
  assert {
    condition = toset([for r in values(aws_route53_record.curto) : "${r.zone_id} ${r.name} ${r.type}"]) == toset(flatten([
      for n in ["besave.io", "www.besave.io", "besave.me", "www.besave.me"] : [
        for t in ["A", "AAAA"] : "${aws_route53_zone.curto[trimprefix(n, "www.")].zone_id} ${n} ${t}"
      ]
    ]))
    error_message = "A e AAAA dos 4 nomes, cada um na zona do seu domínio"
  }
  assert {
    condition = alltrue([for r in values(aws_route53_record.curto) :
      length(r.alias) == 1 && r.alias[0].name == aws_cloudfront_distribution.curto[0].domain_name &&
    r.alias[0].zone_id == aws_cloudfront_distribution.curto[0].hosted_zone_id])
    error_message = "registros curtos apontam para a distribuição curta"
  }
  assert {
    condition     = aws_cloudfront_distribution.curto[0].domain_name != aws_cloudfront_distribution.site.domain_name
    error_message = "teste precisa distinguir as duas distribuições"
  }
}

run "curto_protecao" {
  command = plan
  module {
    source = "./tests/inspecao"
  }

  # CUR-04
  assert {
    condition     = output.prevent_destroy["aws_acm_certificate.curto"]
    error_message = "certificado curto com prevent_destroy = true (AD-022)"
  }

  # CUR-09
  assert {
    condition     = output.prevent_destroy["aws_route53_zone.curto"]
    error_message = "zonas curtas com prevent_destroy = true: zona recriada ganha outros NS"
  }

  # CUR-06
  assert {
    condition     = output.certificado_validado["aws_cloudfront_distribution.curto"]
    error_message = "distribuição curta deve usar o ARN de aws_acm_certificate_validation (espera a emissão)"
  }
}
