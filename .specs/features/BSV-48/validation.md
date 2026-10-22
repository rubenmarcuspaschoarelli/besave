# BSV-48 Validation

**Date**: 2026-10-21
**Spec**: `.specs/features/BSV-48/spec.md` (fonte: `docs/specs/BSV-48.md`)
**Diff range**: `origin/develop...HEAD` (f260174, 2 commits: 85f7226 + f260174)
**Verifier**: sub-agente independente (autor != verificador). Primeira passada em 85f7226; refeita integralmente em f260174 depois que o autor acrescentou os testes de fiação.

**Result**: PASS

**Veredito: PASS (com 1 achado menor e itens reais do dono pendentes)**

---

## Task Completion

Sem `tasks.md` (ticket pequeno, tarefa implícita). Todos os 16 requisitos têm código e teste. Os itens de execução real (VPS, Windows) são do dono e bloqueiam o merge, não a validação.

---

## Spec-Anchored Acceptance Criteria

Testes em `tools/tests/`. Código em `tools/`.

| Critério | Resultado esperado (spec) | Evidência `arquivo:linha` | Result |
|---|---|---|---|
| TEL-01 unidade-modelo sobe `iniciar_vnc.sh %i`, para com `kill :%i` | `ExecStart` termina em `iniciar_vnc.sh %i`, `ExecStop` em `kill :%i` | código `tools/vps/systemd/besave-vnc@.service` (ExecStart/ExecStop); teste `test_unidades.py::test_vnc_e_unidade_modelo_da_tela_n_so_em_localhost` (`servico["ExecStart"].endswith(".../iniciar_vnc.sh %i")`, `ExecStop.endswith("kill :%i")`) | PASS |
| TEL-02 lojas -> `vnc@1`/`:1`; WhatsApp -> `vnc@2`/`:2`; espera o socket da sua tela | After/Requires, `BESAVE_DISPLAY`, `X1`/`X2` | `test_unidades.py` `test_robo_depende_da_tela_vnc`, `test_reinicia_em_falha_e_roda_no_tmux_com_display`, `test_robo_nao_fica_failed_por_falha_de_partida` (`TELA[...]`); `test_iniciar_captura.py::test_sh04` (`DISPLAY=:2`); código `besave-captura-lojas.service`, `besave-captura-whatsapp.service`, `iniciar_captura.sh` | PASS |
| TEL-03 README com túnel 5901 e 5902 | portas no README | `test_vnc.py::test_vnc04_readme_tem_o_tunel_das_duas_portas_e_o_vncpasswd` (`"5901" in leia and "5902" in leia`); `tools/vps/README.md:99` | PASS |
| VNC-01 sem senha (ausente/vazia) -> 78, mensagem com `vncpasswd`, não chama vncserver | exit 78 | `test_vnc.py::test_vnc01_sem_senha_recusa_com_mensagem_e_codigo_78` (`returncode == 78`, `"vncpasswd" in stderr`, `not args.exists()`); `test_vnc01_senha_vazia_ou_em_outro_lugar_tambem_recusa`; código `iniciar_vnc.sh` (`exit 78`) | PASS |
| VNC-02 com senha -> `vncserver :N -fg -localhost yes -geometry 1600x900 -xstartup ...` | argv exato | `test_vnc.py::test_vnc02_...` (`argv[:7] == [":N","-fg","-localhost","yes","-geometry","1600x900","-xstartup"]`, `argv[7]` termina em `xstartup-xfce.sh` (tela 1) ou `xstartup-leve.sh`). Desvio consciente da spec: `-xstartup` agora é `xstartup-xfce.sh`/`xstartup-leve.sh`, não `/usr/bin/startxfce4` (commit f260174); README e `test_vnc05` cobrem | PASS (desvio documentado) |
| VNC-03 N inválido -> exit 2 sem vncserver | exit 2 | `test_vnc.py::test_vnc03_tela_invalida_e_erro_de_uso` (`returncode == 2`, para `()`,`0`,`x`,`1; rm`) | PASS |
| VNC-04 `RestartPreventExitStatus=78` e README com `vncpasswd` | valor 78 | `test_unidades.py` (`servico["RestartPreventExitStatus"] == "78"`); `test_vnc04` (`"vncpasswd" in leia`) | PASS |
| UA-01 sem/ vazia/ inválida -> args idênticos | sem chave `user_agent` | `test_navegador.py::test_ua01_...` (igualdade com `user_agent=None`; `"user_agent" not in` para `""`); `test_ua03_ler_user_agent_do_config` (ausente, vazio, só espaços, número -> None) | PASS |
| UA-02 preenchido -> em `montar_kwargs`, sem espaços; `launch_persistent` passa | kwargs = esperado + `user_agent` | `test_ua02_...` (igualdade completa do dict); `test_ua03` (strip); `test_ua04_launch_persistent_usa_o_user_agent_do_config` (`chamadas[0]["user_agent"] == UA`) | PASS |
| UA-03 logins usam `launch_persistent`; README com valor, conferência e aviso | | `test_ua05_logins_manuais_passam_pelo_launch_persistent`; `README.md` seção "Identificação do navegador" (linhas ~110-130: `navigator.userAgent`, `navigator.platform`, aviso de captcha) | PASS (conteúdo do README sem asserção de teste, só revisão) |
| JAN-01 ausente/inválida -> ritmo inalterado | `ler_janela -> None`, `espera_s == normal` | `test_janela.py::test_jan01_*`, `test_jan02_sem_janela_ritmo_normal_a_qualquer_hora`; `test_fiacao_lojas.py::test_jan04_fila_vazia_fora_da_janela_ritmo_normal`; `test_fiacao_whatsapp.py::test_jan05_sem_janela_nao_dorme_a_noite` | PASS |
| JAN-02 antes fora; `inicio` dentro; `fim` fora; cruzando meia-noite | fronteiras | `test_janela.py::test_jan03_janela_que_cruza_a_meia_noite` (21:59 F, 22:00 T, 23:59 T, 00:00 T, 07:59 T, 08:00 F), `test_jan04_janela_no_mesmo_dia`; parametrizado nos dois robôs | PASS |
| JAN-03 dentro: `min(intervalo, tempo até o fim)` | 7200 / 3600 / normal | `test_janela.py::test_jan05_dentro_espera_o_intervalo_cortado_no_fim` (7200, 3600 às 07:00, normal às 08:00 e 21:00) | PASS |
| JAN-04 lojas dormem também depois de um lote na janela | pausa 7200, sem reler | `test_fiacao_lojas.py::test_jan04_lote_dentro_da_janela_dorme_antes_de_reler_a_fila` (`pausas == [7200]`, `leituras == 2`), `..._lote_fora_da_janela_rele_a_fila_na_hora` (`pausas == []`), `..._fila_vazia_dentro...` (`[7200]`), `..._pausa_dentro_da_janela_e_cortada_no_fim` (`[3600]`); código `main.py:772-774` | PASS (antes era gap; fechado em f260174) |
| JAN-05 WhatsApp dorme em fatias <= 5 s sem fechar; salva no `finally` | 7200 s em fatias, `salvos`, `ctx.fechado` | `test_fiacao_whatsapp.py::test_jan05_dentro_da_janela_dorme_o_intervalo_entre_rodadas` (`sum(longos)==7200 and max<=5`, `salvos and ctx.fechado`, 1 volta só); `..._fora_da_janela...` (3 voltas, sem pausa longa); `..._sem_janela...`; helper `test_janela.py::test_jan06_whatsapp_dorme_so_dentro_da_janela_em_fatias`; código `monitor.py:1253-1258` | PASS (antes era gap; fechado) |
| JAN-06 exemplos documentam a chave sem ligar | bloco presente e inválido | `test_janela.py::test_jan08_exemplos_documentam_a_chave` (`ler_janela(dados) is None`); `config.example.json` dos dois | PASS |

