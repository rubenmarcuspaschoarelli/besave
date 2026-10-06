variable "regiao" {
  description = "Região AWS. CloudFront exige certificado ACM em us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "dominio" {
  description = "Domínio raiz; a zona Route53 já existe."
  type        = string
  default     = "besave.com.br"
}

variable "bucket_site" {
  description = "Bucket privado de origem do site."
  type        = string
  default     = "besave-site"
}

variable "bucket_logs" {
  description = "Bucket dos logs padrão do CloudFront."
  type        = string
  default     = "besave-logs"
}

variable "ativar_dominios" {
  description = "Coloca besave.com.br e www como aliases da distribuição. Só na virada: os nomes precisam sair antes da distribuição antiga."
  type        = bool
  default     = false
}

variable "classe_preco" {
  description = "Price class do CloudFront. PriceClass_100/200 não incluem a América do Sul."
  type        = string
  default     = "PriceClass_All"
}

variable "dominios_curtos" {
  description = "Domínios curtos (CONTRATO §5), registrados fora da AWS. O primeiro é o nome principal do certificado."
  type        = list(string)
  default     = ["besave.io", "besave.me"]
}

variable "ativar_curto" {
  description = "Fase 2 dos domínios curtos: certificado, distribuição e registros. Só depois que os NS das zonas propagarem no registrador."
  type        = bool
  default     = false
}
