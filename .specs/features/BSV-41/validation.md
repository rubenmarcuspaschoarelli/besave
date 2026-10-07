# BSV-41 Validation

## Validation: BSV-41 - PASS

**Veredito: PASS** — 43/43 mutantes mortos, gate verde em `c136bbf`. A execução real do dono continua bloqueando o merge.

**Data**: 2026-10-07
**Verificou**: Verifier independente, sub-agente; autor ≠ verificador. Não alterou código nem testes.
**Spec**: `docs/specs/BSV-41.md` (critério de aceite do dono) e `.specs/features/BSV-41/spec.md` (requisitos EARS do autor)
**Faixa do diff**: `origin/develop..HEAD` = `a230c08..c136bbf` (8 commits: T1–T7 + correção `c136bbf`, só testes, `fake_demo` e a chave `avisos_datas_gravadas` no relatório)
**Histórico**: 1ª passada (até `86e8876`): gate verde, sensor interrompido por falta de memória e 3 lacunas apontadas (ligação do ciclo, teto da cota, WARN do `.png` no envio). O autor corrigiu as três em `c136bbf`. A 2ª passada rodou o sensor completo em lotes de 5 a 10 mutantes.

---

## Tarefas

| Task | Status | Notas |
| ---- | ------ | ----- |
| T1–T7 | ✅ Concluídas | todas marcadas em `tasks.md`; 1 commit cada |
| Correção | ✅ Concluída | `c136bbf`: `cli_ciclo` com aviso no `fake_demo`, `aviso_nao_conta_perto_do_teto`, `envio_aviso_log.rs` |

---

## Critérios de aceite (ancorados na spec)