Regras da spec: (1) sem chaves, comportamento idêntico: coberto por `test_fiacao_*` e UA-01; revisão manual de `main.py`/`monitor.py` contra `origin/develop` confirma que, sem janela, `espera_s()` devolve `normal_s` e `dormir_ate_proxima_rodada(None)` devolve 0 (mensagem de log antes `intervalo_min:g`, agora `espera_s()/60:g`, mesmo valor). (2) sem banco/CSV/dependência de runtime: confirmado no diff. (4) contador salvo no `finally`: JAN-05.

**Status**: todos os 16 ACs com evidência `arquivo:linha`.

---

## Discrimination Sensor

Scratch: `git worktree` temporário FORA do worktree real, removido depois. `git status --porcelain` do worktree real igual ao inicial (limpo). Testes relevantes por mutante (`pytest -x`).

| # | Alvo | Mutação | Resultado |
|---|---|---|---|
| M01 | `core/janela.py` | fim inclusivo (`<` -> `<=`) | Killed |
| M02 | `core/janela.py` | sem ramo da meia-noite (`or` -> `and`) | Killed |
| M03 | `core/janela.py` | sem corte no fim | Killed |
| M04 | `core/janela.py` | início exclusivo | Killed |
| M05 | `core/janela.py` | `inicio == fim` aceito | Killed |
| M06 | `core/janela.py` | `intervalo <= 0` -> `< 0` | Killed |
| M07 | `wa/janela.py` | início exclusivo | Killed |
| M08 | `wa/janela.py` | sem corte no fim | Killed |
| M09 | `wa/janela.py` | fatia 5 -> 50 s | Killed |
| M10 | `wa/janela.py` | dorme também fora da janela | Killed |
| M11 | `wa/janela.py` | sem ramo da meia-noite | Killed |
| M12 | `main.py` | remove a pausa pós-lote | Killed |
| M13 | `main.py` | inverte dentro/fora | Killed |
| M14 | `main.py` | espera sempre `normal_s` | Killed |
| **M15** | `main.py:main()` | **não passa a janela lida do config a `_monitorar`** | **SURVIVED** |
| M16 | `monitor.py` | remove a pausa (`dormido = 0`) | Killed |
| M17 | `monitor.py` | `janela = None` | Killed |
| M18 | `monitor.py` | `dormir_ate_proxima_rodada(None)` | Killed |
| M19 | `browser.py` | UA aplicado mesmo vazio (`is not None`) | Killed (refeito à mão; o padrão do script falhou por CRLF) |
| M20 | `browser.py` | `launch_persistent` sem UA | Killed |
| M21 | `browser.py` | UA sem `strip` | Killed |
| M22 | `iniciar_vnc.sh` | exit 78 -> 1 | Killed |
| M23 | `iniciar_vnc.sh` | aceita só `~/.config/tigervnc/passwd` | Killed |
| M24 | `iniciar_vnc.sh` | aceita só `~/.vnc/passwd` | Killed |
| M25 | `iniciar_vnc.sh` | aceita também `~/.vncpasswd` | Killed |
| M26 | `iniciar_vnc.sh` | `-s` -> `-e` (vazio aceito) | Killed |
| M27 | `iniciar_vnc.sh` | `-localhost no` | Killed |
| M28 | `iniciar_vnc.sh` | aceita tela 0 | Killed |
| M29 | `iniciar_vnc.sh` | tela 2 com `xstartup-xfce` | Killed |
| M30 | `iniciar_vnc.sh` | tela 1 com `xstartup-leve` | Killed |
| M31 | `xstartup-leve.sh` | `xfwm4` -> `startxfce4` | Killed |
| M32 | `xstartup-xfce.sh` | sem `dbus-run-session` | Killed |
| M33 | `besave-vnc@.service` | `RestartPreventExitStatus=1` | Killed |
| M34 | WhatsApp `.service` | `BESAVE_DISPLAY=:1` | Killed |
| M35 | WhatsApp `.service` | `After=besave-vnc@1` | Killed |
| M36 | WhatsApp `.service` | socket `X1` | Killed |
| M37 | lojas `.service` | `Requires=besave-vnc@2` | Killed |
| M38 | `besave-vnc@.service` | `ExecStop` fixo em `:1` | Killed |
| M39 | `besave-vnc@.service` | `ExecStart` sem `%i` | Killed |
| M40 | `iniciar_captura.sh` | padrão `:2` -> `:1` | Killed |

