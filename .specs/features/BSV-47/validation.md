# BSV-47: validation.md

**Verificado por:** Verifier independente, sub-agente (autor ≠ verificador), 2ª rodada. Não escreveu nem alterou código de produção nem testes; os mutantes foram aplicados e revertidos com `git checkout -- <arquivo>`.
**Commits verificados:** `2e4e7fb` (1ª rodada) e `b429e5a` (correções R1/R2 e testes dos mutantes). Branch `rubenmarcus/rub-35-bsv-47-ajustes-vps`. `git status` limpo antes e depois dos mutantes; a única mudança no fim é este arquivo.
**Régua:** "Saídas" e "Critério de aceite" de `docs/specs/BSV-47.md`; requisitos EXP-01..12, LIM, UNI-01..04, ENV, DOC de `.specs/features/BSV-47/spec.md`.

## Veredito da 2ª rodada: PASS (com lacunas de teste não bloqueantes e pendências do dono)

- Gates verdes (abaixo). Todos os critérios automatizáveis da spec cobertos por código e teste.
- R1 e R2 da 1ª rodada resolvidas conforme a decisão do dono e com testes que pegam a regressão.
- Dos 13 sobreviventes da 1ª rodada, 8 agora morrem (M29, M44, M45, M46, M47, M48, M49, M51). Seguem vivos M17, M19, M21, M24 (lacunas de baixo impacto ou redundâncias, nenhuma do caminho crítico) e M50 (equivalente hoje).
- 53 mutantes aplicados nesta rodada: 32 mortos, 21 sobreviventes (listados abaixo). Nenhum sobrevivente é regressão de um requisito EXP/LIM/UNI/ENV nomeado; são cobertura de ligação (`carregar`, `conectar`, `do_env`, `ler_result`), de ramos extremos (> 20 chaves no erro do lote) e de um campo do relatório.
- Continuam pendentes as execuções reais do dono (bloqueiam o merge, lição 5).

## Gates (apps/worker, `CARGO_TARGET_DIR=C:/cargo-target/besave`, `CARGO_BUILD_JOBS=2`, máquina sem mutante rodando)

| gate | resultado |
|---|---|
| `cargo fmt --check` | exit 0 |
| `cargo clippy --all-targets -- -D warnings` | exit 0 |
| `cargo test` (inteiro, testes de tempo incluídos, rodado antes dos mutantes) | exit 0: 512 passed, 0 failed, 3 ignored (60 binários; nenhum `#[ignore]` novo no diff `2e4e7fb..b429e5a`) |
| `systemd-analyze verify` | pendente do dono (sem systemd nesta máquina; está em `worker-arm64.yml`) |
| workflow ARM | pendente do dono (CI) |

## Critérios, um a um (PASS = código e teste conferidos)

