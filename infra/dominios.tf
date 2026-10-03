# Virada (BSV-16): besave.com.br e www na distribuição nova. allow_overwrite porque os registros atuais
# foram criados no console e apontam para o protótipo.
locals {
  registros_site = var.ativar_dominios ? {
    for p in setproduct(local.dominios, ["A", "AAAA"]) : "${p[0]} ${p[1]}" => { nome = p[0], tipo = p[1] }
  } : {}
}

resource "aws_route53_record" "site" {
  for_each = local.registros_site

  zone_id         = data.aws_route53_zone.site.zone_id
  name            = each.value.nome
  type            = each.value.tipo
  allow_overwrite = true

  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}