**Sensor depth**: lightweight ampliado (40 mutantes). **Result**: 39/40 killed; 1 sobrevivente de severidade baixa (M15).

M15: a única linha de `main()` que liga o config à janela nas lojas (`main.py:904-905`) não tem teste, porque `main()` exige Oracle, Playwright e login manual. `_monitorar` e `janela.py` estão cobertos; se essa linha for quebrada, a janela nunca liga nas lojas. Cobertura recomendada, não bloqueante: o teste real da noite (log "janela noturna 22:00-08:00") cobre. Opcional: extrair a leitura da janela para uma função chamada por `main()` e testá-la, ou um teste de texto sobre `main.py`.

---

## Code Quality

| Princípio | Status |
|---|---|
| Mínimo de código | OK. `wa/janela.py` e `core/janela.py` são cópias intencionais (os robôs não compartilham pacote; diff só traz `carregar`/`dormir_ate_proxima_rodada` no WhatsApp). Lógica comum idêntica por `diff`. |
| Mudanças cirúrgicas | OK. `main.py` +27/-? e `monitor.py` +13 só tocam o laço. |
| Sem scope creep | Atenção: `xstartup-xfce.sh`/`xstartup-leve.sh`/`dbus-run-session` (f260174) não constam do `spec.md`/`docs/specs/BSV-48.md`; mudam VNC-02 (`-xstartup`). Decisão do dono; o spec.md deve ser atualizado para refleti-la. |
| Mesmo padrão | OK |
| Testes mapeiam ACs | OK; `tests/falsos.py` isola playwright/oracledb/requests sem dependência de runtime. |
| Dependência nova | Nenhuma. |
| Evidência/segredos (regra 11) | Nenhum token, IP, OCID ou caminho de usuário do Windows nos arquivos do diff. `README.md:45` cita `/home/besave/.vnc/passwd` (nome de usuário de serviço da VPS, não pessoal). |

