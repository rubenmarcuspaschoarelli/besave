# BSV-60 Validation

**Verificador:** Verifier sub-agente independente (autor != verificador), sessão separada da implementação. Não editou o worktree real; sensor rodado em worktree git descartável no scratchpad (removido com `git worktree remove --force` + `prune`; `git status --porcelain` do real igual ao baseline nas duas iterações).
**Data:** 2026-11-13
**Diff range:** `git diff origin/develop..1810d9a` (`origin/develop` é ancestral). Commits: `89e613c` (correção, testes, README/exemplo) e `1810d9a` (fecha G1, só teste). Arquivos: `tools/capture-store-pages/core/estado.py`, `tools/capture-store-pages/README.md`, `tools/capture-store-pages/conf/config.example.json`, `tools/tests/test_config_permissao.py`, `.specs/features/BSV-60/spec.md`.

## Validation

**Result:** PASS (iteração 2, HEAD `1810d9a`)

Todos os critérios de aceite de `docs/specs/BSV-60.md` alcançáveis pelo verificador estão cobertos com evidência. A lacuna G1 da iteração 1 está **fechada**: o mutante e2 morre. Sensor da iteração 2: 15 mutantes, **12 mortos, 3 sobreviventes, todos equivalentes**.

**Bloqueia o merge (dono):** (1) confirmação em Linux pelo CI (job `tools`, lição 12: conferir que o job rodou, com os 9 testes de `test_config_permissao.py` executados e não pulados); (2) teste real na inst1 com a branch: `chmod 600 conf/config.json`, reiniciar as lojas, esperar 3 linhas processadas, `stat -c %a conf/config.json` = `600`.

## Histórico

- **Iteração 1 (HEAD `89e613c`):** PASS com uma lacuna menor G1 (mutante e2 sobrevivia: sem `os.remove` do `.tmp` velho e sem `O_EXCL`, o `.tmp` `0o666` era reaberto e recebia a senha antes do chmod; o teste só olhava o modo no `os.replace`). Sensor: 15 mutantes, 11 mortos, 4 sobreviventes (e2 + 3 equivalentes).
- **Iteração 2 (HEAD `1810d9a`):** commit só de teste. Nova fixture `modos_na_abertura` (`tools/tests/test_config_permissao.py:73-86`, espião em `os.open` que lê o modo do descritor com `fstat`), usada em `test_tmp_nunca_mais_aberto_que_o_original` (`:89-97`) e em `test_tmp_velho_aberto_nao_vaza` (`:100-111`), cujo `.tmp` velho agora é maior que o JSON novo (`:105`) e exige `modos_na_abertura == [0o600]` (`:108`). Nenhuma asserção removida ou afrouxada: a do parametrizado mudou só de variável local (`criados`) para a fixture; o `monkeypatch.undo()` explícito saiu porque a fixture restaura no teardown. Código de produção inalterado desde `89e613c`.

## Ambiente

- Testes de modo POSIX: **rodados no WSL (Ubuntu 26.04.1 LTS), Python 3.14.4, pytest 9.0.2**, `tmp_path` em `/tmp` (ext4, não DrvFs). 9 coletados, 9 passaram, **nenhum pulado**.
- Gates no Windows (Python do host): suíte inteira de `tools/` e `ruff`.

Saída no WSL, iteração 2, HEAD `1810d9a` (redigida):

```
platform linux -- Python 3.14.4, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python3
rootdir: REDACTED/rub-49-bsv-60/tools
configfile: pytest.ini
plugins: typeguard-4.4.4
collecting ... collected 9 items

tests/test_config_permissao.py::test_mantem_600_com_umask_002 PASSED     [ 11%]
tests/test_config_permissao.py::test_mantem_640 PASSED                   [ 22%]
tests/test_config_permissao.py::test_tmp_nunca_mais_aberto_que_o_original[384] PASSED [ 33%]
tests/test_config_permissao.py::test_tmp_nunca_mais_aberto_que_o_original[416] PASSED [ 44%]
tests/test_config_permissao.py::test_tmp_nunca_mais_aberto_que_o_original[256] PASSED [ 55%]
tests/test_config_permissao.py::test_tmp_velho_aberto_nao_vaza PASSED    [ 66%]
tests/test_config_permissao.py::test_original_sumiu_ao_obter_modo_usa_600 PASSED [ 77%]
tests/test_config_permissao.py::test_falha_na_escrita_deixa_original_intacto PASSED [ 88%]
tests/test_config_permissao.py::test_grava_em_qualquer_plataforma PASSED [100%]

============================== 9 passed in 0.33s ===============================
```

