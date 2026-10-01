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
  defaults = { arn = "arn:aws:cloudfront::111111111111:distribution/EEXEMPLO000000" }
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
