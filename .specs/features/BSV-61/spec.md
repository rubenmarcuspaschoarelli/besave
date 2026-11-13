# BSV-61 Envio do Telegram na inst2 (imagens pelo site) Specification

Fonte: `docs/specs/BSV-61.md`.

## Problem Statement

O `besave-envio` lê a foto da oferta e a do aviso do disco da inst1. A inst2 (mensageria) não tem esses
arquivos, mas os dois já estão publicados no site antes de o envio poder usá-los. O envio precisa
buscá-los por HTTPS e a inst2 precisa de um papel de instalação só com o envio.

## Goals

- [ ] Foto da oferta e do aviso por HTTPS quando `BESAVE_IMAGENS_URL` / `BESAVE_AVISOS_URL` estão definidas.
- [ ] `instalar.sh --papel envio` instala só o que a inst2 precisa; o papel padrão segue igual.
- [ ] Roteiro "Inst2 · envio" com a virada.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Mover ciclo ou robôs | spec |
| Fila e publicador do WhatsApp | BSV-62, BSV-63 |
| CDN própria do envio | spec: usa a do site |
| Passo 6.3 (tirar o envio do papel padrão) | só depois da virada, pelo dono; o roteiro registra |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Validação da base | `https://` + host não vazio, sem `?`, `#`, `@` nem espaço; senão erro de configuração (código 2) | Regra 2: só HTTPS e só o host configurado | n |
| URL montada | base sem `/` final + `/` + `{id}.webp` (oferta) ou `{id}.{webp\|jpg}` (aviso, extensão de `DS_IMAGEM` por `formato_imagem`) | Saídas 1–2; lição 14 | n |
| Limite de tamanho | corpo > 5 242 880 bytes = recusado; o cliente real para de ler em 5 MB + 1 | "no máximo 5 MB" | n |
| Timeout | 15 s para pedido + corpo | Saída 1 | n |
| Origem da foto pelo site | `OrigemFoto::Site(url)` | log e `--sim` mostram de onde veio | n |
| Precedência | URL definida → só HTTP (disco não é lido); senão pasta; senão placeholder / sem foto | Saída 3 | n |
| Cliente HTTPS não inicia | WARN e todas as fotos pelo caminho de falha (placeholder / sem foto) | Regra 3: imagem nunca impede o post | n |
| Instalador | `instalar.sh [--papel ciclo\|envio] [ID]`; `ciclo` é o padrão e faz o de hoje; `envio` instala `besave-envio` + `besave-worker` (o `besave-alerta@` usa `--alerta-encerrado`) e copia `besave-envio.service`, `besave-envio.timer`, `besave-alerta@.service` para `BESAVE_UNIDADES` (padrão `/srv/besave/unidades`) | O instalador roda como `besave`, sem sudo; o roteiro faz o `sudo install` em `/etc/systemd/system` | n |
| `systemctl --user` da spec | As unidades são de sistema (`User=besave`, `/etc/systemd/system`): o roteiro usa `sudo systemctl` | Unidades existentes (BSV-43) | n |

**Open questions:** none.

---

## User Stories

### P1: Envio na inst2 sem disco compartilhado ⭐ MVP

Como dono, quero o envio do Telegram na inst2 lendo as imagens pelo site, para liberar a memória da inst1.

**Acceptance Criteria (EARS):**


- **IMG-01** WHEN `BESAVE_IMAGENS_URL` is set THE envio SHALL fetch `GET {base}{id}.webp` and, on `200` with a decodable body ≤ 5 MB, use it as the 800×800 JPEG photo (origin `Site(url)`).
- **IMG-02** WHEN the fetch returns non-200, times out, fails, returns a non-image body or a body > 5 MB THE envio SHALL use the area placeholder and log a WARN with `id` and the status or reason.
- **IMG-03** THE URL built from a base with or without a trailing `/` SHALL be identical.
- **AVI-01** WHEN `BESAVE_AVISOS_URL` is set and `DS_IMAGEM = x.jpg` THE envio SHALL fetch `{base}{id}.jpg` (`x.webp` → `.webp`); on any failure the aviso SHALL go as `sendMessage`.
- **PRE-01** WHEN only the folder is set THE envio SHALL read the folder (existing tests stay green).
- **PRE-02** WHEN URL and folder are set THE envio SHALL call only the URL (0 folder reads) and log an INFO at start.
- **PRE-03** WHEN neither is set THE envio SHALL use the placeholder (aviso without photo).
- **CFG-01** WHEN a base URL is not `https://host…` or carries query, fragment, userinfo or spaces THE envio SHALL fail with a configuration error (exit 2).
- **INS-06** WHEN `instalar.sh --papel envio` runs THE installer SHALL install only `besave-envio`, `besave-worker`, `VERSAO` and the units `besave-envio.service`, `besave-envio.timer`, `besave-alerta@.service`.
- **INS-07** WHEN `instalar.sh` runs without `--papel` (or `--papel ciclo`) THE installer SHALL behave as today (INS-01..05) and install no units; an unknown role SHALL exit 2 without calling `gh`.
- **ENV-01** `infra/vps/envio.env.example` SHALL list `BESAVE_IMAGENS_URL`, `BESAVE_AVISOS_URL`, `TNS_ADMIN`, `BESAVE_LOG_DIR`, `BESAVE_ENVIO_LOCK` and the bot variable names without values, and no `BESAVE_IMAGENS_DIR`.
- **DOC-01** `docs/infra/` SHALL have a section "Inst2 · envio" with Instant Client ARM64 + wallet, binary from `main`, `.env` in `600` and the cut-over order.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| IMG-01 | P1 | T1 | Pending |
| IMG-02 | P1 | T1 | Pending |
| IMG-03 | P1 | T1 | Pending |
| AVI-01 | P1 | T1 | Pending |
| PRE-01 | P1 | T1 | Pending |
| PRE-02 | P1 | T1/T2 | Pending |
| PRE-03 | P1 | T1 | Pending |
| CFG-01 | P1 | T2 | Pending |
| INS-06 | P1 | T3 | Pending |
| INS-07 | P1 | T3 | Pending |
| ENV-01 | P1 | T3 | Pending |
| DOC-01 | P1 | T4 | Pending |

Testes: `apps/worker/tests/envio_site.rs`, `envio_site_log.rs`, `envio_foto.rs`, `envio_aviso_selecao.rs`; `infra/vps/teste_instalar.sh`; DOC-01 por leitura.