| Critério (spec do dono / req.) | Resultado definido pela spec | Evidência `arquivo:linha` – asserção | Status |
| --- | --- | --- | --- |
| 2 avisos ativos → 2 páginas + 2 imagens + índice (PAG-01) | 4 chaves, headers da tabela, índice `[1, 2]` | `apps/worker/tests/aviso_ciclo.rs:112-143` – `assert_eq!(rel.publicados, 2)`, `assert_eq!(idx.keys()…, vec![1, 2])` | ✅ |
| 2ª execução → 0 uploads (PAG-02) | nenhuma gravação nem remoção | `apps/worker/tests/aviso_ciclo.rs:153-157` | ✅ |
| Página: título, imagem, parágrafos, canal, CSS, `noindex` (PAG-03) | HTML exato de cada item | `apps/worker/tests/aviso_pagina.rs:151-179` | ✅ |
| Texto com `<script>` → escapado (PAG-04) | `&lt;script&gt;`, nenhum `<script>` | `apps/worker/tests/aviso_pagina.rs:199-207`; `apps/worker/tests/aviso_ciclo.rs:268-269` | ✅ |
| Link interno válido → botão (PAG-05) | `<a class="cta" href="/oferta/12345/">` | `apps/worker/tests/aviso_pagina.rs:219-230` | ✅ |
| `https://loja.com` → sem botão + WARN (PAG-06) | sem `cta`, WARN com o id | `apps/worker/tests/aviso_pagina.rs:252-253`; `apps/worker/tests/aviso_ciclo.rs:284-287`; `apps/worker/tests/aviso_ciclo_log.rs:77-80` | ✅ |
| `.png` → aviso ignorado + WARN (PAG-07) | fora do conjunto, removido, data anulada, WARN | `apps/worker/tests/aviso_ciclo.rs:305-323`; `apps/worker/tests/aviso_ciclo_log.rs:81` | ✅ |
| Imagem > 1 MB / ausente / sem pasta → página sem imagem (PAG-08) | sem `<img>`; 1 048 576 B exatos passam | `apps/worker/tests/aviso_ciclo.rs:351-367` | ✅ |
| Headers (PAG-09) | `META_PAGINA`; `image/jpeg`/`image/webp`, `public, max-age=3600` | `apps/worker/tests/aviso_modelo.rs:10-27` | ✅ |
| Desativado → página e imagem removidas (REM-01) | removido do bucket e do índice | `apps/worker/tests/aviso_ciclo.rs:187-191` | ✅ |
| `DT_FIM` no passado → removido (REM-02) | fim exclusivo; `AGORA+1` fica | `apps/worker/tests/aviso_ciclo.rs:210-217` | ✅ |
| Apagado do Oracle → removido (REM-03) | 1 removido | `apps/worker/tests/aviso_ciclo.rs:227-229` | ✅ |
| `DT_INICIO` no futuro → não publica (REM-04) | id 1 fora, id 2 (início = agora) dentro | `apps/worker/tests/aviso_ciclo.rs:250-252` | ✅ |
| Índice ausente/ilegível → reconstrói pelo bucket (REM-05) | 2 removidos, índice `[1, 2]` | `apps/worker/tests/aviso_ciclo.rs:414-419` | ✅ |
| Extensão trocada / imagem retirada → chave antiga removida (REM-06) | `1.jpg` some, `1.webp` existe | `apps/worker/tests/aviso_ciclo.rs:379-387` | ✅ |
| Ciclo grava a data ao publicar (DTP-01) | 2 gravadas; 0 na execução seguinte | `apps/worker/tests/aviso_ciclo.rs:428-436` | ✅ |
| Ciclo anula a data ao remover (DTP-02) | `(1, None)` | `apps/worker/tests/aviso_ciclo.rs:198-199` | ✅ |
| `BESAVE_DESTINO_LOCAL` não grava a data (DTP-03) | página na pasta, `avisos_datas_gravadas=0` | `apps/worker/tests/cli_ciclo.rs:300-320` (binário); `apps/worker/tests/aviso_relatorio.rs:138-139` | ✅ |
| Relatório com `avisos_*` e `t_avisos` (REL-01) | valores 2/0/0/2 e depois 0/1 | `apps/worker/tests/aviso_relatorio.rs:74-92` | ✅ |
| Falha na fase → WARN, `avisos_falhas=1`, código 0 (REL-02) | `Codigo::Ok` | `apps/worker/tests/aviso_relatorio.rs:114-121` | ✅ |
| Intervalo 120: 08:00 sim, 09:55 não, 10:00 sim (ENV-01..03) | 1, 1, 2 `sendMessage`; `dt_envio` 08:00/10:00 | `apps/worker/tests/envio_aviso.rs:116-130`; fronteira 09:59:59 `apps/worker/tests/envio_aviso_selecao.rs:43-47` | ✅ |
| Fora da janela → 0 (ENV-04) | nenhuma chamada | `apps/worker/tests/envio_aviso.rs:139-144` | ✅ |
| Dois vencidos → só o mais atrasado (ENV-05) | id 2; empate → menor id | `apps/worker/tests/envio_aviso.rs:168-171`; `apps/worker/tests/envio_aviso_selecao.rs:53-60` | ✅ |
| `DT_PUBLICACAO_SITE` nula → não envia (ENV-06) | `None`, 0 chamadas | `apps/worker/tests/envio_aviso.rs:187-189`; `apps/worker/tests/envio_aviso_selecao.rs:68` | ✅ |
| Inativo / ligação inativa / fora da vigência → não envia (ENV-07) | `None` | `apps/worker/tests/envio_aviso_selecao.rs:83-89` | ✅ |
| Aviso não reduz a cota (ENV-08) | mesmo `devido`/`enviados`; 178 de 180 às 21:55 → lote 2 + aviso | `apps/worker/tests/envio_aviso.rs:202-216`; `apps/worker/tests/envio_aviso.rs:239-244` | ✅ |
| Reserva antes do envio, confirma depois (ENV-09) | linha sem `message_id` no envio; depois `Some(88)` | `apps/worker/tests/envio_aviso.rs:249-253` | ✅ |
| Falha no Telegram → linha apagada, lote segue (ENV-10) | 0 linhas, `enviados == 2`, `aviso_falhou=1` | `apps/worker/tests/envio_aviso.rs:272-281` | ✅ |
| 429 no aviso → encerra sem lote (ENV-11) | `retry_after=30`, 0 ofertas, 0 linhas | `apps/worker/tests/envio_aviso.rs:305-309` | ✅ |
| Sem imagem → `sendMessage` com prévia ligada (ENV-12) | mesma legenda; `is_disabled: false` | `apps/worker/tests/envio_aviso.rs:319-330`, `:341-346` | ✅ |
| Com imagem → `sendPhoto` 800×800 (ENV-13) | JPEG 800×800 | `apps/worker/tests/envio_aviso.rs:388-394`; `apps/worker/tests/envio_aviso_selecao.rs:175-181` | ✅ |
| `.png` no envio → ignorado + WARN (ENV-14) | nada enviado; 1 WARN com o id | `apps/worker/tests/envio_aviso.rs:411-412`; `apps/worker/tests/envio_aviso_log.rs:65-67` | ✅ |
| Silencioso segue o horário de som (ENV-15) | 08:00 true, 10:00 false | `apps/worker/tests/envio_aviso.rs:424-426` | ✅ |
| `--sim` mostra o aviso (ENV-16) | 0 chamadas, 0 linhas, texto com o aviso | `apps/worker/tests/envio_aviso.rs:437-454` | ✅ |
| Legenda exata com `utm_source=telegram`, escapada (LEG-01) | igualdade exata | `apps/worker/tests/envio_aviso_selecao.rs:109-122` | ✅ |
| Legenda ≤ 1024, corta só o texto (LEG-02) | ≤ 1024, título inteiro, `…` antes do link | `apps/worker/tests/envio_aviso_selecao.rs:132-141` | ✅ |
| MANIFEST §1/§4 (DOC-01) | chaves e headers | `docs/MANIFEST.md:19`, `:26`, `:33`, `:102-105` (lidos) | ✅ |
| README: cadastrar, pasta, pausar (DOC-02) | seções | `apps/worker/README.md` seção "Avisos programados (BSV-41)" (lida) | ✅ |
| `fmt`, `clippy -D warnings`, `cargo test` sem rede | verde | ver Gate | ✅ |
| **Real (dono)** | — | — | ⏳ PENDENTE do dono (bloqueia o merge) |

