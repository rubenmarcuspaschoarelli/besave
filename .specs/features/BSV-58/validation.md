# BSV-58 Validation

## Validation: BSV-58 - PASS

**Verdict final (iteração 4, autorizada pelo dono)**: PASS ✅.
- O teste `test_cf01_dominio_da_lista_barrado_pausa_pelo_dominio_nao_pelo_host` (`tools/tests/test_redirecionamento_lote.py:389-400`)
  derruba o M45, o único mutante vivo da iteração 3.
- Somando as quatro rodadas, todos os 46 mutantes distintos morrem.
- Todos os critérios de aceite de `docs/specs/BSV-58.md` têm asserção no valor que a spec define.
- Nenhum defeito de produção foi encontrado.
- Continua bloqueando o merge: a execução real do dono na inst1 (os 4 passos da spec).

**Iteração 3** (`b208b26..a7b1ce2`): reprovada pelo sensor, porque o M45 sobreviveu (a chave da pausa no caso
"domínio da lista barrado pelo Cloudflare" não era verificada com exatidão).
**Iteração 2** (`b208b26..232fe49`): FAIL, porque M43 e M44 sobreviveram.
**Iteração 1** (`b208b26..49098ed`): FAIL, porque M14 (SEG-01) e M31 sobreviveram (detalhes abaixo).
**Iteração 2** (`b208b26..232fe49`): o commit `232fe49` mexeu em `main.py` e `test_redirecionamento_lote.py`.

**Date**: 2026-11-06
**Spec**: `docs/specs/BSV-58.md` (fonte) e `.specs/features/BSV-58/spec.md` (EARS)
**Diff range**: `b208b26..a7b1ce2` + `tools/tests/test_redirecionamento_lote.py` não commitado na árvore de trabalho (iteração 4; `git diff --stat` sobre `a7b1ce2`: só esse arquivo, +14 linhas, nenhum código de produção). As iterações 1, 2 e 3 cobriram `..49098ed`, `..232fe49` e `..a7b1ce2`.
**Verifier**: Verifier independente, sub-agente (autor ≠ verificador). Não escreveu o código nem os testes.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 `core/redirecionamento.py` | ✅ Done | - |
| T2 integração no lote e pausa por domínio | ✅ Done | - |
| T3 Cloudflare fora da lista | ✅ Done | ver lacuna 3 (mensagem em domínio da lista) |
| T4 túnel, README, config de exemplo | ✅ Done | - |

---

## Gate Check (job `tools` do CI, lição 21)

**Iteração 4 (`a7b1ce2` + teste na árvore de trabalho)**: `cd tools && python -m pytest -q` **335 passed**, 0 failed, 0 skipped; `ruff check vps/ tests/`: All checks passed. Delta total desde a base: +65 testes. (Escopo da iteração 4 definido pelo dono: só pytest, ruff e M45.)

**Iteração 3 (`a7b1ce2`, só testes em `test_redirecionamento_lote.py`)**: `pytest -q` **334 passed**, 0 failed, 0 skipped; `ruff check vps/ tests/` limpo; `main.py` com 16 violações, iguais às da base; `unittest` do `capture-chat-groups` 15 OK; shellcheck não executado (nenhum `.sh` no diff). Delta total desde a base: +64 testes.

**Iteração 2 (`232fe49`)**: `pytest -q` **333 passed**, 0 failed, 0 skipped; `ruff check vps/ tests/` limpo;
`main.py` com as mesmas 16 violações da base (BLE001×9, S110×5, F401×1, I001×1), nenhuma nova; `unittest` do
`capture-chat-groups` 15 OK; shellcheck não executado (nenhum `.sh` no diff). Delta total desde a base: +63 testes.

Iteração 1 (`49098ed`):

