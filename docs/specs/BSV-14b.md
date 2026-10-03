# BSV-14b · Worker: alerta de "nenhuma oferta nova" no Telegram (+ orçamento do card, AD-064)

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-14 (mergeado).
AD-032, AD-048, AD-049, AD-064 · Complementar: BSV-15 (vigia)

## Contexto
O worker e o vigia cobrem "ciclo falhou" e "site parou de ser atualizado". Nenhum dos dois percebe
quando o ciclo roda bem e publica um conjunto que não muda: robô parado, captura sem
`DS_URL_AFILIADO`, todas as novas rejeitadas. Em 02/10/2026 a oferta mais recente publicada tinha `dt`
de 23/09, com o worker saudável havia 9 dias e nenhum alerta.

## Objetivo
Quando um ciclo bem-sucedido publica um conjunto cujo maior `dt` é mais velho que o limiar, avisar no
Telegram na hora, lembrar a cada 24 h enquanto durar e mandar mensagem de volta quando chegar oferta nova.
De quebra, alinhar o teste de orçamento do card à AD-064.

## Entregáveis
1. `Relatorio` ganha `dt_mais_recente: Option<i64>` (maior `dt` entre os cards publicados, ativos ou
   expirados; `None` se o conjunto estiver vazio). A linha do relatório ganha `dt_max=` (ISO -03:00)
   e `horas_sem_novas=`.
2. `BESAVE_ALERTA_SEM_NOVAS_HORAS` (limiar): inteiro ≥ 0, padrão **24**; `0` desliga o alerta.
   `BESAVE_ALERTA_SEM_NOVAS_LEMBRETE_HORAS`: inteiro ≥ 0, padrão **24**; `0` = sem lembrete (só aviso e volta).
   Valor inválido em qualquer das duas → erro de configuração (código 2), como as demais variáveis.
3. Em `concluir()`, no ramo de sucesso, depois de `sucesso()`: avaliar `agora - dt_mais_recente` contra o
   limiar e chamar `Alertas::sem_novas(dt_mais_recente, publicadas, agora)` ou `Alertas::com_novas(agora)`.
4. Mensagens (horário de Brasília, -03:00 fixo; sem título, URL, token ou caminho):
   - `⚠️ Besave: nenhuma oferta nova há 26 h` / `última: 01/10 21:57` / `publicadas: 17326` / `host: …`
   - lembrete: mesmo texto, com as horas atualizadas
   - `✅ Besave: ofertas novas de novo (paradas desde 01/10 21:57)`
5. **Teste de orçamento do card alinhado à AD-064:** `tests/card.rs` (`orcamento_de_bytes_do_card`) passa a
   exigir média ≤ 200 B sobre as fixtures, sem teto por card, e ganha um caso com título de 200 caracteres
   acentuados que gera card acima de 220 B e é aceito. É mudança de critério por decisão (AD-064), não
   enfraquecimento de teste: citar a AD no commit. O gate continua sendo `ORCAMENTO_CHUNK` (chunk comprimido
   ≤ 60 KB), sem alteração.
6. README: variável nova e o que fazer quando o alerta chega (olhar robô e `rejeitadas` no log).

## Regras
1. **Estado independente do de falha.** `alerta.json` ganha um bloco `sem_novas` (`desde`, `ultimo_envio`)
   com `#[serde(default)]`: o arquivo antigo (BSV-14) carrega sem perder `falhas`/`envios`. Uma falha de
   ciclo não avalia nem mexe em `sem_novas` (não há relatório).
2. **Anti-spam próprio** (não usa a janela de 2 h da BSV-14): aviso imediato no primeiro ciclo que cruza o
   limiar; lembrete a cada `…_LEMBRETE_HORAS` contado do último envio entregue, enquanto durar; mensagem de
   volta no primeiro ciclo com oferta dentro do limiar, só se um aviso tiver sido entregue. Envio que falha
   → WARN, o estado não avança (tenta no próximo ciclo) e o código de saída não muda.
3. Conjunto vazio (`None`) conta como "sem novas", com `última: —`.
4. Só no modo `--ciclo` com Telegram configurado; `--dry-run` e `--publicar` só imprimem `dt_max` e
   `horas_sem_novas`.
5. Sem dependência nova.

## Fora de escopo
Checar isso no vigia (Lambda); limiar por área ou loja; contar no Oracle as ofertas capturadas e
rejeitadas por falta de URL de afiliado (útil, mas é outro ticket); resumo diário.

## Critério de aceite
- Relógio e Telegram falsos, limiar 24 h e lembrete 24 h: `dt_max` há 23 h → 0 mensagens; há 25 h → 1
  (aviso); ciclos seguintes até 23h55 depois do aviso → 0; 24 h depois do aviso, ainda parado → 1 (lembrete);
  48 h → mais 1; oferta com `dt` recente → 1 mensagem "de novo" com o horário certo; ciclo seguinte → 0.
- Lembrete `0` → só aviso e volta, nenhum lembrete em 72 h parado. Lembrete 6 → lembrete a cada 6 h.
- Aviso que falha no envio → próximo ciclo tenta de novo; o lembrete conta a partir do envio entregue.
- Limiar `0` → nunca avalia. `abc` ou `-1` em qualquer das duas variáveis → código 2 com mensagem clara.
- `orcamento_de_bytes_do_card`: média ≤ 200 B nas fixtures; card de 200 caracteres acentuados (> 220 B) aceito.
- `alerta.json` no formato da BSV-14 (sem `sem_novas`) carrega com `falhas` e `envios` preservados.
- Falha de ciclo durante um "sem novas" ativo → alerta de falha normal, `sem_novas` intacto; recuperação
  ainda parada → só "recuperado" (sem "de novo").
- Telegram falhando → WARN, estado não avança, mesmo código de saída.
- Mensagens sem `http`, token, `C:\Users\` (regex, como na BSV-14) e com `-03:00` coerente.
- Conjunto vazio → alerta com `última: —`.
- `cargo fmt --check`, `clippy -D warnings`, `cargo test` sem rede.
- **Real (dono):** com o estado de hoje (última oferta em 23/09), copiar o binário e rodar a tarefa → 1
  alerta no primeiro ciclo e nenhum outro nas próximas horas (lembrete só 24 h depois); depois que o robô voltar → "de novo". Print das duas
  mensagens sem token/chat_id; linha do relatório com `dt_max` colada.

## Definition of done
PR com README, linha real do relatório e prints, testes verdes; PR `develop → main` depois de copiar o
binário (AD-060).
