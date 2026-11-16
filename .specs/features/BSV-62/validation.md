# BSV-62 — Validação

## Validation: BSV-62 - PASS

**Result**: PASS (ciclo 2, faixa `d30a624..6b2d90d`). No ciclo 1 (`d30a624..466b592`) o veredito foi
FAIL com 4 de 42 mutantes sobreviventes (F3, F8, R01, R13); o commit `6b2d90d` (só testes + falha
injetada no `confirmar` do `FakeEnvio`) fechou as lacunas 1–3 e os quatro agora morrem. Lacunas 4–6
classificadas como não bloqueantes (ver "Ciclo 2" no fim). Continua bloqueando o merge a execução real
do dono (§6).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador.
- **Diff:** ciclo 1 `d30a624..466b592`, 6 commits: `dce7ab7` SQL, `b57187d` frases, `6785adc` layout
  Telegram, `bdc4bf2` legenda WhatsApp, `824bb2c` espelho, `466b592` contrato/README; ciclo 2
  `d30a624..6b2d90d` (+ `6b2d90d` testes).
- **Referência:** `docs/specs/BSV-62.md` (spec do dono); `.specs/features/BSV-62/spec.md` (EARS do autor).
- **Data:** 2026-11-16.
- **Tarefas:** T1–T6 marcadas ✅ em `.specs/features/BSV-62/tasks.md:24-64`.

---

## 1. Checagem ancorada na spec

### 1.1 Critérios de aceite da spec do dono

