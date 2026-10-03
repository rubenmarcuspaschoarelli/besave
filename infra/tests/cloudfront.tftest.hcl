mock_provider "aws" {
  source = "./tests/mocks"
}

run "distribuicao_padrao" {
  command = apply # mock_provider: nada é criado

  # FN-07
  assert {
    condition = alltrue([for f in [aws_cloudfront_function.rewrite_index, aws_cloudfront_function.redirect_afiliado] :
    f.runtime == "cloudfront-js-2.0" && f.publish])
    error_message = "Functions devem usar cloudfront-js-2.0 e publicar"
  }
  assert {
    condition     = aws_cloudfront_function.rewrite_index.code == file("${path.module}/functions/rewrite-index.js") && aws_cloudfront_function.redirect_afiliado.code == file("${path.module}/functions/redirect-afiliado.js")
    error_message = "código das Functions deve vir de infra/functions/*.js"
  }
  assert {
    condition     = aws_cloudfront_function.redirect_afiliado.name == "redirect-afiliado" && aws_cloudfront_function.rewrite_index.name == "rewrite-index"
    error_message = "nomes das Functions"
  }
  assert {
    condition     = aws_cloudfront_key_value_store.redirects.name == "besave-redirects" && tolist(aws_cloudfront_function.redirect_afiliado.key_value_store_associations) == tolist([aws_cloudfront_key_value_store.redirects.arn])
    error_message = "redirect-afiliado deve estar associada à KVS besave-redirects"
  }

  # CF-01
  assert {
    condition     = aws_cloudfront_origin_access_control.site.origin_access_control_origin_type == "s3" && aws_cloudfront_origin_access_control.site.signing_protocol == "sigv4" && aws_cloudfront_origin_access_control.site.signing_behavior == "always"
    error_message = "OAC deve ser s3/sigv4/always"
  }
  assert {
    condition = (length(aws_cloudfront_distribution.site.origin) == 1 &&
      one(aws_cloudfront_distribution.site.origin).domain_name == aws_s3_bucket.site.bucket_regional_domain_name &&
    one(aws_cloudfront_distribution.site.origin).origin_access_control_id == aws_cloudfront_origin_access_control.site.id)
    error_message = "origem única: besave-site via OAC"
  }
  assert {
    condition     = aws_cloudfront_distribution.site.http_version == "http2and3" && aws_cloudfront_distribution.site.enabled
    error_message = "HTTP/2+3 e distribuição habilitada"
  }
  assert {
    condition = alltrue([for b in concat(aws_cloudfront_distribution.site.ordered_cache_behavior, aws_cloudfront_distribution.site.default_cache_behavior) :
      b.viewer_protocol_policy == "redirect-to-https" &&
      toset(b.allowed_methods) == toset(["GET", "HEAD"]) &&
    toset(b.cached_methods) == toset(["GET", "HEAD"])])
    error_message = "todos os behaviors: HTTP→HTTPS, só GET/HEAD"
  }

  # CF-02
  assert {
    condition     = [for b in aws_cloudfront_distribution.site.ordered_cache_behavior : b.path_pattern] == ["/ir/*", "/manifest.json", "/data/*", "/img/*", "/oferta/*"]
    error_message = "behaviors fora da ordem de MANIFEST §5"
  }

  # CF-03
  assert {
    condition = (aws_cloudfront_distribution.site.ordered_cache_behavior[0].cache_policy_id == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" &&
      !aws_cloudfront_distribution.site.ordered_cache_behavior[0].compress &&
    [for f in aws_cloudfront_distribution.site.ordered_cache_behavior[0].function_association : [f.event_type, f.function_arn]] == [["viewer-request", aws_cloudfront_function.redirect_afiliado.arn]])
    error_message = "/ir/*: CachingDisabled, sem compressão, redirect-afiliado em viewer-request"
  }

  # CF-04
  assert {
    condition = (aws_cloudfront_distribution.site.ordered_cache_behavior[1].cache_policy_id == aws_cloudfront_cache_policy.manifest.id &&
      aws_cloudfront_distribution.site.ordered_cache_behavior[1].compress &&
      length(aws_cloudfront_distribution.site.ordered_cache_behavior[1].function_association) == 0 &&
      [aws_cloudfront_cache_policy.manifest.min_ttl, aws_cloudfront_cache_policy.manifest.default_ttl, aws_cloudfront_cache_policy.manifest.max_ttl] == [0, 300, 300] &&
      aws_cloudfront_cache_policy.manifest.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_gzip &&
    aws_cloudfront_cache_policy.manifest.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_brotli)
    error_message = "/manifest.json: TTL 0/300/300, gzip+br, compressão"
  }

  # CF-05
  assert {
    condition = alltrue([for b in slice(aws_cloudfront_distribution.site.ordered_cache_behavior, 2, 4) :
    b.cache_policy_id == aws_cloudfront_cache_policy.imutavel.id && !b.compress && length(b.function_association) == 0])
    error_message = "/data/* e /img/*: política imutável, sem compressão, sem Function"
  }
  assert {
    condition = ([aws_cloudfront_cache_policy.imutavel.min_ttl, aws_cloudfront_cache_policy.imutavel.default_ttl, aws_cloudfront_cache_policy.imutavel.max_ttl] == [0, 31536000, 31536000] &&
      !aws_cloudfront_cache_policy.imutavel.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_gzip &&
    !aws_cloudfront_cache_policy.imutavel.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_brotli)
    error_message = "política imutável: TTL 1 ano, sem gzip/br"
  }

  # CF-06
  assert {
    condition = (aws_cloudfront_distribution.site.ordered_cache_behavior[4].cache_policy_id == aws_cloudfront_cache_policy.oferta.id &&
      aws_cloudfront_distribution.site.ordered_cache_behavior[4].compress &&
      [for f in aws_cloudfront_distribution.site.ordered_cache_behavior[4].function_association : [f.event_type, f.function_arn]] == [["viewer-request", aws_cloudfront_function.rewrite_index.arn]] &&
      aws_cloudfront_cache_policy.oferta.default_ttl == 600 &&
      aws_cloudfront_cache_policy.oferta.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_gzip &&
    aws_cloudfront_cache_policy.oferta.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_brotli)
    error_message = "/oferta/*: TTL padrão 600, gzip+br, rewrite-index"
  }

  # CF-07
  assert {
    condition = (aws_cloudfront_distribution.site.default_cache_behavior[0].cache_policy_id == aws_cloudfront_cache_policy.padrao.id &&
      aws_cloudfront_distribution.site.default_cache_behavior[0].compress &&
      [for f in aws_cloudfront_distribution.site.default_cache_behavior[0].function_association : [f.event_type, f.function_arn]] == [["viewer-request", aws_cloudfront_function.rewrite_index.arn]] &&
      aws_cloudfront_cache_policy.padrao.default_ttl == 300 &&
      aws_cloudfront_cache_policy.padrao.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_gzip &&
    aws_cloudfront_cache_policy.padrao.parameters_in_cache_key_and_forwarded_to_origin[0].enable_accept_encoding_brotli)
    error_message = "default: TTL padrão 300, gzip+br, rewrite-index"
  }

  # CF-08
  assert {
    condition = alltrue([for p in [aws_cloudfront_cache_policy.manifest, aws_cloudfront_cache_policy.imutavel, aws_cloudfront_cache_policy.oferta, aws_cloudfront_cache_policy.padrao] :
      p.parameters_in_cache_key_and_forwarded_to_origin[0].cookies_config[0].cookie_behavior == "none" &&
      p.parameters_in_cache_key_and_forwarded_to_origin[0].headers_config[0].header_behavior == "none" &&
    p.parameters_in_cache_key_and_forwarded_to_origin[0].query_strings_config[0].query_string_behavior == "none"])
    error_message = "chave de cache = path: sem cookie, header ou query string"
  }

  # CF-09
  assert {
    condition = (toset([for e in aws_cloudfront_distribution.site.custom_error_response : [e.error_code, e.response_code, e.response_page_path, e.error_caching_min_ttl]]) ==
    toset([[403, 404, "/404.html", 60], [404, 404, "/404.html", 60]]))
    error_message = "error responses: 403→404 e 404→404 com /404.html, TTL 60, nenhuma 200"
  }

  # CF-11 (padrão)
  assert {
    condition = (length(aws_cloudfront_distribution.site.aliases) == 0 &&
      aws_cloudfront_distribution.site.viewer_certificate[0].cloudfront_default_certificate &&
    aws_cloudfront_distribution.site.viewer_certificate[0].acm_certificate_arn == null)
    error_message = "sem ativar_dominios: sem aliases e com certificado padrão"
  }

  # S3-03
  assert {
    condition = jsondecode(aws_s3_bucket_policy.site.policy) == {
      Version = "2012-10-17"
      Statement = [{
        Sid       = "CloudFrontOAC"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.site.arn}/*"
        Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.site.arn } }
      }]
    }
    error_message = "política do bucket: só GetObject para a distribuição nova via OAC"
  }
  assert {
    condition     = aws_s3_bucket_policy.site.bucket == aws_s3_bucket.site.id
    error_message = "política no bucket do site"
  }

  # S3-04 (a distribuição grava logs no bucket de logs)
  assert {
    condition = (aws_cloudfront_distribution.site.logging_config[0].bucket == aws_s3_bucket.logs.bucket_domain_name &&
    aws_cloudfront_distribution.site.logging_config[0].prefix == "cf/")
    error_message = "logs padrão em besave-logs/cf/"
  }
}

run "distribuicao_com_dominios" {
  command = apply

  variables {
    ativar_dominios = true
  }

  # CF-11 (virada)
  assert {
    condition = (toset(aws_cloudfront_distribution.site.aliases) == toset(["besave.com.br", "www.besave.com.br"]) &&
      aws_cloudfront_distribution.site.viewer_certificate[0].acm_certificate_arn == aws_acm_certificate_validation.site.certificate_arn &&
      !aws_cloudfront_distribution.site.viewer_certificate[0].cloudfront_default_certificate &&
      aws_cloudfront_distribution.site.viewer_certificate[0].ssl_support_method == "sni-only" &&
    aws_cloudfront_distribution.site.viewer_certificate[0].minimum_protocol_version == "TLSv1.2_2021")
    error_message = "com ativar_dominios: 2 aliases e certificado ACM validado"
  }
}
