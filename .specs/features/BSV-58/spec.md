# BSV-58 Robô das lojas: encurtadores bloqueados resolvidos por IP residencial Specification

Fonte: `docs/specs/BSV-58.md`. Depende da BSV-55 (linha retida, `PausaLojas`, Telegram). Lições 14, 16, 29.

## Problem Statement

Desde 06/11 o `amzn.promos.link` responde à inst1 (IP de datacenter da OCI) a página "Sorry, you have been
blocked" do Cloudflare. O robô não reconhece a loja no `page.url` e grava `'9' loja_desconhecida`: 265
ofertas perdidas em 7 dias. Do IP residencial do dono o mesmo link responde `302` para a loja.

## Goals

- [ ] Só o redirect dos domínios configurados sai pelo túnel SOCKS do PC do dono; a loja abre direto na inst1.
- [ ] Falha do túnel retém a linha (`'0'`), pausa o domínio e avisa; nunca vira `'9'`.
- [ ] Bloqueio do Cloudflare em domínio fora da lista retém a linha e sugere incluir o domínio.
- [ ] Script do túnel no PC e README.

## Out of Scope

Proxy residencial pago (alt. B), segunda instância (alt. C), reprocessar as 265 linhas (SQL no PR, dono
aplica), vigia do túnel além da pausa, robô do WhatsApp, execução real na inst1 (dono).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Casamento de domínio | host sem porta, minúsculo; igual ao domínio ou termina em `.` + domínio | Sufixo de rótulo da spec | y |
| Bloco ativo | `redirecionamento` dict com `dominios` não vazio; senão módulo desligado (fluxo de hoje) | Spec saída 1 | y |
| Proxy vazio com domínio na lista | `proxy_indisponivel` sem chamar o `curl` | Regra 2: retida + aviso | y |
| Comando | `curl -sS -o <os.devnull> -w '%{http_code} %{redirect_url}' --proxy <proxy> --max-time <t> --url <url>`, lista, sem `shell=True` | `--url` impede URL iniciada por `-` de virar opção; sem `-L` | n |
| Falha do `curl` | Código de saída ≠ 0, `curl` ausente ou estouro do `subprocess` → `proxy_indisponivel` | Regra 2: falha do túnel nunca vira `'9'`; com `socks5h` o erro do lado do PC também vem como saída ≠ 0 | n |
| HTTP | 403/429/503 → `bloqueado`; 3xx com `redirect_url` → salto; resto (200, 404, 3xx sem destino) → `sem_redirect` | Spec saída 2 | y |
| Saltos | No máximo `max_saltos` chamadas ao `curl`; destino ainda na lista depois delas → `sem_redirect` | Spec | y |
| Segredo | O valor de `proxy` e o `stderr` do `curl` nunca vão a log; o log de configuração diz só quantos domínios | Mais estrito que a spec ("além do log de configuração") | n |
| Chave da pausa | Loja do registry; senão domínio da lista; senão host sem `www.` (Cloudflare) | Spec saída 4; mesma `PausaLojas` | n |
| Mensagens da pausa | Motivo `redirecionamento`: "<dom> em pausa: túnel residencial fora? N linha(s) retida(s)"; motivo `cloudflare`: "<dom> bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?"; demais motivos como na BSV-55 | Spec saídas 4 e 5 | n |
| Telegram do Cloudflare | Pela pausa (3 seguidas → 1 aviso + lembrete + voltou); cada linha loga a sugestão | Evita um Telegram por linha | n |
| Detecção do Cloudflare | Título `Attention Required! \| Cloudflare` ou HTML com `you have been blocked` (sem caixa) | Spec saída 5 | y |
| `sem_redirect` | Neutro para a pausa; segue `_resolver_ponte` pela URL original | Spec saída 3 | y |
| Destino desconhecido | Destino fora da lista e fora do registry segue `_resolver_ponte(destino)` (página aberta direto) | Regra 1 | n |
| Túnel | `BatchMode=yes` a mais que a pré-condição (tarefa sem janela não pode parar numa pergunta do `ssh`); `tools/vps/tunel_residencial.ps1` (PowerShell 5.1), destino e chave por parâmetro ou `BESAVE_TUNEL_DESTINO`/`BESAVE_TUNEL_CHAVE`; `-Ssh` e `-MaxTentativas` para teste | Regra 4: nada de IP/chave no repo | n |

