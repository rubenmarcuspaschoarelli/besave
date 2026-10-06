# Valores falsos compartilhados pelos testes (terraform test, sem conta AWS).
mock_data "aws_route53_zone" {
  defaults = { zone_id = "Z0000000000000EXEMPLO" }
}
mock_resource "aws_acm_certificate" {
  defaults = {
    arn = "arn:aws:acm:us-east-1:111111111111:certificate/00000000-0000-0000-0000-000000000000"
    domain_validation_options = [
      { domain_name = "besave.com.br", resource_record_name = "_a.besave.com.br.", resource_record_type = "CNAME", resource_record_value = "_x.acm-validations.aws." },
      { domain_name = "www.besave.com.br", resource_record_name = "_b.www.besave.com.br.", resource_record_type = "CNAME", resource_record_value = "_y.acm-validations.aws." },
    ]
  }
}
mock_resource "aws_cloudfront_key_value_store" {
  defaults = { arn = "arn:aws:cloudfront::111111111111:key-value-store/00000000-0000-0000-0000-000000000000" }
}
mock_resource "aws_cloudfront_distribution" {
  defaults = {
    arn            = "arn:aws:cloudfront::111111111111:distribution/EEXEMPLO000000"
    domain_name    = "d111111abcdef8.cloudfront.net"
    hosted_zone_id = "Z2FDTNDATAQYW2"
  }
}
mock_resource "aws_acm_certificate_validation" {
  defaults = { certificate_arn = "arn:aws:acm:us-east-1:111111111111:certificate/00000000-0000-0000-0000-000000000000" }
}
# ARNs distintos por Function para os testes distinguirem qual está em cada behavior.
override_resource {
  target = aws_cloudfront_function.rewrite_index
  values = { arn = "arn:aws:cloudfront::111111111111:function/rewrite-index" }
}
override_resource {
  target = aws_cloudfront_function.redirect_afiliado
  values = { arn = "arn:aws:cloudfront::111111111111:function/redirect-afiliado" }
}
mock_data "aws_canonical_user_id" {
  defaults = { id = "0000000000000000000000000000000000000000000000000000000000dono" }
}
# Vigia (BSV-15)
mock_data "aws_caller_identity" {
  defaults = { account_id = "111111111111" }
}
mock_data "aws_region" {
  defaults = { region = "us-east-1" }
}
mock_data "aws_kms_alias" {
  defaults = { target_key_arn = "arn:aws:kms:us-east-1:111111111111:key/00000000-0000-0000-0000-00000000055a" }
}
mock_resource "aws_cloudwatch_log_group" {
  defaults = { arn = "arn:aws:logs:us-east-1:111111111111:log-group:/aws/lambda/besave-vigia" }
}
mock_resource "aws_lambda_function" {
  defaults = { arn = "arn:aws:lambda:us-east-1:111111111111:function:besave-vigia" }
}
override_resource {
  target = aws_iam_role.vigia
  values = { arn = "arn:aws:iam::111111111111:role/besave-vigia", id = "besave-vigia" }
}
override_resource {
  target = aws_iam_role.vigia_agenda
  values = { arn = "arn:aws:iam::111111111111:role/besave-vigia-agenda", id = "besave-vigia-agenda" }
}
# Domínios curtos (BSV-16). zone_id fica aleatório: cada zona recebe um diferente.
mock_resource "aws_route53_zone" {
  defaults = { name_servers = ["ns-1.awsdns-01.org", "ns-2.awsdns-02.co.uk", "ns-3.awsdns-03.com", "ns-4.awsdns-04.net"] }
}
override_resource {
  target = aws_acm_certificate.curto
  values = {
    arn = "arn:aws:acm:us-east-1:111111111111:certificate/00000000-0000-0000-0000-0000000c0870"
    domain_validation_options = [
      { domain_name = "besave.io", resource_record_name = "_a.besave.io.", resource_record_type = "CNAME", resource_record_value = "_x.acm-validations.aws." },
      { domain_name = "www.besave.io", resource_record_name = "_b.www.besave.io.", resource_record_type = "CNAME", resource_record_value = "_y.acm-validations.aws." },
      { domain_name = "besave.me", resource_record_name = "_c.besave.me.", resource_record_type = "CNAME", resource_record_value = "_z.acm-validations.aws." },
      { domain_name = "www.besave.me", resource_record_name = "_d.www.besave.me.", resource_record_type = "CNAME", resource_record_value = "_w.acm-validations.aws." },
    ]
  }
}
override_resource {
  target = aws_acm_certificate_validation.curto
  values = { certificate_arn = "arn:aws:acm:us-east-1:111111111111:certificate/00000000-0000-0000-0000-0000000c0870" }
}
override_resource {
  target = aws_cloudfront_distribution.curto
  values = { arn = "arn:aws:cloudfront::111111111111:distribution/ECURTO00000000", domain_name = "d222222curto00.cloudfront.net", hosted_zone_id = "Z2FDTNDATAQYW2" }
}
override_resource {
  target = aws_cloudfront_function.link_curto
  values = { arn = "arn:aws:cloudfront::111111111111:function/link-curto" }
}
