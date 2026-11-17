# BSV-63 Tasks

## Execution Plan

### Phase 1: Núcleo
T1 → T2 → T3

### Phase 2: Laço e página
T4 → T5

### Phase 3: VPS
T6

### Phase 4: Correções do Verifier (ciclo 1)
T7

### Phase 5: Seletores reais (mapeamento do dono, 16/11)
T8 → T9 → T10

### Phase 6: Achado do teste real (17/11): prévia da foto
T11 → T12 → T13

### Phase 7: 2º achado do teste real (17/11, 3fccc36): anexo pelo menu
T14 → T15

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
T6 → T7
T7 → T8
T8 → T9
T9 → T10
T10 → T11
T11 → T12
T12 → T13
T13 → T14
T14 → T15
```

## Task Breakdown

### T1: Config, ritmo e regras de descarte ✅
**What**: `pub/config.py` (padrões, leitura a cada volta, aviso de permissão), `pub/regras.py` (Brasília, `esperado`/`devido` com `L = 1`, classificação `expirou`/`outro_dia`/`velha`, escolha da mais recente, sono com variação), `config.example.json`, `requirements.txt`, `.gitignore` do perfil.
**Where**: `tools/publish-whatsapp-channel/pub/`, `tools/publish-whatsapp-channel/conf/config.example.json`, `tools/tests/test_pub_regras.py`, `tools/tests/conftest.py`
**Depends on**: none
**Reqs**: RIT-02, RIT-03, RIT-04, ESC-02, ESC-03, ESC-04, CFG-02
**Tests**: `tools/tests/test_pub_regras.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_regras.py`

### T2: Foto ✅
**What**: `pub/foto.py`: baixar com timeout, quadrado 800×800 JPEG branco, placeholder da área, `None` se nada baixar.
**Where**: `tools/publish-whatsapp-channel/pub/foto.py`, `tools/tests/test_pub_foto.py`, `tools/requirements-dev.txt`
**Depends on**: T1
**Reqs**: FOT-01, FOT-02, FOT-03
**Tests**: `tools/tests/test_pub_foto.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_foto.py`

### T3: Fila Oracle, avisos e batimento ✅
**What**: `pub/fila.py` (SQL de parâmetros, contagem do dia, pendentes com `ST_ATIVO`, marcar; reconexão e `call_timeout`), `pub/avisos.py` (Telegram com redação, credencial do ambiente ou `worker.env`), `pub/batimento.py`.
**Where**: `tools/publish-whatsapp-channel/pub/`, `tools/tests/test_pub_fila.py`
**Depends on**: T2
**Reqs**: BAT-01, ISO-01
**Tests**: `tools/tests/test_pub_fila.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_fila.py`

### T4: Laço do publicador ✅
**What**: `pub/publicador.py`: volta (config, descarte, ritmo, escolha, foto, página, estados P→D→E), pausa e avisos, QR, exceção → recarrega uma vez, browser morto → código ≠ 0.
**Where**: `tools/publish-whatsapp-channel/pub/publicador.py`, `tools/tests/pub_falso.py`, `tools/tests/test_pub_publicador.py`
**Depends on**: T3
**Reqs**: RIT-01, RIT-02, RIT-03, ESC-01, EST-01, EST-02, EST-03, EST-04, FOT-03, PAU-01, PAU-02, QR-01, CFG-01, BAT-01, LIM-01
**Tests**: `tools/tests/test_pub_publicador.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_publicador.py`

### T5: Página do WhatsApp Web e main ✅
**What**: `pub/canal_web.py` (seletores com origem documentada, abrir canal, anexar, colar/digitar a legenda com conferência, enviar, confirmar sem relógio, limpar, QR, `--gravar-dom` redigido), fixture HTML sintética, `main.py`.
**Where**: `tools/publish-whatsapp-channel/pub/canal_web.py`, `tools/publish-whatsapp-channel/main.py`, `tools/tests/fixtures/whatsapp_canal.html`, `tools/tests/test_pub_canal_web.py`
**Depends on**: T4
**Reqs**: LEG-01, LEG-02, QR-01, ISO-01
**Tests**: `tools/tests/test_pub_canal_web.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py`

### T6: Vigia, unidades e README ✅
**What**: `vigia_robos.py` com o robô `publicador` e `BESAVE_VIGIA_ROBOS`; `iniciar_publicador.sh`; `besave-publicador-whatsapp.service`; drop-in da inst2; README do programa e de `tools/vps`.
**Where**: `tools/vps/`, `tools/publish-whatsapp-channel/README.md`, `tools/tests/test_vigia_publicador.py`, `tools/tests/test_unidades.py`
**Depends on**: T5
**Reqs**: VIG-01, UNI-01
**Tests**: `tools/tests/test_vigia_publicador.py`, `tools/tests/test_unidades.py`
**Gate**: `cd tools && python -m pytest -q && ruff check vps/ tests/ publish-whatsapp-channel/ && shellcheck vps/*.sh`

### T7: Lacunas do Verifier (ciclo 1) ✅
**What**: testes que matam M21 (`D` do próprio laço conta no teto), M47 (balão de outra mensagem não confirma), M54 (placeholder da área da linha), M55 (limpeza depois de `E` e de `D`). Só testes.
**Where**: `tools/tests/test_pub_publicador.py`, `tools/tests/test_pub_canal_web.py`, `tools/tests/pub_falso.py`
**Depends on**: T6
**Reqs**: RIT-03, FOT-02, LEG-01, EST-01
**Tests**: `tools/tests/test_pub_publicador.py`, `tools/tests/test_pub_canal_web.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_publicador.py tests/test_pub_canal_web.py`

### T8: Seletores reais e fixture real ✅
**What**: `canal_web.py` com a tabela de seletores do dono (data-testid/aria-label/role/title), fluxo por postagem (pula a navegação com o canal aberto; Canais → busca → célula pelo aria-label → cabeçalho igual; input oculto do footer → Anexar → "Fotos e vídeos" com `expect_file_chooser`; legenda cru com cru, 1 nova tentativa, Escape; confirmação positiva: prévia fechada, balão novo, `besave.io/{id}` na legenda, msg-meta enviada/entregue/lida); `FalhaPasso` (falha prevista, sem recarregar); fixture real recortada e redigida de `docs/canal_real.html` (não versionado) + prévia transcrita; simulador de teste; a sintética sai.
**Where**: `tools/publish-whatsapp-channel/pub/canal_web.py`, `tools/publish-whatsapp-channel/pub/publicador.py`, `tools/tests/fixtures/whatsapp_canal_real.html`, `tools/tests/fixtures/whatsapp_simulador.js`, `tools/tests/test_pub_canal_web.py`, `tools/tests/pub_falso.py`, `tools/tests/test_pub_publicador.py`
**Depends on**: T7
**Reqs**: LEG-01, LEG-02, EST-01, EST-02, EST-03, QR-01
**Tests**: `tools/tests/test_pub_canal_web.py`, `tools/tests/test_pub_publicador.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py tests/test_pub_publicador.py` (no WSL com Playwright: 0 skipped)

### T9: README com os seletores reais ✅
**What**: seção "Seletores" com a tabela e a data do mapeamento; fluxo de confirmação atualizado.
**Where**: `tools/publish-whatsapp-channel/README.md`
**Depends on**: T8
**Reqs**: LEG-01
**Tests**: revisão do README
**Gate**: `cd tools && python -m pytest -q tests/test_pub_isolamento.py`

### T10: Lacunas do Verifier (ciclo 3) ✅
**What**: testes que matam M-n (colar rejeitado → nova tentativa digitando), M-s (célula pelo aria-label com outra célula antes) e M-t (canal aberto sem caixa → não envia). Só testes e o cenário `rejeitaColar` do simulador.
**Where**: `tools/tests/test_pub_canal_web.py`, `tools/tests/fixtures/whatsapp_simulador.js`
**Depends on**: T9
**Reqs**: LEG-02, EST-02
**Tests**: `tools/tests/test_pub_canal_web.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py`

### T11: Prévia da foto lenta ou que não abre ✅
**What**: `anexar()` espera a prévia `ESPERA_PREVIA_S = 30`; pelo input sem prévia → Escape e, uma vez, Anexar → "Fotos e vídeos" em `expect_file_chooser`; log `[anexo] caminho=input|menu previa_s=<x.x>` ou `previa=nao`; falha da prévia → `log/falha_<DDMM_HHMMSS>.png` + `.html` redigido, 20 mais recentes. Simulador: `atrasoPrevia`, `inputNaoAbre`, `menu`, `menuNaoAbre`.
**Where**: `tools/publish-whatsapp-channel/pub/canal_web.py`, `tools/publish-whatsapp-channel/main.py`, `tools/tests/test_pub_canal_web.py`, `tools/tests/fixtures/whatsapp_simulador.js`
**Depends on**: T10
**Reqs**: EST-02, FOT-03
**Tests**: `tools/tests/test_pub_canal_web.py` (`-k anexo`)
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py` (WSL: 0 skipped)

### T12: README do anexo e das evidências ✅
**What**: fluxo do anexo (30 s, segundo caminho, log) e `log/falha_*` no README.
**Where**: `tools/publish-whatsapp-channel/README.md`
**Depends on**: T11
**Reqs**: EST-02
**Tests**: revisão do README
**Gate**: `cd tools && python -m pytest -q tests/test_pub_isolamento.py`

### T13: Lacuna do Verifier (ciclo 4) ✅
**What**: teste de que a prévia que abre (pelo input ou pelo menu) não grava evidência em `log/`. Só testes.
**Where**: `tools/tests/test_pub_canal_web.py`
**Depends on**: T12
**Reqs**: EST-02
**Tests**: `tools/tests/test_pub_canal_web.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py -k anexo`

### T14: Anexo pelo menu, clique curto, camadas e evidência em toda falha ✅
**What**: caminho único Anexar → "Fotos e vídeos" em `expect_file_chooser` (o input oculto do footer sai); item ausente em 5 s = falha prevista; antes e depois de falha, Escape até sumir camada (`[role="dialog"]` menos o aviso fixo do canal) e a prévia (máx. 3) e caixa do canal visível, senão falha prevista + recarrega; cliques com 5 s e motivo do call log; evidência em toda falha, inclusive inesperada; janela `--window-size` + `no_viewport` (`BESAVE_JANELA`).
**Where**: `tools/publish-whatsapp-channel/pub/canal_web.py`, `tools/publish-whatsapp-channel/main.py`, `tools/tests/test_pub_canal_web.py`, `tools/tests/fixtures/whatsapp_simulador.js`
**Depends on**: T13
**Reqs**: EST-02, FOT-03, LIM-01
**Tests**: `tools/tests/test_pub_canal_web.py` (`-k anexo`, `motivo`, `janela`)
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py` (WSL: 0 skipped)

### T15: README do anexo pelo menu e da janela
**What**: fluxo do anexo, camadas, clique curto, evidência e tamanho da janela no README.
**Where**: `tools/publish-whatsapp-channel/README.md`
**Depends on**: T14
**Reqs**: EST-02
**Tests**: revisão do README
**Gate**: `cd tools && python -m pytest -q tests/test_pub_isolamento.py`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| RIT-02..04, ESC-02..04, CFG-02 | `tools/tests/test_pub_regras.py` | T1 |
| FOT-01..03 | `tools/tests/test_pub_foto.py` | T2 |
| BAT-01, ISO-01 (avisos redigidos, SQL) | `tools/tests/test_pub_fila.py` | T3 |
| RIT-01, ESC-01, EST-01..04, FOT-03, PAU-01..02, QR-01, CFG-01, LIM-01 | `tools/tests/test_pub_publicador.py` | T4 |
| LEG-01..02, QR-01 (DOM), ISO-01 | `tools/tests/test_pub_canal_web.py` | T5 |
| VIG-01, UNI-01 | `tools/tests/test_vigia_publicador.py`, `tools/tests/test_unidades.py` | T6 |
| EST-02, FOT-03, LIM-01 (anexo pelo menu, clique curto, camadas, evidência, janela) | `tools/tests/test_pub_canal_web.py` | T14 |
| EST-02, FOT-03 (prévia lenta, 2º caminho, evidência) | `tools/tests/test_pub_canal_web.py` | T11 |
| LEG-02, EST-02 (lacunas M-n, M-s, M-t) | `tools/tests/test_pub_canal_web.py` | T10 |
| LEG-01..02, EST-01..03 (seletores reais, fixture real) | `tools/tests/test_pub_canal_web.py`, `tools/tests/test_pub_publicador.py` | T8 |
| RIT-03, FOT-02, LEG-01, EST-01 (lacunas M21, M47, M54, M55) | `tools/tests/test_pub_publicador.py`, `tools/tests/test_pub_canal_web.py` | T7 |

## Gate Check Commands

| Level | Command |
| ----- | ------- |
| quick | `cd tools && python -m pytest -q tests/<arquivo>` |
| build | `cd tools && python -m pytest -q && ruff check vps/ tests/ publish-whatsapp-channel/ && shellcheck vps/*.sh` |