Open questions: none

---

## User Stories

### P1: Encurtador bloqueado sem perder oferta ⭐ MVP

**Acceptance Criteria**:

1. CFG-01: WHEN o bloco `redirecionamento` falta ou `dominios` está vazio, THE SYSTEM SHALL seguir o fluxo de hoje sem chamar o `curl`.
2. DOM-01: THE SYSTEM SHALL casar `amzn.promos.link` e `promos.link` com `promos.link`, e SHALL NOT casar `xpromos.link`, `promos.link.exemplo.com` nem `amazon.com.br`.
3. CMD-01: THE SYSTEM SHALL montar o comando como lista exata `curl -sS -o <devnull> -w '%{http_code} %{redirect_url}' --proxy <proxy da config> --max-time <timeout> --url <url>`, sem `-L` e sem `shell=True`.
4. RES-01: WHEN o `curl` devolve 3xx para domínio fora da lista, THE SYSTEM SHALL devolver esse destino, e o navegador SHALL abrir a página da loja direto (sem proxy).
5. RES-02: WHEN o destino ainda é de domínio da lista, THE SYSTEM SHALL dar outro salto pelo proxy, até `max_saltos`; esgotado, SHALL devolver `sem_redirect`.
6. RES-03: WHEN o resultado é `sem_redirect`, THE SYSTEM SHALL seguir o `_resolver_ponte` de hoje com a URL original.
7. FAL-01: IF o `curl` não conecta no proxy (ou não há proxy), THEN THE SYSTEM SHALL marcar `redirecionamento_indisponivel`: linha `'0'`, nada gravado em fila nem `OFERTA`, ponteiro travado.
8. FAL-02: IF o proxy responde 403/429/503, THEN THE SYSTEM SHALL marcar `redirecionamento_indisponivel` como em FAL-01.
9. PAU-01: WHEN o domínio soma 3 falhas seguidas, THE SYSTEM SHALL pausá-lo, enviar 1 aviso ("<dom> em pausa: túnel residencial fora? N linha(s) retida(s)"), deixar as linhas dele `pausada(0)` sem `curl` e seguir as outras lojas; WHEN volta, SHALL avisar "voltou" e processar a linha retida.
10. CF-01: WHEN o navegador cai na página de bloqueio do Cloudflare num domínio fora da lista, THE SYSTEM SHALL reter a linha (`redirecionamento_indisponivel`) e logar `<dominio> bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?`; 3 seguidas → pausa e Telegram com a mesma frase.
11. CF-02: WHEN a página de domínio desconhecido é comum, THE SYSTEM SHALL continuar gravando `'9' loja_desconhecida`.
12. SEG-01: THE SYSTEM SHALL NOT escrever o valor de `proxy` em nenhuma saída.
13. TUN-01: THE SYSTEM SHALL manter o túnel com `ssh -i <chave> -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -o BatchMode=yes -R 127.0.0.1:1080 <destino>` em laço, reconectando 30 s depois de cair, com log curto sem destino nem chave, lidos de parâmetro ou ambiente.
14. DOC-01: THE SYSTEM SHALL documentar em `tools/vps/README.md` o túnel, a porta só no `127.0.0.1` da inst1, o PC desligado (retidas + aviso), a tarefa agendada, como parar e como incluir domínio; e o bloco em `config.example.json`.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CFG-01 | P1 | Execute | Done |
| DOM-01 | P1 | Execute | Done |
| CMD-01 | P1 | Execute | Done |
| RES-01 | P1 | Execute | Done |
| RES-02 | P1 | Execute | Done |
| RES-03 | P1 | Execute | Done |
| FAL-01 | P1 | Execute | Done |
| FAL-02 | P1 | Execute | Done |
| PAU-01 | P1 | Execute | Done |
| CF-01 | P1 | Execute | Done |
| CF-02 | P1 | Execute | Done |
| SEG-01 | P1 | Execute | Done |
| TUN-01 | P1 | Execute | Done |
| DOC-01 | P1 | Execute | Done |

## Success Criteria

- [ ] `pytest`, `ruff check vps/ tests/` e `shellcheck vps/*.sh` verdes em `tools/`; Verifier independente PASS; teste real do dono na inst1.
