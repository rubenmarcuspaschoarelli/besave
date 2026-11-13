# BSV-61 — Validação

## Validation: BSV-61 - PASS

**Result**: PASS (ciclo 2, faixa `c232100..1363d9b`). No ciclo 1 (`c232100..c219043`) o veredito foi
reprovado com 4 de 21 mutantes sobreviventes; o commit `1363d9b` (só testes) fechou as lacunas 1–3 e os
mutantes `c`, `q` e `k` agora morrem. Lacunas 4–6 aceitas pelo coordenador (ver "Ciclo 2" no fim).

- **Quem verificou:** Verifier independente (sub-agente), autor ≠ verificador.
- **Diff:** ciclo 1 `c232100..c219043` (3 commits: `53531b7` worker, `237e087` vps, `c219043` docs);
  ciclo 2 `c232100..1363d9b` (+ `1363d9b` testes).
- **Referência:** `docs/specs/BSV-61.md` (spec do dono); `.specs/features/BSV-61/spec.md` (EARS do autor).
- **Data:** 2026-11-13.

---

## 1. Checagem ancorada na spec

| Critério (spec do dono) | Resultado definido na spec | Código | Teste (`file:line` + asserção) | Resultado |
|---|---|---|---|---|
| Oferta `200` webp → foto 800×800, sem placeholder | origem = site, 800×800, ≠ placeholder | `apps/worker/src/envio/foto.rs:36`, `apps/worker/src/envio/foto.rs:44` | `apps/worker/tests/envio_site.rs:131` `assert_eq!(origem, OrigemFoto::Site(".../ofertas/7.webp"))`; `:137` `dimensions() == (800, 800)`; `:139` pixel central vermelho; `:143` `assert_ne!(jpeg, placeholder)` | ✅ PASS |
| `404` → placeholder + WARN com o motivo | placeholder da área; WARN com `id` e status | `apps/worker/src/envio/site.rs:96`, `apps/worker/src/envio/foto.rs:45` | `apps/worker/tests/envio_site.rs:151`, `:165` `origem == Placeholder(Pets)`, `:166` jpeg == placeholder; `apps/worker/tests/envio_site_log.rs:65`, `:83` WARN contém `id=7` e `status 404` | ✅ PASS |
| Timeout → placeholder + WARN | idem, motivo "timeout" | `apps/worker/src/envio/site.rs:187-189` (cliente real), `:23` | `apps/worker/tests/envio_site.rs:154`; `apps/worker/tests/envio_site_log.rs:66` `timeout de 15 s` | ✅ PASS (pelo fake; o timeout real de 15 s não é afirmado — lacuna 2) |
| Corpo não-imagem → placeholder + WARN | idem, motivo "não é imagem" | `apps/worker/src/envio/foto.rs:39-41` | `apps/worker/tests/envio_site.rs:157-158`; `apps/worker/tests/envio_site_log.rs:67` | ✅ PASS |
| Corpo > 5 MB → placeholder + WARN | idem; limite 5 MB | `apps/worker/src/envio/site.rs:15`, `:99` | `apps/worker/tests/envio_site.rs:159`, `:173-185` (5 MB aceito, 5 MB + 1 recusado), `:174` `MAX_BYTES == 5*1024*1024`; `apps/worker/tests/envio_site_log.rs:68` `maior que 5242880 bytes` | ✅ PASS |
| "O mutante que ignora o tamanho máximo falha" | mutante morto | `apps/worker/src/envio/site.rs:99` | mutantes `a` e `b` mortos (tabela §3) | ✅ PASS |
| Saída 1: "só `200`" | qualquer status ≠ 200 → placeholder | `apps/worker/src/envio/site.rs:96` | `apps/worker/tests/envio_site.rs:151-153` cobre 404/500/301, nenhum 2xx ≠ 200 | ❌ GAP (mutante `c` sobrevive) |
| Saída 1: "Timeout 15 s" | 15 s | `apps/worker/src/envio/site.rs:17` | nenhuma asserção do valor | ❌ GAP (mutante `q` sobrevive) |
| URL: base com e sem `/` → mesma URL, comparada inteira | `https://besave.com.br/img/ofertas/5412.webp` nas duas | `apps/worker/src/envio/site.rs:89-91` | `apps/worker/tests/envio_site.rs:200-206` `assert_eq!(urls, [url_inteira, url_inteira])`; `:207-214` no aviso | ✅ PASS |
| Aviso `DS_IMAGEM = x.jpg` → `GET {base}{id}.jpg` | `https://besave.com.br/img/avisos/3.jpg` | `apps/worker/src/envio/aviso.rs:64`, `:75` | `apps/worker/tests/envio_site.rs:223` URL inteira; `:228` `.WEBP` → `4.webp` | ✅ PASS |
| Aviso: falha → `sendMessage`, sem foto | `None` e método `sendMessage` | `apps/worker/src/envio/rodada.rs:280` | `apps/worker/tests/envio_site.rs:242-244` `== None` (404, timeout, lixo, > 5 MB); `:410` `metodos == ["sendMessage", "sendPhoto"]` | ✅ PASS |
| Precedência: só pasta → lê a pasta; testes de hoje verdes | origem `Oferta(dir/9/9.webp)`, 1 leitura, 0 HTTP | `apps/worker/src/envio/foto.rs:50`, `apps/worker/src/envio/aviso.rs:78` | `apps/worker/tests/envio_site.rs:304-306`, `:338-340`; `envio_foto.rs` e `envio_aviso_selecao.rs` sem alteração e verdes | ✅ PASS |
| Precedência: URL + pasta → só a URL (pasta 0 leituras) | 1 GET, 0 leituras, também quando a URL falha | `apps/worker/src/envio/foto.rs:36`, `apps/worker/src/envio/aviso.rs:64` | `apps/worker/tests/envio_site.rs:279-280`, `:293-294` (URL 404 + pasta: placeholder e 0 leituras), `:334-335`, `:419` | ✅ PASS |
| Precedência: nenhuma → placeholder / sem foto | `Placeholder(area)`; aviso `None` | `apps/worker/src/envio/foto.rs:63`, `apps/worker/src/envio/aviso.rs:84` | `apps/worker/tests/envio_site.rs:316-318`, `:347` | ✅ PASS |
| Saída 3: URL + pasta → INFO no início | INFO | `apps/worker/src/envio/binario.rs:319-333`, `:351-360` | nenhum teste | ⚠️ sem evidência de teste (lacuna 5) |
| Instalador: `envio` instala só as unidades do envio | `besave-envio`, `besave-worker`, 3 unidades; `besave-ciclo` intacto | `infra/vps/instalar.sh:38-40`, `:85-89` | `infra/vps/teste_instalar.sh:174-207` (lista exata de `bin/` e de unidades, `cmp` com o repositório, `papel=envio`) | ✅ PASS |
| Instalador: papel padrão igual | 3 binários, nenhuma unidade | `infra/vps/instalar.sh:28`, `:35-37` | `infra/vps/teste_instalar.sh:88-89`, `:165-172`, `:59` (`sem_unidades` em todo `intacto`) | ✅ PASS |
| Papel desconhecido → código 2 sem `gh` | 2 | `infra/vps/instalar.sh:41` | `infra/vps/teste_instalar.sh:216-223` | ✅ PASS |
| Saída 4: `envio.env.example` com URLs, `TNS_ADMIN`, `BESAVE_LOG_DIR`, `BESAVE_ENVIO_LOCK`, bot sem valor, sem `BESAVE_IMAGENS_DIR` | chaves presentes/ausentes; segredos vazios | `infra/vps/envio.env.example:10-28` | `apps/worker/tests/worker_env_vps.rs:362-386` (presença/ausência), `:388-399` (vazios), `:401-406` (URLs passam em `base`) | ✅ PASS |
| CFG/Regra 2: só HTTPS, só o host, nada além de id + extensão | `http://`, `?`, `#`, `@`, espaço → erro | `apps/worker/src/envio/site.rs:113-126`, `apps/worker/src/envio/binario.rs:348-350` | `apps/worker/tests/envio_site.rs:442-457`; mutantes `g`, `r` mortos | ✅ PASS (código 2 no binário não testado — lacuna 6) |
| Regra 1: sem dependência nova | `Cargo.toml` intocado | — | `git diff c232100..HEAD --stat` não lista `Cargo.toml`/`Cargo.lock` | ✅ PASS |
| Regra 3: falha de imagem não impede o post | placeholder / `sendMessage` | `apps/worker/src/envio/binario.rs:362-372` (cliente que não inicia → `SemHttp`) | `apps/worker/tests/envio_site.rs:406-410` | ✅ PASS |
| Regra 4: sem token, chat_id, IP, host interno | nada | — | varredura do diff (regex de IP, token de bot, `C:\Users`, `chat_id`): 0 ocorrências; `envio.env.example` só com nomes | ✅ PASS |
| Roteiro (Saída 5): Instant Client ARM64 + wallet, binário de `main`, `.env` 600, virada | seção "Inst2 · envio" | `docs/infra/VPS-INSTANCIA-1.md:179`, `:189-190`, `:192`, `:201`, `:212-221` | leitura | ✅ PASS |
| Virada (Saída 6): desligar inst1, só então ligar inst2 | ordem 6.1 → 6.2 | `docs/infra/VPS-INSTANCIA-1.md:213-216` | leitura | ✅ PASS com divergência registrada (§4) |