| gate | comando | resultado |
| ---- | ------- | --------- |
| pytest | `cd tools && python -m pytest -q` | **332 passed**, 0 failed, 0 skipped (53 s) |
| unittest (chat-groups, mesmo job) | `cd tools/capture-chat-groups && python -m unittest discover -s tests` | 15 OK |
| ruff do CI | `cd tools && python -m ruff check vps/ tests/` | All checks passed |
| ruff nos módulos novos | `ruff check capture-store-pages/core/redirecionamento.py core/bloqueio.py` | All checks passed |
| ruff `main.py` vs base | `main.py` de `HEAD` contra `git show b208b26:tools/capture-store-pages/main.py` | 16 = 16 violações, mesmos códigos e contagens (BLE001×9, S110×5, F401×1, I001×1); nenhuma nova |
| shellcheck | `shellcheck vps/*.sh` | **não executado**: `shellcheck` não instalado e Docker parado. Nenhum `.sh` mudou no diff (`git diff --stat b208b26..HEAD`), então o gate do CI roda sobre os mesmos arquivos de `develop`. |

- Testes antes: 270; depois: 332; delta +62 (todos em arquivos novos; nenhum teste existente alterado ou apagado).
- Os testes do túnel rodaram de verdade (PowerShell presente; 6 passed com `-rs`, sem skip).

---

## Spec-Anchored Acceptance Criteria

Testes em `tools/tests/`. R = `test_redirecionamento.py`, L = `test_redirecionamento_lote.py`, T = `test_tunel_residencial.py`.

