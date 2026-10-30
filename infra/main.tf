terraform {
  required_version = ">= 1.11" # use_lockfile estável (BSV-53)

  # Nome literal (backend não aceita variável); o mesmo de infra/estado/. Lock nativo do S3, sem DynamoDB.
  backend "s3" {
    bucket       = "besave-tfstate"
    key          = "infra/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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

locals {
  dominios = [var.dominio, "www.${var.dominio}"]
}