## 2. Gates

| Gate | Comando | Resultado |
|---|---|---|
| fmt | `cargo fmt --check` (apps/worker) | ok |
| clippy | `cargo clippy --all-targets -- -D warnings` | ok, sem aviso |
| testes | `cargo test` (`CARGO_TARGET_DIR=C:\cargo-target\besave`, `CARGO_BUILD_JOBS=2`) | 582 passaram, 0 falharam, 3 ignorados (nenhum `#[ignore]` novo no diff) |
| instalador | `bash teste_instalar.sh` (cópia LF no WSL) | `ok: teste_instalar` |
| shellcheck | `shellcheck v0.10.0 *.sh` (`instalar.sh`, `teste_instalar.sh`) | exit 0, sem achado |
| `worker-arm64` (CI) | não executável localmente | **pendente** (lição 12: conferir na PR) |

O job `tools` também roda `shellcheck ../vps/*.sh`, mas é `tools/vps/`, que o ticket não toca.

## 3. Sensor de discriminação

Worktree temporário `git worktree add --detach %TEMP%\bsv61-mut HEAD` (Rust) e cópia LF em `mktemp -d` no
WSL (shell). Testes Rust: `--test envio_site --test envio_site_log --test envio_foto --test envio_aviso
--test envio_aviso_selecao --test envio_execucao --test worker_env_vps`. Lotes de 5, 5, 4 + 1.
`git status --porcelain` da árvore real igual antes e depois (vazio); worktree e pasta do WSL removidos.

