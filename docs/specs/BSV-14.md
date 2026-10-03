# BSV-14 · Worker: execução agendada, trava, logs e alerta de falha no Telegram

**Papel:** Backend Rust (+ script PowerShell) · **Pasta:** `apps/worker/` · **Depende de:** BSV-12c (mergeado).
MANIFEST.md §6 · Complementar: BSV-15 (vigia externo, infra)

## Contexto
O worker publica um ciclo completo em ~20–60 s (BSV-12c). Hoje roda à mão. Ele precisa rodar sozinho
a cada 5 minutos na máquina do dono (Windows, perto do Oracle XE local), sem sobreposição, com log
em arquivo e aviso imediato no Telegram quando um ciclo falha. Se a máquina desligar, quem avisa é o
vigia externo (BSV-15) — não este ticket.

## Objetivo
Um comando `besave-worker ciclo` adequado ao Agendador de Tarefas do Windows, mais o script que
registra a tarefa. Ciclo com sucesso: silencioso (só log). Ciclo com falha: log + mensagem no Telegram,
sem spam.

## Entregáveis
1. Modo `--ciclo` (ou subcomando `ciclo`): equivale a `--publicar --sim`, com:
   - `--env-file <caminho>`: carrega variáveis de um `.env` **fora do repo** antes de qualquer outra
     coisa (crate `dotenvy`). Variáveis já presentes no ambiente têm precedência.
   - **Trava**: arquivo de lock exclusivo (`BESAVE_LOCK`, padrão `%LOCALAPPDATA%\besave\worker.lock`).
     Se outro ciclo estiver rodando, sai com código 0 e log INFO "ciclo anterior em andamento" —
     não é falha. Lock com PID e horário; lock "órfão" (processo inexistente) é tomado com WARN.
     (Defesa adicional; o Agendador também será configurado para não sobrepor.)
   - **Logs em arquivo**: `BESAVE_LOG_DIR` (padrão `%LOCALAPPDATA%\besave\logs`), um arquivo por dia,
     retenção de 14 dias (`tracing-appender` com rotação diária + limpeza dos antigos no início do ciclo).
     O relatório final do ciclo vai para o log em uma linha estruturada (chave=valor), além da saída atual.
2. **Alerta de falha** via Bot API do Telegram (`sendMessage`, HTTPS, sem crate de bot — `reqwest` com
   `rustls` ou o cliente HTTP já presente no SDK; justificar). `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`
   vêm do `.env`. Mensagem curta: `⚠️ Besave worker: falha no ciclo` + tipo do erro (nome da variante,
   não o texto completo) + fase em que parou + horário de Brasília (offset fixo -03:00) + host.
   Nunca incluir URL de afiliado, credencial, token ou caminho com nome de usuário.
   - **Anti-spam**: estado em `%LOCALAPPDATA%\besave\alerta.json`. Mesma variante de erro → no máximo
     1 mensagem a cada 2 h. Primeiro ciclo bem-sucedido após falha → mensagem `✅ Besave worker: recuperado
     após N falhas (desde HH:MM)`.
   - Falha ao enviar para o Telegram → WARN no log; nunca muda o código de saída nem derruba o ciclo.
   - Sem `TELEGRAM_*` configurado → alerta desligado com INFO no log (ambiente de dev).
3. **Códigos de saída**: 0 sucesso ou ciclo pulado pela trava; 1 falha de ciclo; 2 erro de configuração
   (env ausente, `.env` ilegível) — para o Agendador registrar o resultado.
4. `apps/worker/scripts/registrar-tarefa.ps1`: registra (ou atualiza) a tarefa "Besave Worker" no Agendador:
   a cada 5 min, indefinidamente, iniciar também 1 min após o logon/boot; **não iniciar nova instância se
   já estiver rodando**; parar se passar de 20 min; rodar com o usuário atual, "somente quando conectado"
   (o Oracle e a pasta de imagens estão no perfil dele); caminho do executável **release** e do `.env`
   como parâmetros. Também `remover-tarefa.ps1`. Sem senha no script.
5. README: como gerar o bot (BotFather), obter o `chat_id`, variáveis novas, registrar/remover a tarefa,
   onde ficam os logs.

## Regras
- Nada de loop interno com `sleep`: o agendamento é do Windows (reinício, boot e logs de execução de graça).
- O ciclo continua sendo o mesmo `gerar()`; este ticket só embrulha execução, trava, log e alerta.
- Dependências permitidas: `dotenvy`, `tracing-appender`, `fs2` (ou equivalente para lock de arquivo),
  cliente HTTPS para o Telegram. Justificar cada uma no PR.
- Tokens nunca em log, nem em `Debug` de structs (campos sensíveis com `Debug` manual mascarado).

## Fora de escopo
Vigia externo / máquina desligada (BSV-15), resumo diário, comandos pelo Telegram, rodar fora do Windows.

## Critério de aceite
- `--env-file` inexistente → código 2, mensagem clara; variável de ambiente já definida vence o `.env`.
- Dois processos simultâneos: o segundo sai com 0 e log "ciclo anterior em andamento"; lock de PID morto é tomado.
- Falha injetada (fonte fake que erra) → código 1, log com fase, 1 chamada ao cliente Telegram (fake);
  segunda falha igual dentro de 2 h → 0 chamadas; sucesso seguinte → 1 chamada "recuperado".
- Mensagem do alerta não contém `http` de afiliado, token, `C:\Users\` (teste por regex).
- Cliente Telegram falhando → ciclo termina com o código que teria sem alerta; WARN no log.
- Rotação: arquivos de log com mais de 14 dias removidos no início do ciclo (teste com diretório temporário).
- `cargo fmt --check`, `clippy -D warnings`, `cargo test` sem rede.
- **Real (dono):** criar bot, preencher `.env`, `registrar-tarefa.ps1`; após 30 min, 6 execuções no
  histórico do Agendador com resultado 0 e 6 linhas de relatório no log do dia; renomear temporariamente
  `BESAVE_KVS_ARN` no `.env` para um ARN inválido → alerta no Telegram no próximo ciclo e só um até
  corrigir; corrigir → mensagem "recuperado".

## Definition of done
PR com README, scripts, prints do Agendador (histórico) e das duas mensagens do Telegram (com o
token e o chat_id fora do print), testes verdes.
