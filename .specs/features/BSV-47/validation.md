# BSV-47: validation.md

**Verificado por:** Verifier independente, sub-agente (autor ≠ verificador). Não escreveu nem alterou código de produção nem testes.
**Commit verificado:** `2e4e7fb` (branch `rubenmarcus/rub-35-bsv-47-ajustes-vps`), worktree limpo antes e depois (`git status` vazio, `git diff` vazio).
**Régua:** "Saídas" e "Critério de aceite" de `docs/specs/BSV-47.md`; requisitos EXP/LIM/UNI/ENV/DOC de `.specs/features/BSV-47/spec.md`.

## Veredito geral: PASS com ressalvas

Nenhum critério automatizável falhou e o gate está verde. 38 de 51 mutantes morreram; os 13 sobreviventes se dividem em
lacunas de teste reais (7), redundâncias de código equivalentes (4) e consequência de desenho já aceita (2). Há duas
ressalvas de comportamento que o dono deve decidir antes do merge (R1 e R2). Os itens "Real (dono)" continuam pendentes.

## Gates (apps/worker, `CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=2`, sem carga)

| gate | resultado |
|---|---|
| `cargo fmt --check` | exit 0 |
| `cargo clippy --all-targets -- -D warnings` | exit 0 |
| `cargo test` (rodado inteiro, sem mutante em andamento, máquina livre, testes de tempo incluídos) | exit 0: 496 passed, 0 failed, 3 ignored (57 binários; nenhum `#[ignore]` novo no diff) |
| `systemd-analyze verify` | pendente do dono (sem systemd nesta máquina); está no workflow `worker-arm64.yml` |
| workflow ARM | pendente do dono (CI) |

## Critérios, um a um

Legenda: PASS = código e teste que o cobre conferidos; PASS* = passa com ressalva; pendente = execução real do dono.

### Saídas