Regras transversais conferidas lendo o código:
- **Regra 6 do CLAUDE.md**: `apps/worker/templates/aviso.html` não tem URL externa. O único link de fora é o do canal (`BESAVE_CANAL_URL`), que a spec pede. O link interno passa por `link_interno_valido` (`apps/worker/src/avisos/modelo.rs:37`) e todo texto sai escapado.
- **Sem dependência nova**: `Cargo.toml`/`Cargo.lock` sem mudança na faixa.
- **Legenda ≤ 1024**: garantida pelo `caber`. Pior caso (título de 120 caracteres todo `"` → 720 unidades): cerca de 850 unidades.
- **Desvios declarados nas Assumptions, todos coerentes com a spec**: recusa de `//host` além da regex (morto por M16), fase de avisos não fatal (M37), `max-age=3600` também para `.webp`, fim de vigência exclusivo (M01), desempate pelo menor id (M05).

---

## Sensor de discriminação

Worktree temporário fora do repositório (`git worktree add --detach <REDACTED-temp> HEAD`, em `c136bbf`) com `CARGO_TARGET_DIR=<REDACTED>` próprio e `CARGO_BUILD_JOBS=1`. Lotes de 5 a 10 mutantes, um mutante por vez, arquivo restaurado depois de cada um; rodam só os binários de teste indicados. Worktree removido com `git worktree remove --force` e diretório de build apagado. `git status --porcelain` do tree real: vazio antes e depois.