| id | veredito | evidência |
|---|---|---|
| EXP-01 fila `_estado/expurgo.json` gravada antes de upload/manifest, id fora de chunks/sitemap/contagem | PASS | `src/geracao.rs:252-263` (carrega, devolve reativados, registra `ids_anteriores`, reconcilia, salva), `src/site.rs:144-147`; `tests/expurgo.rs` `desativacao_de_dia_...` e `fila_salva_so_quando_muda_e_sem_url`. M19/M21/M24 vivos: ordem contra imagens e redundância das duas fontes de saída não observadas (ver lacunas) |
| EXP-02 fora da janela, nenhuma remoção | PASS | `src/expurgo.rs:303-306`; `tests/expurgo.rs` (14.577 ids, zero chamadas à remoção e à KVS), janela inclusiva/exclusiva/meia-noite |
| EXP-03 até `BESAVE_EXPURGO_MAX`, `ceil(chaves/1000)` chamadas, fila gravada a cada chamada | PASS | `src/expurgo.rs:307-327`, `src/publicador.rs:180`; `tests/expurgo.rs` (3000 por noite, 1000 ids → 3 chamadas, 1001 → 4) |
| EXP-04 interrupção retoma sem perder nem repetir | PASS | `tests/expurgo.rs` (falha na 4ª chamada: fila com 1000, retomada total sem duplicata; id cortado na fronteira, ≤ 2 chaves reenviadas) |
| EXP-05 manifest antes de qualquer remoção | PASS | `src/geracao.rs:352` (manifest) antes de `:375` (executar); `tests/expurgo.rs`, `tests/plano.rs` |
| EXP-06 reconciliação única de órfãs | PASS* | `src/expurgo.rs:248-271`; `tests/expurgo.rs` (777 só página, 888 só `-small`, 999 ambos). *M17 vivo: a metade "páginas" não é isolada dos demais caminhos (L1) |
| EXP-07 id reativado sai da fila sem ser apagado | PASS | `tests/expurgo.rs` `oferta_reativada_...` |
| EXP-08 sem mudança e fila vazia, só os manifests mudam | PASS | `tests/expurgo.rs` (gravações `[manifest.prev.json, manifest.json]`, zero `remover_lote`) |
| EXP-09 relatório `expurgo_enfileirados/removidos/pendente`, `t_expurgo` | PASS | `src/execucao.rs:201-203,t_expurgo`; `tests/dry_run.rs` |
| EXP-10 falha do expurgo não falha o ciclo; `expurgo_falhou=1`; ids na fila; `DT_PUBLICACAO_SITE` e avisos seguem; aviso `Expurgo` 1 por 2 h sem contar falha | PASS* | `src/geracao.rs:375-388` (WARN, `falhou: true`, `pendente = fila.len()`), `src/execucao.rs:250-254`, `src/alerta.rs:343-364` (`Alertas::aviso`), `src/expurgo.rs:161`; `tests/expurgo_falha.rs` (4 testes: ciclo Ok e ids `[2,3]` na fila; `DT_PUBLICACAO_SITE` da oferta nova e aviso publicado; 1 mensagem em 2 ciclos, 2ª após 2 h, `falhas == 0`; sem falha não avisa). *O campo `expurgo_falhou` da linha de log do relatório não é testado (N4h vivo) |
| EXP-11 `DeleteObjects` 200 com `Errors` falha o lote, com contagem e chaves no erro e no log | PASS | `src/aws.rs:179-215,337-343`; `tests/aws_limites.rs` `delete_objects_com_erros_parciais_...` (servidor local real, 2 chaves, contagem `2 erro(s) no lote`, chaves no erro e no log, chave não afetada ausente) e `..._sem_erros_e_sucesso`. Ramo com mais de 20 chaves sem teste (N5b/c/f/i) |
| EXP-12 chaves da KVS em `UpdateKeys` de até 50 | PASS | `src/redirects.rs:341-368` (`LOTE_KVS`, `lotes_kvs`), `src/aws.rs:566` (`aplicar` usa `lotes_kvs`), `remover_chaves` em `src/redirects.rs:311`; `tests/redirects.rs` `quatorze_mil_e_quinhentas_exclusoes_viram_290_lotes_de_ate_50` |
| LIM-01 AWS: conexão, leitura, tentativa, operação; servidor mudo vira erro dentro do limite com operação e chave | PASS | `src/aws.rs:65-100`; `tests/aws_limites.rs:52-106`. `config_padrao()` (o que `carregar` usa) coberta por `config_padrao_do_carregar_...` (M44a morto). `carregar` chamar `config_padrao` não é testado (M44b vivo) |
| LIM-02 Oracle: `BESAVE_ORACLE_TIMEOUT_S` (padrão 120 s) aplicado à conexão | PASS* | `src/oracle.rs:26-70,98-124` (`abrir_limitada`); `tests/oracle.rs` (padrão, env, inválidos, `abrir_limitada` aplica exatamente o valor, propaga erro de abertura). M47 e M48 mortos. Continuam sem teste o fio `conectar → abrir_limitada` (M47b) e o descarte do erro de `limitar_chamadas` (M48b); a spec pede servidor mudo "simulado" e o autor entregou conexão falsa (aceito na 1ª rodada, L3) |
| UNI-01 `OnFailure=besave-alerta@%n.service` e `TimeoutStartSec=15min` nas duas unidades | PASS | `infra/vps/besave-ciclo.service:8,17`, `besave-envio.service:8,16`; `tests/unidades_vps.rs:41-52`. Sem `SuccessExitStatus` (decisão do dono), conferido por `grep` |
| UNI-02 unidade de alerta lê só o `.env`, sem segredo, roda `--alerta-encerrado %i` | PASS | `infra/vps/besave-alerta@.service:11-12`; `tests/unidades_vps.rs:54-75` |
| UNI-03 mesmo bot e mesma repetição (1 por variante a cada 2 h) | PASS | `src/unidade.rs:121-133` (`Alertas::falha`, mesmo estado do worker); `tests/unidade.rs` (borda `2h-1s`/`2h`, título, arquivo ao lado da trava) |
| UNI-04 só avisa para `timeout`, `signal`, `core-dump`, `watchdog` | PASS* | `src/unidade.rs:74-117`; `tests/unidade.rs` `result_de_timeout_sinal_core_dump_e_watchdog_avisa` (cada valor + `"timeout\n"`), `result_exit_code_nao_avisa_...` (`exit-code`, `success`, `resources`, vazio: sem aviso e sem arquivo de estado), `sem_conseguir_ler_o_result_avisa_mesmo_assim`. *A chamada real a `systemctl show -p Result --value` (`ler_result`) e o fio em `executar` não têm teste (N2e/N2f/N2g vivos); o pendente do dono cobre com o `TimeoutStartSec` curto |
| ENV-01 modelo do `.env` | PASS | `infra/vps/worker.env.example`; `tests/unidades_vps.rs:78-97`, `tests/worker_env_vps.rs` |
| ENV-02 sem credenciais, falha "credenciais AWS ausentes" | PASS* | `src/aws.rs:149-165`; `tests/aws_limites.rs` (`exigir_credenciais` isolada e `ContextoAws::com_sdk` sem região / sem credenciais / completo, M45 e M45c mortos). `carregar` chamar `com_sdk_em` não testado (M45b vivo) |
| DOC-01 CONTRATO §7 e MANIFEST §1 e §6 | PASS | `docs/CONTRATO.md:194-206`, `docs/MANIFEST.md:36,161-168`; 2ª rodada acrescentou "falha do expurgo não derruba o ciclo" nos dois. Versão do contrato inalterada (nenhum campo/enum/chave de dado nova) |