| Critério (spec do dono) | Resultado definido | Código | Teste (`file:line` + asserção) | Resultado |
|---|---|---|---|---|
| Espelho: Telegram confirma → 1 linha `P` com legenda, `ID_ENVIO_TELEGRAM`, `DS_AREA_SLUG` `meu-lar` | 1 linha por post; campos exatos | `apps/worker/src/envio/rodada.rs:214-216`, `:341-365`; `apps/worker/src/envio/oracle.rs:90` | `apps/worker/tests/envio_espelho.rs:88` `fila.len() == 2`; `:94-104` `assert_eq!(l, &FilaWhatsapp{canal: 2, id_envio_telegram: e.id_envio, legenda: legenda_whatsapp(..), area_slug: "meu-lar", ..})`; `:125-130` SQL inteiro com `'P'` e `SQ_ENVIO_WHATSAPP.NEXTVAL` | ✅ PASS (o `caiu` usado é sempre `false` no teste — lacuna 3) |
| Telegram falha → 0 linhas | 0 | `apps/worker/src/envio/rodada.rs:218-229` | `apps/worker/tests/envio_espelho.rs:143-144` (400) e `:148-150` (429) `fila_whatsapp().is_empty()` | ✅ PASS |
| Sem a variável → 0 linhas | 0 | `apps/worker/src/envio/rodada.rs:214`; `apps/worker/src/envio/binario.rs:110-122` | `apps/worker/tests/envio_espelho.rs:159-162`; `:168-173` (`None`, `""`, `"whatsapp"` → `None`) | ✅ PASS |
| Falha ao inserir → WARN, código 0, `ENVIO_TELEGRAM` confirmado intacto | `Ok`, `message_id` gravado, WARN com `id` e motivo | `apps/worker/src/envio/rodada.rs:360-363` | `apps/worker/tests/envio_espelho.rs:184-191` (`rodar(..).unwrap()`, `enviados == 2`, `espelho_falhas == 2`, todos `message_id.is_some()`); `apps/worker/tests/envio_espelho_log.rs:89-91` WARN com `id=41` e o motivo | ✅ PASS |
| Mesma oferta duas vezes → 1 linha, sem erro | 1 linha; sem WARN | `apps/worker/src/envio/rodada.rs:359`; `apps/worker/src/envio/oracle.rs:335` (ORA-00001 → `Ok(false)`) | `apps/worker/tests/envio_espelho.rs:206-208`, `:216-219`; `apps/worker/tests/envio_espelho_log.rs:105` `w.is_empty()` | ✅ PASS no fake; o ramo ORA-00001 do Oracle real não é testável aqui (lacuna 5) |
| Layout Telegram: linha em branco depois do título e antes da frase; frase como última linha | legenda inteira | `apps/worker/src/envio/legenda.rs:224-236` | `apps/worker/tests/envio_legenda.rs:48-58` (`assert_eq!` inteiro) | ✅ PASS |
| Layout: com e sem `pd`; 29% sem selo e 45%; recorrência; 1 e 3 cupons; destaque; `caiu`; sem opcionais | legendas inteiras | `apps/worker/src/envio/legenda.rs:106-172` | Telegram: `apps/worker/tests/envio_legenda.rs:48` (45%), `:73-86` (completa, `split('\n')`), `:100-110` (sem `pd`/sem opcionais), `:123-133` (29%), `:253-264` (3 cupons). WhatsApp: `apps/worker/tests/envio_legenda_whatsapp.rs:44-54`, `:67-80`, `:92-102`, `:114-124`, `:134-145` | ✅ PASS |
| Exemplo do dono 51217 nos dois canais | legenda inteira | idem | `apps/worker/tests/envio_legenda.rs:288-299`; `apps/worker/tests/envio_legenda_whatsapp.rs:165-176` | ✅ PASS — mas ícone e frase vêm de `emb.escolher(51217)`, não de valor fixo (lacuna 1) |
| Frases: mesma oferta → mesmo par nos dois canais e em duas execuções | igualdade | `apps/worker/src/envio/frases.rs:126-130` | `apps/worker/tests/envio_frases.rs:70-73`; `apps/worker/tests/envio_legenda_whatsapp.rs:178` (`tg.ends_with(..{icone} <i>{frase}</i>)`), `:180-183` (nova carga) | ✅ PASS |
| 1.000 ids: todas as frases e ícones, nenhuma > 15%, vizinhos fora da ordem (`id mod n` falha) | 12 e 11 distintos; ≤ 150; seguidos < 200 | `apps/worker/src/envio/frases.rs:42-52` | `apps/worker/tests/envio_frases.rs:93-102`, `:118-119`; mutante F1 morto | ✅ PASS |
| `🏃‍♂️` sai inteiro (mutante por caractere falha) | item de 4 pontos de código | `apps/worker/src/envio/frases.rs:59-70` | `apps/worker/tests/envio_frases.rs:126-133` (`chars().count() == 4`, todo ícone ∈ lista); mutante F2 morto | ✅ PASS |
| Arquivo válido de 2 frases → só essas 2 | `["Primeira frase.", "Segunda frase."]` | `apps/worker/src/envio/frases.rs:106-123` | `apps/worker/tests/envio_frases.rs:147-148` | ✅ PASS |
| Arquivo inválido ou lista vazia → WARN e embutidas | `== embutidas()`; 1 WARN | `apps/worker/src/envio/frases.rs:116-121` | `apps/worker/tests/envio_frases.rs:154-172` (JSON quebrado, sem `icones`, listas vazias, só frases vazias, arquivo ausente); `apps/worker/tests/envio_frases_log.rs:51-53` (1 WARN com `BESAVE_FRASES_CANAL` e o nome do arquivo) | ✅ PASS |
| Frase com `<&>` escapada no Telegram; `*` removido no WhatsApp | `&lt;já&gt; &amp;`; sem `*` | `apps/worker/src/envio/legenda.rs:226`, `:242` | `apps/worker/tests/envio_legenda.rs:161-164`; `apps/worker/tests/envio_legenda_whatsapp.rs:196-208` (`🚨 _Corra, é agora!_`) | ✅ PASS |
| Limite: título longo + 3 cupons → cupons saem, título cortado, frase inteira, ≤ 1024 UTF-16 (Telegram) e ≤ 1024 car. e 4000 bytes (WhatsApp); mutante que corta a frase e o que só mede caracteres falham | idem | `apps/worker/src/envio/legenda.rs:69-71`, `:186-220` | `apps/worker/tests/envio_legenda.rs:383-391`; `apps/worker/tests/envio_legenda_whatsapp.rs:223-240`, `:247-253` (1000 vs 1001 emojis de 4 bytes); mutantes L14, L15, L16a–c, L17 mortos | ✅ PASS |
| Encerrada: linha em branco depois do título, sem frase e sem link | legenda inteira | `apps/worker/src/envio/legenda.rs:257-267` | `apps/worker/tests/envio_legenda.rs:228-238` (`assert_eq!` inteiro, sem `href`, nenhuma frase embutida) | ✅ PASS |
| Isolamento: legenda do aviso não muda; só testes de layout BSV-40/50 atualizados | `aviso.rs` intocado | `apps/worker/src/envio/aviso.rs` fora do diff | `apps/worker/tests/envio_aviso.rs` só ganhou `frases`/`espelho_whatsapp` no `Contexto` (§4) e passa | ✅ PASS |
| Gates | verdes | — | §2 | ✅ PASS |
| Real (dono) | SQL, `--sim` na inst2, 2 h de espelho, troca de frase | — | não executável aqui | **pendente — bloqueia o merge** (§6) |

### 1.2 Requisitos EARS do autor