| Critério (spec do dono / EARS) | Resultado definido pela spec | `file:line` + asserção | Resultado |
| --- | --- | --- | --- |
| Domínio (DOM-01): `amzn.promos.link`, `promos.link` casam; `xpromos.link`, `promos.link.exemplo.com`, `amazon.com.br` não | sufixo de rótulo | `R:58-69` parametrizado, `assert rd.ler_config(CFG).dominio(url) == esperado` (inclui porta e caixa, `?u=promos.link`) | ✅ |
| Comando inteiro (CMD-01, lição 14): `--proxy` da config, sem `-L`, `--max-time`, URL argumento único | lista exata | `R:77-81` `assert curl.comandos == [["curl","-sS","-o",os.devnull,"-w","%{http_code} %{redirect_url}","--proxy",PROXY,"--max-time","20","--url",CURTO]]` e `not kwargs.get("shell")`; `R:88-89` URL com espaço/`-`/`;` em um argumento e timeout 7 da config | ✅ |
| 302 → Amazon: destino devolvido, página aberta pelo navegador é a da Amazon, sem proxy (RES-01) | destino; navegador abre só a loja | `R:96` `== (AMAZON, None)`; `L:156-161` `status[1]=="ok"`, `visitas == [amz(1)]` (navegador nunca abriu o encurtador), `"redirect (proxy) -> amazon" in out`, `"oracle=ok"`, `ponteiro == [1]` | ✅ (o "sem proxy" do navegador é por construção: `core/browser.py` não mudou e não tem `proxy`; o navegador falso não observa proxy) |
| 302 → domínio da lista → 302 → ML: dois saltos pelo proxy (RES-02) | 2 chamadas pelo proxy | `R:103-105` `== (ML, None)`, URLs `[CURTO, meio]`, `--proxy` == PROXY em todas; `L:169` `visitas == [ml]` e 2 comandos | ✅ |
| `max_saltos` esgotado → `sem_redirect` | `sem_redirect` | `R:111-112` com `max_saltos=2`: `== (None,"sem_redirect")` e `len(curl.comandos) == 2` | ✅ |
| 200 sem Location / código inesperado → `sem_redirect` | `sem_redirect` | `R:115-118` (`200`, `404`, `302` sem destino, `500`) | ✅ |
| `sem_redirect` → fluxo de hoje (`_resolver_ponte`) (RES-03) | navegador decide | `L:178` `visitas[0] == curto(1)` e `ok`; `L:184` página comum → `loja_desconhecida` | ✅ |
| Falha: curl sem conexão com o proxy → `retida(0)`, nada em `OFERTA`, ponteiro travado (FAL-01) | `proxy_indisponivel` → retida | `R:123-126` exit 5/7/97/28 → `proxy_indisponivel`; `R:129-136` curl ausente / `TimeoutExpired`; `L:202-210` `status[1]=="redirecionamento_indisponivel"`, `db.erros == []`, `db.ofertas == [2]`, `lojas.ponteiro == []`, `"oracle=retida(0)"` | ✅ |
| 403 pelo proxy → `retida(0)` (FAL-02), também 429/503 | `bloqueado` → retida | `R:145-148` 403/429/503 → `"bloqueado"`; `R:151-154` no 2º salto; `L:202` parametrizado com `(0,"403 ")`, `429`, `503` | ✅ |
| Regra 2: sem proxy configurado e domínio na lista → retida + aviso, sem curl | retida | `R:139-142` `proxy_indisponivel` e `comandos == []`; `L:213-217` retida, `visitas == []`, `db.erros == []` | ✅ |
| 3 seguidas → pausa por domínio + 1 aviso (PAU-01) | 1 Telegram com a frase da spec | `L:226-231` 3 retidas, linha 5 `loja_pausada` sem curl (`len(comandos) == 3`), `len(enviados) == 1`, `"promos.link em pausa: túnel residencial fora? 4 linha(s) retida(s)" in enviados[0]`, Amazon segue `ok` | ✅ |
| Linhas do domínio em pausa → `pausada(0)` sem curl; monitor não relê em laço | `pausada(0)` | `L:245` `"oracle=pausada(0)"`; `L:266` `lotes == [] and esperas == [180]` | ✅ |
| Volta → "voltou" e a linha retida processada | voltou + ok | `L:236-237` `status[5]=="ok"`, `db.capturas == [5]`, `"voltou" in enviados[1]` e `"promos.link"` | ✅ |
| Lembrete de 6 h | existe | iteração 2: `L:297` `"túnel residencial fora?" in amb.enviados[1] and "continua em pausa" in amb.enviados[1]` (M31 morto). Iteração 3: lembrete do Cloudflare em `L:340-343` `"continua bloqueado pelo Cloudflare" in amb.enviados[1]` e `"incluir em redirecionamento.dominios?" in amb.enviados[1]` (M44, M46 mortos) | ✅ |
| Sem config: bloco ausente → fluxo de hoje (mutante que sempre usa proxy falha) (CFG-01) | sem curl | `R:45-48` 4 formas → `None`; `L:189-197` `curl.comandos == []`, `visitas[0] == curto(1)`, `ok`; mutantes M7 e M36 mortos | ✅ |
| Cloudflare fora da lista → `retida(0)` com a sugestão no log, não `'9'` (CF-01) | retida + frase | `L:318-327` (título+texto, só título, só texto): `redirecionamento_indisponivel`, `db.erros == []`, `ponteiro == []`, `"achadinhos.exemplo.com.br bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?" in out`, `"oracle=retida(0)"` | ✅ |
| Domínio da lista barrado pelo Cloudflare (correção 3, fora do texto da spec) | retida, sem sugerir incluir | `L:366-372` `status[1]=="redirecionamento_indisponivel"`, `db.erros == []`, `"incluir em redirecionamento.dominios?" not in out` (log). Iteração 3: `L:379-387` 3 linhas barradas → `len(enviados) == 1`, `"promos.link em pausa: túnel residencial fora?" in enviados[0]`, `"incluir em" not in enviados[0]` (M43 morto). Iteração 4: `L:389-400` `assert amb.pausa.em_pausa("promos.link")`; 4ª linha `https://ml.promos.link/REDACTED4` → `status[4] == "loja_pausada"`, `db.erros == [] and db.capturas == []`, nenhum `curl` novo e `visitas == []` (M45 morto) | ✅ |
| Cloudflare 3 seguidas → pausa + Telegram com a frase | 1 aviso | `L:333-337` `status[4]=="loja_pausada"`, `len(enviados) == 1`, frase no aviso; `L:353-361` voltou | ✅ |
| Página comum de domínio desconhecido continua `'9' loja_desconhecida` (CF-02, discrimina) | `'9'` | `L:347-350` `status[1]=="loja_desconhecida"` e `db.erros == [(1,"loja_desconhecida")]` | ✅ |
| Segredo: nenhuma saída contém o valor de `proxy` (SEG-01) | nunca | `R:159-161` `descrever` sem PROXY/1080; `L:291-305` stdout+stderr+Telegram (falha, pausa, lembrete, voltou, sucesso, log do monitor) sem `PROXY`, `1080`, `127.0.0.1` | ✅ iteração 2: `L:293` `curl.respostas[curto(0)] = (0, "200 ")` põe o ramo `sem_redirect` no cenário; M14 morto |
| Regra 3: não regravar `DS_URL_ORIGEM` | não muda | Leitura do código: nenhuma escrita de `DS_URL_ORIGEM` em `capture-store-pages` (só leitura em `main.py:333` e `core/oracle_db.py:94`); `out['url']` continua a original (`main.py:531-547` só troca a variável local `url`) | ✅ por leitura (sem teste; mutante não aplicável sem criar escrita nova) |
| Regra 1: só o redirect pelo proxy | só curl | `L:157` navegador só abre a loja; `L:197` nada vai ao curl sem a config; `L:327` Cloudflare fora da lista não chama curl | ✅ |
| Túnel (TUN-01): `ssh -N -R 127.0.0.1:1080`, `ServerAliveInterval`, `ExitOnForwardFailure`, reconecta em 30 s, log sem IP/chave, de parâmetro ou ambiente | comando inteiro | `T:45-52` `chamadas == [esperado(chave)] * 3` (lista inteira) e log sem destino/chave; `T:55-58` `"nova tentativa em 30 s"`; `T:61-66` ambiente; `T:69-74` sem destino → exit 2 sem ssh | ✅ |
| Regra 4 / regra 11: sem IP, host, chave, usuário no repo | nada | `T:77-83` sem IPv4 ≠ 127.0.0.1 nem `PRIVATE KEY` em script, README e config; varredura do diff pelo Verifier: só `203.0.113.9` (TEST-NET-3, documentação) nos testes e `ubuntu@<ip-da-inst1>` (placeholder) no README | ✅ |
| README (DOC-01) e config de exemplo | conteúdo | `T:86-96` termos obrigatórios e bloco `redirecionamento` com os valores da spec | ✅ |
| Gates `pytest`, ruff, shellcheck | verdes | ver Gate Check | ✅ (shellcheck não executado; nenhum `.sh` mudou) |
| Real na inst1 (dono) | 4 passos | - | ⏭️ Fora do Verifier: **bloqueia o merge** |