| # | Arquivo:linha | Mutação | Testes | Resultado |
| - | ------------- | ------- | ------ | --------- |
| M01 | `apps/worker/src/avisos/modelo.rs:24` | fim de vigência inclusivo (`<` → `<=`) | aviso_ciclo, envio_aviso_selecao | ✅ MORTO |
| M02 | `apps/worker/src/avisos/modelo.rs:24` | início exclusivo (`<=` → `<`) | aviso_ciclo, envio_aviso_selecao | ✅ MORTO |
| M03 | `apps/worker/src/avisos/modelo.rs:24` | `vigente` ignora `ST_ATIVO` | aviso_ciclo, envio_aviso_selecao | ✅ MORTO |
| M04 | `apps/worker/src/envio/aviso.rs:38` | intervalo `>=` → `>` | envio_aviso_selecao, envio_aviso | ✅ MORTO |
| M05 | `apps/worker/src/envio/aviso.rs:40` | desempate pelo maior id | envio_aviso_selecao, envio_aviso | ✅ MORTO |
| M06 | `apps/worker/src/envio/aviso.rs:40` | menor atraso em vez do maior | envio_aviso_selecao, envio_aviso | ✅ MORTO |
| M07 | `apps/worker/src/envio/aviso.rs:24` | `DT_PUBLICACAO_SITE` não exigida no envio | envio_aviso_selecao, envio_aviso | ✅ MORTO |
| M08 | `apps/worker/src/envio/aviso.rs:26` | envio aceita `.png` | envio_aviso_selecao, envio_aviso, envio_aviso_log | ✅ MORTO |
| M09 | `apps/worker/src/avisos/publicacao.rs:282` | não anula `DT_PUBLICACAO_SITE` | aviso_ciclo, aviso_relatorio | ✅ MORTO |
| M10 | `apps/worker/src/avisos/publicacao.rs:245` | não remove a imagem antiga (extensão trocada) | aviso_ciclo | ✅ MORTO |
| M11 | `apps/worker/src/avisos/publicacao.rs:261` | remoção não apaga a imagem | aviso_ciclo | ✅ MORTO |
| M12 | `apps/worker/src/avisos/publicacao.rs:260` | remoção não apaga a página | aviso_ciclo | ✅ MORTO |
| M13 | `apps/worker/templates/aviso.html:32` | parágrafo sem escape (`|safe`) | aviso_pagina, aviso_ciclo | ✅ MORTO |
| M14 | `apps/worker/templates/aviso.html:24` | `<h1>` sem escape | aviso_pagina | ✅ MORTO |
| M15 | `apps/worker/src/avisos/modelo.rs:31` | aceita link externo | aviso_pagina, aviso_ciclo | ✅ MORTO |
| M16 | `apps/worker/src/avisos/modelo.rs:39` | aceita `//host` | aviso_pagina | ✅ MORTO |
| M17 | `apps/worker/src/avisos/publicacao.rs:152` | 1 MB `>` → `>=` | aviso_ciclo | ✅ MORTO |
| M18 | `apps/worker/src/avisos/publicacao.rs:200` | ciclo aceita `.png` | aviso_ciclo, aviso_ciclo_log | ✅ MORTO |
| M19 | `apps/worker/src/envio/rodada.rs:166` | aviso fora da janela | envio_aviso | ✅ MORTO |
| M20 | `apps/worker/src/envio/rodada.rs:180` | aviso ocupa vaga do lote (`lote_devido − 1`) | envio_aviso | ✅ MORTO |
| M21 | `apps/worker/src/envio/rodada.rs:178` | aviso soma em `enviados_hoje` (cota `QT_MAX_DIA`) | envio_aviso | ✅ MORTO (`aviso_nao_conta_perto_do_teto`) |
| M22 | `apps/worker/src/envio/rodada.rs:311` | não cancela a reserva na falha | envio_aviso | ✅ MORTO |
| M23 | `apps/worker/src/envio/rodada.rs:314` | 429 no aviso não encerra | envio_aviso | ✅ MORTO |
| M24 | `apps/worker/src/envio/rodada.rs:292` | `sendPhoto` sem imagem | envio_aviso | ✅ MORTO |
| M25 | `apps/worker/src/envio/rodada.rs:296` | não confirma `NR_MESSAGE_ID` | envio_aviso | ✅ MORTO |
| M26 | `apps/worker/src/envio/rodada.rs:281` | não reserva `ENVIO_AVISO` | envio_aviso | ✅ MORTO |
| M27 | `apps/worker/src/envio/rodada.rs:167` | silencioso invertido no aviso | envio_aviso | ✅ MORTO |
| M28 | `apps/worker/src/envio/aviso.rs:46` | título da legenda sem escape | envio_aviso_selecao | ✅ MORTO |
| M29 | `apps/worker/src/envio/aviso.rs:15` | link sem `utm_source` | envio_aviso_selecao, envio_aviso | ✅ MORTO |
| M30 | `apps/worker/src/envio/aviso.rs:48` | legenda sem corte em 1024 | envio_aviso_selecao | ✅ MORTO |
| M31 | `apps/worker/src/avisos/publicacao.rs:250` | página sobe sempre (índice não idempotente) | aviso_ciclo | ✅ MORTO |
| M32 | `apps/worker/src/avisos/publicacao.rs:230` | imagem sobe sempre | aviso_ciclo | ✅ MORTO |
| M33 | `apps/worker/src/avisos/publicacao.rs:269` | índice regravado sempre | aviso_ciclo | ✅ MORTO |
| M34 | `apps/worker/src/avisos/publicacao.rs:189` | sem índice não reconstrói pelo bucket | aviso_ciclo | ✅ MORTO |
| M35 | `apps/worker/src/avisos/publicacao.rs:273` | `marcar` ignorado na função | aviso_ciclo, aviso_relatorio | ✅ MORTO |
| M36 | `apps/worker/src/ciclo.rs:342` | `marcar = true` no destino local | cli_ciclo, aviso_relatorio | ✅ MORTO (`cli_ciclo.rs:320`) |
| M37 | `apps/worker/src/execucao.rs:157` | falha da fase não conta `avisos_falhas` | aviso_relatorio | ✅ MORTO |
| M38 | `apps/worker/src/avisos/publicacao.rs:277` | regrava a data todo ciclo | aviso_ciclo | ✅ MORTO |
| M39 | `apps/worker/src/envio/rodada.rs:431` | `--sim` não mostra o aviso | envio_aviso | ✅ MORTO |
| M40 | `apps/worker/templates/aviso.html:8` | página sem `noindex` | aviso_pagina | ✅ MORTO |
| M41 | `apps/worker/src/envio/http.rs:147` | prévia do link desligada | envio_aviso | ✅ MORTO |
| M42 | `apps/worker/src/avisos/publicacao.rs:215` | link inválido sem WARN | aviso_ciclo_log | ✅ MORTO |
| M43 | `apps/worker/src/ciclo.rs:342` | destino local sem a fase de avisos | cli_ciclo | ✅ MORTO |