| ID | Código | Teste (`file:line` + asserção) | Resultado |
|---|---|---|---|
| SQL-01 | `apps/worker/sql/bsv-62.sql:9-14` (checagem 0), `:19-26`, `:33-52`, `:61-64` | `apps/worker/tests/envio_whatsapp_sql.rs:29-40` (INSERTs exatos, 40/8/22), `:46-58` (colunas e tipos), `:66-85` (sequence, PK, UK, 1 FK, sem FK de OFERTA, CHECK, índice), `:90-96` (checagem antes do 1º INSERT), `:102-118` (GRANTs comentados, sem link/`+55`/token/8+ dígitos/IP) | ✅ PASS |
| FRA-01 | `apps/worker/src/envio/frases.rs:42-52`, `:126-130` | `apps/worker/tests/envio_frases.rs:70-73` (determinismo) | ⚠️ PASS parcial: a fórmula exata (`SHA-256`, `"{id}:{sal}"`, sal `frase`/`icone`, big-endian) não é afirmada — mutantes F3 e F8 sobrevivem (lacuna 1) |
| FRA-02 | idem | `apps/worker/tests/envio_frases.rs:93-119` | ✅ PASS |
| FRA-03 | `apps/worker/src/envio/frases.rs:59-70` | `apps/worker/tests/envio_frases.rs:59-63` (lista igual à spec), `:126-133` | ✅ PASS |
| FRA-04 | `apps/worker/src/envio/frases.rs:106-123`; `apps/worker/src/envio/binario.rs:365-366` | `apps/worker/tests/envio_frases.rs:138-172`; `apps/worker/tests/envio_frases_log.rs:51-59` | ✅ PASS |
| FRA-05 | `apps/worker/src/envio/frases.rs:75-87` | `apps/worker/tests/envio_frases.rs:177-187` (120 `é` fica, 121 sai, vazia sai, trim); `apps/worker/tests/envio_frases_log.rs:68` (2 WARNs) | ✅ PASS |
| LAY-01 | `apps/worker/src/envio/legenda.rs:224-236` | §1.1 Layout | ✅ PASS |
| LAY-02 | `apps/worker/src/envio/legenda.rs:226` | `apps/worker/tests/envio_legenda.rs:161-164` | ✅ PASS |
| WA-01 | `apps/worker/src/envio/legenda.rs:58-61`, `:240-253` | `apps/worker/tests/envio_legenda_whatsapp.rs:44-183` | ✅ PASS |
| WA-02 | `apps/worker/src/envio/legenda.rs:75-84` | `apps/worker/tests/envio_legenda_whatsapp.rs:196-208` (cada marcador e espaço duplo; mutantes L02–L06 mortos) | ✅ PASS |
| LIM-01 | `apps/worker/src/envio/legenda.rs:206-220` | `apps/worker/tests/envio_legenda.rs:304-368`, `:373-391` | ✅ PASS |
| LIM-02 | `apps/worker/src/envio/legenda.rs:69-71` | `apps/worker/tests/envio_legenda_whatsapp.rs:223-224`, `:247-253`, `:265` | ✅ PASS |
| ENC-01 | `apps/worker/src/envio/legenda.rs:257-267` | `apps/worker/tests/envio_legenda.rs:228-238` | ✅ PASS |
| ISO-01 | aviso fora do diff | `apps/worker/tests/envio_aviso.rs` (asserções inalteradas, verdes) | ✅ PASS |
| ESP-01 | `apps/worker/src/envio/rodada.rs:341-365` | `apps/worker/tests/envio_espelho.rs:83-115` | ✅ PASS (ordem depois do `confirmar` não discriminada — lacuna 2; `caiu` — lacuna 3) |
| ESP-02 | `apps/worker/src/envio/rodada.rs:214`, `:218-229` | `apps/worker/tests/envio_espelho.rs:135-174` | ✅ PASS |
| ESP-03 | `apps/worker/src/envio/rodada.rs:360-363` | `apps/worker/tests/envio_espelho.rs:178-191`; `apps/worker/tests/envio_espelho_log.rs:89-91` | ✅ PASS |
| ESP-04 | `apps/worker/src/envio/rodada.rs:359`; `apps/worker/src/envio/oracle.rs:335` | `apps/worker/tests/envio_espelho.rs:196-219`; `apps/worker/tests/envio_espelho_log.rs:105` | ✅ PASS (fake) |
| ESP-05 | espelho só no laço das candidatas (`apps/worker/src/envio/rodada.rs:214-216`) | `apps/worker/tests/envio_espelho.rs:224-258` (aviso enviado, 1 edição, fila vazia); mutantes R08/R09 mortos | ✅ PASS |
| CON-01 | `docs/CONTRATO.md:7-8`, `:284-345`; `packages/contract/package.json` 1.7.0 | `apps/worker/tests/envio_modelo.rs:38-39` `versao_contrato() == "1.7.0"`; `npm run validate` OK | ✅ PASS |
| DOC-01 | `apps/worker/README.md:601-602`, `:611-645` | leitura (variáveis, troca sem recompilar, SQL, pausar) | ✅ PASS |

## 2. Gates