**Status (iteração 4)**: todos os critérios da spec do dono e as três correções do autor cobertos com asserção exata.

---

## Discrimination Sensor

Worktree temporário (`git worktree add --detach` em pasta de rascunho fora do repo), um mutante por vez, só os testes relevantes (`test_redirecionamento*.py`, `test_tunel_residencial.py`, `test_pausa_lojas.py`, `test_bloqueio_lojas.py`), lotes de 5 a 16. Worktree removido no fim; `git status --porcelain` da árvore real igual ao de antes (vazio).

| # | Arquivo | Mutante | Resultado | Teste que matou |
| - | ------- | ------- | --------- | --------------- |
| M1 | `core/redirecionamento.py:44` | `endswith(dominio)` sem o ponto | ✅ morto | `R::test_dom01_sufixo_de_rotulo[xpromos.link]` |
| M2 | `redirecionamento.py:93` | `-L` no comando | ✅ morto | `R::test_cmd01_comando_inteiro` |
| M3 | `redirecionamento.py:109` | curl exit≠0 → `sem_redirect` | ✅ morto | `R::test_fal01_curl_sem_conexao_com_o_proxy` |
| M4 | `redirecionamento.py:20` | só 403 bloqueia (sem 429/503) | ✅ morto | `R::test_fal02_bloqueado_pelo_proxy[429]` |
| M5 | `redirecionamento.py:103` | `max_saltos + 1` | ✅ morto | `R::test_res02_max_saltos_esgotado_e_sem_redirect` |
| M6 | `redirecionamento.py:103` | `max_saltos - 1` | ✅ morto | idem |
| M7 | `main.py:463` | `_redirecionar` ignora a config (domínio e proxy fixos) | ✅ morto | `L::test_cfg01_sem_bloco_e_o_fluxo_de_hoje[None]` |
| M8 | `main.py:72` | `redirecionamento_indisponivel` fora de `STATUS_RETER` | ✅ morto | `L::test_fal_linha_retida_nada_gravado_e_ponteiro_travado` |
| M9 | `main.py:478` | sem `registrar_bloqueio` no redirect | ✅ morto | `L::test_pau01_tres_falhas_...` |
| M10 | `main.py:459-462` | não checa pausa antes do curl | ✅ morto | `L::test_pau01_tres_falhas_...` |
| M11 | `main.py:941` | `_sem_lojas_em_pausa` ignora `redir` | ✅ morto | `L::test_pau01_monitor_nao_rele_em_laco_...` |
| M12 | `redirecionamento.py:132` | Cloudflare só pelo título | ✅ morto | `L::test_cf01_..._retem_e_sugere[SO_TEXTO]` |
| M13 | `main.py:559` | Cloudflare não retém (vira `'9'`) | ✅ morto | `L::test_cf01_..._retem_e_sugere` |
| M14 | `main.py:473` | imprime o proxy no log do `sem_redirect` | ❌ **sobreviveu** | - |
| M15 | `vps/tunel_residencial.ps1:58` | sem `ExitOnForwardFailure` | ✅ morto | `T::test_tun01_reconecta_com_o_comando_inteiro_...` |
| M16 | `tunel_residencial.ps1:75` | sem laço (1 tentativa) | ✅ morto | idem |
| M17 | `tunel_residencial.ps1:59` | `-R 1080` sem `127.0.0.1` | ✅ morto | idem |
| M18 | `redirecionamento.py:87` | `descrever` mostra o proxy | ✅ morto | `R::test_seg01_descricao_da_config_nao_traz_o_proxy` |
| M19 | `main.py:467` | sucesso do redirect não zera a pausa | ✅ morto | `L::test_pau01_tres_falhas_...` (sem "voltou") |
| M20 | `main.py:470` | destino resolvido mas navegador abre o encurtador | ✅ morto | `L::test_res01_302_amazon_pelo_proxy_e_pagina_aberta_direto` |
| M21 | `redirecionamento.py:99` | sem proxy → `sem_redirect` (viraria `'9'`) | ✅ morto | `R::test_fal01_sem_proxy_configurado_nem_chama_o_curl` |
| M22 | `redirecionamento.py:107` | exceção do subprocess → `sem_redirect` | ✅ morto | `R::test_fal01_curl_ausente_ou_travado` |
| M23 | `redirecionamento.py:76` | `dominios` vazio liga o módulo | ✅ morto | `R::test_cfg01_bloco_ausente_ou_sem_dominios_desliga` |
| M24 | `redirecionamento.py:105` | `shell=True` | ✅ morto | `R::test_cmd01_comando_inteiro` |
| M25 | `redirecionamento.py:117` | 403 → `sem_redirect` | ✅ morto | `R::test_fal02_bloqueado_pelo_proxy[403]` |
| M26 | `main.py:558` | Cloudflare não registra pausa | ✅ morto | `L::test_cf01_tres_seguidas_...` |
| M27 | `main.py:550` | ponte comum não zera a pausa | ✅ morto | `L::test_cf01_dominio_que_volta_a_responder_avisa_voltou` |
| M28 | `core/bloqueio.py:88` | aviso de redirecionamento cai no texto genérico | ✅ morto | `L::test_pau01_tres_falhas_...` |
| M29 | `redirecionamento.py:94` | URL posicional, sem `--url` | ✅ morto | `R::test_cmd01_comando_inteiro` |
| M30 | `redirecionamento.py:94` | `--max-time` ignora a config | ✅ morto | `R::test_cmd01_url_com_espaco_e_traco_...` |
| M31 | `core/bloqueio.py:120` | lembrete de 6 h do redirecionamento com texto genérico ("VNC") | ❌ **sobreviveu** | - (spec-precision gap) |
| M32 | `redirecionamento.py:121` | aceita destino ainda da lista (sem 2º salto) | ✅ morto | `R::test_res02_dois_saltos_pelo_proxy_ate_o_ml` |
| M33 | `main.py:475` | imprime o proxy na linha retida | ✅ morto | `L::test_seg01_proxy_nunca_aparece_na_saida` |
| M34 | `redirecionamento.py:109` | imprime o stderr do curl (traz `127.0.0.1:1080`) | ✅ morto | idem |
| M35 | `redirecionamento.py:130` | Cloudflare só pelo texto | ✅ morto | `L::test_cf01_..._retem_e_sugere[SO_TITULO]` |
| M36 | `main.py:493` | `_processar_lote` sem config liga o proxy por padrão | ✅ morto | `L::test_cfg01_sem_bloco_e_o_fluxo_de_hoje[None]` |
| M37 | `main.py:476` | restantes do domínio fora da contagem | ✅ morto | `L::test_pau01_tres_falhas_...` ("4 linha(s)") |
| M38 | `main.py:451` | chave da pausa = host, sem o domínio da lista | ✅ morto | idem |
| M39 | `tunel_residencial.ps1:24` | espera padrão 10 s | ✅ morto | `T::test_tun01_espera_padrao_de_30_s` |
| M40 | `tunel_residencial.ps1:57` | sem `ServerAliveInterval` | ✅ morto | `T::test_tun01_reconecta_...` |
| M41 | `tunel_residencial.ps1:70` | log com o destino | ✅ morto | idem |

