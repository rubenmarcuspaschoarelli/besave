# BSV-15 — Vigia externo do site (Lambda + EventBridge Scheduler + Telegram)

Fonte: `docs/specs/BSV-15.md` (escopo); MANIFEST §1, §2, §5.
Pasta: `infra/`. Depende de BSV-4 (infra, em `develop`) e BSV-14 (bot do Telegram: só o token e o chat).

## Problem Statement

O worker roda na máquina do dono. Se a máquina desligar, perder rede ou o Oracle cair, nenhum alerta
local sai, porque o processo que avisaria é justamente o que parou. Falta um vigia barato, fora da
máquina, que perceba que o site parou de ser atualizado ou parou de responder.

## Goals

- [ ] A cada 10 min, uma Lambda confere o frescor do `manifest.json` (S3) e a disponibilidade do site (CloudFront).
- [ ] O Telegram recebe aviso só na transição ok→alerta, lembrete a cada 3 h e aviso de recuperação com a duração.
- [ ] Custo dentro do free tier; o segredo nunca vai para o state nem para o git.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Alertas de custo (Budgets), monitoramento do Oracle, painel, resumo diário | spec: fora de escopo |
| Mudança na distribuição, no bucket ou na política do worker | spec: regras |
| Criar os parâmetros SSM | o dono cria no console/CLI (spec §5) |
| Alarme sobre erros da própria Lambda | não pedido; o log fica no CloudWatch por 14 dias |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Chamadas assinadas (S3, SSM) | `boto3` do runtime `python3.12` da Lambda; HTTP do site e do Telegram com `urllib`; nada empacotado além de `handler.py` | Escolha do dono (01/10). A spec diz "só biblioteca padrão", mas S3/SSM exigem SigV4. O `boto3` do runtime não precisa de toolchain de build. Os testes injetam dublês, então o CI não instala `boto3`. Vira AD | y |
| Import do `boto3` | Só dentro de `lambda_handler`, ao montar os clientes reais | Os testes importam o módulo sem `boto3` instalado | y |
| Referência aos parâmetros SSM | O ARN é montado a partir de `data.aws_caller_identity` + `data.aws_region` + o nome. Não há `data "aws_ssm_parameter"` | O data source `aws_ssm_parameter` guarda `value` no state, que é o que a spec proíbe. O preço é que o `plan` não falha se o parâmetro não existir; nesse caso o erro aparece no `lambda invoke` do README | n |
| Chave KMS do `kms:Decrypt` | `data "aws_kms_alias" "ssm"` (`alias/aws/ssm`) → `target_key_arn` | A spec pede a chave padrão `aws/ssm`. O alias existe depois que o dono cria o 1º SecureString, e o README manda criar os parâmetros antes do `plan` | n |
| Estado ausente ou ilegível | Qualquer falha no `GetObject` de `_estado/vigia.json` → "sem estado" (`ok`). `NoSuchKey` → log INFO; qualquer outro código → log ERROR com o código. JSON inválido → `ok` + log ERROR | Risco aceito pelo dono (01/10). `s3:ListBucket` com `s3:prefix = "_estado/vigia.json"` faz o S3 responder `NoSuchKey` para arquivo inexistente; `AccessDenied` passa a ser problema real (dono, 01/10) | y |
| Formato de data no estado | ISO 8601 UTC com `Z` (`2026-10-01T12:00:00Z`) | CLAUDE.md regra 5: no dado é UTC; na exibição é Brasília (-03:00) | y |
| Quando o estado é gravado | Só quando se envia um aviso (alerta, lembrete ou recuperação). Ciclo ok→ok e alerta sem lembrete devido não fazem `PutObject` | Evita uma escrita a cada 10 min; a spec só pede estado para o anti-spam | n |
| Lembrete | Quando `agora - ultimo_aviso >= 180 min` | Spec: "lembrete a cada 3 h" | y |
| `desde` no alerta de frescor | `LastModified` do manifest, não a hora da detecção | "parado por" deve medir quanto tempo o site ficou sem atualizar; usar a hora da detecção subestimaria em até `LIMIAR_MIN` | n |
| Duração na recuperação | `agora - desde`: `< 60 min` → `"{m} min"`; senão `"{h}h{mm:02}"` (`1h40`, `3h05`) | Exemplo da spec: "parado por 1h40" | n |
| Falha de leitura do `manifest.json` no S3 (`HeadObject` erra) | Conta como problema de frescor ("manifest.json inacessível no S3") | O vigia não tem como afirmar que está fresco | n |
| Disponibilidade | `GET` sem `Accept-Encoding`, timeout de 10 s; precisa de 200 e de um JSON objeto com a chave `versao`. Qualquer outra coisa conta como problema, e a mensagem diz o motivo (`HTTP 403`, `timeout`, `JSON sem versao`) | Spec §3 | y |
| URL verificada | `https://${aws_cloudfront_distribution.site.domain_name}/manifest.json` na variável de ambiente `URL_MANIFEST` | Spec: `<dominio_distribuicao>`; funciona antes e depois da virada de DNS | n |
| Retentativas | `aws_scheduler_schedule.target.retry_policy.maximum_retry_attempts = 0` e `aws_lambda_function_event_invoke_config.maximum_retry_attempts = 0` | O próximo ciclo (10 min) é a retentativa. Retentativa automática depois de um aviso enviado com falha ao gravar o estado duplicaria a mensagem | n |
| Falha no Telegram | O `lambda_handler` loga o erro e **retorna normalmente**, sem gravar o estado | Spec: "o estado não avança". Levantar exceção não ajuda, porque as retentativas estão desligadas | y |
| Segredos lidos | O SSM só é consultado quando há aviso a enviar | Evita 2 `GetParameter` a cada 10 min sem necessidade | n |
| Log sem token | Erros de envio logam só o tipo da exceção e o status HTTP, nunca a URL `bot<token>` | Spec: mensagens nunca incluem token. `HTTPError.url` traria o token | y |
| Provider novo | `hashicorp/archive` (`archive_file`) | A spec exige `archive_file`. O zip vai para `infra/.build/`, que entra no `.gitignore` | y |
| Parâmetros da Lambda | `python3.12`, 128 MB, timeout de 30 s (cobre 10 s do site + Telegram + S3) | — | n |
| Objeto `_estado/vigia.json` legível pelo CloudFront | Aceito: ele só tem situação e horários | É o mesmo caso do `_estado/paginas.json` (BSV-21); o bucket e a distribuição não mudam | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Verificações ⭐ MVP