(`[384]`, `[416]`, `[256]` = `0o600`, `0o640`, `0o400`.)

## Gates (rodados pelo verificador, de `tools/`, em `1810d9a`)

| Gate | Resultado |
| --- | --- |
| `python -m pytest -q -p no:cacheprovider` (Windows) | **487 passed, 86 skipped** (9,1 s). Skips: 7 de `test_config_permissao.py` (modo POSIX, esperado; os 2 sem modo rodaram) e 79 de testes bash (`bash indisponivel` neste ambiente: `test_iniciar_captura` 33, `test_parar_scope` 6, `test_reinicio_whatsapp` 13, `test_scope_lojas` 6, `test_scope_whatsapp` 9, `test_vnc` 12), sem relação com a BSV-60 (nenhum `.sh` no diff). Total coletado 573 = base + 9 novos. |
| `python -m ruff check vps/ tests/` | All checks passed! |
| WSL: `python3 -m pytest -v -rs tests/test_config_permissao.py` | 9 passed, 0 skipped |

Integridade de testes: o diff só acrescenta `tools/tests/test_config_permissao.py`; nenhum teste removido ou afrouxado.

## Spec-anchored: critério de aceite de `docs/specs/BSV-60.md`

Código: `tools/capture-store-pages/core/estado.py` (E). Testes: `tools/tests/test_config_permissao.py` (T), linhas de `1810d9a`.

| Critério | Esperado (spec) | Teste (file:line + asserção) | Código | Resultado |
| --- | --- | --- | --- | --- |
| Mantém 600 | config `600`, umask `002` → `600` e chave nova gravada | T:56-62 `_modo(caminho) == 0o600`, `ultimo_id_processado == 42`, `senha == "s"` (resto preservado); fixture umask T:16-20 | E:166, 174, 179-181 | PASS. Nota: com o `.tmp` nascendo em `0o600`, o mutante sem `chmod` (a) passa neste teste e morre pelos de `640`/`400` (T:66, T:89); a frase da spec "o mutante sem o chmod falha" vale para a suíte, não para este caso isolado. |
| Mantém outro modo | `640` → `640` (discrimina "força 600") | T:66-70 `_modo == 0o640`; T:89-97 parametrizado `600/640/400`, `modos_no_replace == [original]` | E:166, 180 | PASS (mutante b morto) |
| Sem janela aberta | `.tmp` nunca com bits g/o além dos do original, inclusive no `os.replace` | T:89-97: `modos_na_abertura == [0o600]` (T:95), `modos_no_replace == [original]` (T:96), `m & ~original & 0o077 == 0` (T:97); T:100-111 `.tmp` velho `0o666` e maior que o JSON: `modos_na_abertura == [0o600]` (T:108), `modos_no_replace == [0o600]` (T:109), config final parseável com a chave nova (T:111) | E:170-174 (remove `.tmp` velho, `O_EXCL`, `0o600`), E:179-181 (chmod antes do replace) | PASS (mutantes c1, c2, d, e1, **e2**, f mortos) |
| Original inexistente → 600 | fallback `600` | T:114-128 `os.stat` falso → `modos_no_replace == [0o600]`, `_modo == 0o600` | E:165-168 | PASS (mutante g morto) |
| Atomicidade | falha na escrita → original intacto, com o modo original | T:131-144 `json.dump` quebrado com `ENOSPC` → texto igual, `.tmp` inexistente, modo `0o600` | E:169-187 (`.tmp` + `fsync` E:178 + `os.replace` E:181; `os.remove(tmp)` no except E:184-187) | PASS (mutantes h, i mortos). O modo original do teste é `600`, igual ao de criação; nenhum mutante plausível mexe no original numa falha. |
| Windows sem quebra | sem chmod, grava como antes | T:147-154 roda em todas as plataformas (rodou no Windows: grava duas vezes, sem `.tmp`, `os.access(W_OK)`); T:131 também roda no Windows | E:179 `if os.name != 'nt'` | PASS (mutante j morto no Linux; no Windows a suíte passou) |
| README / exemplo | uma linha: `600` no Linux, robô mantém o modo | — (documentação) | `tools/capture-store-pages/README.md:92-93`; `tools/capture-store-pages/conf/config.example.json:2` (`"_permissao"`) | PASS |
| Regra 1: atomicidade de hoje | `.tmp` + `fsync` + `os.replace` | T:131-144 | E:164, 178, 181 | PASS (fsync só por leitura de código; mutante m equivalente para teste) |
| Regra 2: sem dependência nova | — | — | E:16 `import stat` (stdlib); diff não toca `requirements*`/`pyproject*` | PASS |
| Regra 2: sem mudar umask do processo | — | `grep umask` em `capture-store-pages/*.py`, `core/*.py`: só o comentário E:163; a umask do teste é restaurada pela fixture T:16-20 | — | PASS |
| Gates | pytest + ruff | tabela acima | — | PASS |
| Real (dono) | `stat -c %a` = `600` após 3 linhas | — | — | **NÃO EXECUTADO: bloqueia o merge** |

