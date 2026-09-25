# Valores falsos compartilhados pelos testes (terraform test, sem conta AWS).
mock_data "aws_route53_zone" {
  defaults = { zone_id = "Z0000000000000EXEMPLO" }
}
mock_resource "aws_acm_certificate" {
  defaults = {
    domain_validation_options = [
      { domain_name = "besave.com.br", resource_record_name = "_a.besave.com.br.", resource_record_type = "CNAME", resource_record_value = "_x.acm-validations.aws." },
      { domain_name = "www.besave.com.br", resource_record_name = "_b.www.besave.com.br.", resource_record_type = "CNAME", resource_record_value = "_y.acm-validations.aws." },
    ]
  }
}