**User Story**: Como dono, quero que algo fora da minha máquina perceba quando o site para de atualizar ou de responder.

**Acceptance Criteria**:

1. VER-01: WHEN o `LastModified` de `manifest.json` no S3 tem no máximo `LIMIAR_MIN` minutos (padrão 30) THEN o vigia SHALL considerar o frescor ok.
2. VER-02: WHEN o `LastModified` tem mais de `LIMIAR_MIN` minutos, ou o `HeadObject` falha THEN o vigia SHALL registrar um problema de **frescor**.
3. VER-03: WHEN o `GET` em `URL_MANIFEST` devolve 200 com um JSON que tem `versao` THEN o vigia SHALL considerar a disponibilidade ok.
4. VER-04: IF o `GET` dá timeout ou erro de rede, devolve status ≠ 200, ou devolve um corpo que não é um JSON com `versao` THEN o vigia SHALL registrar um problema de **disponibilidade**, com texto distinto do de frescor.
5. VER-05: The `GET` SHALL usar timeout de 10 s.

**Independent Test**: dublês de S3/HTTP com idade e status controlados.

### P1: Avisos e anti-spam

**User Story**: Como dono, quero um aviso por problema, um lembrete de vez em quando e o aviso de volta, sem spam.

**Acceptance Criteria**:

1. AVI-01: WHEN a situação era `ok` (ou o estado não existe) e não há problema THEN o vigia SHALL NOT enviar mensagem nem gravar o estado.
2. AVI-02: WHEN a situação era `ok` e há problema THEN o vigia SHALL enviar exatamente 1 mensagem com os problemas e gravar `{situacao: "alerta", desde: <início>, ultimo_aviso: agora}`, sendo `<início>` o menor entre o `LastModified` do manifest (se o problema é de frescor) e `agora` (qualquer outro problema).
3. AVI-03: WHILE em `alerta` com `agora - ultimo_aviso < 3 h` e problema persistente, o vigia SHALL NOT enviar mensagem nem gravar o estado.
4. AVI-04: WHILE em `alerta` com `agora - ultimo_aviso >= 3 h` e problema persistente, o vigia SHALL enviar 1 lembrete e gravar `ultimo_aviso = agora`, mantendo `desde`.
5. AVI-05: WHEN a situação era `alerta` e não há problema THEN o vigia SHALL enviar `✅ Besave: site atualizado de novo (parado por <duração>)`, com a duração `agora - desde`, e gravar `{situacao: "ok", desde: agora, ultimo_aviso: agora}`.
6. AVI-06: IF o envio ao Telegram falha (erro de rede, status ≠ 200, `ok` ≠ `true`, ou falha ao ler o SSM) THEN o vigia SHALL logar o erro e SHALL NOT gravar o estado; a execução seguinte SHALL tentar de novo.
7. AVI-07: The horários nas mensagens SHALL estar em Brasília (-03:00, `HH:MM`); no estado SHALL ser ISO 8601 UTC.
8. AVI-08: The mensagens e os logs SHALL NOT conter o token, o `chat_id`, ARN nem URL de afiliado.
9. AVI-09: IF a leitura de `_estado/vigia.json` falha THEN o vigia SHALL seguir sem estado (`ok`); com `NoSuchKey` SHALL logar em INFO, e com qualquer outro código SHALL logar em ERROR com o código.