| # | Mutante | Onde | Resultado | Teste que matou |
|---|---|---|---|---|
| a | ignora o máximo (`if false && corpo.len() > MAX_BYTES`) | `site.rs:99` | morto | `limite_de_5_mb_inclusivo`, `oferta_falhas_viram_placeholder`, `aviso_falha_sem_foto` |
| b | `>` → `>=` | `site.rs:99` | morto | `limite_de_5_mb_inclusivo` |
| c | aceita qualquer 2xx | `site.rs:96` | **sobreviveu** | — |
| d1 | pasta antes da URL na oferta | `foto.rs:36` | morto | `precedencia_oferta`, `execucao_com_urls` |
| d2 | pasta antes da URL no aviso | `aviso.rs:64` | morto | `precedencia_aviso`, `execucao_com_urls` |
| e | `url()` sem tirar a `/` final | `site.rs:90` | morto | `aviso_pela_url`, `precedencia_aviso`, `execucao_com_urls`, … |
| f | extensão fixa `webp` no aviso | `aviso.rs:75` | morto | `aviso_pela_url`, `precedencia_aviso`, `execucao_com_urls` |
| g | `base()` aceita `http://` | `site.rs:117` | morto | `base_validada` |
| h | WARN sem o motivo | `foto.rs:45-48` | morto | `warn_com_id_e_motivo` |
| p | cliente real sem `Limited` (lê o corpo inteiro) | `site.rs:174` | **sobreviveu** | — (resultado igual: `baixar` recusa em `site.rs:99`; muda só a memória) |
| q | `TIMEOUT` 15 → 150 s | `site.rs:17` | **sobreviveu** | — |
| r | `base()` aceita `?` | `site.rs:122` | morto | `base_validada` |
| s | URL do aviso falha → cai na pasta | `aviso.rs:76` | morto | `execucao_com_urls` |
| t | URL da oferta falha → lê a pasta | `foto.rs:45` | morto | `precedencia_oferta` |
| i | papel envio instala também `besave-ciclo` | `instalar.sh:39` | morto | INS-06 "besave-ciclo foi trocado" |
| j | papel padrão copia as unidades | `instalar.sh:37` | morto | INS-01 "instalou unidades" |
| k | papel envio confere só os 2 binários dele, não o artefato inteiro | `instalar.sh:71` | **sobreviveu** | — (o caso "hash errado" é pego pelo `sha256sum -c` de `instalar.sh:75`) |
| l | papel envio sem `besave-alerta@` | `instalar.sh:40` | morto | INS-06 lista de unidades |
| m | papel desconhecido vira `ciclo` | `instalar.sh:41` | morto | INS-07 `--papel x` código 0 |
| n | `VERSAO` sem `papel=` | `instalar.sh:79-80` | morto | INS-01 "VERSAO sem papel=ciclo" |
| o | unidades não copiadas | `instalar.sh:87` | morto | INS-06 lista de unidades |

