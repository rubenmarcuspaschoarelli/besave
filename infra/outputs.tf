output "bucket_site" {
  description = "Bucket de origem (BESAVE_BUCKET do worker)."
  value       = aws_s3_bucket.site.bucket
}

output "dominio_distribuicao" {
  description = "Domínio *.cloudfront.net para validar antes da virada."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "arn_kvs" {
  description = "ARN da KVS de redirects (BESAVE_KVS_ARN do worker)."
  value       = aws_cloudfront_key_value_store.redirects.arn
}

output "arn_distribuicao" {
  description = "ARN da distribuição nova."
  value       = aws_cloudfront_distribution.site.arn
}

output "ns_curtos" {
  description = "NS de cada zona curta, para configurar no registrador antes de ativar_curto."
  value       = { for d, z in aws_route53_zone.curto : d => z.name_servers }
}