| M14 (it. 2) | `main.py:473` | imprime o proxy no log do `sem_redirect` | ✅ morto | `L::test_seg01_proxy_nunca_aparece_na_saida` |
| M31 (it. 2) | `core/bloqueio.py:120` | lembrete do túnel com texto genérico | ✅ morto | `L::test_seg01_proxy_nunca_aparece_na_saida` |
| M42 (it. 2) | `main.py:556` | domínio da lista barrado volta a sugerir incluir (log) | ✅ morto | `L::test_cf01_dominio_ja_na_lista_barrado_nao_sugere_incluir` |
| M43 (it. 2) | `main.py:565` | domínio da lista barrado registra a pausa com motivo `cloudflare` (Telegram sugeriria incluir) | ❌ **sobreviveu** | - |
| M44 (it. 2) | `core/bloqueio.py:125` | lembrete do Cloudflare com texto genérico ("VNC") | ❌ **sobreviveu** | - (spec-precision gap) |

**Sensor depth**: expandido. Iteração 1: 41 mutantes sobre `49098ed`. Iteração 2: worktree temporário em `232fe49`
fora do repo (removido; árvore real só com o `validation.md`), M14, M31 e três mutantes novos.
| M43 (it. 3) | `main.py:565` | motivo `cloudflare` para domínio da lista | ✅ morto | `L::test_cf01_dominio_ja_na_lista_barrado_tres_vezes_avisa_tunel_sem_sugerir` |
| M44 (it. 3) | `core/bloqueio.py:125` | lembrete do Cloudflare com texto genérico | ✅ morto | `L::test_cf01_tres_seguidas_pausam_o_dominio_e_avisam_com_a_sugestao` |
| M45 (it. 3) | `main.py:549` | chave da pausa do Cloudflare = host inteiro (`amzn.promos.link`), não o domínio da lista | ❌ **sobreviveu** | - |
| M46 (it. 3) | `core/bloqueio.py:126-128` | lembrete do Cloudflare sem "incluir em redirecionamento.dominios?" | ✅ morto | `L::test_cf01_tres_seguidas_pausam_o_dominio_e_avisam_com_a_sugestao` |

