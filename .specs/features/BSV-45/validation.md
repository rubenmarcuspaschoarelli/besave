# BSV-45 — validation.md

**Veredito: PASS** (com 3 lacunas de cobertura não bloqueantes; ver "Lacunas")
**Verificador:** Verifier independente (sub-agente, autor ≠ verificador; o autor foi outra sessão). Não é auto-verificação.
**Alvo:** commit `fbcbbf9` (diff `fbcbbf9^..fbcbbf9`, 15 arquivos, +1343/-77), branch `rubenmarcus/rub-40-bsv-45-imagem-por-hash`.
**Data:** 2026-10-28. Nenhum código de produção nem teste foi alterado pelo Verifier.

## 1. Gates (apps/worker, `CARGO_TARGET_DIR` compartilhado, `CARGO_BUILD_JOBS=1`)

| gate | resultado |
|---|---|
| `cargo fmt --check` | exit 0 |
| `cargo clippy --all-targets -- -D warnings` | exit 0 |
| `cargo test --no-fail-fast` | 561 passed, 0 failed, 3 ignored |

Os 3 `ignored` são testes de desempenho já marcados `#[ignore]` antes do ticket
(`trinta_mil_cards_em_ate_30_segundos`, `cinco_mil_ids_em_ate_5_segundos`, `trinta_mil_paginas_em_ate_60_segundos`).
Contagem de testes em `tests/imagens.rs`: 24 antes, 24 depois (nenhum apagado). `tests/imagens_hash.rs`: 23 testes novos.
Os gates de CI rodaram em máquina sem outra compilação do Verifier em paralelo; os testes de tempo do expurgo passaram na mediana.

## 2. Spec-anchored outcome check

Testes novos em `apps/worker/tests/imagens_hash.rs` (IH); adaptados em `tests/imagens.rs` (IM), `tests/expurgo.rs` (EX), `tests/ciclo.rs`, `tests/geracao.rs`.

### Critério de aceite de `docs/specs/BSV-45.md`

| critério | evidência `arquivo:linha` + asserção | resultado |
|---|---|---|
| Defeito de 19/10: trocado, mesmo id, sobe, `reenviadas = 1`, sem apagar | IH:190 `rel.reenviadas == 1`; IH:193 `gravadas.len() == antes + 2`; IH:199 `remocoes().is_empty()`; IH:195 bucket com conteúdo B | PASS |
| Inalterado: 0 uploads, 0 listagem, índice não regravado | IH:287-291 (`publicadas 0`, `imagens_gravadas` igual, `listagens_de_ofertas 0`, `gravacoes_do_indice` igual); via `gerar` IH:703-707 | PASS |
| Id novo sobe e entra no índice | IH:226-231 (`publicadas 1`, `reenviadas 0`, índice com hash da origem) | PASS |
| Índice ausente / JSON inválido / valor fora do formato: lista, reconstrói, sem erro; seguinte não lista | IH:350-358 (ausente); IH:375-399 (5 variantes: json, lista, hash curto, maiúsculo, valor não-string); seguinte `listagens == 0` IH:398 | PASS (WARN não é asserido, ver lacuna L3) |
| Reconciliação: HORAS=0 lista todo ciclo; padrão não lista antes e lista depois; chave apagada não volta antes / volta depois | IH:432 (HORAS=0), IH:438 (24h-1s não lista), IH:440 (24h lista), IH:446 (marca andou); IH:461 e IH:469 (as duas metades) | PASS |
| `sem_origem` e falha de envio não gravam hash; ciclo seguinte tenta de novo | IH:517 `!contains_key("9")`, IH:521-523; falha: IH:542-548, IH:553 (`publicadas 6`), IH:554 (`+12` gravações) | PASS |
| Expurgo: continua no índice até a fila; na janela 2 chaves e fora do índice; reentrada sobe; reativado não reenviado | IH:635-636 (EXP-01), IH:641-642 (EXP-02), IH:660-662 (EXP-03), IH:680-683 (EXP-04) | PASS |
| Placeholders: ausente publica, presente não republica | IH:308, IH:315, IH:328; IM:381-395 (adaptado) | PASS |
| Orçamento: índice 30.000 ids ≤ 1 MB | IH:726 `por_id * 30_000 <= 1_000_000` (amostra de 2.000 ids com ids de 6 dígitos, projeção linear); IH:728 trava o piso da amostra | PASS (projeção, não 30k reais; aceitável, linear por construção) |
| Relatório traz `t_imagens_listagem` e `imagens_reenviadas` | IH:742-743 (campos exatos na linha); `--publicar` imprime `imagens_reenviadas` em `src/main.rs:239` (sem teste) | PASS parcial (ver L2) |
| Gates | seção 1 | PASS |
| Real (dono): 3 ciclos contra Oracle/bucket | fora do alcance do Verifier | PENDENTE (bloqueia o merge, execução do dono) |

