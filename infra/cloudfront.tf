# Distribuição nova (AD-016), behaviors de MANIFEST.md §5. A atual (E28G93A17WHHD) não é tocada.

locals {
  # Política gerenciada "CachingDisabled" (ID fixo da AWS).
  politica_sem_cache = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  origem_site        = "s3-besave-site"
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = var.bucket_site
  description                       = "Leitura do bucket ${var.bucket_site} pela distribuição nova"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# id → URL de afiliado; o worker (BSV-12) popula.
resource "aws_cloudfront_key_value_store" "redirects" {
  name    = "besave-redirects"
  comment = "id da oferta -> URL de afiliado (/ir/{id})"
}

resource "aws_cloudfront_function" "rewrite_index" {
  name    = "rewrite-index"
  runtime = "cloudfront-js-2.0"
  comment = "/x/ e /x sem extensão -> /x/index.html"
  publish = true
  code    = file("${path.module}/functions/rewrite-index.js")
}

resource "aws_cloudfront_function" "redirect_afiliado" {
  name                         = "redirect-afiliado"
  runtime                      = "cloudfront-js-2.0"
  comment                      = "/ir/{id} -> 302 para a URL da KVS"
  publish                      = true
  code                         = file("${path.module}/functions/redirect-afiliado.js")
  key_value_store_associations = [aws_cloudfront_key_value_store.redirects.arn]
}

# Chave de cache = path em todas as políticas próprias.
resource "aws_cloudfront_cache_policy" "manifest" {
  name        = "besave-manifest"
  min_ttl     = 0
  default_ttl = 300
  max_ttl     = 300

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

# /data/* (pré-comprimido em br) e /img/*: nomes com hash, imutáveis.
resource "aws_cloudfront_cache_policy" "imutavel" {
  name        = "besave-imutavel"
  min_ttl     = 0
  default_ttl = 31536000
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = false
    enable_accept_encoding_brotli = false
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_cache_policy" "oferta" {
  name        = "besave-oferta"
  min_ttl     = 0
  default_ttl = 600
  max_ttl     = 86400

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

# Máximo de 1 ano para valer o Cache-Control immutable de _app/**.
resource "aws_cloudfront_cache_policy" "padrao" {
  name        = "besave-padrao"
  min_ttl     = 0
  default_ttl = 300
  max_ttl     = 31536000

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

resource "aws_cloudfront_distribution" "site" {
  enabled         = true
  comment         = "besave - site novo (BSV-4)"
  http_version    = "http2and3"
  is_ipv6_enabled = true
  price_class     = var.classe_preco
  # Aliases só na virada: o CNAME ainda pertence à distribuição antiga.
  aliases = var.ativar_dominios ? local.dominios : []

  origin {
    origin_id                = local.origem_site
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  ordered_cache_behavior {
    path_pattern           = "/ir/*"
    target_origin_id       = local.origem_site
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = local.politica_sem_cache
    compress               = false

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.redirect_afiliado.arn
    }
  }

  ordered_cache_behavior {
    path_pattern           = "/manifest.json"
    target_origin_id       = local.origem_site
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.manifest.id
    compress               = true
  }

  # Chunks já vêm com Content-Encoding: br; o CloudFront não recomprime.
  ordered_cache_behavior {
    path_pattern           = "/data/*"
    target_origin_id       = local.origem_site
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.imutavel.id
    compress               = false
  }

  ordered_cache_behavior {
    path_pattern           = "/img/*"
    target_origin_id       = local.origem_site
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.imutavel.id
    compress               = false
  }

  ordered_cache_behavior {
    path_pattern           = "/oferta/*"
    target_origin_id       = local.origem_site
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.oferta.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.rewrite_index.arn
    }
  }

  default_cache_behavior {
    target_origin_id       = local.origem_site
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.padrao.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.rewrite_index.arn
    }
  }

  # AD-020 (proposta): sem fallback SPA. OAC devolve 403 para objeto inexistente; o mundo vê 404.
  dynamic "custom_error_response" {
    for_each = [403, 404]
    content {
      error_code            = custom_error_response.value
      response_code         = 404
      response_page_path    = "/404.html"
      error_caching_min_ttl = 60
    }
  }

  logging_config {
    bucket          = aws_s3_bucket.logs.bucket_domain_name
    prefix          = "cf/"
    include_cookies = false
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = !var.ativar_dominios
    acm_certificate_arn            = var.ativar_dominios ? aws_acm_certificate_validation.site.certificate_arn : null
    ssl_support_method             = var.ativar_dominios ? "sni-only" : null
    minimum_protocol_version       = var.ativar_dominios ? "TLSv1.2_2021" : "TLSv1"
  }

  depends_on = [aws_s3_bucket_ownership_controls.logs]
}