| M45 (it. 4) | `main.py:549` | chave da pausa do Cloudflare = host inteiro | ✅ morto | `L::test_cf01_dominio_da_lista_barrado_pausa_pelo_dominio_nao_pelo_host` |

**Prova do M45 (iteração 4)**:
- Worktree temporário em `a7b1ce2`, fora do repo, com o `test_redirecionamento_lote.py` copiado da árvore real.
- **Sem o mutante**, o teste novo passa: `1 passed`.
- **Com o M45** (`chave = redirecionamento.host_sem_www(url) or _chave_pausa(url, redir)` em `main.py:549`), o teste
  falha: `1 failed, 58 passed` no lote relevante, com saída (redigida):

```
>       assert amb.pausa.em_pausa("promos.link")
E       AssertionError: assert False
E        +  where False = em_pausa('promos.link')
FAILED tests/test_redirecionamento_lote.py::test_cf01_dominio_da_lista_barrado_pausa_pelo_dominio_nao_pelo_host
```

- Depois de restaurado, o lote relevante volta a `101 passed`.
- Worktree removido; a árvore real ficou só com o teste do autor (`M`) e este `validation.md` (`??`).

**Result**: iteração 1: 39/41; iteração 2: 3/5; iteração 3: 3/4; iteração 4: 1/1. Total: 46/46 mutantes distintos mortos.
Iteração 3 num worktree temporário em `a7b1ce2`, fora do repo, removido no fim; a árvore real só tem o `validation.md`.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / sem scope creep | ✅ (`-Ssh`/`-MaxTentativas` no `.ps1` só para teste, declarados na spec EARS) |
| Surgical changes / só a pasta da spec | ✅ `tools/capture-store-pages/`, `tools/vps/`, `tools/tests/` |
| Sem dependência nova | ✅ stdlib + `curl`; `subprocess` sem `shell=True` |
| Matches patterns | ✅ reaproveita `PausaLojas`, `STATUS_RETER`, `_Cronometro` |
| Spec-anchored outcome check | ⚠️ ver SEG-01 e lembrete |
| Every test maps to a requirement | ✅ cabeçalhos por ID (CFG/DOM/CMD/RES/FAL/PAU/CF/SEG/TUN/DOC) |
| Guidelines: `CLAUDE.md`, `tools/capture-store-pages/CLAUDE.md` | ✅ config nova refletida em `config.example.json` com `_obs` |