### Requisitos EARS de `.specs/features/BSV-60/spec.md`

| ID | Evidência | Resultado |
| --- | --- | --- |
| PERM-01 | T:56-62 | PASS |
| PERM-02 | T:66-70, T:89-97 | PASS |
| PERM-03 | T:89-97, T:100-111 | PASS |
| PERM-04 | T:114-128 | PASS |
| PERM-05 | T:131-144 | PASS |
| PERM-06 | T:147-154; marca `so_posix` T:13 | PASS |
| PERM-07 | README.md:92-93, config.example.json:2 | PASS |

## Sensor de discriminação

Scratch: `git worktree add --detach <scratchpad>/wt-bsv60b 1810d9a` (iteração 1 usou `<scratchpad>/wt-bsv60` em `89e613c`); harness em arquivo do scratchpad (não versionado) aplica cada mutante em `core/estado.py` do scratch e roda só `tests/test_config_permissao.py` no WSL; restaura o arquivo no `finally`. Dois lotes (8 + 7), um processo por vez. Worktree removido; `git status --porcelain` do real igual ao baseline (só este `validation.md` não rastreado).

**Iteração 2: 15 mutantes, 12 mortos, 3 sobreviventes (equivalentes).**

| Mutante | O que muda | Iteração 1 | Iteração 2 | Teste que mata / justificativa |
| --- | --- | --- | --- | --- |
| a | sem o `chmod` | morto | morto | `test_mantem_640`, `test_tmp_nunca_mais_aberto_que_o_original[640,400]` |
| b | `chmod(tmp, 0o600)` forçado | morto | morto | idem |
| c1 | volta a `open(tmp, 'w')` (umask), mantendo o chmod | morto | morto | `test_tmp_nunca_mais_aberto_que_o_original` (×3), `test_tmp_velho_aberto_nao_vaza` |
| c2 | `open(tmp, 'w')` sem chmod (o defeito original) | morto | morto | 7 testes, incl. `test_mantem_600_com_umask_002` |
| d | `os.open(..., 0o666)` | morto | morto | `test_tmp_nunca_mais_aberto_que_o_original` (×3), `test_tmp_velho_aberto_nao_vaza` |
| e1 | sem remover o `.tmp` velho | morto | morto | `test_tmp_velho_aberto_nao_vaza` |
| e2 | sem remover o `.tmp` velho **e** sem `O_EXCL` | **sobrevivia (G1)** | **morto** | `test_tmp_velho_aberto_nao_vaza` (T:108 `modos_na_abertura == [0o600]`) |
| f | chmod depois do `os.replace` | morto | morto | `test_tmp_nunca_mais_aberto_que_o_original[640,400]` |
| g | fallback `0o644` | morto | morto | `test_original_sumiu_ao_obter_modo_usa_600` |
| h | sem `os.remove(tmp)` no except | morto | morto | `test_falha_na_escrita_deixa_original_intacto` |
| i | escreve direto no caminho, sem `.tmp`/replace | morto | morto | 6 testes, incl. `test_falha_na_escrita_deixa_original_intacto` |
| j | `os.name == 'nt'` invertido (sem chmod no Linux) | morto | morto | `test_mantem_640` e parametrizados |
| k | sem `O_EXCL` (mantém o `os.remove`) | sobrevive | sobrevive, **equivalente** | o `os.remove` imediatamente antes garante que o `.tmp` não existe; só difere numa corrida com outro escritor, que não existe (um processo por config) |
| l | sem `& 0o777` | sobrevive | sobrevive, **equivalente** na prática | `S_IMODE` só acrescentaria setuid/setgid/sticky, que um `config.json` não tem |
| m | sem `os.fsync` | sobrevive | sobrevive, **equivalente para teste** | durabilidade só se observa com queda de energia; conferido por leitura (E:178) |