---

## Edge Cases

- [x] Bloco inválido (hora ruim, intervalo <= 0, `inicio == fim`, não-dict) -> sem janela (`test_jan01`)
- [x] Pausa cortada no `fim` (07:00 -> 3600 s)
- [x] Janela cruzando a meia-noite, e janela no mesmo dia
- [x] Arquivo de config ausente/ilegível (`carregar`, `ler_user_agent`)
- [x] Senha vazia ou em caminho errado (`~/.vncpasswd`) recusa
- [ ] Janela aplicada a `main()` das lojas (M15): sem teste automatizado

---

## Gate Check

- **Gate**: `cd tools && python -m pytest -q` (venv com pytest em `$TEMP/venv48`), em f260174, sem outra carga
- **Resultado**: 123 passed, 0 failed, 0 skipped (118 s). Na primeira passada (85f7226): 112 passed. Delta f260174: +11 testes (`test_fiacao_lojas.py`, `test_fiacao_whatsapp.py`, ampliação de `test_vnc.py`)
- **Contagem antes da feature**: os `test_*.py` de BSV-48 (`test_janela`, `test_navegador` ampliado, `test_vnc`) são novos; `test_unidades.py`/`test_iniciar_captura.py` foram adaptados, não enfraquecidos (asserts passaram a conferir a tela por robô). Nenhum teste apagado ou pulado.
- **Não executado nesta máquina (Windows)**: `shellcheck` e `systemd-analyze verify` (não existem aqui). Rodar no CI Linux/VPS. O bash dos testes é o Git Bash.

---

## Não executado / pendências do dono (bloqueiam o merge)

1. `shellcheck tools/vps/*.sh` e `systemd-analyze --user verify tools/vps/systemd/*.service`.
2. Real VPS: telas em `localhost:5901`/`5902`; noite com janela ligada (log a cada 2 h, retomada às 8 h); 1 dia sem Play Store; oferta ML com afiliado enquanto o dono usa a outra tela; `encerrar_captura.sh`.
3. Real Windows: 1 h dos dois robôs sem diferença no log.
4. Conferir na VPS que `xfwm4` sozinho na tela `:2` sustenta o Chromium do WhatsApp (decisão nova de f260174, sem teste possível aqui).

---

## Requirement Traceability Update

TEL-01..03, VNC-01..04, UA-01..03, JAN-01..06: Verified (VNC-02 com desvio documentado do `-xstartup`).

---

## Summary

**Overall**: PASS
**Spec-anchored check**: 16/16 ACs com evidência; nenhum spec-precision gap
**Sensor**: 39/40 killed (sobrevivente M15, baixo)
**Gate**: 123 passed

**Recomendações**: (1) cobrir ou aceitar M15; (2) atualizar `spec.md` com os xstartup e a senha em dois caminhos; (3) `shellcheck` e `systemd-analyze` no CI/VPS antes do merge.
