# BSV-49 · Backup diário do banco (export de madrugada, OCI + S3, teste de restauração)

**Papel:** Infra (bash + systemd) + Terraform · **Pastas:** `infra/backup/` (novo, roda na instância 2) e
`infra/` (Terraform do bucket de backup na AWS) · **Depende de:** nada em andamento.
AD-100, AD-104; `docs/infra/VPS-INSTANCIA-1.md` (acesso, ACL do banco)

## Contexto
Desde 15/10 o banco de produção é o Autonomous Database **Always Free**, que **não faz restauração**: sem
volta a um ponto no tempo e sem backup manual (documentação da Oracle, "Always Free Autonomous AI
Database"). Hoje um `DELETE`/`UPDATE` errado, um script com defeito ou um problema na conta apaga dados sem
volta. O único "backup" é o XE local parado desde 15/10, cada dia mais velho. A instância 2
(`bsv-agent-2026`, ARM, 4 GB) foi reservada para apoio, inclusive backup (AD-104).

## Objetivo
Todo dia de madrugada existe uma cópia completa do schema `BESAVE` em dois provedores diferentes (OCI e
AWS), com retenção definida, alerta quando falha e prova mensal de que ela restaura.

## Saídas
1. **Export diário às 03:30** (fora da janela pesada do expurgo, 02:00–05:00, que só mexe no S3; se o
   agente medir conflito de carga no banco, propor outro horário): Data Pump do schema `BESAVE`.
   Caminho provável, **a confirmar na documentação atual do Autonomous (regra 8)**: `expdp` do Instant
   Client Tools ARM64 na instância 2 gravando direto no bucket da OCI por credencial (auth token) — sem
   arquivo grande no disco do banco (20 GB). Nome com data: `besave-AAAAMMDD.dmp` + log.
2. **Cópia para a AWS:** bucket novo `besave-backup` (privado, sem acesso público, criptografia padrão,
   versionamento, regra de ciclo de vida) em Terraform; usuário IAM próprio com permissão só de gravar e
   ler em `besave-backup/db/` (nada de apagar). A cópia sai da instância 2.
3. **Retenção:** OCI 7 dias (o bucket Always Free tem 20 GB); AWS 30 dias pela regra de ciclo de vida.
   Medir o tamanho real do dump e registrar no PR.
4. **Teste de restauração mensal (dia 1, 05:00):** importa o último dump num schema `BESAVE_RESTORE` no
   mesmo banco, compara contagem de linhas por tabela com `BESAVE` (tolerância: linhas criadas depois do
   export) e objetos inválidos, e apaga o schema de teste no fim.
5. **Alerta no Telegram** (mesmo bot dos alertas, token num `.env` da instância 2 com `chmod 600`) quando
   o export, a cópia ou o teste mensal falham, e um resumo semanal curto ("7/7 backups ok, último N MB").
6. **Roteiro de restauração** (`infra/backup/README.md`): restaurar uma tabela, restaurar o schema
   inteiro num banco novo, e a ordem (parar timers e robôs da instância 1 antes). Inclui a criação do
   usuário de backup no banco (feita pelo dono, como ADMIN, com só os papéis de Data Pump necessários) e o
   IP da instância 2 na lista de IPs do banco.
7. Unidades `systemd` (timer diário e mensal) com `OnFailure=` para o alerta.

## Regras
1. O backup nunca escreve no schema `BESAVE`; o teste de restauração só no `BESAVE_RESTORE`.
2. Nenhum segredo no repositório: senha do usuário de backup, auth token da OCI e chave AWS só no `.env`
   da instância 2 (regra 11). O usuário de backup não é o `BESAVE`.
3. Sem dependência nova de runtime além de ferramentas oficiais (Instant Client Tools, OCI CLI ou
   `curl`, AWS CLI), justificadas no PR (regra 7).
4. Script idempotente: rodar duas vezes no mesmo dia não duplica nem apaga o anterior.
5. Testes de comando montado comparam o comando inteiro (lição 14).

## Fora de escopo
Backup das imagens locais da instância 1 (o S3 já é a cópia publicada), backup do repositório, alta
disponibilidade do banco, migrar para banco pago.

## Critério de aceite
- `shellcheck` limpo; testes dos scripts com comandos simulados (export, cópia, retenção, teste mensal,
  alerta), incluindo falha em cada etapa → alerta e código ≠ 0.
- `terraform validate` e `terraform test` do bucket e do IAM (só gravar e ler no prefixo; teste que prova
  que apagar é negado).
- **Real (dono):** um export manual e um agendado na madrugada; dump presente nos dois buckets; teste de
  restauração rodado à mão com contagens batendo; uma falha forçada (credencial errada por um dia de
  teste) gerando alerta; tamanho e tempo do export registrados no PR.

## Definition of done
PR com scripts, unidades, Terraform e README de restauração, `validation.md` do Verifier independente e o
primeiro backup real confirmado nos dois buckets antes do merge.