| Gate | Comando | Resultado |
|---|---|---|
| fmt | `cargo fmt --check` (apps/worker) | exit 0 |
| clippy | `cargo clippy --all-targets -- -D warnings` | exit 0, sem aviso |
| testes | `cargo test --no-fail-fast` (`CARGO_TARGET_DIR` compartilhado, `CARGO_BUILD_JOBS=2`) | **618 passaram, 0 falharam, 3 ignorados** (nenhum `#[ignore]` no diff) |
| contrato | `cd packages/contract && npm ci && npm run validate` | exit 0, `contrato OK` |
| CI `worker-arm64` | não executável localmente | **pendente** (lição 12: conferir na PR) |

O site lê a versão do contrato só pelo major (`apps/site/src/lib/dados/sincronizador.ts:10`, `:132`);
`apps/site/src/lib/dados/tipos.test.ts:35` lê a fixture `manifest-ok.json` (continua `1.6.0`), então o
job do site não é afetado.

## 3. Sensor de discriminação

Método (sem `git stash`, nada fora do worktree): backup do arquivo-alvo em
`.specs/features/BSV-62/_mutantes/`, mutação no arquivo real, `cargo test --no-fail-fast --test …` só
com os testes relevantes, restauração do backup. Lotes de 8–10. `git status --porcelain` conferido depois
de cada lote: igual à linha de base (vazia, mais a pasta `_mutantes/`); a pasta foi apagada no fim.

Testes por lote: F = `envio_frases envio_frases_log envio_legenda envio_legenda_whatsapp envio_espelho
envio_espelho_log`; L = `envio_legenda envio_legenda_whatsapp envio_espelho envio_aviso`; R/B =
`envio_espelho envio_espelho_log envio_aviso envio_execucao`.