| # | item | veredito | evidência |
|---|---|---|---|
| 1a | id que sai do conjunto sai de chunks/sitemap/contagem no mesmo ciclo e vai para fila `_estado/expurgo.json` (id + data) | PASS | `src/geracao.rs:252-263` (carrega, devolve reativados, registra `ids_anteriores` fora do conjunto, reconcilia, salva); `src/site.rs:144-147` (registra saídas de página); `src/expurgo.rs:173-181` (formato id → ISO UTC). Teste: `tests/expurgo.rs:346-386` (`desativacao_de_dia_...`: manifest `total_ofertas==2`, sitemap sem o id, arquivo ainda lá), `:495-515` (`fila_salva_so_quando_muda_e_sem_url`) |
| 1b | fila só roda na janela `BESAVE_EXPURGO_JANELA` (padrão 02:00-05:00, Brasília); fora dela nada é apagado | PASS | `src/expurgo.rs:96-104,303-306`; testes `tests/expurgo.rs:94-115` (início inclusivo, fim exclusivo, cruza meia-noite), `:166-183` (14.577 ids, zero chamadas, zero remoções, zero chamadas à KVS). Mutantes M01-M05 e M09 mortos |
| 1c | até `BESAVE_EXPURGO_MAX` ids por ciclo (padrão 3000) | PASS | `src/expurgo.rs:307`, `:23`; teste `tests/expurgo.rs:188-215` (pendentes 11.577, 8.577, 5.577, 2.577, 0; `removidos <= 3000`). M10 morto |
| 1d | `DeleteObjects` de até 1000 chaves, `ceil(chaves/1000)` chamadas | PASS | `src/expurgo.rs:314-315`, `src/publicador.rs:180`, `src/aws.rs:272-308`; testes `tests/expurgo.rs:201` (chamadas == `ceil(chaves/1000)` por noite), `:218-227` (1000 ids → 3, 1001 → 4). M28 morto |
| 1e | estado gravado depois de cada lote; interrompido retoma sem repetir e sem perder | PASS | `src/expurgo.rs:318-327`; testes `tests/expurgo.rs:232-259` (falha na 4ª chamada: 3000 chaves apagadas, fila com 1000, retomada total 6000 remoções sem duplicata, KVS vazia), `:264-282` (id cortado na fronteira: nenhuma chave perdida, ≤ 2 reenviadas). M06, M07, M11 mortos |
| 2 | reconciliação única de órfãs (imagens e páginas fora do conjunto e fora da fila) | PASS* | `src/expurgo.rs:248-271`, `src/imagens.rs` (`ids_de_oferta`); teste `tests/expurgo.rs:435-478` (777 só página, 888 só `-small`, 999 ambos; entram uma vez; segunda rodada e órfã nova não reentram). M12, M13, M14, M18 mortos. **Lacuna L1:** a metade "páginas" da reconciliação (M17) não é provada, porque no teste o índice `paginas.json` está ausente e `paginas_no_bucket` (`src/site.rs:100-115`) já enfileira a página; o caso real (índice válido, página fora dele) não tem teste |
| 3a | AWS: tempo de conexão, leitura, tentativa e operação configurados; servidor que aceita e não responde vira erro dentro do limite, com operação e chave | PASS | `src/aws.rs:65-100` (`LimitesTempo`/`timeout_config`); testes `tests/aws_limites.rs:52-64` (servidor TCP real mudo; `HeadObject` e chave no erro em < 6 s), `:68-84` (`DeleteObjects`), `:88-106` (configuração inteira). M40-M43 mortos |
| 3b | AWS: o limite vale no caminho de produção (`ContextoAws::carregar`) | lacuna (L2) | `src/aws.rs:117` aplica `LimitesTempo::default()`; **nenhum teste** cobre `carregar()` (M44 sobreviveu): só `com_endpoint` é exercitado |
| 3c | Oracle: tempo por chamada (`BESAVE_ORACLE_TIMEOUT_S`, padrão 120 s); estouro vira erro com operação e chave | PASS* (parcial) | `src/oracle.rs:26-70,97-122`; testes `tests/oracle.rs:229-259` (padrão, env, valores ruins, valor chega à conexão falsa). **Lacuna L3:** a spec pede "servidor local que aceita e não responde (AWS e Oracle simulados)". O autor testou só a configuração com trait falso; `conectar()` chamar `limitar_chamadas` (M47) e o valor passado a `set_call_timeout` (M48, 2x) sobrevivem. Teste de rede real contra Oracle exigiria Instant Client; a ligação em `conectar` poderia ser testada sem ele (ver proposta) |
| 3d | estouro vira alerta normal | PASS | erro propaga por `Falha::de_geracao`/`Falha::execucao` até `concluir` → `Alertas::falha` (`src/execucao.rs`, `src/ciclo.rs:344-360`); `ErroGeracao::Expurgo` mapeada para a fase "expurgo" (`src/execucao.rs:76`) |
| 4a | `OnFailure=besave-alerta@%n.service` e `TimeoutStartSec=15min` em `besave-ciclo` e `besave-envio` | PASS | `infra/vps/besave-ciclo.service:8,17`, `besave-envio.service:8,16`; teste `tests/unidades_vps.rs:41-52`. M34-M37 mortos |
| 4b | unidade de alerta lê só o `.env`, sem segredo, roda o subcomando | PASS | `infra/vps/besave-alerta@.service:11-12`; teste `tests/unidades_vps.rs:54-75`. M38, M39 mortos |
| 4c | subcomando `--alerta-encerrado`, mesmo bot, mesma repetição (1 envio por variante a cada 2 h), estado separado do envio | PASS | `src/unidade.rs:42-105`, `src/main.rs:61,88`; testes `tests/unidade.rs:41-135` (mensagem, repetição de 2 h na borda `2h-1s`/`2h`, título e estado do envio, arquivo ao lado da trava, unidade desconhecida), `:153-188` (binário real: `--help`, sai 2 sem Telegram, sai 2 com unidade desconhecida). M30-M33 mortos. M29 (valor da constante `VARIANTE`) sobrevive (L4) |
| 4d | `systemd-analyze verify` limpo; alerta real no Telegram | pendente do dono | workflow `worker-arm64.yml:120` inclui a unidade nova |
| 5 | modelo do `.env`: `AWS_ACCESS_KEY_ID`/`SECRET`, `AWS_REGION`, aspas simples, sem `AWS_PROFILE` | PASS | `infra/vps/worker.env.example`; testes `tests/unidades_vps.rs:78-97`, `tests/worker_env_vps.rs` |
| 5b | falha clara "credenciais AWS ausentes" em vez de metadados de instância | PASS* | `src/aws.rs:149-165` (`exigir_credenciais`), `tests/aws_limites.rs:111-134`, `src/ciclo.rs:347-349` (vira código 2). **Lacuna L2b:** a função é testada isolada; `ContextoAws::validar` chamá-la (M45) sobrevive |
| 6 | CONTRATO §7 e MANIFEST §1/§6 na mesma PR | PASS | `docs/CONTRATO.md` §7 (expurgo na janela, em lotes, reativação sai da fila), `docs/MANIFEST.md` §1 (`_estado/expurgo.json`) e §6 passo 7. Versão do contrato não muda (nenhum campo/enum/chave de dado nova) |