### Regras da spec

| regra | veredito | evidência |
|---|---|---|
| 1 idempotência (AD-028) | PASS | EXP-08 |
| 2 manifest nunca espera o expurgo | PASS | EXP-05; agora também vale quando o expurgo falha (EXP-10) |
| 3 noite normal cabe, excedente continua e aparece em `expurgo_pendente` | PASS | `tests/expurgo.rs` (11.577, 8.577, 5.577, 2.577, 0) |
| 4 sem dependência nova | PASS | `git diff 2e4e7fb..b429e5a -- apps/worker/Cargo.toml` vazio |
| 5 teste de tempo com aquecimento e mediana | PASS | `tests/expurgo.rs` (1 aquecimento + 5 rodadas, mediana); passou no `cargo test` completo sem carga |

## Decisões do dono desde a 1ª rodada: conferência

- **R1 (alerta duplicado):** resolvida. `Result` consultado por `systemctl show -p Result --value`; só `timeout`, `signal`, `core-dump`, `watchdog` avisam; `exit-code` não avisa nem grava estado; sem `SuccessExitStatus`. Os quatro valores têm mutante morto (N1a-N1d), `exit-code` acrescentado à lista é morto (N1e), `trim` é coberto (N1f), o ramo de erro de leitura é coberto (N2a), a inversão da guarda e o retorno de `alertar_se_encerrada` são cobertos (N2b, N2c).
- **R2 (falha do expurgo não falha o ciclo):** resolvida. Mutante que devolve o erro de `gerar` (M51) morre em 3 testes; `falhou`, `pendente`, o `if` de `concluir`, a chamada a `aviso`, a variante e a fase do aviso têm mutantes mortos (N4a-N4f). `Alertas::aviso` não conta falha (N3a morto), respeita a janela de 2 h na borda (N3b morto) e persiste o envio (N3d, N3e mortos).
- **KVS em `UpdateKeys` de 50:** conferida no código de produção (`aplicar` usa `lotes_kvs`) e no teste dos 290 lotes.

