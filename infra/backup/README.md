# infra/backup — backup diário do banco (BSV-49)

O banco de produção é o Autonomous Database **Always Free**, que não restaura (nem ponto no tempo, nem
backup manual). Este diretório é a rede de segurança, e roda na **instância 2** (`bsv-agent-2026`, AD-104):

| quando | o quê | script |
|---|---|---|
| todo dia 03:30 | Data Pump do schema `BESAVE` direto para o bucket da OCI → cópia para o S3 → apaga da OCI o que passou de 7 dias | `backup-diario.sh` |
| dia 1, 05:00 | importa o último dump em `BESAVE_RESTORE`, compara contagens e objetos inválidos, apaga o schema de teste | `teste-restauracao.sh` |
| segunda, 08:00 | resumo curto no Telegram ("4/7 ok, último N MB, último teste") | `resumo-semanal.sh` |
| se uma unidade morrer sem avisar | alerta de segurança (`OnFailure=`) | `alerta.sh` |

Retenção: **7 dias na OCI** (script), **30 dias na AWS** (regra de ciclo de vida do bucket, `infra/backup.tf`).
Nenhum script escreve em `BESAVE`; o teste de restauração escreve só em `BESAVE_RESTORE`.

Cada dia gera `besave-AAAAMMDD-NNN.dmp` (o Data Pump divide em arquivos de até 5 GB),
`besave-AAAAMMDD.log` (saída do `expdp`; **é o marcador de "export completo"**, sobe por último) e, no S3,
`SHA256SUMS`. No S3 tudo fica em `db/AAAAMMDD/`.

**Como o dump fica na OCI e no S3.** O `expdp` para o Object Storage deixa cada `besave-AAAAMMDD-NNN.dmp` com
**0 byte**; o conteúdo está nos segmentos (`besave-AAAAMMDD-NNN.dmp_segments/aaaaaa…`, ou `…dmp_aaaaaa` nos exemplos
da Oracle). A Oracle diz que baixar o `.dmp` de 0 byte pela CLI não traz o dump
([docs](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/export-data-download-run-pump.html)),
Para o S3, `backup-diario.sh` baixa
tudo, **remonta o `.dmp` concatenando os segmentos em ordem alfabética**, confere que o tamanho é a soma dos segmentos
e sobe só o `.dmp` inteiro (com o `SHA256SUMS` dele); `BYTES` no histórico é o tamanho real. A Oracle não documenta a
ordem dos segmentos (assumi a alfabética, a dos objetos grandes da API Swift); por isso **a primeira remontagem
real precisa ser provada com um `impdp` do arquivo remontado** (seção 6, "Dump só na AWS").

Testes: `bash infra/backup/teste_backup.sh` (comandos falsos, sem rede) e `shellcheck -x -P SCRIPTDIR infra/backup/*.sh`.
Ambos rodam no CI (job `infra`).

---

## 1. Ferramentas na instância 2 (ARM64, Ubuntu 24.04)

Só ferramentas oficiais; nada compilado:

- **Oracle Instant Client** ARM64, pacotes *Basic*, *Tools* (`expdp`/`impdp`) e *SQL\*Plus*, versão ≥ 19.9
  (exigência do parâmetro `credential` do Data Pump no Autonomous); no `PATH` do usuário `besave` e `ldconfig` feito.
- **OCI CLI** (instalador oficial) — autenticação por *instance principal*, sem chave em disco (passo 2).
- **AWS CLI v2** (aarch64).
- `curl`, `flock` (util-linux) e `sha256sum` já vêm no Ubuntu.
- Fuso: `sudo timedatectl set-timezone America/Sao_Paulo` (os horários dos timers são locais).
- Wallet do banco em `/srv/besave/oracle/wallet` (como na inst1, `docs/infra/VPS-INSTANCIA-1.md` Fase 4) e o IP da
  inst2 na lista de IPs permitidos do banco (Fase 0.6).

## 2. OCI: bucket e permissão (console, uma vez)

1. Bucket `besave-backup` (Standard, privado, sem versionamento), na região do banco (Vinhedo).
2. **Grupo dinâmico** (Identidade → Domínios → Grupos dinâmicos; só a inst2): nome `besave-inst2-backup`, regra
   ```
   ANY {instance.id = '<OCID da instância bsv-agent-2026>'}
   ```
   e a **política** (Identidade → Políticas, no compartimento do bucket, ou na raiz do tenancy):
   ```
   Allow dynamic-group besave-inst2-backup to manage objects in compartment <compartimento> where target.bucket.name = 'besave-backup'
   ```
   `manage objects` cobre listar, ler, gravar e apagar objetos **só desse bucket**; não dá acesso a outros buckets,
   nem a `manage buckets`. Se usar domínio que não seja o padrão, escreva `dynamic-group <domínio>/besave-inst2-backup`.
   O CLI usa `--auth instance_principal`; nenhum segredo da OCI vai para o `.env`. Teste na inst2:
   `oci os object list --bucket-name besave-backup --auth instance_principal` (deve responder, mesmo vazio).
