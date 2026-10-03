# BSV-14b — validation

**Verificado por:** sub-agente Verifier independente (autor ≠ verificador), 2026-10-03; re-verificação (ciclo 1 de correção) após o commit `fad9c39`.
**Veredito: PASS** — todos os critérios de aceite (exceto o "Real", **Pendente do dono**) passam e 13/13 mutantes morrem. Os gaps G1 e G2 do ciclo anterior foram fechados pelos testes `dt_mais_recente_inclui_expiradas` e `sem_configurar_nunca_avalia`.

Diff verificado: `git diff origin/develop..HEAD -- apps/worker` com `origin/develop` = `aac5bd3202cb07b7c7bdce08190f5749be555a14` e `HEAD` = `fad9c396fa31679c980092481b00a553aa3df92a` (branch rebaseada em `develop`; 12 arquivos, +800/−15).

## Gate (rodado pelo Verifier, apps/worker, sem rede, alvo compartilhado, `CARGO_BUILD_JOBS=2`)
`cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test` → saída 0.
`cargo test`: **305 passed, 0 failed, 3 ignored** (antes do ciclo: 303; +2 = os dois testes novos). Os 3 ignored são pré-existentes (`ciclo.rs`, `imagens.rs`, `paginas.rs`, um cada).

## Critério de aceite → evidência → resultado

