variable "regiao" {
  description = "Região AWS do bucket do state."
  type        = string
  default     = "us-east-1"
}

variable "bucket_estado" {
  description = "Bucket privado do state do Terraform. O backend de infra/main.tf usa o mesmo nome, literal."
  type        = string
  default     = "besave-tfstate"
}