### ACs do `spec.md` (IMG/IDE/REC/FAL/EXP/ORC/REL)

| AC | evidência | resultado |
|---|---|---|
| IMG-01 | IH:179-201 e IH:205-214 (só o small) | PASS |
| IMG-02 | IH:226-228 | PASS |
| IMG-03 (objeto plano, 16 hex, `no-store`, sem URL, hash = grande ++ small) | IH:243 `meta == META_ESTADO`; IH:246 sem "http"; IH:248-251 | PASS |
| IMG-04 (gravado depois dos uploads; não regrava se igual) | IH:267 `ultima_imagem < pos_indice`; IH:291 | PASS |
| IDE-01 | IH:287-291 (`reaproveitadas == 3`) | PASS |
| IDE-02 | IH:315-328 (inclui que `img/placeholder/` é listado todo ciclo, IH:317-323) | PASS |
| REC-01 | IH:350-358; par incompleto sobe IH:363-370 | PASS |
| REC-02 | IH:375-399 | PASS (WARN não asserido, L3) |
| REC-03 | IH:404-416 | PASS |
| REC-04 | IH:420-447 (inclui fronteira 24h-1s / 24h) | PASS |
| REC-05 | IH:452-471 (`reenviadas == 0` na restauração, IH:465) | PASS |
| REC-06 | IH:475-505 (padrões, valores válidos, 3 inválidos com `ErroConfigSite::Invalida(nome)`) | PASS |
| FAL-01 | IH:512-524 | PASS |
| FAL-02 | IH:529-556 (bloco 2 falha; blocos anteriores no índice) | PASS |
| FAL-03 | IH:560-577 (mantém hash anterior; id sem hash fica fora) | PASS |
| EXP-01..04 | IH:621-687 | PASS |
| ORC-01 | IH:715-732 | PASS |
| REL-01 | IH:736-744 | PASS parcial (L2) |

Edge cases do spec.md: "índice com ids fora do conjunto e fora da fila são mantidos por `gerar`" — coberto indiretamente por EXP-01 (IH:635); "chaves estranhas só contadas" — mantido por `tests/imagens.rs` `chaves_estranhas_contadas_ignoradas_e_mantidas` (inalterado, passa).

### Testes antigos alterados pelo autor — enfraqueceram a verificação?

| teste | alteração | veredito |
|---|---|---|
| IM `id_ja_publicado_com_origem_igual_e_reaproveitado` (REU-01) | Antes: origem trocada ainda era reaproveitada. Isso era o defeito; a nova spec inverte. Agora afirma origem igual → reaproveita e adiciona `gravacoes().len()` inalterado (IM:~320). O caso "origem trocada" migrou para IH:179. | Inversão exigida pela spec; não enfraquece (acrescenta asserção). |
| IM REU-03 placeholders | contagem restrita a `img/placeholder/` porque agora o índice também é gravado | Necessário; mesma precisão sobre placeholders. |
| IM `cinco_mil_ids_existentes_decididos_so_por_listagem` (LST-01) | Passou a escrever origens e a esperar que a única gravação nova seja `_estado/imagens.json` | Mantém `reaproveitadas == 5000`, `publicadas == 0` e a contagem de listagens; mais específico, não menos. |
| IM `placeholder_existente_nao_e_reenviado...` (LST-04) | Filtra gravações por `img/` | Necessário; continua exigindo exatamente o placeholder ausente. |
| `tests/geracao.rs` | `reenviadas: 0` no literal; `_estado/imagens.json` na lista de chaves permitidas em `falha_na_kvs_nao_grava_manifest` | Ajuste de compilação / lista permitida. A asserção da lista é negativa ("nenhuma gravação fora destas"); incluir a chave nova afrouxa só no que a spec manda (índice é gravado antes da KVS, passo 1). Aceitável. |
| `tests/ciclo.rs` | `_estado/imagens.json` na lista de gravações do 1º ciclo; `..ConfigSite::default()` | Adaptação direta do contrato (nova chave S3). |
| `tests/expurgo.rs` | só assinatura (`&mut IndiceImagens::default()`) | Mecânica. Nenhuma asserção alterada. |
| `tests/worker_env_vps.rs` | 2 variáveis opcionais documentadas | Mecânica. |

