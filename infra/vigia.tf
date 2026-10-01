# Vigia externo (BSV-15): a cada 10 min confere frescor e disponibilidade do site e avisa no Telegram.
# Os parâmetros SSM são criados pelo dono; aqui só o ARN montado pelo nome, nunca o valor (não vai ao state).
locals {
  vigia               = "besave-vigia"
  vigia_param_token   = "/besave/telegram/token"
  vigia_param_chat_id = "/besave/telegram/chat_id"
  vigia_ssm_arn       = "arn:aws:ssm:${data.aws_region.atual.region}:${data.aws_caller_identity.atual.account_id}:parameter"
}

data "aws_caller_identity" "atual" {}

data "aws_region" "atual" {}

# Chave gerenciada dos SecureString; existe depois que o dono cria o primeiro parâmetro.
data "aws_kms_alias" "ssm" {
  name = "alias/aws/ssm"
}

data "archive_file" "vigia" {
  type        = "zip"
  source_file = "${path.module}/lambdas/vigia/handler.py"
  output_path = "${path.module}/.build/vigia.zip"
  # Modo fixo: o zip (e o source_code_hash) fica igual no Windows e no Linux.
  output_file_mode = "0644"
}

resource "aws_cloudwatch_log_group" "vigia" {
  name              = "/aws/lambda/${local.vigia}"
  retention_in_days = 14
}

resource "aws_iam_role" "vigia" {
  name = local.vigia
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "vigia" {
  name = "${local.vigia}-minimo"
  role = aws_iam_role.vigia.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LerManifestEEstado"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = [
          "${aws_s3_bucket.site.arn}/manifest.json",
          "${aws_s3_bucket.site.arn}/_estado/vigia.json",
        ]
      },
      {
        Sid      = "GravarEstado"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.site.arn}/_estado/vigia.json"
      },
      {
        Sid    = "LerSegredos"
        Effect = "Allow"
        Action = "ssm:GetParameter"
        Resource = [
          "${local.vigia_ssm_arn}${local.vigia_param_token}",
          "${local.vigia_ssm_arn}${local.vigia_param_chat_id}",
        ]
      },
      {
        Sid      = "DecifrarSegredos"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = data.aws_kms_alias.ssm.target_key_arn
      },
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.vigia.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "vigia" {
  function_name    = local.vigia
  role             = aws_iam_role.vigia.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.vigia.output_path
  source_code_hash = data.archive_file.vigia.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      BUCKET        = aws_s3_bucket.site.bucket
      URL_MANIFEST  = "https://${aws_cloudfront_distribution.site.domain_name}/manifest.json"
      LIMIAR_MIN    = "30"
      PARAM_TOKEN   = local.vigia_param_token
      PARAM_CHAT_ID = local.vigia_param_chat_id
    }
  }

  depends_on = [aws_cloudwatch_log_group.vigia, aws_iam_role_policy.vigia]
}

# O próximo ciclo é a retentativa: repetir após um aviso enviado duplicaria a mensagem.
resource "aws_lambda_function_event_invoke_config" "vigia" {
  function_name          = aws_lambda_function.vigia.function_name
  maximum_retry_attempts = 0
}

resource "aws_iam_role" "vigia_agenda" {
  name = "${local.vigia}-agenda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.atual.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "vigia_agenda" {
  name = "${local.vigia}-invocar"
  role = aws_iam_role.vigia_agenda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "InvocarVigia"
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.vigia.arn
    }]
  })
}

resource "aws_scheduler_schedule" "vigia" {
  name                = local.vigia
  schedule_expression = "rate(10 minutes)"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.vigia.arn
    role_arn = aws_iam_role.vigia_agenda.arn

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}
