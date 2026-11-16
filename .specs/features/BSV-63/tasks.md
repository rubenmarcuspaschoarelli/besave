# BSV-63 Tasks

## Execution Plan

### Phase 1: Núcleo
T1 → T2 → T3

### Phase 2: Laço e página
T4 → T5

### Phase 3: VPS
T6

```
T1 → T2
T2 → T3
T3 → T4
T4 → T5
T5 → T6
```

## Task Breakdown

### T1: Config, ritmo e regras de descarte ✅
**What**: `pub/config.py` (padrões, leitura a cada volta, aviso de permissão), `pub/regras.py` (Brasília, `esperado`/`devido` com `L = 1`, classificação `expirou`/`outro_dia`/`velha`, escolha da mais recente, sono com variação), `config.example.json`, `requirements.txt`, `.gitignore` do perfil.
**Where**: `tools/publish-whatsapp-channel/pub/`, `tools/publish-whatsapp-channel/conf/config.example.json`, `tools/tests/test_pub_regras.py`, `tools/tests/conftest.py`
**Depends on**: none
**Reqs**: RIT-02, RIT-03, RIT-04, ESC-02, ESC-03, ESC-04, CFG-02
**Tests**: `tools/tests/test_pub_regras.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_regras.py`

### T2: Foto
**What**: `pub/foto.py`: baixar com timeout, quadrado 800×800 JPEG branco, placeholder da área, `None` se nada baixar.
**Where**: `tools/publish-whatsapp-channel/pub/foto.py`, `tools/tests/test_pub_foto.py`, `tools/requirements-dev.txt`
**Depends on**: T1
**Reqs**: FOT-01, FOT-02, FOT-03
**Tests**: `tools/tests/test_pub_foto.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_foto.py`

### T3: Fila Oracle, avisos e batimento
**What**: `pub/fila.py` (SQL de parâmetros, contagem do dia, pendentes com `ST_ATIVO`, marcar; reconexão e `call_timeout`), `pub/avisos.py` (Telegram com redação, credencial do ambiente ou `worker.env`), `pub/batimento.py`.
**Where**: `tools/publish-whatsapp-channel/pub/`, `tools/tests/test_pub_fila.py`
**Depends on**: T2
**Reqs**: BAT-01, ISO-01
**Tests**: `tools/tests/test_pub_fila.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_fila.py`

### T4: Laço do publicador
**What**: `pub/publicador.py`: volta (config, descarte, ritmo, escolha, foto, página, estados P→D→E), pausa e avisos, QR, exceção → recarrega uma vez, browser morto → código ≠ 0.
**Where**: `tools/publish-whatsapp-channel/pub/publicador.py`, `tools/tests/pub_falso.py`, `tools/tests/test_pub_publicador.py`
**Depends on**: T3
**Reqs**: RIT-01, RIT-02, RIT-03, ESC-01, EST-01, EST-02, EST-03, EST-04, FOT-03, PAU-01, PAU-02, QR-01, CFG-01, BAT-01, LIM-01
**Tests**: `tools/tests/test_pub_publicador.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_publicador.py`

### T5: Página do WhatsApp Web e main
**What**: `pub/canal_web.py` (seletores com origem documentada, abrir canal, anexar, colar/digitar a legenda com conferência, enviar, confirmar sem relógio, limpar, QR, `--gravar-dom` redigido), fixture HTML sintética, `main.py`.
**Where**: `tools/publish-whatsapp-channel/pub/canal_web.py`, `tools/publish-whatsapp-channel/main.py`, `tools/tests/fixtures/whatsapp_canal.html`, `tools/tests/test_pub_canal_web.py`
**Depends on**: T4
**Reqs**: LEG-01, LEG-02, QR-01, ISO-01
**Tests**: `tools/tests/test_pub_canal_web.py`
**Gate**: `cd tools && python -m pytest -q tests/test_pub_canal_web.py`

### T6: Vigia, unidades e README
**What**: `vigia_robos.py` com o robô `publicador` e `BESAVE_VIGIA_ROBOS`; `iniciar_publicador.sh`; `besave-publicador-whatsapp.service`; drop-in da inst2; README do programa e de `tools/vps`.
**Where**: `tools/vps/`, `tools/publish-whatsapp-channel/README.md`, `tools/tests/test_vigia_publicador.py`, `tools/tests/test_unidades.py`
**Depends on**: T5
**Reqs**: VIG-01, UNI-01
**Tests**: `tools/tests/test_vigia_publicador.py`, `tools/tests/test_unidades.py`
**Gate**: `cd tools && python -m pytest -q && ruff check vps/ tests/ publish-whatsapp-channel/ && shellcheck vps/*.sh`

## Test Coverage Matrix

| Req | Test file | Task |
| --- | --- | --- |
| RIT-02..04, ESC-02..04, CFG-02 | `tools/tests/test_pub_regras.py` | T1 |
| FOT-01..03 | `tools/tests/test_pub_foto.py` | T2 |
| BAT-01, ISO-01 (avisos redigidos, SQL) | `tools/tests/test_pub_fila.py` | T3 |
| RIT-01, ESC-01, EST-01..04, FOT-03, PAU-01..02, QR-01, CFG-01, LIM-01 | `tools/tests/test_pub_publicador.py` | T4 |
| LEG-01..02, QR-01 (DOM), ISO-01 | `tools/tests/test_pub_canal_web.py` | T5 |
| VIG-01, UNI-01 | `tools/tests/test_vigia_publicador.py`, `tools/tests/test_unidades.py` | T6 |

## Gate Check Commands

| Level | Command |
| ----- | ------- |
| quick | `cd tools && python -m pytest -q tests/<arquivo>` |
| build | `cd tools && python -m pytest -q && ruff check vps/ tests/ publish-whatsapp-channel/ && shellcheck vps/*.sh` |
