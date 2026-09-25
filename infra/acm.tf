data "aws_route53_zone" "site" {
  name = var.dominio
}

resource "aws_acm_certificate" "site" {
  domain_name               = var.dominio
  subject_alternative_names = ["www.${var.dominio}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Indexado pelos domínios (conhecidos no plano), não por domain_validation_options (computado).
# allow_overwrite: o CNAME de validação é o mesmo do certificado atual da conta, se existir.
resource "aws_route53_record" "validacao_acm" {
  for_each = toset(local.dominios)

  zone_id         = data.aws_route53_zone.site.zone_id
  name            = one([for o in aws_acm_certificate.site.domain_validation_options : o.resource_record_name if o.domain_name == each.key])
  type            = one([for o in aws_acm_certificate.site.domain_validation_options : o.resource_record_type if o.domain_name == each.key])
  records         = [one([for o in aws_acm_certificate.site.domain_validation_options : o.resource_record_value if o.domain_name == each.key])]
  ttl             = 300
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "site" {
  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for r in aws_route53_record.validacao_acm : r.fqdn]
}