| # | Mutante | Onde | Resultado | Teste que matou |
|---|---|---|---|---|
| F1 | escolha por `id mod n` (frase e ícone) | `frases.rs:51` | morto | `mil_ids_espalham` |
| F2 | ícones separados por caractere (`concat().chars()`) | `frases.rs:59-62` | morto | `embutidas_sao_as_da_spec`, `corredor_sai_inteiro`, `mil_ids_espalham` |
| F3 | **mesmo sal** (`"frase"` também no ícone) | `frases.rs:127` | **sobreviveu** | — |
| F4 | `MAX_FRASE` 121 | `frases.rs:11` | morto | `warn_no_arquivo_invalido_e_na_frase_descartada` |
| F5 | `n <= MAX_FRASE` → `<` | `frases.rs:86` | morto | `frase_longa_ou_vazia_descartada`, `frase_nunca_cortada`, `limite_com_frase_inteira` |
| F6 | frase vazia aceita (`n <= MAX_FRASE`) | `frases.rs:86` | morto | `arquivo_ruim_usa_embutidas`, `frase_longa_ou_vazia_descartada` |
| F7 | arquivo inválido devolve erro (derruba) | `frases.rs:120` | morto | `arquivo_ruim_usa_embutidas`, `warn_no_arquivo_invalido_e_na_frase_descartada` |
| F8 | hash little-endian (CONTRATO §11.2 diz big-endian) | `frases.rs:46` | **sobreviveu** | — |
| L01 | `legenda_whatsapp` com `utm_source=telegram` | `legenda.rs:60` | morto | `post_confirmado_vai_para_a_fila`, `basica`, `completa`, … |
| L02 | limpeza não remove `*` | `legenda.rs:78` | morto | `marcadores_removidos` |
| L03 | não remove `_` | `legenda.rs:78` | morto | `marcadores_removidos` |
| L04 | não remove `~` | `legenda.rs:78` | morto | `marcadores_removidos` |
| L05 | não remove `` ` `` | `legenda.rs:78` | morto | `marcadores_removidos` |
| L06 | não junta espaços | `legenda.rs:81` | morto | `marcadores_removidos` |
| L07 | Telegram sem linha em branco depois do título | `legenda.rs:229` | morto | `legenda_basica`, `legenda_completa`, `exemplo_do_dono_51217`, … |
| L08 | WhatsApp sem linha em branco depois do título | `legenda.rs:246` | morto | `basica`, `completa`, `marcadores_removidos`, … |
| L09 | Telegram sem linha em branco antes da frase | `legenda.rs:232` | morto | `legenda_basica`, `frase_escapada`, `frase_nunca_cortada`, … |
| L10 | WhatsApp sem linha em branco antes da frase | `legenda.rs:249` | morto | `basica`, `limite_com_frase_inteira`, `titulo_de_emojis_cabe`, … |
| L11 | `legenda_encerrada` sem a linha em branco | `legenda.rs:260` | morto | `legenda_encerrada_riscada_sem_link` |
| L12 | `legenda_encerrada` com a frase | `legenda.rs:265` | morto | `legenda_encerrada_riscada_sem_link` |
| L13 | frase sem `escapar` no Telegram | `legenda.rs:226` | morto | `frase_escapada` |
| L14 | `cabe_whatsapp` só mede caracteres | `legenda.rs:70` | morto | `limite_em_bytes` |
| L15 | `cabe_whatsapp` só mede bytes | `legenda.rs:70` | morto | `limite_com_frase_inteira`, `limite_em_bytes` |
| L16a | frase cortada (20 car.) no Telegram | `legenda.rs:226` | morto | `frase_nunca_cortada`, `legenda_basica`, … |
| L16b | frase cortada no WhatsApp | `legenda.rs:242` | morto | `limite_com_frase_inteira`, `basica`, … |
| L16c | frase omitida quando é preciso cortar o título (`caber_em` tira o último bloco) | `legenda.rs:219` | morto | `frase_nunca_cortada`, `limite_com_frase_inteira`, … |
| L17 | frase dentro do título cortado (Telegram) | `legenda.rs:227`, `:232` | morto | `frase_nunca_cortada`, `cupons_do_fim_saem_antes_do_titulo`, … |
| R01 | **espelho antes do `confirmar`** | `rodada.rs:208-216` | **sobreviveu** | — |
| R02 | espelho também quando o Telegram falha | `rodada.rs:218` | morto | `falha_do_telegram_nao_enfileira` |
| R03 | erro da fila propagado (`?`) | `rodada.rs:215`, `:360-363` | morto | `falha_na_fila_nao_desfaz_o_telegram`, `warn_na_falha_e_silencio_na_duplicata` |
| R04 | duplicata conta como falha e avisa | `rodada.rs:359` | morto | `duplicata_ignorada`, `warn_na_falha_e_silencio_na_duplicata` |
| R05 | `DS_AREA_SLUG` = `format!("{:?}", area)` | `rodada.rs:354` | morto | `post_confirmado_vai_para_a_fila` |
| R06 | slug em maiúsculas | `rodada.rs:354` | morto | `post_confirmado_vai_para_a_fila` |
| R07 | `id_envio_telegram` = `message_id` | `rodada.rs:215` | morto | `post_confirmado_vai_para_a_fila` |
| R08 | espelho na edição "Oferta encerrada" | `rodada.rs:243` | morto | `aviso_e_encerrada_nao_espelham` |
| R09 | espelho no aviso | `rodada.rs:315` | morto | `aviso_e_encerrada_nao_espelham` |
| R10 | `espelhados` não contado | `rodada.rs:358` | morto | `post_confirmado_vai_para_a_fila` |
| R11 | `dt_fila` = 0 | `rodada.rs:355` | morto | `post_confirmado_vai_para_a_fila` |
| R12 | fila recebe a legenda do Telegram | `rodada.rs:353` | morto | `post_confirmado_vai_para_a_fila` |
| R13 | **fila com `caiu = false` fixo** | `rodada.rs:353` | **sobreviveu** | — |
| B01 | `espelho_do_env` inválida → canal 0 | `binario.rs:119` | morto | `variavel_do_espelho`, `warn_na_falha_e_silencio_na_duplicata` |
| B02 | `espelho_do_env` inválida → erro (pânico) | `binario.rs:119` | morto | `variavel_do_espelho`, `warn_na_falha_e_silencio_na_duplicata` |

**Total: 42 mutantes, 38 mortos, 4 sobreviventes (F3, F8, R01, R13).** Nenhum equivalente: os quatro mudam
o resultado observável (F3/F8: o par escolhido para cada id; R01: linha `P` gravada com o post ainda não
confirmado no Oracle; R13: legenda do WhatsApp sem "📉 Caiu mais o preço!!!" quando o Telegram tem).

## 4. Isolamento (testes alterados)

`git diff d30a624..HEAD -- apps/worker/tests/`: nenhum teste apagado, ignorado ou afrouxado.

| Arquivo | Mudança | Por quê |
|---|---|---|
| `tests/envio_legenda.rs` | `legenda_basica`, `legenda_completa`, `sem_preco_de`, `selo_a_partir_do_parametro`, `texto_escapado`, `titulo_longo_cortado`, `titulo_que_cabe_fica_inteiro`, `legenda_encerrada_riscada_sem_link`, `varios_cupons_na_mesma_linha`, `cupons_do_fim_saem_antes_do_titulo`: novo argumento `&Frases` e as asserções de layout passam ao layout da BSV-62 (linha em branco depois do título, linha em branco + frase no fim). Novos: `frase_escapada`, `exemplo_do_dono_51217`, `frase_nunca_cortada`. | Mudança de requisito (Saída 4). Várias asserções ficaram **mais fortes**: `sem_preco_de`, `selo_a_partir_do_parametro` e `varios_cupons_na_mesma_linha` passaram de `contains` para `assert_eq!` da legenda inteira (o `!contains("Cupom:")` removido em `varios_cupons…` está coberto pela igualdade inteira). `reais_com_milhar` intocado. |
| `tests/envio_aviso.rs`, `envio_execucao.rs`, `envio_http.rs`, `envio_site.rs` | só `frases` e `espelho_whatsapp: None` no `Contexto` (+ `use`/`static FRASES`) | Campos novos de `Contexto`; nenhuma asserção mudou. |
| `tests/envio_modelo.rs` | `contrato_na_versao_1_6_0` → `contrato_na_versao_1_7_0`, valor `1.6.0` → `1.7.0` | Versão do contrato (Saída 6). |
| `tests/worker_env_vps.rs` | 2 entradas novas em `OPCIONAIS` (`BESAVE_ENVIO_ESPELHO_WHATSAPP`, `BESAVE_FRASES_CANAL`) | Variáveis novas lidas em `src/`. |
| Novos | `envio_frases.rs`, `envio_frases_log.rs`, `envio_legenda_whatsapp.rs`, `envio_espelho.rs`, `envio_espelho_log.rs`, `envio_whatsapp_sql.rs` | — |

`apps/worker/frases_canal.json:3-17`: 11 ícones e 12 frases, idênticos aos da spec do dono (conferido
também pelo teste `apps/worker/tests/envio_frases.rs:59-63`, que compara com as listas transcritas da spec).

Regra 2 (sem dependência nova): `Cargo.toml`/`Cargo.lock` fora do diff; `sha2` já existia.

## 5. Segurança (regra 11)

Varredura de `git diff d30a624..HEAD` (linhas adicionadas) por caminho de usuário, token de bot, IP,
`chat.whatsapp.com`, `wa.me`, `+55`, `chat_id =`, ARN e host interno: 0 ocorrências reais (só o nome do
canal público em `sql/bsv-62.sql:20` e a lista de proibidos do próprio teste
`apps/worker/tests/envio_whatsapp_sql.rs:105`). O README cita caminhos genéricos (`/srv/besave/…`,
`C:\besave\…`), sem nome de usuário.

## 6. Bloqueia o merge (execução real do dono)

1. Rodar `sql/bsv-62.sql` (checagem 0: `AL32UTF8`, canal 2 e fila inexistentes).
2. `besave-envio --sim` com o binário da branch na inst2: layout novo com frase e ícone, e a prévia do WhatsApp.
3. 2 h de envio: posts com o layout novo, frases variando, cada post confirmado com 1 linha `P` certa
   (`SELECT` redigido no PR); conferir também que a duplicata (ORA-00001) cai em `Ok(false)` sem WARN.
4. Trocar uma frase no arquivo de `BESAVE_FRASES_CANAL`: a próxima execução usa o texto novo.
5. Job `worker-arm64` verde na PR (lição 12).

## 7. Lacunas ranqueadas

1. **Escolha por hash não fixada (mutantes F3 e F8)** — FRA-01, Saída 3 ("o resultado é testável");
   `apps/worker/src/envio/frases.rs:42-52`, `:127-128`. Todos os testes comparam `escolher(id)` consigo
   mesmo ou com `emb.escolher(51217)`; trocar o sal do ícone, a ordem dos bytes ou o formato
   `"{id}:{sal}"` muda a frase de toda oferta sem quebrar nada. Sugestão: em `tests/envio_frases.rs`,
   afirmar valores calculados fora do código — por exemplo `escolher(51217) == ("🏃‍♂️", "Garanta agora,
   antes que o preço mude!")` (índices 6 e 3; conferido com `hashlib.sha256` em Python) e
   `escolher(5412) == ("🏃‍♂️", "Não deixe para depois, pode acabar!")` (6 e 5), mais um id cujo índice
   de ícone difira de `h(id,"frase") mod 11`, e usar esses valores fixos nos testes do exemplo 51217.
2. **Ordem espelho → depois do `confirmar` não discriminada (mutante R01)** — Saída 2 ("depois de
   confirmar … `NR_MESSAGE_ID` gravado"), ESP-01; `apps/worker/src/envio/rodada.rs:208-216`. O
   `FakeEnvio` não sabe falhar no `confirmar`, então espelhar antes dele dá o mesmo resultado nos testes.
   Sugestão: falha injetada `falhar_confirmacao` no fake (`apps/worker/src/envio/fonte.rs`) e teste em
   `tests/envio_espelho.rs`: Telegram ok + `confirmar` falha → `rodar` devolve erro e `fila_whatsapp()`
   vazia.
3. **`caiu` do espelho não testado (mutante R13)** — Saída 5 ("o mesmo `caiu` do post do Telegram");
   `apps/worker/src/envio/rodada.rs:353`. `post_confirmado_vai_para_a_fila`
   (`apps/worker/tests/envio_espelho.rs:100`) compara com `legenda_whatsapp(&o, false, …)` e só tem
   ofertas sem envio anterior. Sugestão: oferta repetida com queda de preço (como os testes de repetição
   da BSV-40) e asserção de que a linha da fila contém `📉 *Caiu mais o preço!!!*`.
4. **Spec do autor vs. dono, cupom com `_` no WhatsApp**: `BE_SAVE` vira `BESAVE`
   (`apps/worker/tests/envio_legenda_whatsapp.rs:192`, `:203`), o código copiado do WhatsApp fica
   diferente do real. Segue a letra da Saída 5; o autor marcou para o dono decidir no PR. Não é defeito.
5. **ORA-00001 → `Ok(false)` só pelo fake** (`apps/worker/src/envio/oracle.rs:335`): o fake reimplementa a
   unicidade; o ramo real fica para o teste real (§6 item 3). Baixa.
6. **`docs/MANIFEST.md:49` e `packages/contract/fixtures/manifest-ok.json:2` seguem com `"contrato":
   "1.6.0"`** de exemplo, enquanto o worker passará a gravar `1.7.0`. Não quebra nada (o site compara só
   o major); fora do escopo literal da spec (§11 + `package.json`). Cosmético; na BSV-50 foram
   atualizados junto.

## 8. Qualidade do código

| Check | Ok? |
|---|---|
| Só o pedido; sem dependência nova | sim |
| Padrões existentes (trait + fake, `thiserror`, sem `unwrap` fora de teste, `tracing`) | sim |
| Só arquivos do escopo (`apps/worker/`, `docs/CONTRATO.md`, `packages/contract/package*.json`, `.specs/`) | sim |
| Testes mapeiam para critérios e comparam a legenda inteira (lição 14) | sim |
| Asserções enfraquecidas em testes existentes | não (as de layout ficaram mais fortes) |

## 9. Saída do `validate_state.py` (ciclo 1)

```
$ python .claude/skills/tlc-spec-driven/scripts/validate_state.py BSV-62 --root .
  ERROR BSV-62: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)

validate_state: 1 error(s) across [BSV-62]
exit=1
```

Esperado com o veredito FAIL. Depois da limpeza, `git status --porcelain` só lista este `validation.md`.

---

## Ciclo 2 (faixa `d30a624..6b2d90d`)

Commit `6b2d90d` `test(worker): valores fixos do hash, confirmação e caiu na fila (BSV-62)`: testes em
`apps/worker/tests/{envio_frases,envio_espelho,envio_legenda,envio_legenda_whatsapp}.rs`, a tarefa T7 em
`.specs/features/BSV-62/tasks.md` e, em `apps/worker/src/envio/fonte.rs:138`, `:220-222`, `:332-334`, só o
`FakeEnvio` (falha injetada `falhar_confirmacao`). Nenhuma mudança no código de produção do envio
(`rodada.rs`, `legenda.rs`, `frases.rs`, `oracle.rs`, `binario.rs` intocados); nenhuma asserção afrouxada
(nos dois testes do exemplo 51217, `emb.escolher(51217)` virou valor fixo, o que é mais forte).

### Correções conferidas

| Lacuna | Evidência | Valor da spec |
|---|---|---|
| 1 — escolha por hash fixada (F3, F8) | `apps/worker/tests/envio_frases.rs:79-91` `assert_eq!(f.escolher(id), (icone, frase))` para os ids 51217, 5412, 1, 2 e 3; `apps/worker/tests/envio_legenda.rs:278` e `apps/worker/tests/envio_legenda_whatsapp.rs:154-155` com o par fixo de 51217 | `h` = 8 primeiros bytes big-endian do SHA-256 de `"{id}:{sal}"`, sal `frase`/`icone`, `mod 12`/`mod 11` (Saída 3, CONTRATO §11.2). **Recalculado pelo Verifier com `hashlib` (Python, sem o código Rust):** 51217 → ícone 6 `🏃‍♂️`, frase 3 "Garanta agora, antes que o preço mude!"; 5412 → 6, 5 "Não deixe para depois, pode acabar!"; 1 → 8 `🏃`, 11 "Clique e garanta o seu antes que o preço mude!"; 2 → 2 `☝️`, 3 "Garanta agora, …"; 3 → 6, 7 "Não fique de fora, a promoção já está no fim!" — os 5 batem. Com sal igual (F3) o ícone de 51217 seria o índice 8; com little-endian (F8), 10/6: os dois divergem. |
| 2 — espelho só depois do `confirmar` (R01) | `apps/worker/tests/envio_espelho.rs:156-165`: `falhar_confirmacao(true)` → `rodar(..).unwrap_err()`, `falha.fase == "confirmacao_oracle"` (`:162`) e `fila_whatsapp().is_empty()` | Saída 2: linha `P` só depois de `NR_MESSAGE_ID` gravado |
| 3 — `caiu` na fila (R13) | `apps/worker/tests/envio_espelho.rs:168-198`: mesmo produto enviado antes a R$ 200,00, hoje R$ 100,00 → `fila[0].legenda == legenda_whatsapp(&o, true, ..)` (`:189`), contém `📉 *Caiu mais o preço!!!*` (`:193`) e o post do Telegram tem `📉 <b>Caiu mais o preço!!!</b>` | Saída 5: "o mesmo `caiu` do post do Telegram" |

### Gates (ciclo 2)

| Gate | Resultado |
|---|---|
| `cargo fmt --check` | exit 0 |
| `cargo clippy --all-targets -- -D warnings` | exit 0, sem aviso |
| `cargo test --no-fail-fast` | **621 passaram, 0 falharam, 3 ignorados** (618 do ciclo 1 + 3 novos) |
| `cd packages/contract && npm ci && npm run validate` | exit 0, `contrato OK` |
| CI `worker-arm64` | pendente (lição 12: conferir na PR) |

### Mutantes re-rodados (mesmo isolamento: backup em `_mutantes/`, mutação, `cargo test --test …`, restauração)

| # | Mutante | Ciclo 1 | Ciclo 2 | Teste que matou |
|---|---|---|---|---|
| F3 | mesmo sal para frase e ícone (`frases.rs:127`) | sobreviveu | **morto** | `escolha_com_valores_fixos`, `exemplo_do_dono_51217`, `exemplo_do_dono_51217_igual_ao_telegram` |
| F8 | hash little-endian (`frases.rs:46`) | sobreviveu | **morto** | `escolha_com_valores_fixos`, `exemplo_do_dono_51217`, `exemplo_do_dono_51217_igual_ao_telegram` |
| R01 | espelho antes do `confirmar` (`rodada.rs:208-216`) | sobreviveu | **morto** | `sem_confirmacao_nao_enfileira` |
| R13 | fila com `caiu = false` (`rodada.rs:353`) | sobreviveu | **morto** | `caiu_vai_para_a_fila` |
| F1 | `id mod n` | morto | morto | `escolha_com_valores_fixos`, `mil_ids_espalham`, … |
| F2 | ícones por caractere | morto | morto | `embutidas_sao_as_da_spec`, `corredor_sai_inteiro`, … |
| L07 | Telegram sem linha em branco depois do título | morto | morto | `legenda_basica`, `legenda_completa`, … |
| L14 | `cabe_whatsapp` só caracteres | morto | morto | `limite_em_bytes` |
| L16c | frase omitida quando o título é cortado | morto | morto | `frase_nunca_cortada`, `limite_com_frase_inteira`, … |
| R02 | espelho quando o Telegram falha | morto | morto | `falha_do_telegram_nao_enfileira` |
| R05 | slug com `{:?}` | morto | morto | `post_confirmado_vai_para_a_fila` |
| R08 | espelho na edição "Oferta encerrada" | morto | morto | `aviso_e_encerrada_nao_espelham` |

**Total acumulado: 42 mutantes, 42 mortos, 0 sobreviventes** (amostra de 8 dos 38 já mortos re-rodada:
nenhuma regressão). `git status --porcelain` igual à linha de base depois de cada lote; `_mutantes/` apagada.

### Lacunas 4–6: classificação

| Lacuna | Classificação | Motivo |
|---|---|---|
| 4 — cupom com `_` perde o `_` no WhatsApp (`BE_SAVE` → `BESAVE`) | **aceita, não bloqueante** | É o que a Saída 5 manda ("`*`, `_`, `~` e `` ` `` são removidos" do texto variável, que inclui o cupom); mudar seria contrariar a spec. Decisão de produto do dono, que precisa constar no PR. |
| 5 — ORA-00001 → `Ok(false)` só testado no fake (`apps/worker/src/envio/oracle.rs:335`) | **aceita, não bloqueante para o código; coberta pelo teste real** | Não há Oracle no ambiente de teste. A lógica de "duplicata ignorada" em `rodada.rs:359` está testada e o ramo real fica no passo 3 da execução real (§6), que já bloqueia o merge. |
| 6 — `docs/MANIFEST.md:49` e `packages/contract/fixtures/manifest-ok.json:2` em `1.6.0` | **aceita, não bloqueante** | Fora da pasta da spec (Saída 6 só pede CONTRATO §11 e `package.json`); a fixture não é lida pelo worker e o site compara só o major (`apps/site/src/lib/dados/sincronizador.ts:132`). Trocar a fixture exigiria mexer em `apps/site/src/lib/dados/tipos.test.ts:35`, também fora do escopo. Fica como sugestão de ticket do dono. |

### Veredito final

PASS. Continua bloqueando o merge a execução real do dono (§6): SQL, `--sim` na inst2, 2 h de espelho com
`SELECT` redigido, troca de frase sem recompilar, e o job `worker-arm64` verde na PR.

### Saída do `validate_state.py` (ciclo 2)

```
$ python .claude/skills/tlc-spec-driven/scripts/validate_state.py BSV-62 --root .
validate_state: 0 error(s) across [BSV-62]
exit=0
```