## Sensor de discriminação (53 mutantes; `CARGO_BUILD_JOBS=1`, lotes de 10; só os binários de teste relevantes; arquivo restaurado com `git checkout -- <arquivo>` após cada um; nenhum deixou de compilar ou de aplicar)

Grupos de teste: geração/expurgo = `expurgo, expurgo_falha, ciclo, indice_redirects, plano, geracao, site, redirects`; unidade = `unidade, unidades_vps` (+ `alerta` em N2e); aviso = `expurgo_falha, alerta, alerta_sem_novas`; AWS = `aws_limites`; Oracle = `oracle`; config = `expurgo, site` (+ `worker_env_vps`); relatório = geração + `dry_run, execucao`.

### Os 13 sobreviventes da 1ª rodada

| id | mutante | resultado | observação |
|---|---|---|---|
| M17 | reconciliação ignora a listagem de páginas | **sobreviveu** | Sem teste novo. Cobertura redundante via `paginas_no_bucket` quando o índice está ausente. Teste proposto: ciclo 1 cria o índice; gravar `oferta/777/index.html` no bucket; apagar `expurgo.json`; ciclo 2 deve enfileirar 777 |
| M19 | `gerar` não salva a fila antes das imagens | **sobreviveu** | Sem teste novo. Equivalente na prática: o próximo ciclo recalcula os mesmos ids (índice da KVS só muda depois). Registrado como equivalente |
| M21 | `gerar` não enfileira `ids_anteriores` | **sobreviveu** | Sem teste novo. Redundante com as saídas de página (`site.rs:144-146`). Teste proposto: id no índice de redirects sem entrada em `paginas.json` que sai do conjunto deve entrar na fila |
| M24 | `site.rs` não salva a fila após registrar saídas | **sobreviveu** | Equivalente na prática (`gerar` já salvou os mesmos ids). Cai junto com M21 em um teste que isole a saída só de página |
| M29 | valor de `VARIANTE` trocado | morto | `texto_da_variante_e_da_fase_e_o_combinado` (literal). Também morto o mutante da `FASE` (M29b) |
| M44 | `carregar` sem limites de tempo | morto (M44a: `config_padrao` sem `timeout_config`) | `config_padrao_do_carregar_traz_os_limites_de_tempo`. Ver M44b abaixo |
| M45 | `validar` sem `exigir_credenciais` | morto (M45; também M45c sem checar região) | `contexto_sem_regiao_ou_sem_credenciais_nao_carrega`. Ver M45b abaixo |
| M46 | `DeleteObjects` ignora `Errors` | morto | `delete_objects_com_erros_parciais_...` |
| M47 | Oracle sem `limitar_chamadas` | morto | `abrir_limitada_aplica_o_timeout_da_config_na_conexao_aberta`. Ver M47b abaixo |
| M48 | limite do Oracle multiplicado por 2 | morto | idem |
| M49 | `ConfigSite` ignora `BESAVE_EXPURGO_*` | morto | `config_do_site_le_a_janela_e_o_maximo_do_expurgo`. Ver M49b abaixo |
| M50 | `remover_lote` só o primeiro grupo de 1000 | **sobreviveu** | Equivalente hoje: `executar` nunca passa mais de 1000 chaves por chamada (`src/expurgo.rs:314`). Teste de unidade com 2500 chaves contra o servidor local contaria 3 `POST ?delete` |
| M51 | falha do expurgo engolida em `gerar` | morto (invertido: agora o mutante propaga o erro) | os 3 testes de `expurgo_falha.rs` |

### Mutantes novos (ligação e pontos da 2ª rodada)

