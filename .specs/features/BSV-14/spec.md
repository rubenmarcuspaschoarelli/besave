# BSV-14 — Execução agendada, trava, logs e alerta de falha no Telegram

Fonte: `docs/specs/BSV-14.md` (escopo); MANIFEST §6.
Pasta: `apps/worker/` (+ `apps/worker/scripts/`). Depende de BSV-12c (em `develop`).

## Problem Statement

O worker publica um ciclo em ~20–60 s, mas roda à mão. Precisa rodar sozinho a cada 5 min no
Windows do dono, sem sobreposição, com log em arquivo e aviso no Telegram quando um ciclo falha,
sem spam. Máquina desligada é BSV-15.

## Goals

- [ ] `besave-worker --ciclo --env-file <.env>` = `--publicar --sim` + trava + log em arquivo + alerta.
- [ ] Ciclo ok: silencioso (só log). Ciclo com falha: log + 1 mensagem no Telegram por variante a cada 2 h.
- [ ] Código de saída 0/1/2 legível pelo Agendador; scripts para registrar/remover a tarefa.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Vigia externo / máquina desligada | BSV-15 |
| Resumo diário, comandos pelo Telegram | spec: fora de escopo |
| Rodar fora do Windows | spec: fora de escopo (os testes rodam no CI Linux, com caminhos injetados) |
| Loop interno com `sleep` | spec: o agendamento é do Windows |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Forma do modo | Flag `--ciclo` no mesmo grupo de `--dry-run`/`--gerar`/`--publicar`; `--env-file` vale para qualquer modo | A spec aceita flag ou subcomando; flag mantém o CLI atual intacto | n |
| Precedência do `.env` | `--env-file` é lido do `argv` antes do `clap` (os `env =` do clap já enxergam o `.env`); `dotenvy::from_path` não sobrescreve variável já definida | "carrega antes de qualquer outra coisa"; "ambiente vence o `.env`" | y |
| Trava | `std::fs::File::try_lock` (estável desde Rust 1.89; toolchain 1.95), sem `fs2`. O SO solta a trava quando o processo morre. Ao adquirir, grava `pid=… inicio=…`; ao soltar, acrescenta ` fim=…`. "Lock órfão" = conteúdo sem `fim=` com a trava livre (o processo morreu sem soltar) → tomado com `WARN` que cita o conteúdo anterior. O arquivo nunca é apagado | Spec permite "fs2 ou equivalente"; a std dispensa dependência e checagem de PID por API do Windows. No Windows a trava bloqueia leitura por outro handle, então o PID só é lido depois (diagnóstico do órfão) | n |
| Log em arquivo | Sem `tracing-appender`: cada execução dura < 20 min, então o arquivo do dia é escolhido no início (`besave-worker.AAAA-MM-DD.log`, data de Brasília, -03:00) e aberto em append; `tracing-subscriber` escreve nele e no stderr | `tracing-appender` rotaciona por data UTC (virada às 21h de Brasília) e só serve a processos longos; uma dependência a menos | n |
| Retenção | No início do ciclo (depois da trava) remove `besave-worker.AAAA-MM-DD.log` com data < hoje − 14 dias (Brasília); outros arquivos da pasta ficam | "mais de 14 dias"; data no nome é determinística (mtime muda com cópia) | n |
| Cliente HTTPS | `hyper-util` (client legacy) + `hyper-rustls` + `http-body-util` + `bytes`, todos já no `Cargo.lock` pelo SDK AWS (TLS = rustls/aws-lc-rs já compilado); nenhum pacote novo no lock | Spec: "cliente HTTP já presente no SDK; justificar". `reqwest` traria crates novas e inclui a URL (com o token) no texto do erro | n |
| Timeout do Telegram | 10 s por envio (`tokio::time::timeout`; liga a feature `time` do `tokio`, sem crate nova) | Envio travado não pode segurar o ciclo | n |
| Variante do erro | Primeiros 2 identificadores do `Debug` do erro (`Redirects(Kvs { … })` → `Redirects::Kvs`); só `[A-Za-z0-9_]` | Spec: "nome da variante, não o texto completo"; nunca carrega dado do erro | n |
| Fase | `env_file`, `config`, `trava`, `conexao_oracle`, `contexto_aws`; erro de `gerar()` → `leitura_fonte` (Fonte), `imagens`, `chunks` (Chunk, ChunkAcimaDoOrcamento), `paginas` (Site), `redirects`, `manifest` (Manifest*, VersaoContrato), `s3` (Publicador) | `gerar()` não muda (spec); a variante de topo de `ErroGeracao` diz o módulo onde parou. `Publicador` ocorre em várias fases: `s3` é o nome honesto | n |
| Código 2 (configuração) | `.env` ilegível/ausente; env obrigatória ausente ou inválida (`BESAVE_*`, `BESAVE_FONTE`, mapeamento, `TELEGRAM_*` pela metade, `LOCALAPPDATA` ausente sem `BESAVE_LOCK`/`BESAVE_LOG_DIR`); região AWS ausente | Spec §3 | n |
| Gatilho de boot | Só "1 min após o logon"; sem gatilho de inicialização | Com "somente quando conectado" (Interactive), um gatilho de boot sem logon não roda a tarefa; o de logon cobre o boot seguido de logon | n |
| Erro do `.env` | `LineParse` do `dotenvy` vira "linha malformada (posição N)", sem o texto da linha | O erro original ecoa a linha, que pode ter token/senha (achado do Verifier) | n |
| Sem janela de console | Binário `besave-ciclo` com `windows_subsystem = "windows"` chama `ciclo::executar` da lib (mesmo caminho do `--ciclo`); o `--ciclo` continua para uso manual, com stderr e stdout | Ajuste do dono (01/10): janela a cada 5 min é inaceitável | y |
| Argumentos do `besave-ciclo` | Só `--env-file <arq>`/`--env-file=<arq>` (ou nenhum); o resto → código 2 (`variante=Argumento`), só no log | Sem console, `clap` imprimiria erro no vazio | n |
| Teste sem AWS do ciclo inteiro | `BESAVE_DESTINO_LOCAL` (pasta + KVS em memória) e `BESAVE_AGORA` (só com destino local) | A fonte fake data as ofertas a partir de `agora`; sem relógio fixo os bytes do chunk mudam entre execuções. Restrito ao destino local para nunca afetar publicação real | n |
| Mapeamento padrão | `include_str!` de `packages/contract/mapeamento.json` (mesmo padrão do `PACKAGE_CONTRATO` em `geracao.rs`); `BESAVE_MAPEAMENTO`/`--mapeamento` só como override | Execução real: caminho relativo depende da pasta de trabalho do Agendador | y |
| Alerta em código 2 | Também alerta (fase `config`/`env_file`) quando `TELEGRAM_*` está disponível | É falha de ciclo; a execução real do dono depende de um alerta | n |
| `TELEGRAM_*` pela metade | Código 2 | Desligar em silêncio esconderia o erro | n |
| Host na mensagem | `COMPUTERNAME` (Windows) ou `HOSTNAME`; só `[A-Za-z0-9._-]`, até 63 chars; senão `desconhecido` | Spec pede host; filtro garante que não vaza caminho | n |
| Horário na mensagem | `dd/mm/aaaa HH:MM (-03:00)` | Spec: Brasília, offset fixo | n |
| Estado do anti-spam | `alerta.json` na pasta do lock padrão (`%LOCALAPPDATA%\besave\`): `falhas`, `desde` (unix), `envios` (variante → unix do último envio entregue). JSON ilegível → `WARN` e estado vazio. Gravação que falha → `WARN` | Spec §2 | n |
| Janela | Mesma variante: envia se nunca entregue ou se `agora − último ≥ 7200 s`. Variante diferente tem janela própria | "no máximo 1 mensagem a cada 2 h" | y |
| Recuperação | 1º sucesso com `falhas > 0` → `✅ Besave worker: recuperado após N falhas (desde HH:MM)` (N = ciclos falhos seguidos, HH:MM de Brasília da 1ª); estado zera só se o envio deu certo (senão tenta no próximo sucesso) | Spec §2; recado perdido seria pior que atrasado | n |
| Envio que falha | Falha: não registra o envio (o próximo ciclo tenta de novo); `WARN`; código de saída inalterado | Spec: "nunca muda o código de saída" | n |
| Ciclo pulado pela trava | Não toca o estado do alerta | Não é falha nem sucesso | n |
| Sem `TELEGRAM_*` | `INFO` "alerta desligado" e o estado não é lido nem gravado | Ambiente de dev | n |
| Linha de relatório | `INFO` com mensagem `relatorio` e campos `chave=valor` (contagens, redirects, imagens, páginas, `t_*`, `tempo_ms`) — uma linha | Spec §1 | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Modo ciclo e configuração ⭐ MVP

**User Story**: Como dono, quero um comando único para o Agendador que leia o `.env` de fora do repo e devolva um código de saída claro.

**Acceptance Criteria**:

1. CIC-01: WHEN `--ciclo` roda THEN o worker SHALL executar o mesmo `gerar()` que `--publicar --sim` (escrevendo no destino).
2. CIC-02: IF `--env-file` aponta para arquivo inexistente ou ilegível THEN o worker SHALL sair com código 2 e mensagem que nomeia `--env-file`.
3. CIC-03: WHEN uma variável está no ambiente e no `.env` THEN o valor do ambiente SHALL vencer.
4. CIC-04: IF a configuração obrigatória está ausente ou inválida THEN o worker SHALL sair com código 2; falha de execução do ciclo SHALL sair com 1; sucesso ou ciclo pulado SHALL sair com 0.
5. CIC-05: IF uma linha do `.env` está malformada THEN o worker SHALL sair com código 2 e SHALL NOT ecoar o conteúdo da linha no log nem no stderr (spec do dono: "tokens nunca em log").
6. CIC-06: The binário `besave-ciclo` (`#![windows_subsystem = "windows"]`, ajuste do dono de 01/10) SHALL executar o mesmo caminho do `--ciclo` (função da lib, sem lógica duplicada), SHALL NOT escrever em stdout nem stderr, e SHALL produzir a mesma linha `relatorio` que `besave-worker --ciclo` para a mesma fonte fake; argumento desconhecido SHALL sair com código 2.
7. CIC-07: WHERE `BESAVE_DESTINO_LOCAL` está definida, o ciclo SHALL publicar na pasta (layout do bucket) com KVS em memória, sem exigir `BESAVE_BUCKET`/`BESAVE_KVS_ARN`; `BESAVE_AGORA` SHALL fixar o relógio só nesse caso.
8. CIC-08: WHEN `BESAVE_MAPEAMENTO` não está definida THEN `--ciclo`, `besave-ciclo` e os modos manuais SHALL usar o `mapeamento.json` do contrato embutido no binário (`include_str!`), com qualquer pasta de trabalho; WHEN está definida THEN SHALL ler esse arquivo (override explícito). Bug da execução real do dono (02/10): o Agendador roda em `C:\besave\bin` e o padrão relativo `../../packages/contract/mapeamento.json` não resolvia (código 2).

**Independent Test**: binário com `--ciclo --env-file` e env controlada, sem rede.

### P1: Trava

**User Story**: Como dono, quero que dois ciclos nunca rodem juntos.

**Acceptance Criteria**:

1. TRV-01: WHILE outro processo segura a trava THEN um novo `--ciclo` SHALL sair com código 0 e log `INFO` "ciclo anterior em andamento".
2. TRV-02: WHEN a trava é adquirida THEN o arquivo SHALL conter o PID e o horário de início.
3. TRV-03: IF o arquivo de trava tem conteúdo mas nenhum processo segura a trava (órfão) THEN o ciclo SHALL tomá-la e logar `WARN`.
4. TRV-04: WHEN o ciclo termina THEN a trava SHALL ser solta e um novo ciclo SHALL conseguir adquiri-la.

### P1: Logs em arquivo

**User Story**: Como dono, quero um log por dia com o relatório de cada ciclo, sem encher o disco.

**Acceptance Criteria**:

1. LOG-01: The worker SHALL escrever em `BESAVE_LOG_DIR` (padrão `%LOCALAPPDATA%\besave\logs`) no arquivo `besave-worker.AAAA-MM-DD.log` do dia de Brasília.
2. LOG-02: WHEN o ciclo começa THEN arquivos `besave-worker.AAAA-MM-DD.log` com mais de 14 dias SHALL ser removidos e os demais SHALL ficar.
3. LOG-03: WHEN o ciclo termina com sucesso THEN o log SHALL ter uma linha `relatorio` com os campos em `chave=valor`.
4. LOG-04: WHEN o ciclo falha THEN o log SHALL ter uma linha `ERROR` com `fase=` e `variante=`.

### P1: Alerta no Telegram

**User Story**: Como dono, quero saber no celular quando um ciclo falha e quando volta, sem spam.

**Acceptance Criteria**:

1. ALR-01: WHEN um ciclo falha e a variante não foi alertada nas últimas 2 h THEN o worker SHALL enviar 1 mensagem que começa com `⚠️ Besave worker: falha no ciclo` e traz variante, fase, horário de Brasília (-03:00) e host.
2. ALR-02: WHEN a mesma variante falha de novo em menos de 2 h THEN o worker SHALL NOT enviar mensagem; WHEN passam 2 h THEN SHALL enviar de novo.
3. ALR-03: WHEN o primeiro ciclo bem-sucedido segue N falhas THEN o worker SHALL enviar `✅ Besave worker: recuperado após N falhas (desde HH:MM)` e zerar o estado; o sucesso seguinte SHALL NOT enviar.
4. ALR-04: The mensagem SHALL NOT conter `http`, o token, nem `C:\Users\`.
5. ALR-05: IF o envio ao Telegram falha THEN o ciclo SHALL terminar com o mesmo código de saída e logar `WARN`.
6. ALR-06: IF `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` estão ausentes THEN o alerta SHALL ficar desligado com `INFO`; IF só um deles existe THEN SHALL sair com código 2.
7. ALR-07: The token SHALL NOT aparecer no `Debug` da configuração.

### P2: Agendador e documentação

**User Story**: Como dono, quero registrar e remover a tarefa com um script e saber onde olhar.

**Acceptance Criteria**:

1. AGD-01: `scripts/registrar-tarefa.ps1` SHALL registrar ou atualizar "Besave Worker" apontando para `besave-ciclo.exe` (sem janela de console): a cada 5 min indefinidamente, gatilho 1 min após logon, `MultipleInstances IgnoreNew`, limite de 20 min, usuário atual em modo interativo (somente quando conectado), executável e `.env` por parâmetro, sem senha.
2. AGD-02: `scripts/remover-tarefa.ps1` SHALL remover a tarefa.
3. AGD-03: The README SHALL documentar BotFather, `chat_id`, variáveis novas, registrar/remover e local dos logs.

---

## Edge Cases

- WHEN `alerta.json` está corrompido THEN o worker SHALL logar `WARN` e tratar como estado vazio (ALR-01 segue valendo).
- WHEN duas variantes diferentes falham na mesma janela THEN cada uma SHALL ter seu envio (janela por variante).
- WHEN o envio do "recuperado" falha THEN o estado SHALL permanecer e o próximo sucesso SHALL tentar de novo.

Dimensions: dados sensíveis no log (CIC-05); estado persistido (ALR-01..03, edge de JSON corrompido); falha de dependência externa (ALR-05); concorrência (TRV-01..04); dados sensíveis (ALR-04, ALR-07); observabilidade (LOG-01..04); configuração (CIC-02..04, ALR-06). Auth e rate limit: N/A because o worker só envia mensagem ao próprio bot e o anti-spam limita o volume.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CIC-01 | P1: Modo ciclo | T6 | Done |
| CIC-02 | P1: Modo ciclo | T6 | Done |
| CIC-03 | P1: Modo ciclo | T6 | Done |
| CIC-04 | P1: Modo ciclo | T5, T6 | Done |
| CIC-05 | P1: Modo ciclo | T8 | Done |
| CIC-06 | P1: Modo ciclo | T9 | Done |
| CIC-07 | P1: Modo ciclo | T9 | Done |
| CIC-08 | P1: Modo ciclo | T11 | Done |
| TRV-01 | P1: Trava | T1, T6 | Done |
| TRV-02 | P1: Trava | T1 | Done |
| TRV-03 | P1: Trava | T1 | Done |
| TRV-04 | P1: Trava | T1 | Done |
| LOG-01 | P1: Logs | T2 | Done |
| LOG-02 | P1: Logs | T2 | Done |
| LOG-03 | P1: Logs | T5 | Done |
| LOG-04 | P1: Logs | T5 | Done |
| ALR-01 | P1: Alerta | T3, T5 | Done |
| ALR-02 | P1: Alerta | T3, T5 | Done |
| ALR-03 | P1: Alerta | T3, T5 | Done |
| ALR-04 | P1: Alerta | T3 | Done |
| ALR-05 | P1: Alerta | T3, T5 | Done |
| ALR-06 | P1: Alerta | T3, T6 | Done |
| ALR-07 | P1: Alerta | T3 | Done |
| AGD-01 | P2: Agendador | T7, T10 | Done |
| AGD-02 | P2: Agendador | T7 | Done |
| AGD-03 | P2: Agendador | T7, T10 | Done |

**Coverage:** 26 total, 26 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` verde, sem rede.
- [ ] Execução real do dono (bloqueia o merge): bot criado, `.env` preenchido, `registrar-tarefa.ps1`; em 30 min, 6 execuções com resultado 0 e 6 linhas `relatorio` no log do dia; `BESAVE_KVS_ARN` inválido → 1 alerta até corrigir; corrigido → "recuperado".