Nenhum teste foi pulado, apagado ou enfraquecido.

## 3. Sensor de discriminação

Worktree temporário separado (detached em `fbcbbf9`), `CARGO_TARGET_DIR` compartilhado, `CARGO_BUILD_JOBS=1`, lotes de 10/10/9 mais 2 avulsos, rodando `cargo test --test imagens_hash --test imagens --test expurgo --test geracao --test ciclo`. Worktree removido com `git worktree remove --force` e `prune`; `git status --porcelain` do repositório real vazio antes e depois.

| id | mutante | resultado | teste que matou |
|---|---|---|---|
| a | `anterior == hash` → `!=` | KILLED | `arquivo_trocado...`, `segunda_execucao_completa...` |
| b1 | hash só do arquivo grande | KILLED | `indice_e_objeto_plano...`, `arquivo_trocado...` |
| b2 | hash só do small | KILLED | idem |
| c | ordem small ++ grande | KILLED (não equivalente) | IH:251 `hash_da_origem` |
| d1 | `>= limite` → `> limite` | KILLED | `intervalo_zero...` (fronteira 24h), `chave_apagada...` |
| d2 | ignora `relistar_horas` | KILLED | `intervalo_zero...` |
| e | não grava `relistado_em` | KILLED | `chave_apagada...`, `gerar_nao_lista...` |
| f | não grava índice na falha de bloco | KILLED | `falha_de_envio...` |
| g | grava hash antes do `gravar_lote` (hash de bloco que falhou) | KILLED | `falha_de_envio...` |
| h | `sem_origem` entra no índice | KILLED | `sem_origem_nao_entra...` |
| i | remove `indice.remover` do expurgo | KILLED | `id_que_saiu_continua...` |
| j | fila antes do índice no expurgo | SURVIVED, equivalente | só observável com queda entre as duas gravações (falha injetada em `gravar` do índice entre elas não existe nos testes); ver L4 |
| j2 | remove `indice.salvar` do expurgo | KILLED | `id_que_saiu_continua...` (EXP-02) |
| k | reconstrução com par no bucket sobe | KILLED | `indice_ausente...`, `cinco_mil_ids...` |
| l | id novo sem listagem tratado como "no bucket" | KILLED | `id_novo_sobe...`, `sem_origem...` |
| m | `reenviadas` conta restauração | KILLED | `chave_apagada...` (IH:465) |
| n | remove `!fila_reconciliada` de `deve_listar` | **SURVIVED** | lacuna L1 |
| w | `gerar` passa `true` fixo em vez de `fila.reconciliado()` | **SURVIVED** | lacuna L1 (mesma) |
| o | listar placeholders só quando lista ofertas | KILLED | `segunda_execucao_sem_mudanca...` e outros |
| p | retira `t_imagens_listagem` da linha | KILLED (com ajuste do tamanho do array) | `linha_do_ciclo_agendado...` |
| p2 | retira `imagens_reenviadas` da linha | KILLED (idem) | idem |
| q | `gerar` zera `tempos.imagens_listagem` | **SURVIVED** | lacuna L2 |
| r | remove `!confiavel` de `deve_listar` | SURVIVED, equivalente | índice não confiável tem `relistado_em = None`, que já força a listagem |
| s | `salvar` sempre grava (sem comparar com o lido) | KILLED | `segundo_ciclo...`, ciclo/site |
| t | remove o `salvar` final | KILLED | `primeira_execucao_publica...`, `chave_apagada...` |
| u | `hash_valido` aceita qualquer tamanho | KILLED | `indice_invalido_reconstroi...` (hash curto) |
| v | não incrementa `reenviadas` | KILLED | `arquivo_trocado...` |
| x | `relistado_em` gravado mesmo sem listar | KILLED | `intervalo_zero...`, `gerar_nao_lista...` |
| y | chave `_*` desconhecida invalida o índice | **SURVIVED** | lacuna L5 (decisão do spec.md, não da spec do ticket) |