| id | mutante | resultado | quem mata / proposta |
|---|---|---|---|
| M44b | `carregar` ignora `config_padrao` (usa `aws_config::defaults` puro) | **sobreviveu** | `carregar` não é exercitada. Teste: binário de teste próprio com `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` definidos, chamando `ContextoAws::carregar()` e afirmando `timeout_config` (ou expor `sdk()`) |
| M45b | `carregar` não valida (monta `Self` direto) | **sobreviveu** | mesmo teste, com e sem as variáveis de credencial (sem elas deve dar `CredenciaisAusentes`, com `AWS_EC2_METADATA_DISABLED=true`) |
| M47b | `conectar` abre direto, sem `abrir_limitada` | **sobreviveu** | Exige banco. Limitação aceita (L3 da 1ª rodada) |
| M48b | `abrir_limitada` descarta o erro de `limitar_chamadas` (`let _ =`) | **sobreviveu** | Teste: conexão falsa cujo `limitar` devolve `Err`; `abrir_limitada` deve falhar |
| M49b | `ConfigSite::do_env` passa ambiente vazio | **sobreviveu** | Ligação de uma linha. Teste com `std::env::set_var` em binário próprio, ou cobrir pelo teste do binário `besave-worker --dry-run` com `BESAVE_EXPURGO_MAX` |
| N1a-N1d | cada um dos 4 valores de `Result` removido | morto (4/4) | `result_de_timeout_sinal_core_dump_e_watchdog_avisa` |
| N1e | `exit-code` aceito como encerrado | morto | `result_exit_code_nao_avisa_...` |
| N1f | `encerrado_pelo_sistema` sem `trim` | morto | caso `"timeout\n"` |
| N2a | erro de leitura do `Result` não avisa | morto | `sem_conseguir_ler_o_result_avisa_mesmo_assim` |
| N2b | guarda de `alertar_se_encerrada` invertida | morto | os dois testes de `Result` |
| N2c | `alertar_se_encerrada` devolve `false` depois de avisar | morto | os testes de `Result` e de erro de leitura |
| N2e | `executar` usa `alertar` em vez de `alertar_se_encerrada` | **sobreviveu** | O fio do subcomando para o filtro de `Result` não é testado: os testes do binário só cobrem `--help` e saídas 2. Teste: tornar `ler_result` injetável por variável de ambiente de teste, ou `PATH` com um `systemctl` falso (script em CI Linux) |
| N2f | `ler_result` sem `--value` | **sobreviveu** | `ler_result` sem teste (precisa de `systemctl`). Teste: extrair `interpretar(status_ok, stdout)` e/ou `PATH` com `systemctl` falso |
| N2g | `ler_result` com a guarda `status.success()` invertida | **sobreviveu** | idem. Direção perigosa: com sucesso devolveria erro (avisa sempre), mas com falha do `systemctl` devolveria saída vazia (não avisa); em ambos o resultado é parcialmente seguro (erro → avisa) |
| N3a | `Alertas::aviso` conta falha | morto | `falhas == 0` |
| N3b | janela do aviso `<=` | morto | segundo aviso exatamente em +2 h |
| N3c | janela do aviso 1 h (`JANELA/2`) | **sobreviveu** | O teste só mede +5 min e +2 h. Teste: terceiro envio em +1 h 30 min deve continuar suprimido |
| N3d | `aviso` não grava o estado | morto | 1 mensagem em 2 ciclos |
| N3e | `aviso` não registra o envio | morto | idem |
| N4a | `falhou: false` no ramo de erro | morto | EXP-10 |
| N4b | `pendente: 0` no ramo de erro | morto | `falha_do_expurgo_deixa_o_ciclo_ok_e_os_ids_na_fila` |
| N4c | `if !rel.expurgo.falhou` | morto | com e sem falha |
| N4d | `concluir` não chama `aviso` | morto | 1 mensagem esperada |
| N4e | variante do aviso trocada | morto | `erro: Expurgo` |
| N4f | fase do aviso trocada | morto | `fase: expurgo` |
| N4h | `expurgo_falhou` fixo em `0` na linha de log do relatório | **sobreviveu** | Nenhum teste de `linha_relatorio` lê o campo. Teste: relatório com `expurgo.falhou = true` deve conter `expurgo_falhou=1` (padrão de `tests/aviso_relatorio.rs`) |
| N5a | `CHAVES_NO_LOG = 1` | morto | segunda chave ausente do erro |
| N5b | `CHAVES_NO_LOG = 1000` | **sobreviveu** | só 2 chaves nos testes. Teste: 25 chaves com erro → erro lista 20 e traz `e mais 5` |
| N5c | contagem do erro = chaves listadas | **sobreviveu** | só diverge acima de 20; mesmo teste |
| N5d | motivo = `code` antes de `message` | **sobreviveu** | o texto do motivo (`Access Denied`) não é afirmado; afirmar `Access Denied` e `We encountered an internal error` |
| N5e | motivo omitido no erro | **sobreviveu** | idem |
| N5f | sem `take(CHAVES_NO_LOG)` | **sobreviveu** | mesmo teste de > 20 |
| N5g | sem `warn!` por chave | morto | verificação do log |
| N5h | chave do erro = primeira do lote | morto | chave do erro é a primeira com falha (`oferta/2/...`) |
| N5i | sem o texto `e mais N` | **sobreviveu** | mesmo teste de > 20 |