**Profundidade**: P0 (canal público e dados no site; ≥ 5 mutantes manuais cobrindo todos os ramos novos). **Resultado**: 43/43 mortos — PASS.

---

## Gate

- Comando (tree real, `CARGO_TARGET_DIR=<REDACTED>`, `CARGO_BUILD_JOBS=1`): `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`
- Resultado em `c136bbf`: exit 0. `fmt` ok; `clippy` sem avisos; **426 passados, 0 falhos, 3 ignorados**, em 51 binários. Os 3 `#[ignore]` são anteriores; o diff não acrescenta nenhum. Em `86e8876` eram 424 passados, em 50 binários.
- Antes do ticket: 372. Depois: 426. Delta **+54** (aviso_ciclo 17, envio_aviso 16, envio_aviso_selecao 9, aviso_pagina 5, aviso_relatorio 4, aviso_ciclo_log 1, aviso_modelo 1, envio_aviso_log 1), além das asserções novas em `cli_ciclo.rs`. Nenhum teste removido ou enfraquecido.
- Sem rede: fakes `FakeFonte`, `PublicadorMemoria`, `FakeEnvio`, `FakeCanal`, `RelogioFake`; o `cli_ciclo` usa `BESAVE_FONTE=fake` e `BESAVE_DESTINO_LOCAL`.

---

## Qualidade de código