**G1: fechada** em `1810d9a` (evidência: `tools/tests/test_config_permissao.py:73-86`, `:105`, `:108`; mutante e2 morto).

## Regra 3: escritores de arquivo em `core/` e `main.py`

Busca por `os.replace`, `open(..., 'w'/'wb'/'a')`, `json.dump`, `write_text`, `write_bytes`, `.save(` em `tools/capture-store-pages/core/*.py` e `main.py`.

| Local | O que grava | Segredo? |
| --- | --- | --- |
| `core/estado.py:174-181` (`os.open` + `json.dump` + `os.replace`) | `conf/config.json` (controle) | **Sim** (senha do Oracle, `app_secret`). É o objeto desta correção. |
| `core/batimento.py:45-46` (`write_text` + `os.replace`) | `conf/batimento.json`: `pid`, `em`, `prazo`, `fase` (`batimento.py:61-66`) | Não. Nasce com a umask (`664`), sem impacto. |
| `core/csv_io.py:52` (`open(path, 'w')`), chamado por `main.py:878` (`_gravar_csv`, pasta de log) | CSV da captura: colunas da fila + `url_final`/`url_besave`/campos capturados (pode ter URL de afiliado) | Nenhuma credencial. URL de afiliado não é segredo de acesso, mas o arquivo nasce `664` na pasta de log; observação para o PR, não defeito. |
| `core/imagens_oferta.py:122-123` (`write_bytes` + `os.replace`) | `.webp` das ofertas | Não |
| `core/imagens_produto.py:85` (`img.save`) | `.webp` de produto | Não |
| `core/images.py:99` (`final.save`), `core/images.py:129-130` (`open(filename, 'wb')`) | imagens baixadas / marca d'água | Não |
| `main.py` | nenhum escritor direto além da chamada `main.py:878` | — |

Fora de Python: o perfil persistente do Chrome (`core/browser.py`, `PERFIL_DIR`) guarda a sessão logada das lojas (cookies); quem grava é o Chromium, com a umask do processo. Fica como achado para o PR (fora do escopo).

## Verificação de evidência (regra 11)

`git diff origin/develop..1810d9a` varrido por `C:\Users\`, `/home/<usuário>`, `/mnt/c/Users`, tokens de bot: nada. A senha `"s"` do teste é fictícia. A saída do WSL acima teve o `rootdir` trocado por `REDACTED`.

## Qualidade de código

Mudança mínima e restrita a `_gravar_controle` (só stdlib). Observação não bloqueante: se `open(fd, 'w')` falhasse depois do `os.open` (E:175), o fd vazaria; caso irreal (só falharia por encoding inválido, que é constante).

## Pendências do dono (bloqueiam o merge)

1. CI em Linux (job `tools`): conferir com `gh run list`/aba Checks que rodou e que os 9 testes de `test_config_permissao.py` passaram sem skip (lição 12).
2. Real na inst1 com a branch: `chmod 600 conf/config.json` → reiniciar as lojas → 3 linhas processadas → `stat -c %a conf/config.json` = `600`.