**Total: 21 mutantes, 17 mortos, 4 sobreviventes (c, p, q, k).**

## 4. Lacunas de precisão da spec e divergências

1. **`systemctl --user` (Saída 6.1)**: as unidades são de sistema (`User=besave`, `/etc/systemd/system`); o
   roteiro usa `sudo systemctl` e registra o motivo (`docs/infra/VPS-INSTANCIA-1.md:224`). Divergência
   correta; a spec deve ser corrigida.
2. **Saída 6.3 "remover o timer da inst1 no instalador do papel padrão"**: o papel padrão nunca instalou
   unidades (`infra/vps/instalar.sh:36-37`); o roteiro interpreta como "tirar `besave-envio` do papel
   padrão (ticket do dono) e apagar as unidades da inst1" (`docs/infra/VPS-INSTANCIA-1.md:217-219`) e o
   autor deixou para depois da virada (spec do autor, Out of Scope). Spec ambígua; decisão do dono.
3. **Saída 4 "só `besave-envio.service`/`.timer` e `besave-alerta@`"**: o papel também instala o binário
   `besave-worker` (`instalar.sh:39`), necessário porque `besave-alerta@.service` executa
   `besave-worker --alerta-encerrado`. Coerente, mas a spec não diz.
4. **"Fakes de HTTP (servidor local ou trait)"**: o autor usou trait; o cliente real `SiteHttps`
   (`apps/worker/src/envio/site.rs:158-191`: timeout, `Limited`, descarte do corpo ≠ 200) não tem teste
   automatizado. Aceitável pela letra da spec; fica para o teste real do dono.

## 5. Lacunas ranqueadas

1. **Mutante `c` — "só `200`" não discriminado** (`apps/worker/src/envio/site.rs:96`). Sugestão: incluir
   `Ok((204, webp(10, 10)))` e `Ok((206, webp(10, 10)))` nos casos de
   `apps/worker/tests/envio_site.rs:150-160` (e um em `aviso_falha_sem_foto`, `:235-240`).
2. **Mutante `q` — "Timeout 15 s" sem asserção** (`apps/worker/src/envio/site.rs:17`). Sugestão:
   `assert_eq!(TIMEOUT, Duration::from_secs(15))` em `envio_site.rs` (como `:174` faz com `MAX_BYTES`).
3. **Mutante `k` — "papel envio confere o artefato inteiro" não discriminado**
   (`infra/vps/instalar.sh:71`). O caso de `infra/vps/teste_instalar.sh:209-214` é pego pelo `sha256sum -c`.
   Sugestão: caso INS-06 com `besave-ciclo` removido de `art/` e de `SHA256SUMS` → código ≠ 0 e `intacto`.
4. **Mutante `p` — cliente real sem limite** (`apps/worker/src/envio/site.rs:174`): resultado igual por
   causa do `baixar`; risco só de memória (1 GB livre a menos numa inst2 de 4 GB). Aceitável como
   equivalente no resultado; se quiser cobrir, extrair a leitura do corpo para uma função genérica sobre
   `http_body::Body` e testar com um corpo em memória de `MAX_BYTES + 1`.
5. **INFO "URL e pasta definidas" sem teste** (`apps/worker/src/envio/binario.rs:319-333`). Baixa.
6. **CFG-01 código 2 no binário sem teste** (`apps/worker/src/envio/binario.rs:348-350`); só `base()` é
   testada. Baixa (`Falha::config` já é coberta em outros tickets).