| Princípio | Status |
| --------- | ------ |
| Escopo: `apps/worker/`, `docs/MANIFEST.md` §1/§4 | ✅ |
| `sql/bsv-41.sql` intocado | ✅ |
| Sem dependência nova | ✅ |
| Sem `unwrap`/`expect` fora de teste em `src/avisos/`, `src/envio/aviso.rs` | ✅ |
| Oracle e S3 só por trait com fake (`FonteOfertas`, `FonteEnvio`, `Publicador`) | ✅ |
| Asserções nos valores da spec (não na implementação) | ✅ |
| Diretrizes: `CLAUDE.md`, `apps/worker/CLAUDE.md` | ✅ |

---

## Lacunas (ranqueadas)

1. ~~Ligação dos avisos em `src/ciclo.rs` sem teste~~ — **resolvida** em `c136bbf` (`apps/worker/tests/cli_ciclo.rs:300-320`); M36 e M43 mortos.
2. ~~"Aviso não conta na cota" longe do teto~~ — **resolvida** em `c136bbf` (`apps/worker/tests/envio_aviso.rs:222-244`); M21 morto.
3. ~~WARN do `.png` no envio sem asserção~~ — **resolvida** em `c136bbf` (`apps/worker/tests/envio_aviso_log.rs:65-67`).
4. **[real] SQL dos avisos sem teste**: `SQL_AVISOS` (`apps/worker/src/oracle.rs`), `SQL_AVISOS_CANAL`, reserva e sequência `SQ_ENVIO_AVISO` (`apps/worker/src/envio/oracle.rs`), com bind `:desloc` repetido e conversão de fuso. Só a execução real prova.
5. **[real] Ligação S3 do ciclo** (`marcar = true` no ramo `Destino::Aws`, `apps/worker/src/ciclo.rs:356`): o caminho exige AWS. Só a execução real prova a gravação de `DT_PUBLICACAO_SITE`.
6. **[menor/doc] MANIFEST §6** não cita a fase de avisos depois do manifest. A saída 5 da spec pede só §1/§4.
7. **[spec-precision] CloudFront `/img/*`**: o behavior é de 1 ano, e o `max-age=3600` da imagem só vale se a política respeitar o `Cache-Control` da origem. Premissa declarada pelo autor (`min_ttl = 0`); a troca da imagem no mesmo nome deve ser conferida na execução real.

---

## Bloqueia o merge (execução real do dono)

- Rodar `apps/worker/sql/bsv-41.sql`.
- Cadastrar o aviso de afiliado com imagem em `BESAVE_AVISOS_DIR` (no `.env` do ciclo e do envio), ligado ao canal 1 com `NR_INTERVALO_MIN = 120`.
- Ciclo seguinte: `https://besave.com.br/avisos/{id}/` abre com imagem e texto; `AVISO.DT_PUBLICACAO_SITE` preenchida; relatório com `avisos_publicados=1`.
- `besave-envio --sim` mostra o aviso (legenda e `aviso-{id}.jpg`).
- Ao longo de um dia: aviso no canal a cada ~2 h, só entre 8 h e 22 h; lotes de ofertas sem perda de cota.
- Desativar (`ST_ATIVO = 0`): página some no ciclo seguinte, data anulada, envio para.
- Prints do canal e da página sem token nem `chat_id` (regra 11).

---

## Rastreabilidade

| Requisito | Novo status |
| --------- | ----------- |
| PAG-01..09, REM-01..06, DTP-01..03, REL-01..02, ENV-01..16, LEG-01..02, DOC-01..02 | ✅ Verificado |
| Execução real | ⏳ Dono |

## Resumo

**Geral**: ✅ Pronto do lado do código; o merge depende só da execução real do dono.
**Critérios**: 40/40 requisitos com evidência; nenhuma lacuna aberta de teste; 2 itens só provados na execução real (lacunas 4–5) e 1 premissa de CDN (lacuna 7).
**Sensor**: 43/43 mortos.
**Gate**: 426 passados, 0 falhos, 3 ignorados.