### Regras

| # | regra | veredito | evidência |
|---|---|---|---|
| R1 | idempotência (AD-028): sem mudança e fila vazia, só os manifests mudam, sem chamada de remoção | PASS | `src/expurgo.rs:300-302`; `tests/expurgo.rs:391-407` (fora e dentro da janela: gravações `[manifest.prev.json, manifest.json]`, zero `remover_lote`) |
| R2 | o manifest nunca espera o expurgo | PASS | `src/geracao.rs:352` (manifest) antes de `:375` (executar); `tests/expurgo.rs:379-386` (posição de `gravar manifest.json` < primeira remoção), `tests/plano.rs` (todo `Remover` depois do manifest). M23 morto |
| R3 | noite normal cabe; excedente continua e aparece em `expurgo_pendente=` | PASS | `tests/expurgo.rs:188-215`; `src/execucao.rs` (`expurgo_enfileirados/removidos/pendente`, `t_expurgo`), `tests/dry_run.rs` |
| R4 | sem dependência nova | PASS | `Cargo.toml` sem alteração no diff (`git show 2e4e7fb --stat`) |
| R5 | teste de tempo com aquecimento e mediana | PASS | `tests/expurgo.rs:534-554` (1 aquecimento + 5 rodadas, mediana < 5 s); passou no `cargo test` completo sem carga |

### Critério de aceite agregado

| critério | veredito |
|---|---|
| 14.577 ids: nada fora da janela; na janela `≤ ceil(chaves/1000)`; interrupção retoma sem repetir/perder; manifest antes de qualquer remoção | PASS (testes acima; o cenário de 14.577 exercita `FilaExpurgo::executar` direto, o de ciclo completo usa 2-5 ids) |
| órfãs entram na fila uma vez | PASS* (L1) |
| limites: servidor mudo → erro dentro do limite (AWS e Oracle); configuração inteira | PASS no AWS; parcial no Oracle (L3) |
| `OnFailure`: `systemd-analyze verify`, unidade lê só o `.env`, teste do subcomando | PASS (conteúdo e subcomando); `verify` pendente do dono |
| gates `fmt/clippy/test` | PASS; workflow ARM pendente do dono |
| **Real (dono):** noite com a fila cheia e `expurgo_pendente=0`; desativação de dia sai da lista e arquivo só some de madrugada; `TimeoutStartSec` curto → alerta no Telegram | pendente do dono (bloqueia o merge, lição 5) |

## Pontos de atenção pedidos

- **(a) Limite do Oracle sem servidor mudo:** lacuna parcial (L3). AWS tem o teste exigido, com socket real. No Oracle só há configuração; o caminho `conectar` → `limitar_chamadas` → `set_call_timeout` não tem teste (M47, M48 vivos). Não exige Instant Client para corrigir: basta extrair a parte pura (`conectar` recebendo um fechamento/trait de conexão) ou testar `limitar_chamadas` com o fake e um teste de leitura do código. Aceitável para o merge se o dono registrar a lacuna; a spec literal ("servidor local ... Oracle simulado") não é cumprida ao pé da letra.
- **(b) Chave da KVS retida até a janela:** correto e testado. `aplicar_diff` não apaga `retidos` (`src/redirects.rs`), `sincronizar_com_indice` mantém o hash deles no índice, `remover_chaves` apaga da KVS e regrava o índice com ETag/ItemCount novos. M22, M25, M26, M27 mortos (`expurgo_apaga_a_chave_na_kvs`, `apagar_tira_a_chave_da_kvs_e_atualiza_o_indice`: o ciclo seguinte volta em modo `Indice` sem listar a KVS). Efeito colateral aceitável: `/ir/{id}` de oferta expurgada ainda redireciona até a janela (CONTRATO §7 diz isso).
- **(c) Ordem:** fila gravada antes de imagens/chunks/páginas/manifest (`src/geracao.rs:263`, depois `src/site.rs:147` antes das páginas); remoção depois do manifest (`:375`). Provado para o manifest (M23 morto). A parte "antes de qualquer upload" não é provada contra as imagens (M19 vive), mas é inofensiva: se o ciclo cair entre as imagens e a fila, o próximo recalcula os mesmos ids de `ids_anteriores`, porque o índice da KVS só muda depois (`src/geracao.rs:333-334`).
- **(d) Reativação:** `devolver_publicados` roda antes de registrar (`src/geracao.rs:253`), a chave da KVS foi retida (não foi apagada) e a página/imagem não foram apagadas; `tests/expurgo.rs:411-429` prova que nada é apagado e a KVS ainda tem 5413. M08 e M20 mortos. Se a reativação ocorre depois que o id já foi apagado, ele é republicado normalmente (imagem ausente na listagem sobe de novo).
- **(e) Alerta duplicado: confirmado (R1 abaixo).**
- **(f) Falha no expurgo depois do manifest: confirmado impacto (R2 abaixo).**

