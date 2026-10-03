# Domínios curtos (BSV-16, CONTRATO §5): besave.io/{id} e besave.me/{id} → 301 para besave.com.br.
# Fase 1 (sempre): só as zonas, para o dono delegar os NS no registrador.
# Fase 2 (ativar_curto, depois que o NS propagar): certificado, Function, distribuição e registros.
locals {
  nomes_curtos = flatten([for d in var.dominios_curtos : [d, "www.${d}"]])
  # nome → zona do domínio dele (www.besave.io → besave.io).
  zona_curta = { for n in local.nomes_curtos : n => trimprefix(n, "www.") }
  registros_curtos = var.ativar_curto ? {
    for p in setproduct(local.nomes_curtos, ["A", "AAAA"]) : "${p[0]} ${p[1]}" => { nome = p[0], tipo = p[1] }
  } : {}
}

resource "aws_route53_zone" "curto" {
  for_each = toset(var.dominios_curtos)

  name    = each.key
  comment = "Domínio curto (BSV-16); registrado fora da AWS, delegado por NS"
}

resource "aws_acm_certificate" "curto" {
  count = var.ativar_curto ? 1 : 0

  domain_name               = var.dominios_curtos[0]
  subject_alternative_names = slice(local.nomes_curtos, 1, length(local.nomes_curtos))
  validation_method         = "DNS"

  # Links curtos ficam em posts permanentes do canal: destroy acidental derruba o TLS (AD-022).
  lifecycle {
    create_before_destroy = true
    prevent_destroy       = true
  }
}

resource "aws_route53_record" "validacao_curto" {
  for_each = var.ativar_curto ? local.zona_curta : {}

  zone_id = aws_route53_zone.curto[each.value].zone_id
  name    = one([for o in aws_acm_certificate.curto[0].domain_validation_options : o.resource_record_name if o.domain_name == each.key])
  type    = one([for o in aws_acm_certificate.curto[0].domain_validation_options : o.resource_record_type if o.domain_name == each.key])
  records = [one([for o in aws_acm_certificate.curto[0].domain_validation_options : o.resource_record_value if o.domain_name == each.key])]
  ttl     = 300
}

resource "aws_acm_certificate_validation" "curto" {
  count = var.ativar_curto ? 1 : 0

  certificate_arn         = aws_acm_certificate.curto[0].arn
  validation_record_fqdns = [for r in aws_route53_record.validacao_curto : r.fqdn]
}

resource "aws_cloudfront_function" "link_curto" {
  count = var.ativar_curto ? 1 : 0

  name    = "link-curto"
  runtime = "cloudfront-js-2.0"
  comment = "/{id} -> 301 https://besave.com.br/oferta/{id}/"
  publish = true
  code    = file("${path.module}/functions/link-curto.js")
}

# A Function sempre responde: a origem existe só porque a distribuição exige uma.
resource "aws_cloudfront_distribution" "curto" {
  count = var.ativar_curto ? 1 : 0

  enabled         = true
  comment         = "besave-curto - links curtos (BSV-16)"
  http_version    = "http2and3"
  is_ipv6_enabled = true
  price_class     = var.classe_preco
  aliases         = local.nomes_curtos

  origin {
    origin_id   = "besave-com-br"
    domain_name = var.dominio

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # allow-all: link colado sem esquema vira http://; a Function já responde com destino https://,
  # sem o salto extra de redirect-to-https.
  default_cache_behavior {
    target_origin_id       = "besave-com-br"
    viewer_protocol_policy = "allow-all"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = local.politica_sem_cache
    compress               = false

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.link_curto[0].arn
    }
  }

  logging_config {
    bucket          = aws_s3_bucket.logs.bucket_domain_name
    prefix          = "curto/"
    include_cookies = false
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = false
    acm_certificate_arn            = aws_acm_certificate_validation.curto[0].certificate_arn
    ssl_support_method             = "sni-only"
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  depends_on = [aws_s3_bucket_acl.logs]
}

resource "aws_route53_record" "curto" {
  for_each = local.registros_curtos

  zone_id = aws_route53_zone.curto[local.zona_curta[each.value.nome]].zone_id
  name    = each.value.nome
  type    = each.value.tipo

  alias {
    name                   = aws_cloudfront_distribution.curto[0].domain_name
    zone_id                = aws_cloudfront_distribution.curto[0].hosted_zone_id
    evaluate_target_health = false
  }
}