3. **Auth token** do usuário OCI que o banco usará para gravar no bucket (Perfil → Tokens de autenticação). Ele fica
   só dentro do banco (passo 4), nunca em arquivo.

## 3. AWS (Terraform + chave)

```sh
cd infra && terraform apply        # cria besave-backup (privado, versionado, criptografado, 30 dias) e o usuário besave-backup
```
O **usuário IAM `besave-backup` é criado pelo Terraform** (não crie à mão). Só **depois do `apply`**, no console IAM,
**gere a chave de acesso** desse usuário (o Terraform não cria chave) e, na inst2,
`sudo -iu besave aws configure --profile besave-backup`. A policy só deixa gravar/ler/listar em `db/` e **nega apagar**
(inclusive versão e bucket); a expiração de 30 dias é do próprio S3.

Teste de acesso: `aws s3 ls s3://besave-backup/db/ --profile besave-backup`. Listar a **raiz**
(`aws s3 ls s3://besave-backup/`) é **negado de propósito** (o usuário só enxerga `db/`); `AccessDenied` ali é o esperado.

## 4. Banco: usuário de backup (feito pelo dono, como ADMIN)

Execute `sql/backup-dono.sql` (preenche a senha em `&senha_backup`). Cria `BESAVE_BACKUP` (só `CREATE SESSION`, os
papéis `DATAPUMP_CLOUD_EXP`/`DATAPUMP_CLOUD_IMP`, leitura de dicionário e de tabelas) e as duas rotinas
`ADMIN.BACKUP_PREPARA_RESTORE` / `BACKUP_LIMPA_RESTORE` que criam e apagam **somente** `BESAVE_RESTORE`.

Depois, conectado **como `BESAVE_BACKUP`**, crie a credencial do bucket:

```sql
BEGIN
  DBMS_CLOUD.CREATE_CREDENTIAL(
    credential_name => 'BACKUP_OCI_CRED',
    username        => '<usuário OCI>',
    password        => '<auth token do passo 2>');
END;
/
```
Se o primeiro `expdp` reclamar de credencial padrão, o ADMIN define
`ALTER DATABASE PROPERTY SET DEFAULT_CREDENTIAL = 'BESAVE_BACKUP.BACKUP_OCI_CRED';` (a documentação do Autonomous
descreve os dois caminhos; confirmar na primeira execução real).

## 5. Instalação na inst2

```sh
sudo install -d -o besave -g besave -m 750 /srv/besave/backup /srv/besave/backup/estado
sudo install -o besave -g besave -m 755 infra/backup/*.sh /srv/besave/backup/
sudo install -o besave -g besave -m 600 infra/backup/backup.env.example /srv/besave/backup/backup.env   # preencher os "..."
sudo cp infra/backup/systemd/* /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now besave-backup-diario.timer besave-backup-teste.timer besave-backup-resumo.timer
```
(`teste_backup.sh` não precisa ir para a máquina.) O `.env` guarda a senha do `BESAVE_BACKUP`, o token do bot e o
perfil AWS; `chmod 600`, dono `besave`, nunca no git.

Formato do `backup.env`: `CHAVE=valor`, sem aspas, **LF** (não salve do Windows: o CR no fim vira parte do valor) e
sem espaço no fim da linha; o script recusa o arquivo e diz qual chave. `BACKUP_DB_PASS` não pode ter `#`, espaço,
aspas, `@` nem `/` (o `userid=` do parfile quebra: `#` vira comentário e o `expdp` falha com `ORA-12162`); o script
recusa antes de chamar qualquer coisa. Use só letras, números, `_` e `-`.

Execução manual (a primeira, em horário calmo):

```sh
sudo -u besave /srv/besave/backup/backup-diario.sh      # mede tamanho e tempo; vale também como "export manual"
sudo -u besave /srv/besave/backup/teste-restauracao.sh  # teste de restauração à mão
sudo -u besave BACKUP_DIA=20261101 /srv/besave/backup/backup-diario.sh   # BACKUP_DIA só para ensaio
tail -n 3 /srv/besave/backup/estado/historico.log       # AAAAMMDD ok <bytes> <segundos>
```
Rodar duas vezes no mesmo dia não duplica nem apaga o anterior. Falha forçada: troque `BACKUP_DB_PASS` por um valor
errado por um dia, rode, confirme o alerta no Telegram e o código ≠ 0, e volte o valor.

## 6. Restaurar

**Antes de qualquer restauração (ordem):**

1. Na inst1, pare o que escreve: `sudo systemctl stop besave-ciclo.timer besave-envio.timer` (e depois os serviços,
   se estiverem rodando) e as unidades dos robôs de captura (`docs/infra/VPS-INSTANCIA-1.md`, Fase 7). Se o PC ainda
   tiver tarefas ligadas, desligue-as também.
2. Escolha o dump: `oci os object list --bucket-name besave-backup --prefix besave- --auth instance_principal`
   (OCI, 7 dias) ou `aws s3 ls s3://besave-backup/db/ --profile besave-backup` (AWS, 30 dias). Só vale dia que tem
   `besave-AAAAMMDD.log`.