Total: 30 mutantes, 24 mortos, 2 equivalentes (j, r), 4 sobreviventes reais (n, w contam como um achado; q; y). Mutante 'z' do script era no-op e foi descartado.

## 4. Lacunas (ranqueadas)

1. **L1 (média) — `fila_reconciliada` em `deve_listar` sem teste (n, w).** O caso é: índice válido e recente, mas `_estado/expurgo.json` ainda com `reconciliado = false`. Com a condição removida o ciclo não lista, `FilaExpurgo::reconciliar` (`src/expurgo.rs:255-277`) recebe `ids_de_oferta()` vazio e marca `reconciliado = true`, perdendo para sempre as imagens órfãs de ids fora do conjunto (a parte de `oferta/` continua coberta pela listagem de páginas). Nenhum teste monta esse estado. Sugestão: teste em `gerar` com índice válido, fila sem `reconciliado`, imagem órfã no bucket e esperar 1 listagem e a órfã enfileirada.
2. **L2 (baixa) — `t_imagens_listagem` real não é testado de ponta a ponta (q).** REL-01 usa `Relatorio::default()` com valor injetado (IH:737-743); nada prova que `gerar` preenche o campo (`src/geracao.rs:413`). Também não há teste para a linha de `--publicar` (`src/main.rs:239`). O dono mede `t_imagens_listagem` na execução real, então o risco é de observabilidade, não de dado.
3. **L3 (baixa) — WARN do índice inválido não asserido.** A spec pede WARN (REC-02); o teste só confere reconstrução sem erro. Sem captura de `tracing` no repositório, é a mesma limitação de outros testes do worker.
4. **L4 (baixa) — ordem índice-antes-da-fila no expurgo (j) é inobservável pelos testes.** Só uma falha injetada entre as duas gravações a distingue. A decisão está documentada em `src/expurgo.rs` (comentário de `executar`) e no MANIFEST §6 passo 7; registrado como equivalente para os testes atuais.
5. **L5 (muito baixa) — tolerância a chaves `_*` desconhecidas (y)** vem do spec.md (premissa), não da spec do ticket; sem teste. Impacto: um campo futuro com `_` no índice reconstruiria tudo em vez de ser ignorado.

Também sem cobertura automatizada e dependente do dono: o tempo real da listagem antes/depois e os 3 ciclos contra Oracle/bucket (Definition of done da spec).

## 5. Qualidade de código (spot-check)

- Sem dependência nova (`sha2`/`serde_json` já existiam; `hash16` reaproveitado de `paginas`).
- Diff restrito a `apps/worker/` e `docs/MANIFEST.md` (regra 10, mesma PR); `docs/MANIFEST.md` §1 e §6 atualizados, incluindo o "preço da economia" (regra 1 da spec).
- `unwrap`/`expect` fora de teste: nenhum introduzido. Erros com `thiserror` (`ErroIndice`, `ErroConfigImagens`).
- Índice sem URL de afiliado (IH:246).
- Evidência: este arquivo não contém caminhos de usuário, tokens nem hostnames.

## 5. Fechamento das lacunas 1, 3 e 4 (rodada 2)

Testes novos, derivados da spec (autor da correção ≠ Verifier; mutantes rodados pelo autor da correção):

| lacuna | teste | evidência |
|---|---|---|
| 1 `fila_reconciliada` | `fila_nao_reconciliada_forca_listagem_e_a_orfa_entra_na_fila` (`tests/imagens_hash.rs`) | índice válido e recente + fila sem `reconciliado` + órfã 99 no bucket → 1 listagem, `enfileirados == 1`, fila com `"99"` e `reconciliado:true`, ciclo seguinte sem listagem |
| 3 WARN do índice | `indice_invalido_loga_warn_e_ausente_nao` (`tests/imagens_indice_log.rs`, binário próprio) | JSON inválido e valor fora do formato → 1 WARN citando `imagens.json`; índice ausente → 0 WARN |
| 4 chave `_*` | `chave_desconhecida_com_underscore_nao_invalida_o_indice` (`tests/imagens_hash.rs`) | índice com `_desconhecida` → 0 listagem, `reaproveitadas == 1`, 0 upload |