---

## Lacunas (iteração 4)

Nenhuma lacuna bloqueante. Ficam só pontos informativos:
- "Navegador sem proxy": provado pela construção do código (`core/browser.py` sem mudança e sem `proxy`).
- `shellcheck`: não executado localmente (sem `shellcheck` e sem Docker); nenhum `.sh` no diff, e o CI roda.
- Log do `.ps1`: diz "nova tentativa" também na última tentativa (só com `-MaxTentativas`, em teste).
- O teste da iteração 4 ainda não está commitado: o PASS vale para `a7b1ce2` + esse arquivo.

Fechadas: M14, M31, M42, M43, M44, M46 e M45.

---

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| CFG-01, DOM-01, CMD-01, RES-01, RES-02, RES-03, FAL-01, FAL-02, CF-01, CF-02, TUN-01, DOC-01 | ✅ Verified |
| PAU-01 | ✅ Verified (lembrete: spec-precision gap) |
| SEG-01 | ✅ Verified (iteração 2) |
| Correção 3 (domínio da lista barrado pelo Cloudflare) | ✅ Verified (iteração 4) |

---

## Propostas de lição (para o dono)

- Teste de "segredo nunca aparece na saída" precisa percorrer **todos** os ramos que imprimem; um mutante por `print` novo mostra o ramo esquecido (BSV-58: M14).
- Mensagem nova de aviso tem texto asserido também no lembrete, não só no primeiro aviso (BSV-58: M31, M44).
- Correção que muda log **e** aviso precisa de teste nos dois; um teste de uma linha só não chega à pausa (BSV-58: M43).
- Asserção por trecho (`in`) de um nome que é sufixo de outro (`promos.link` em `amzn.promos.link`) não distingue os dois; verificar o começo da mensagem ou o estado (BSV-58: M45).

## Summary

**Overall**: ✅ Ready para a PR (iteração 4), dependendo do commit do teste novo e da execução real do dono.
**Spec-anchored check**: todos os critérios da spec do dono com asserção no valor que ela define
**Sensor**: 46/46 mutantes distintos mortos (iterações 1 a 4)
**Gate**: 335 passed, 0 failed; ruff limpo; shellcheck não executado (sem `.sh` no diff)
**Bloqueia o merge também**: teste real do dono na inst1 (4 passos da spec).
