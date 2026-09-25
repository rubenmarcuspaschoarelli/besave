terraform {
  required_version = ">= 1.7"

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

locals {
  dominios = [var.dominio, "www.${var.dominio}"]
}
