# Bootstrap do bucket do state (BSV-53). State local próprio: mudança rara, ver README da infra.
terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.regiao

  default_tags {
    tags = {
      Projeto    = "besave"
      Gerenciado = "terraform"
    }
  }
}