## Ressalvas de comportamento (decisão do dono)

**R1, alerta duplicado e contagem inflada (média).** `besave-ciclo.service` chama `besave-ciclo`, que sai com código 1 (falha) ou 2 (config) depois de o próprio worker já ter alertado (`src/execucao.rs`, `concluir`: `Alertas::falha`). O systemd marca a unidade como falha e dispara `OnFailure`, que alerta de novo com outra variante (`EncerradoPeloSistema`), portanto a regra de 2 h por variante não deduplica. Resultado: toda falha comum gera 2 mensagens, e `alerta.json` (arquivo compartilhado, `src/alerta.rs:315-318`, `falhas += 1`) conta 2 por ciclo, inflando a mensagem de "recuperado". Não viola "toda parada gera alerta", mas contradiz a intenção da regra de repetição. Opções: `SuccessExitStatus=1 2` nas duas unidades (o worker já alertou nesses casos; `OnFailure` fica para timeout/sinal/falha de início) ou fazer o subcomando só alertar se a unidade tiver `Result` diferente de `exit-code`. Teste sugerido: texto da unidade (padrão de `tests/unidades_vps.rs`) exigindo a opção escolhida.

**R2, `Falha` no expurgo impede `marcar_publicacao_site` e os avisos (média).** O expurgo roda dentro de `gerar` e seu erro sobe como `Err` (`src/geracao.rs:375`); em `src/ciclo.rs:355-356` `marcar_publicacao_site` e `publicar_avisos_ciclo` só rodam se `rodar` for `Ok`. Se o `DeleteObjects` falhar na janela (S3 indisponível, permissão), o manifest já foi publicado, mas: (i) `DT_PUBLICACAO_SITE` das ofertas novas não é gravada, o `dp` delas continua sendo recalculado a cada ciclo (card muda, último chunk regravado, perda de idempotência) e o canal do Telegram (`besave-envio`) não vê as ofertas; (ii) os avisos (BSV-41) não publicam. Dura enquanto o erro durar dentro da janela (até 3 h). A spec tratou como "erro do ciclo, depois do manifest" (tabela de decisões), então não é FAIL, mas o impacto é maior do que o texto sugere. Sugestão: capturar o erro do expurgo em `gerar` (WARN, `expurgo_falhas`, alerta por outro caminho), ou mover a marcação para antes do expurgo. M51 (erro do expurgo engolido) sobrevive: nenhum teste fixa a semântica escolhida.

## Sensor de discriminação: mutantes (51; `CARGO_BUILD_JOBS=1`, lotes de 10, só os binários de teste relevantes; arquivo restaurado com `git checkout -- <arquivo>` após cada um)

Testes usados por grupo: expurgo/geração = `expurgo, ciclo, indice_redirects, plano, geracao`; unidade = `unidade, unidades_vps` (+ `alerta` no M32); AWS = `aws_limites`; Oracle = `oracle`; config = `site, worker_env_vps, expurgo`. Nenhum mutante deixou de compilar ou de aplicar.

