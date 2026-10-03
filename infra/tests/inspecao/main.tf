# Módulo só de teste: lê os .tf da raiz e expõe os blocos `resource` como texto.
# terraform test não enumera recursos; ausência e meta-argumentos (prevent_destroy) só se provam assim.
locals {
  raiz = "${path.module}/../.."
  # Linhas comentadas saem antes da análise: `# prevent_destroy = true` não conta.
  fontes = [for f in fileset(local.raiz, "*.tf") : replace(file("${local.raiz}/${f}"), "/(?m)^[ \\t]*(#|//).*$/", "")]
  # "tipo.nome" => corpo; o bloco termina no primeiro "}" em coluna 0 (terraform fmt garante).
  blocos = merge([for src in local.fontes : {
    for m in regexall("(?ms)^resource \"([^\"]+)\" \"([^\"]+)\" \\{(.*?)^\\}", src) : "${m[0]}.${m[1]}" => m[2]
  }]...)
}

output "recursos" {
  value = keys(local.blocos)
}

# Blocos que expiram objetos do bucket do site: lifecycle configuration apontando para ele
# ou lifecycle_rule inline no próprio aws_s3_bucket.site.
output "expiracao_no_site" {
  value = [for k, v in local.blocos : k if can(regex("expir", v)) && (
    k == "aws_s3_bucket.site" ||
    (startswith(k, "aws_s3_bucket_lifecycle_configuration.") && can(regex("aws_s3_bucket\\.site\\.|var\\.bucket_site\\b|\"besave-site\"", v)))
  )]
}

output "prevent_destroy" {
  value = { for k, v in local.blocos : k => can(regex("(?s)lifecycle\\s*\\{[^}]*prevent_destroy\\s*=\\s*true", v)) }
}

# BSV-15: data source que leria o valor de um parâmetro SSM (o valor iria ao state).
output "le_parametro_ssm" {
  value = anytrue([for src in local.fontes : can(regex("(?m)^data \"aws_ssm_parameters?(_by_path)?\"", src))])
}

# BSV-15: recursos declarados em vigia.tf.
output "recursos_vigia" {
  value = [for m in regexall("(?m)^resource \"([^\"]+)\" \"([^\"]+)\"", replace(file("${local.raiz}/vigia.tf"), "/(?m)^[ \t]*(#|//).*$/", "")) : "${m[0]}.${m[1]}"]
}