Resumo: 53 aplicados, 32 mortos, 21 sobreviventes. Equivalentes ou redundantes: M19, M24, M50 (e M17/M21 enquanto os caminhos paralelos existirem). Lacunas de teste reais, em ordem de valor: N2e/N2f/N2g (caminho real do `systemctl`), N4h (campo do relatório), M44b/M45b (`carregar`), N5b/c/f/i (> 20 chaves), N3c, N5d/N5e, M48b, M49b, M47b (exige banco).

## Achados novos (não bloqueiam; o dono decide)

1. **Panic do worker deixa de avisar (consequência da R1).** `besave-ciclo` não captura panic; o processo sai com 101, o `Result` da unidade é `exit-code`, e `besave-alerta@` agora ignora esse caso. Antes da R1 o `OnFailure` cobriria; hoje um panic gera zero alerta. O Cargo.toml não define `panic = "abort"` (que daria `signal`). Opções: `std::panic::catch_unwind` em `ciclo::executar` que chame `Alertas::falha`, ou `panic = "abort"` no perfil release (vira `signal`, avisa). Teste proposto: texto do `Cargo.toml` no padrão de `tests/unidades_vps.rs`.
2. **`removidos` e `chaves` zeram quando o expurgo falha no meio** (`src/geracao.rs:379-385` substitui o relatório por `Default` + `pendente`). Lotes já apagados antes da falha não aparecem em `expurgo_removidos`; `pendente` está certo. Efeito só no relatório. Opção: `executar` devolver o parcial junto do erro.
3. **`ler_result` e o fio em `executar` sem teste** (N2e/N2f/N2g): o comportamento de produção da R1 só é verificado por fechamento injetado; o primeiro teste real é o do dono com `TimeoutStartSec` curto. O fallback "não conseguiu ler → avisa" torna a falha de leitura segura; a inversão da guarda de sucesso (N2g) não é.
4. **Chaves da KVS e `remover_chaves` chamam `carregar_base` a cada lote** (observação da 1ª rodada, inalterada): se o índice de redirects estiver inconsistente, cada lote lista a KVS. Improvável, pois o ciclo regrava o índice antes do expurgo.

## Pendente do dono (bloqueia o merge, lição 5)

- Noite com a fila cheia (sobras de 21/10): relatório da manhã com `expurgo_pendente=0` e `expurgo_falhou=0`. Registrar o `t_expurgo` real (a estimativa do README é 44 `DeleteObjects` + 290 `UpdateKeys` para 14,5 mil ids).
- Durante o dia, desativação nova sai da lista na hora e o arquivo só some de madrugada.
- Ciclo encerrado à força (`TimeoutStartSec` curto por 10 min) gera 1 alerta no Telegram (`Result=timeout`); uma falha comum (`exit-code`, por exemplo Oracle fora) gera só o alerta do worker, sem o do `besave-alerta@`. Confirmar que `systemctl show -p Result --value` funciona na versão do systemd da VPS.
- `systemd-analyze verify` limpo e workflow ARM verde (`worker-arm64.yml`); copiar `besave-alerta@.service` para `/etc/systemd/system/` e `daemon-reload`.
- Confirmar que a IAM do usuário do worker cobre `s3:DeleteObject` (usado também por `DeleteObjects`) e `cloudfront-keyvaluestore:UpdateKeys`.
- Decidir sobre o achado 1 (panic sem alerta) antes ou depois do merge.

## Evidência de execução e segurança

Nenhum arquivo de evidência (log, print, saída) foi adicionado ao repositório; o script dos mutantes e a saída bruta ficaram no scratchpad da sessão, fora do worktree. Nenhum caminho com nome de usuário, token ou host foi copiado para este arquivo. `git status` ao final: somente este arquivo alterado.