| id | mutante | resultado | quem mata / proposta |
|---|---|---|---|
| M01 | janela com fim inclusivo | morto | `janela_e_em_brasilia_...` |
| M02 | janela com início exclusivo | morto | idem |
| M03 | janela que cruza a meia-noite, fim inclusivo | morto | `janela_que_atravessa_a_meia_noite` |
| M04 | idem, início exclusivo | morto | idem |
| M05 | fuso com sinal trocado | morto | janela, meia-noite, `desativacao_de_dia_...` |
| M06 | `ate = enviadas / 2` | morto | `expurgo_muda_hash_e_faixa_vazia_some` (teste de ciclo anterior) |
| M07 | não salvar a fila após cada lote | morto | `interrompido_no_meio_...`, `interrupcao_no_meio_de_um_id_...` |
| M08 | `devolver_publicados` não remove | morto | `oferta_reativada_sai_da_fila_...` |
| M09 | executar sem checar a janela | morto | 3+ testes |
| M10 | `max` ignorado | morto | `na_janela_apaga_em_lotes_...`, tempo |
| M11 | id não sai da fila após apagar | morto | `id_sem_chave_...`, `desativacao_de_dia_...` |
| M12 | reconciliação roda sempre | morto | `indice_valido_nao_lista_...` |
| M13 | `reconciliado` nunca marcado | morto | idem |
| M14 | reconciliação não exclui publicados | morto | `apagar_tira_a_chave_da_kvs_...` |
| M15 | `salvar` sempre grava | morto | `indice_ilegivel_reenvia_tudo_...` etc. |
| M16 | KVS não apagada na janela | morto | `expurgo_apaga_a_chave_na_kvs` |
| M17 | reconciliação ignora a listagem de páginas | **sobreviveu** | Equivalente só no teste atual (índice ausente cobre via `paginas_no_bucket`). Teste: ciclo 1 cria o índice; gravar `oferta/777/index.html` no bucket; zerar `reconciliado` (apagar `expurgo.json`); ciclo 2 deve enfileirar 777 |
| M18 | `ids_de_oferta` ignora `-small` | morto | `orfas_entram_na_fila_uma_vez` |
| M19 | `gerar` não salva a fila antes dos uploads de imagem | **sobreviveu** | `site.rs` salva antes das páginas; a ordem em relação às imagens não é observada. Teste: publicador espião com `FalhaEmImagens` e id saindo; a fila deve estar gravada (ou provar que o recálculo do próximo ciclo basta, caso em que o mutante é equivalente) |
| M20 | `gerar` não devolve reativados | morto | `oferta_reativada_...` |
| M21 | `gerar` não enfileira `ids_anteriores` | **sobreviveu** | Redundante com as saídas de página (`site.rs:144-146`) enquanto toda oferta da KVS tem página no índice. Teste: id na KVS/índice de redirects sem entrada em `paginas.json` (render falhou antes) que sai do conjunto deve entrar na fila |
| M22 | `retidos` vazio no diff da KVS | morto | `expurgo_apaga_a_chave_na_kvs` |
| M23 | expurgo executado antes do manifest | morto | `indice_corrompido_...`, `expurgo_apaga_...`, `plano` |
| M24 | `site.rs` não salva a fila após registrar saídas | **sobreviveu** | Equivalente na prática (gerar já salvou os mesmos ids via `ids_anteriores`); morreria junto com M21 em um teste que isole a saída só de página |
| M25 | índice de redirects perde os retidos | morto | `expurgo_apaga_a_chave_na_kvs` |
| M26 | diff da KVS apaga os retidos | morto | idem |
| M27 | `remover_chaves` não tira do índice | morto | `diff_de_seis_chaves_...` |
| M28 | `LOTE_REMOCAO = 1001` | morto | `lote_exato_usa_ceil_...`, `interrompido_...` |
| M29 | valor de `VARIANTE` trocado | **sobreviveu** | Os testes comparam com a própria constante (espelham a implementação). Teste: assert literal `"erro: EncerradoPeloSistema"` |
| M30 | títulos de ciclo/envio trocados | morto | `ciclo_encerrado_avisa_...` |
| M31 | alerta sem título | morto | `envio_tem_titulo_...` |
| M32 | repetição 2 h → 1 h | morto | `mesma_variante_respeita_janela_de_duas_horas` |
| M33 | estado do envio no mesmo arquivo do ciclo | morto | `estado_fica_ao_lado_da_trava` |
| M34 | `OnFailure` removido do ciclo | morto | `ciclo_e_envio_disparam_...` |
| M35 | `OnFailure` removido do envio | morto | idem |
| M36 | `TimeoutStartSec=20min` no ciclo | morto | idem |
| M37 | idem no envio | morto | idem |
| M38 | unidade de alerta sem `EnvironmentFile` | morto | `unidade_de_alerta_roda_...` |
| M39 | `ExecStart` com `%n` em vez de `%i` | morto | idem |
| M40 | `connect_timeout` trocado | morto | `limites_padrao_e_timeout_config_completos` |
| M41 | `read_timeout` removido | morto | idem |
| M42 | `operation_timeout` removido | morto | idem |
| M43 | `operation_attempt_timeout` removido | morto | idem |
| M44 | `ContextoAws::carregar` sem `timeout_config` | **sobreviveu** | Teste: extrair `carregar_com(limites)` ou expor o `SdkConfig` e afirmar `timeout_config()`; hoje só `com_endpoint` é exercido |
| M45 | `validar` sem `exigir_credenciais` | **sobreviveu** | Teste: `ContextoAws::com_endpoint` sem provedor (ou `validar` com `SdkConfig` sem credenciais) deve dar `CredenciaisAusentes` |
| M46 | `DeleteObjects` ignora `Errors` da resposta parcial | **sobreviveu** | Teste: servidor local que responde 200 com `<Error>` no XML e `remover_lote` deve falhar com a chave |
| M47 | Oracle sem `limitar_chamadas` em `conectar` | **sobreviveu** | Teste: separar `conectar` em `abrir` + `limitar_chamadas` e injetar a conexão falsa, ou teste de inspeção do código |
| M48 | Oracle: limite multiplicado por 2 em `set_call_timeout` | **sobreviveu** | Só aparece com o `impl LimiteDeChamada for Connection` testável (precisa de conexão real); aceitar como limitação do OCI |
| M49 | `ConfigSite::do_env` ignora `BESAVE_EXPURGO_*` | **sobreviveu** | Teste: `ConfigSite::de(env)` com `BESAVE_EXPURGO_JANELA`/`MAX` deve refletir em `.expurgo`; hoje só `ConfigExpurgo::de` é testado (a ligação de env a produção não tem teste) |
| M50 | `PublicadorS3::remover_lote` só o primeiro grupo | **sobreviveu** | Equivalente hoje: `executar` nunca passa mais de 1000 chaves. Teste de unidade com 2500 chaves contra servidor local contaria 3 `POST ?delete` |
| M51 | falha do expurgo engolida em `gerar` | **sobreviveu** | Teste: `gerar` com `falhando_em_remover_lote_na(1)` deve devolver `Err(ErroGeracao::Expurgo)` com o manifest já gravado (fixa a decisão de R2) |

