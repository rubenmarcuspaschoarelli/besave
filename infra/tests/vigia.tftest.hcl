mock_provider "aws" {
  source = "./tests/mocks"
}

run "vigia" {
  command = apply # mock_provider: nada é criado

  # INF-01
  assert {
    condition = (aws_lambda_function.vigia.function_name == "besave-vigia" &&
      aws_lambda_function.vigia.runtime == "python3.12" &&
      aws_lambda_function.vigia.handler == "handler.lambda_handler" &&
      aws_lambda_function.vigia.role == aws_iam_role.vigia.arn &&
      aws_lambda_function.vigia.filename == data.archive_file.vigia.output_path &&
    aws_lambda_function.vigia.source_code_hash == data.archive_file.vigia.output_base64sha256)
    error_message = "Lambda besave-vigia: python3.12, handler.lambda_handler, zip do archive_file"
  }
  assert {
    condition     = endswith(data.archive_file.vigia.source_file, "lambdas/vigia/handler.py") && data.archive_file.vigia.type == "zip"
    error_message = "o zip deve vir de lambdas/vigia/handler.py"
  }
  assert {
    condition     = data.archive_file.vigia.output_file_mode == "0644"
    error_message = "modo fixo no zip: o source_code_hash não pode depender do SO"
  }
  assert {
    condition = aws_lambda_function.vigia.environment[0].variables == tomap({
      BUCKET        = "besave-site"
      URL_MANIFEST  = "https://${aws_cloudfront_distribution.site.domain_name}/manifest.json"
      LIMIAR_MIN    = "30"
      PARAM_TOKEN   = "/besave/telegram/token"
      PARAM_CHAT_ID = "/besave/telegram/chat_id"
    })
    error_message = "ambiente da Lambda difere da spec"
  }
  assert {
    condition     = aws_lambda_function.vigia.timeout == 30 && aws_lambda_function.vigia.memory_size == 128
    error_message = "timeout 30 s, 128 MB"
  }

  # INF-02
  assert {
    condition = (aws_scheduler_schedule.vigia.schedule_expression == "rate(10 minutes)" &&
      aws_scheduler_schedule.vigia.flexible_time_window[0].mode == "OFF" &&
      aws_scheduler_schedule.vigia.target[0].arn == aws_lambda_function.vigia.arn &&
    aws_scheduler_schedule.vigia.target[0].role_arn == aws_iam_role.vigia_agenda.arn)
    error_message = "agenda: rate(10 minutes) chamando a Lambda pelo role da agenda"
  }
  assert {
    condition = jsondecode(aws_iam_role_policy.vigia_agenda.policy) == {
      Version = "2012-10-17"
      Statement = [{
        Sid      = "InvocarVigia"
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = "arn:aws:lambda:us-east-1:111111111111:function:besave-vigia"
      }]
    } && aws_iam_role_policy.vigia_agenda.role == aws_iam_role.vigia_agenda.id
    error_message = "role da agenda só invoca o vigia"
  }
  assert {
    condition = jsondecode(aws_iam_role.vigia_agenda.assume_role_policy).Statement[0].Principal == { Service = "scheduler.amazonaws.com" } && (
    jsondecode(aws_iam_role.vigia_agenda.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "111111111111")
    error_message = "role da agenda: só o Scheduler desta conta assume"
  }
  assert {
    condition     = jsondecode(aws_iam_role.vigia.assume_role_policy).Statement[0].Principal == { Service = "lambda.amazonaws.com" }
    error_message = "role do vigia é assumido pela Lambda"
  }

  # INF-03
  assert {
    condition     = aws_cloudwatch_log_group.vigia.name == "/aws/lambda/besave-vigia" && aws_cloudwatch_log_group.vigia.retention_in_days == 14
    error_message = "grupo de log /aws/lambda/besave-vigia com 14 dias"
  }

  # INF-04: exatamente estas ações, só nestes recursos
  assert {
    condition = jsondecode(aws_iam_role_policy.vigia.policy) == {
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
            "arn:aws:ssm:us-east-1:111111111111:parameter/besave/telegram/token",
            "arn:aws:ssm:us-east-1:111111111111:parameter/besave/telegram/chat_id",
          ]
        },
        {
          Sid      = "DecifrarSegredos"
          Effect   = "Allow"
          Action   = "kms:Decrypt"
          Resource = "arn:aws:kms:us-east-1:111111111111:key/00000000-0000-0000-0000-00000000055a"
        },
        {
          Sid      = "Logs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "arn:aws:logs:us-east-1:111111111111:log-group:/aws/lambda/besave-vigia:*"
        },
      ]
    } && aws_iam_role_policy.vigia.role == aws_iam_role.vigia.id
    error_message = "policy do vigia difere do mínimo da spec"
  }
  assert {
    condition     = data.aws_kms_alias.ssm.name == "alias/aws/ssm"
    error_message = "kms:Decrypt na chave padrão aws/ssm"
  }

  # INF-07
  assert {
    condition = (aws_scheduler_schedule.vigia.target[0].retry_policy[0].maximum_retry_attempts == 0 &&
      aws_lambda_function_event_invoke_config.vigia.maximum_retry_attempts == 0 &&
    aws_lambda_function_event_invoke_config.vigia.function_name == aws_lambda_function.vigia.function_name)
    error_message = "0 retentativas no Scheduler e na invocação assíncrona"
  }
}

run "vigia_inspecao" {
  command = plan

  module {
    source = "./tests/inspecao"
  }

  # INF-05: o valor dos parâmetros nunca é lido pelo Terraform (iria ao state)
  assert {
    condition     = length([for k in output.recursos : k if startswith(k, "aws_ssm_parameter.")]) == 0 && !output.le_parametro_ssm
    error_message = "nenhum aws_ssm_parameter (resource ou data) no Terraform"
  }

  # INF-06: o vigia não declara nada sobre a distribuição, os buckets ou o usuário do worker
  assert {
    condition = length([for k in output.recursos_vigia : k if can(regex("^aws_(cloudfront_|s3_|iam_user)", k))]) == 0 && (
    length(output.recursos_vigia) == 8)
    error_message = "vigia.tf só cria Lambda, log, roles, policies, invoke config e agenda"
  }
}