## 6. Bloqueia o merge (execução real do dono, com o binário da branch na inst2)

1. Job `worker-arm64` verde na PR (lição 12).
2. `besave-envio --sim` na inst2: oferta com `Site("https://…/img/ofertas/{id}.webp")` e aviso com imagem.
3. Virada (inst1 `disable --now`, depois inst2 `enable --now`), um dia de envio normal, inst1 sem posts.
4. `free -m` na inst2 antes e depois da virada.

## 7. Qualidade do código

| Check | Ok? |
|---|---|
| Só o pedido; sem dependência nova | sim |
| Padrões existentes (trait + fake, `thiserror`, sem `unwrap` fora de teste, `tracing`) | sim |
| Só arquivos do escopo (`apps/worker/`, `infra/vps/`, `docs/infra/`, `.specs/`) | sim |
| Testes mapeiam para critérios e afirmam valores (URL inteira, 800×800, origem, contagem de leituras) | sim |
| Asserções enfraquecidas em testes existentes | não (só troca de assinatura `Option<&Path>` → `&Imagens`) |

---

## Ciclo 2 (faixa `c232100..1363d9b`)

Commit `1363d9b` `test(worker): so 200, timeout de 15 s e artefato inteiro no papel envio (BSV-61)`: só
testes (`apps/worker/tests/envio_site.rs`, `infra/vps/teste_instalar.sh`); nenhum código de produção mudou.

### Correções conferidas

| Lacuna | Evidência | Valor da spec |
|---|---|---|
| 1 — "só `200`" | `apps/worker/tests/envio_site.rs:154-155` (`Ok((204, webp))`, `Ok((206, webp))` → placeholder); `apps/worker/tests/envio_site.rs:240-241` (aviso → `None`) | qualquer status ≠ 200 → placeholder / sem foto |
| 2 — "Timeout 15 s" | `apps/worker/tests/envio_site.rs:177` `assert_eq!(TIMEOUT, Duration::from_secs(15))` | 15 s |
| 3 — artefato inteiro no papel envio | `infra/vps/teste_instalar.sh:218-223` (sem `besave-ciclo` em `art/` e em `SHA256SUMS` → código ≠ 0, `intacto`) | o artefato traz os 3 binários (`infra/vps/instalar.sh:20`, `:71`) |

### Gates (ciclo 2)

| Gate | Resultado |
|---|---|
| `cargo fmt --check` | ok |
| `cargo clippy --all-targets -- -D warnings` | ok |
| `cargo test --test envio_site` | 10 passaram, 0 falharam |
| `bash teste_instalar.sh` (WSL, cópia LF) | `ok: teste_instalar` |
| shellcheck v0.10.0 `instalar.sh teste_instalar.sh` | exit 0 |

### Mutantes re-rodados (mesmo isolamento: worktree temporário em `%TEMP%` a partir de `1363d9b`, cópia LF em `mktemp -d` no WSL)

| # | Mutante | Ciclo 1 | Ciclo 2 | Teste que matou |
|---|---|---|---|---|
| c | aceita qualquer 2xx (`site.rs:96`) | sobreviveu | **morto** | `oferta_falhas_viram_placeholder`, `aviso_falha_sem_foto` |
| q | `TIMEOUT` 15 → 150 s (`site.rs:17`) | sobreviveu | **morto** | `limite_de_5_mb_inclusivo` |
| k | papel envio confere só os 2 binários (`instalar.sh:71`) | sobreviveu | **morto** | INS-06 "artefato sem besave-ciclo: código 0" |

**Total acumulado: 21 mutantes, 20 mortos, 1 sobrevivente (`p`, equivalente no resultado — aceito).**
`git status --porcelain` da árvore real igual antes e depois; worktree temporário e pasta do WSL removidos.

### Lacunas aceitas (não bloqueiam)

- 4 — cliente real sem limite (`apps/worker/src/envio/site.rs:174`): resultado igual por `site.rs:99`; coberto pelo teste real do dono.
- 5 — INFO "URL e pasta" sem teste (`apps/worker/src/envio/binario.rs:319-333`).
- 6 — código 2 do binário sem teste (`apps/worker/src/envio/binario.rs:348-350`).

### Veredito final

PASS. Continua bloqueando o merge a execução real do dono (§6): `worker-arm64` verde na PR, `--sim` na inst2,
virada e um dia de envio, `free -m` antes e depois.