3. Restaure (a, b ou c abaixo), **confira** e só então religue timers e robôs (na ordem: ciclo, envio, robôs).

Dump só na AWS: baixe `db/AAAAMMDD/` com `aws s3 cp --recursive` e confira com `sha256sum -c SHA256SUMS`. Os `.dmp`
do S3 já estão inteiros (não há segmentos). Suba cada `.dmp` e o `.log` para o bucket da OCI com `oci os object put`
(mesmos nomes), porque o `impdp` lê de lá; objeto inteiro é leitura
normal para o `impdp`.

Os exemplos usam um *parfile* com a senha (`chmod 600`, apague depois); `AAAAMMDD` é o dia do dump.

### a) Uma tabela (ex.: `OFERTA`, apagada ou corrompida)

```sh
# 1) importa só a tabela num schema à parte; BESAVE fica intocado
sqlplus ... exec ADMIN.BACKUP_PREPARA_RESTORE        # como BESAVE_BACKUP; recria BESAVE_RESTORE vazio
cat > imp.par <<'PAR'
userid=BESAVE_BACKUP/<senha>@bsvdb_high
tables=BESAVE.OFERTA
remap_schema=BESAVE:BESAVE_RESTORE
credential=BACKUP_OCI_CRED
dumpfile=<BACKUP_OCI_URI>/besave-AAAAMMDD-%L.dmp
transform=segment_attributes:n
directory=data_pump_dir
logfile=restore-oferta.log
PAR
impdp parfile=imp.par
```
2) Confira `SELECT COUNT(*)` em `BESAVE_RESTORE.OFERTA`. 3) Como o dono do `BESAVE` (ou ADMIN), traga as linhas que
faltam: `INSERT INTO BESAVE.OFERTA SELECT * FROM BESAVE_RESTORE.OFERTA r WHERE NOT EXISTS (SELECT 1 FROM BESAVE.OFERTA o WHERE o.ID_OFERTA = r.ID_OFERTA);`
(ou, se a tabela foi perdida inteira, `CREATE TABLE BESAVE.OFERTA AS SELECT * FROM BESAVE_RESTORE.OFERTA` e recriar
índices/constraints a partir do log). 4) `exec ADMIN.BACKUP_LIMPA_RESTORE`.

### b) Schema inteiro, em um banco novo

1. Crie o Autonomous novo, libere os IPs (inst1, inst2, PC), baixe o wallet e repita os passos 4 (usuário de backup
   e credencial) nele. Crie o usuário dono: `CREATE USER BESAVE IDENTIFIED BY "<senha>" QUOTA UNLIMITED ON DATA;` com os
   mesmos privilégios do antigo (anote-os antes; o export de schema não leva `GRANT` de sistema).
2. Importe sem remapear:
   ```
   userid=BESAVE_BACKUP/<senha>@<alias do banco novo>
   schemas=BESAVE
   credential=BACKUP_OCI_CRED
   dumpfile=<BACKUP_OCI_URI>/besave-AAAAMMDD-%L.dmp
   transform=segment_attributes:n
   exclude=cluster,db_link
   directory=data_pump_dir
   logfile=restore-total.log
   ```
3. Confira como no AD-100: contagem de linhas das tabelas, sequências, objetos inválidos
   (`SELECT COUNT(*) FROM dba_objects WHERE owner='BESAVE' AND status='INVALID'`) e a soma de `ORA_HASH` linha a
   linha em `OFERTA`, `OFERTA_FILA_CAPTURA`, `PRODUTO` e `ENVIO_TELEGRAM`. O banco tem de estar com
   `DBTIMEZONE = -03:00` e `SYSDATE_AT_DBTIMEZONE = TRUE` (senão o `SYSDATE` sai em UTC).
4. Aponte worker, envio e robôs para o banco novo (`BESAVE_ORACLE_DSN`, `TNS_ADMIN`, `dsn`/`config_dir` dos robôs,
   `backup.env`) e religue na ordem acima. Linhas criadas depois do dump (até 24 h) se perdem: reconstrua da fila
   de captura ou das lojas.

### c) Voltar o banco inteiro ao estado do dump (banco atual com dados errados)

Faça (b) num banco novo e troque a conexão; não apague nem sobrescreva o banco atual até conferir o novo.

---

## 7. O que o teste mensal confere

`BESAVE_RESTORE` recebe o último dump com `remap_schema`. Para cada tabela de `BESAVE`, passa se
|origem − restore| ≤ máximo(20, 5% da origem) (linhas criadas ou apagadas depois do export); tabela ausente no restore
reprova; objetos inválidos no restore não podem passar dos de `BESAVE`. Os limites vêm de
`BACKUP_TOLERANCIA_PCT` e `BACKUP_TOLERANCIA_MIN`. Ao fim, `ADMIN.BACKUP_LIMPA_RESTORE` apaga o schema, mesmo se o
teste falhou. Resultado em `estado/ultimo-teste.txt` e no Telegram.