Lacuna 2 (`t_imagens_listagem` preenchido por `gerar`, linha do `--publicar`) continua aberta: o campo é tempo real medido, sem asserção determinística.

Mutantes (`CARGO_BUILD_JOBS=1`, lote de 5, `git checkout src` após cada um; árvore limpa no fim):

| # | mutante | resultado |
|---|---|---|
| M1 | remover `!fila_reconciliada` de `deve_listar` (`imagens.rs`) | morto (`fila_nao_reconciliada_...`) |
| M2 | `geracao.rs` passa `true` no lugar de `fila.reconciliado()` | morto (`fila_nao_reconciliada_...`) |
| M3 | remover o `warn!` do índice inválido | morto (`indice_invalido_loga_warn_...`) |
| M4 | chave `_*` desconhecida invalida o índice | morto (`chave_desconhecida_...`) |
| M5 | `warn!` também com índice ausente | morto (`indice_invalido_loga_warn_...`) |

Gates após a rodada: `cargo fmt --check` OK, `cargo clippy --all-targets -- -D warnings` OK, `cargo test --no-fail-fast` 564 passados, 0 falhas.

## 6. Emenda do dono: hash16 passa a ser impressão digital de metadados (rodada 3)

`hash16("len_g:mtime_ns_g:len_s:mtime_ns_s")` por `std::fs::metadata`; o conteúdo só é lido quando o id vai subir. Spec (`docs/specs/BSV-45.md` Saída 1, `.specs/features/BSV-45/spec.md` IMG-03 e IMG-05..08), MANIFEST §1 e §6 passo 1 e README atualizados. O resto não mudou.

Testes (`tests/imagens_hash.rs`; o mtime é fixado por `set_modified`, sem depender da granularidade do sistema de arquivos):

| AC | teste | resultado esperado |
|---|---|---|
| IMG-06 | `outro_tamanho_sobe` | tamanho diferente → sobe, `reenviadas = 1` |
| IMG-07 | `mesmo_tamanho_e_mtime_diferente_sobe_uma_vez` | sobe uma vez; ciclo seguinte reaproveita |
| IMG-07 | `mtime_so_em_nanossegundos_diferente_sobe` | diferença de 500 ms → sobe |
| IMG-06 | `mtime_preservado_e_tamanho_diferente_sobe` | cópia com `-p` e tamanho diferente → sobe |
| IMG-08 | `metadados_iguais_nao_sobem_mesmo_com_conteudo_trocado` | **limite aceito**: conteúdo trocado com len e mtime restaurados não sobe; bucket e índice intactos |
| FAL-01 | `reconstrucao_nao_adota_id_sem_origem` | par no bucket, sem origem → `sem_origem`, fora do índice |

Limite do IMG-05: não há asserção que prove "nenhum arquivo é lido" no ciclo sem mudança (leitura sem efeito observável); ficou coberto pelo mutante M5 (hash por conteúdo, morto pelos testes de formato do índice) e pelo teste do limite aceito.

Mutantes do trecho novo (`CARGO_BUILD_JOBS=1`, lote de 7, `src/imagens.rs` restaurado ao fim de cada lote):

| # | mutante | resultado |
|---|---|---|
| M1 | impressão sem `len` | morto |
| M2 | mtime em segundos (`as_secs`) | morto |
| M3 | ignora o `-small` | morto |
| M4 | ignora o `{id}.webp` | morto |
| M5 | hash volta a ser do conteúdo | morto |
| M6 | `metadata` ausente vira impressão vazia | **sobreviveu** na 1ª passada; morto após `reconstrucao_nao_adota_id_sem_origem` |
| M7 | impressão só com o grande | morto |

Gates: `cargo fmt --check` OK, `cargo clippy --all-targets -- -D warnings` OK, `cargo test --no-fail-fast` sem falhas (570 passados, 0 falhas).
