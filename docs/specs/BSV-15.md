# BSV-15 · Infra: vigia externo do site (Lambda + EventBridge Scheduler + Telegram)

**Papel:** DevOps · **Pasta:** `infra/` · **Depende de:** BSV-4 (infra), BSV-14 (bot do Telegram).
MANIFEST.md §2, §5

## Contexto
O worker roda na máquina do dono (BSV-14). Se a máquina desligar, perder rede ou o Oracle cair, nenhum
alerta local sai — o processo que avisaria é o que parou. É preciso um vigia **fora** da máquina,
barato, que perceba que o site parou de ser atualizado ou parou de responder.

## Objetivo
A cada 10 minutos, uma função na AWS confere o frescor do `manifest.json` e a disponibilidade do site
pelo CloudFront, e avisa no Telegram na transição para problema e na recuperação.

## Entregáveis
1. Lambda `besave-vigia` em **Python 3.12**, só biblioteca padrão (`urllib`, `json`), arquivo único
   `infra/lambdas/vigia/handler.py`, empacotado pelo Terraform (`archive_file`). Justificativa: ~60 linhas,
   sem toolchain de build no CI; Rust/cargo-lambda não se paga aqui (vira AD).
2. Agendamento com **EventBridge Scheduler** (`rate(10 minutes)`).
3. Verificações:
   - **Frescor**: `HeadObject` em `s3://besave-site/manifest.json` → `LastModified`. Alerta se mais velho que
     `LIMIAR_MIN` (padrão 30 min). Lê o S3 direto (sem o cache de 300 s do CloudFront).
   - **Disponibilidade**: `GET https://<dominio_distribuicao>/manifest.json` com timeout 10 s → precisa de 200 e
     JSON com `versao`. Alerta em erro/timeout/status ≠ 200.
4. **Estado e anti-spam** em `s3://besave-site/_estado/vigia.json`: `{ "situacao": "ok|alerta", "desde": ..., "ultimo_aviso": ... }`.
   Mensagem só na transição ok→alerta, lembrete a cada 3 h enquanto em alerta, e na volta alerta→ok
   (`✅ Besave: site atualizado de novo (parado por 1h40)`). Horários em Brasília (-03:00).
5. Segredos: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` em **SSM Parameter Store SecureString**
   (`/besave/telegram/token`, `/besave/telegram/chat_id`), criados **pelo dono** no console/CLI — o Terraform
   só referencia o nome (data source), nunca o valor, para o segredo não ir ao state.
6. IAM da Lambda (mínimo): `s3:GetObject` em `manifest.json` e `_estado/vigia.json`; `s3:PutObject` só em
   `_estado/vigia.json`; `ssm:GetParameter` nos dois parâmetros (+ `kms:Decrypt` da chave padrão `aws/ssm`);
   logs no CloudWatch com retenção de **14 dias** (grupo de log criado pelo Terraform, não implícito).
7. Testes: `terraform test` cobrindo recursos, agendamento, retenção e a policy exata; testes Python
   (`unittest`, sem rede, com dublês de S3/HTTP/Telegram) para a máquina de estados do aviso.
   Job `infra` do CI roda os testes Python.

## Regras
- Mensagens nunca incluem token, ARN completo nem URL de afiliado.
- Falha ao enviar para o Telegram → log de erro e o estado **não** avança (tenta de novo no próximo ciclo).
- Custo esperado: dentro do free tier (4.320 invocações/mês, Scheduler e SSM standard gratuitos). Registrar no README.
- Nada que mude a distribuição, o bucket ou a política do worker.

## Fora de escopo
Alertas de custo (Budgets), monitoramento do Oracle, painel, resumo diário.

## Critério de aceite
- Dublês: manifest com 10 min → ok, sem mensagem; 31 min → alerta (1 mensagem); seguinte ainda velho → 0;
  3 h depois → lembrete; fresco de novo → "voltou" com duração.
- HTTP 403/timeout no CloudFront → alerta de disponibilidade (distinto do de frescor).
- Telegram falhando → estado não avança; próxima execução tenta de novo.
- `terraform fmt/validate/test` limpos; `plan` real (dono) só com `to add`, `0 to change`, `0 to destroy`.
- **Real (dono):** criar os 2 parâmetros SSM; `apply`; `aws lambda invoke` manual → ok sem mensagem;
  desativar a tarefa do worker (BSV-14) por 40 min → alerta no Telegram; reativar → "voltou".

## Definition of done
PR com README (criar parâmetros SSM, testar com `lambda invoke`, custo), `plan` colado, testes verdes,
prints das mensagens (sem token/chat_id).