Resumo: 51 aplicados, 38 mortos, 13 sobreviventes. Equivalentes ou redundantes: M19, M24, M50 e M17/M21 (cobertos por caminho paralelo). Lacunas de teste reais: M29, M44, M45, M46, M47, M48, M49, M51 (e M17, M21 como testes do caso real).

## Lacunas e recomendações

Ordem de valor (nenhuma bloqueia, segundo a régua da spec; as duas primeiras merecem decisão do dono):

1. **R1:** alerta duplicado. Decidir `SuccessExitStatus=1 2` ou equivalente.
2. **R2:** falha do expurgo suspende marcação de publicação e avisos. Decidir entre isolar o erro do expurgo e manter como está.
3. **L3/M47/M48:** teste de ligação do limite do Oracle em `conectar`; a spec pediu comportamento, o autor entregou configuração.
4. **M49:** teste de que `ConfigSite::do_env` lê `BESAVE_EXPURGO_*` (sem ele, um typo no nome da variável em produção passa e o expurgo roda na janela padrão sem aviso).
5. **M44/M45/M46:** testes do caminho de produção de AWS (limites em `carregar`, credenciais em `validar`, `Errors` parcial do `DeleteObjects`).
6. **M17/M21/M29:** testes do caso real da reconciliação de páginas, da saída sem página e do texto literal da variante.
7. Observação: `remover_chaves` chama `carregar_base` a cada lote; se o índice de redirects estiver inconsistente, cada lote lista a KVS (lento, mas o ciclo já regrava o índice antes do expurgo, então é improvável).

## Pendente do dono (bloqueia o merge, lição 5)

- Noite com a fila cheia (sobras de 21/10): relatório da manhã com `expurgo_pendente=0`.
- Durante o dia, desativação nova sai da lista na hora e o arquivo só some de madrugada.
- Ciclo encerrado à força (`TimeoutStartSec` curto por 10 min) gera alerta real no Telegram (e verificar o alerta duplicado de R1 numa falha comum).
- `systemd-analyze verify` limpo e workflow ARM verde (`worker-arm64.yml`); copiar `besave-alerta@.service` para `/etc/systemd/system/` e `daemon-reload` (README do worker, passo de instalação).
- Confirmar que a IAM do usuário do worker cobre `s3:DeleteObject` para `DeleteObjects` em lote e a KVS.

## Evidência de execução e segurança

Nenhum arquivo de evidência (log, print, saída) foi adicionado ao repositório; os resultados brutos dos mutantes ficaram no scratchpad da sessão, fora do worktree. `git status` e `git diff` limpos ao final do sensor de mutantes (antes de criar este arquivo).