**Independent Test**: a sequência do critério de aceite (10 min → 31 min → ainda velho → +3 h → fresco) sobre um S3 em memória.

### P1: Infra (Terraform)

**User Story**: Como dono, quero a infra do vigia no mesmo Terraform, mínima e sem segredo no state.

**Acceptance Criteria**:

1. INF-01: The Terraform SHALL criar a Lambda `besave-vigia` (`python3.12`, handler `handler.lambda_handler`), empacotada por `archive_file` a partir de `infra/lambdas/vigia/handler.py`, com o ambiente `BUCKET`, `URL_MANIFEST`, `LIMIAR_MIN=30`, `PARAM_TOKEN=/besave/telegram/token` e `PARAM_CHAT_ID=/besave/telegram/chat_id`.
2. INF-02: The Terraform SHALL criar um `aws_scheduler_schedule` com `rate(10 minutes)` apontando para a Lambda, por meio de um role que só pode `lambda:InvokeFunction` nela.
3. INF-03: The Terraform SHALL criar o grupo de log `/aws/lambda/besave-vigia` com retenção de 14 dias.
4. INF-04: The role da Lambda SHALL ter exatamente: `s3:GetObject` em `manifest.json` e `_estado/vigia.json`; `s3:PutObject` só em `_estado/vigia.json`; `s3:ListBucket` no bucket só com `StringEquals s3:prefix = "_estado/vigia.json"` (dono, 01/10); `ssm:GetParameter` nos 2 parâmetros; `kms:Decrypt` na chave `aws/ssm`; `logs:CreateLogStream` + `logs:PutLogEvents` só no grupo do vigia.
5. INF-05: The Terraform SHALL NOT ler o valor dos parâmetros SSM (nenhum `aws_ssm_parameter`, nem resource nem data).
6. INF-06: The Terraform SHALL NOT alterar a distribuição, os buckets nem a política do worker.
7. INF-07: The Scheduler e a invocação assíncrona da Lambda SHALL ter 0 retentativas.

### P2: Operação

**Acceptance Criteria**:

1. OPS-03: The job `infra` do CI SHALL rodar os testes Python do vigia.
2. OPS-04: The `infra/README.md` SHALL explicar como criar os 2 parâmetros SSM, testar com `aws lambda invoke` e qual é o custo esperado (free tier).

---

## Edge Cases

- WHEN `LastModified` tem exatamente `LIMIAR_MIN` minutos THEN o frescor SHALL ser ok (o alerta exige "mais velho que").
- WHEN há os dois problemas THEN a mensagem SHALL listar os dois.
- WHEN o estado gravado é inválido THEN o vigia SHALL tratá-lo como `ok`.
- WHEN a recuperação falha no Telegram THEN o estado SHALL continuar `alerta`, e o próximo ciclo saudável SHALL enviar a recuperação.

Dimensions: estado persistido e transições (AVI-01..05); falha de dependência externa (VER-02, VER-04, AVI-06); idempotência/retry (AVI-06, INF-07); auth (INF-04, INF-05); observabilidade (INF-03, AVI-06); dados sensíveis (AVI-08, INF-05). Validação de entrada e concorrência: N/A, porque a única entrada é o evento fixo do Scheduler e só há uma execução a cada 10 min (timeout de 30 s).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| VER-01 | P1: Verificações | T1 | Done |
| VER-02 | P1: Verificações | T1 | Done |
| VER-03 | P1: Verificações | T1 | Done |
| VER-04 | P1: Verificações | T1 | Done |
| VER-05 | P1: Verificações | T1 | Done |
| AVI-01 | P1: Avisos | T1 | Done |
| AVI-02 | P1: Avisos | T1 | Done |
| AVI-03 | P1: Avisos | T1 | Done |
| AVI-04 | P1: Avisos | T1 | Done |
| AVI-05 | P1: Avisos | T1 | Done |
| AVI-06 | P1: Avisos | T1 | Done |
| AVI-07 | P1: Avisos | T1 | Done |
| AVI-08 | P1: Avisos | T1 | Done |
| AVI-09 | P1: Avisos | T1 | Done |
| INF-01 | P1: Infra | T2 | Done |
| INF-02 | P1: Infra | T2 | Done |
| INF-03 | P1: Infra | T2 | Done |
| INF-04 | P1: Infra | T2 | Done |
| INF-05 | P1: Infra | T2 | Done |
| INF-06 | P1: Infra | T2 | Done |
| INF-07 | P1: Infra | T2 | Done |
| OPS-03 | P2: Operação | T3 | Done |
| OPS-04 | P2: Operação | T3 | Done |

**Coverage:** 23 total, 23 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] `python -m unittest` (sem rede), `terraform fmt -check -recursive`, `validate` e `test` verdes.
- [ ] Execução real (dono): criar os 2 parâmetros; `plan` só com `to add`; `apply`; `aws lambda invoke` → ok sem mensagem; worker parado por 40 min → alerta; worker de volta → "voltou".