| # | Critério (spec) | Evidência código | Evidência teste (asserção) | Resultado |
|---|---|---|---|---|
| 1 | 23 h → 0; 25 h → 1 aviso; até 23h55 depois → 0; +24 h → lembrete; +48 h → mais 1; oferta recente → 1 "de novo" com horário certo; ciclo seguinte → 0 | `src/alerta.rs:338-352` (limiar), `:355-379` (aviso/lembrete), `:382-396` (volta) | `tests/alerta_sem_novas.rs:91-133` (`assert_eq!(t.n(), 0/1/2/3/4)`, `"há 49 h"`, `"há 73 h"`, `"✅ Besave: ofertas novas de novo (paradas desde 24/09 09:40)"`); fronteiras `:359-385`, `:389-402` | PASS |
| 2 | Lembrete `0` → só aviso e volta (nada em 72 h); lembrete 6 → a cada 6 h | `src/alerta.rs:362` (`lembrete > 0 && agora - t >= lembrete`) | `:137-152` (n=1 em 73 ciclos, depois volta n=2); `:156-168` (n=4 em 0/6/12/18 h); `:406-418` (5h59→1, 6h00→2) | PASS |
| 3 | Aviso que falha → próximo ciclo tenta de novo; lembrete conta do envio entregue | `src/alerta.rs:369-377` (estado só avança em `Ok`) | `:172-196` (tentativas=2, depois n=1; `entregue+24h-1`→1; `entregue+24h`→2; WARN no log); `:200-215` (volta falha → retenta) | PASS |
| 4 | Limiar `0` → nunca avalia (e `Alertas::new` sem configurar nasce desligado) | `src/alerta.rs:339-342` | `:219-228` (`tentativas == 0`, com `Some` e `None`); `:422` `sem_configurar_nunca_avalia` | PASS |
| 5 | `abc`/`-1` em qualquer das duas variáveis → código 2 com mensagem clara | `src/alerta.rs:197-212` (`parse::<u64>` → erro com `var`); `src/ciclo.rs:231-233` (`Falha::config`) | `:232-260` (4 combinações, mensagem contém a variável); `tests/cli_ciclo.rs:514-532` (`status.code() == Some(2)` + log contém a variável) | PASS |
| 6 | `orcamento_de_bytes_do_card`: média ≤ 200 B; card com título de 200 caracteres acentuados (> 220 B) aceito | `src/conversao.rs:76,81-113` (sem teto por card; truncamento só em 200 caracteres) | `tests/card.rs:84-96` (`media <= 200.0`, teto por card removido); `tests/card.rs:100-112` (`titulo == "é"*200`, `bytes > 220`, `unwrap()`) | PASS |
| 7 | `alerta.json` no formato BSV-14 (sem `sem_novas`) carrega com `falhas` e `envios` preservados | `src/alerta.rs:230` (`#[serde(default)]`) | `:264-280` (`v["falhas"]==2`, `v["desde"]`, `v["envios"][…]`) | PASS |
| 8 | Falha de ciclo durante "sem novas" ativo → alerta de falha normal, `sem_novas` intacto; recuperação ainda parada → só "recuperado" | `src/alerta.rs:324-331` (recuperação preserva `sem_novas`) | `:285-309` (`n==2 "falha no ciclo"`, `n==3 "recuperado"`, depois `n==3`, `v["sem_novas"]==sn_antes["sem_novas"]`) | PASS |
| 9 | Telegram falhando → WARN, estado não avança, mesmo código de saída | `src/alerta.rs:377,394` (WARN); `src/execucao.rs:189-195` (`concluir` ignora retorno, `Codigo::Ok`) | `:172-196`, `:200-215`; `tests/execucao.rs` `ciclo_ok_parado_alerta_e_falha_nao_avalia` (`Codigo::Ok`) | PASS |
| 10 | Mensagens sem `http`, token, `C:\Users\` e com `-03:00` coerente | `src/alerta.rs:144-157` | `:313-332` (`!contains("http")`, `!contains(TOKEN)`, `!contains(r"C:\Users\")`, `[0].contains("-03:00")`); horário `última: 24/09 09:40` coerente com `DT`=12:40Z (`:107`) | PASS |
| 11 | Conjunto vazio → alerta com `última: —` | `src/alerta.rs:144-151` | `:336-344` (`"última: —"`, `"publicadas: 0"`) | PASS |
| 12 | `Relatorio.dt_mais_recente` (ativos ou expirados), linha com `dt_max=` e `horas_sem_novas=`; `--dry-run`/`--publicar` imprimem os dois | `src/geracao.rs:71-72,203`; `src/execucao.rs:125-153`; `src/main.rs:221,272-283` | `tests/execucao.rs` `relatorio_traz_dt_max_e_horas_sem_novas` (`dt_max=2026-09-24T08:40:00-03:00`, `horas_sem_novas=6`); `tests/dry_run.rs:459-474` (`ends_with("-03:00")`); `tests/geracao.rs:306-307` (`Some(1_790_253_660)`) ; `tests/geracao.rs:851` `dt_mais_recente_inclui_expiradas` (expirada com `dt` maior entra) | PASS |
| 13 | Integração: ciclo ok parado → aviso; falha não avalia | `src/execucao.rs:189-195` | `tests/execucao.rs` `ciclo_ok_parado_alerta_e_falha_nao_avalia` (`len()==3`, `starts_with("⚠️ Besave: nenhuma oferta nova há 31 h")`) | PASS |
| 14 | `fmt`, `clippy -D warnings`, `cargo test` sem rede | — | Gate acima: exit 0, 303/0/3 | PASS |
| 15 | **Real (dono)** | — | — | **Pendente do dono** |

### Spec-anchored (valores afirmados são os da spec, não da implementação)
- Horas 23/25/23h55/24 h/48 h, lembrete 0 e 6, `-03:00`, `última: —`, média 200 B e card > 220 B: asserções usam os números da spec.
- ⚠️ Spec-precision gap: a spec não define a fronteira exata do limiar (24 h exatas). O teste `limiar_estrito_em_torno_de_24_h` (`:359-385`) fixa "estritamente mais velho" (24 h exatas → 0); decisão do autor, coerente com "mais velho que o limiar". Não é erro, mas o dono deve confirmar.
- ⚠️ Divergência menor de texto: o código escreve `última: 24/09 09:40 (-03:00)` (`src/alerta.rs:150`); o exemplo da spec é `última: 01/10 21:57` sem o sufixo. A spec também exige "`-03:00` coerente" nas mensagens, então é compatível; o teste só afirma o prefixo `última: 24/09 09:40`.

## Sensor de discriminação (worktree temporária em `fad9c39`; árvore real intocada)
Cada mutante aplicado isoladamente em `git worktree` descartável, com `CARGO_TARGET_DIR` próprio, `cargo test --no-fail-fast` completo, revertido antes do próximo.

| Mutante | Resultado | Testes que falham |
|---|---|---|
| a1 `agora - d > limite` → `>=` | **MORTO** | `limiar_estrito_em_torno_de_24_h` |
| a2 `> limite + 3600` | **MORTO** | 10 em `alerta_sem_novas` (`aviso_lembretes_e_volta`, `limiar_estrito…`, `mensagens_limpas`, …) |
| b `agora - t >= lembrete` → `>` | **MORTO** | `lembrete_de_24_h_na_fronteira`, `lembrete_de_6_h_na_fronteira`, `lembrete_de_seis_horas`, `aviso_lembretes_e_volta`, `aviso_que_falha_…` |
| c `com_novas` envia sem aviso entregue | **MORTO** | `volta_sem_aviso_previo_nao_envia`, `aviso_lembretes_e_volta`, `limiar_estrito_…` |
| d remover `#[serde(default)]` de `sem_novas` | **MORTO** | `arquivo_antigo_preserva_falhas_e_envios` |
| e `sucesso()` salva `EstadoAlerta::default()` | **MORTO** | `falha_de_ciclo_nao_mexe_em_sem_novas` |
| f `Alertas::new` com limiar 24 em vez de 0 | **MORTO** (antes sobrevivia) | `sem_configurar_nunca_avalia` (`tests/alerta_sem_novas.rs:422`) |
| g remover `avaliar_novas` em `concluir` | **MORTO** | `ciclo_ok_parado_alerta_e_falha_nao_avalia` |
| h1 `-1` aceito como 0 | **MORTO** | `config_do_env`, `cli_ciclo::alerta_sem_novas_invalido_sai_com_2` |
| h2 inválido aceito como 0 | **MORTO** | `config_do_env`, `cli_ciclo::alerta_sem_novas_invalido_sai_com_2` |
| i `sem_novas` avança estado com envio falho | **MORTO** | `aviso_que_falha_tenta_de_novo_e_lembrete_conta_do_entregue` |
| j `dt_mais_recente` só sobre ativas | **MORTO** (antes sobrevivia) | `dt_mais_recente_inclui_expiradas` (`tests/geracao.rs:851`) |
| k teto de 220 B por card reintroduzido | **MORTO** | `card_com_titulo_longo_acentuado_e_aceito`, `titulo_de_200_nao_e_cortado`, 2 testes de truncamento em `card.rs`, `chunk_acima_do_orcamento_falha_sem_gravar_nada` |

**13 de 13 mortos; nenhum sobrevivente.**

## Gaps e decisões
- G1 (expiradas em `dt_mais_recente`) e G2 (default "desligado" de `Alertas::new`): **fechados** (mutantes j e f agora morrem).
- **G3 — decisão do dono, não falha:** fronteira exata do limiar (24 h exatas). A spec não define; o autor fixou "estritamente mais velho" e o teste `limiar_estrito_em_torno_de_24_h` trava isso.
- **G4 — decisão do dono, não falha:** o texto `última: 24/09 09:40 (-03:00)` leva o sufixo ` (-03:00)`, ausente do exemplo da spec; compatível com "`-03:00` coerente".
- **Real (dono): Pendente do dono** — rodar com o estado real (última oferta 23/09): 1 alerta no 1º ciclo, nenhum nas horas seguintes, lembrete só após 24 h, "de novo" quando o robô voltar; prints sem token/chat_id e linha do relatório com `dt_max`.

## Isolamento
Sensor rodou em worktree temporária fora do repo (removida, assim como o diretório de build). `git status --porcelain` da árvore real antes e depois: só ` M .specs/features/BSV-14b/validation.md`. Nenhum código de produção ou teste alterado; nenhum `git stash`, `commit`, `push` ou `cargo clean`.
