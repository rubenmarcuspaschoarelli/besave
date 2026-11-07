# BSV-55 Robô das lojas: partida sem perguntas e bloqueio que não perde oferta Specification

Fonte: `docs/specs/BSV-55.md`. AD-107; lições 28, 29.

## Problem Statement

02–05/11: o robô das lojas subiu pelo `systemd` e ficou 3 dias parado num `input()` ("Login na Shopee
agora?"). Na volta, a Shopee sem sessão de afiliado gravou linhas como sucesso sem `DS_URL_AFILIADO`
(oferta some do site) e o captcha do Mercado Livre virou `pagina_sem_produto` (`'9'`, definitivo).

## Goals

- [ ] `--sem-perguntas`: nenhum `input()` em caminho nenhum; a unidade usa a opção.
- [ ] Captcha e telas de login/verificação das três lojas = `bloqueado_ou_login`, linha fica em `'0'`.
- [ ] Sessão de afiliado ausente (`sessao`) segura a linha; `outro` segue como hoje.
- [ ] 3 bloqueios seguidos de uma loja → pausa só dela; aviso no Telegram, lembrete, "voltou".

## Out of Scope

Vigia externo (BSV-57), reinício do WhatsApp (BSV-54), sequence (BSV-56), recuperar linhas de 02–05/11,
login automático, mudança de schema ou SP, execução real na inst1 (dono).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Onde casa a marca de bloqueio | Caminho da URL (`urlparse(...).path`), minúsculo | `validateCaptcha` da Amazon tem `C` maiúsculo; query (`?next=/verify/...`) não é a tela | n |
| Marcas | `verify/`, `account-verification`, `captcha`, `buyer/login` (Shopee), `lgz/login` (ML), `ap/signin` (Amazon) | Telas conhecidas das três lojas; exemplo redigido no teste | n |
| `sessao` no afiliado | Só Shopee: formulário do `custom_link` não abriu ou a aba caiu em tela de login | Falha independe da URL do produto. SiteStripe/barra do ML ausentes dependem da página: seguem `outro` (senão um produto sem widget prende a loja na sonda) | n |
| Corta-circuito do `link_afiliado` (5 seguidas) | Conta só `outro`; `sessao` é tratada pela pausa | Senão, depois da pausa a loja desistida devolveria vazio e gravaria sem afiliado | n |
| Status da linha com `sessao` | `sessao_afiliado_ausente`, fica `'0'`, nada gravado na fila nem em `OFERTA` | Regra 1: sem schema novo; motivo só no log/CSV | n |
| Ponteiro | Linha bloqueada (página ou `sessao`) trava o ponteiro como a falha de conexão da BSV-52 (`db.trava_ponteiro`) | "mesma regra da BSV-52" | n |
| Linhas da loja pausada | Status `loja_pausada`, `'0'`, não travam o ponteiro, não entram em `adiados`; no monitor saem do lote antes do processamento | Regra 2; sem laço apertado quando só sobram linhas pausadas | n |
| Sonda ao fim da pausa | A 1ª linha da loja depois do prazo; resultado neutro (erro, descarte) não fecha a sonda | Só bloqueio ou sucesso dizem algo da sessão | n |
| "Navegador do próprio perfil" | `processos.chrome_aberto()` (Windows). No Linux o perfil travado já falha no `launch_persistent` com `exit 1` | Checar `SingletonLock` erra depois de reboot (pid reaproveitado) e prenderia a unidade | n |
| Config | `bloqueio.pausa_minutos` (60); `alerta.telegram_token`, `alerta.telegram_chat_id` | Spec; limiar 3 e lembrete 6 h são constantes | n |
| Telegram | Cópia de `enviar_telegram` (urllib) em `core/alerta.py` do robô | Os robôs rodam de pastas diferentes; sem dependência nova | n |

Open questions: none

---

## User Stories

### P1: Partida sem pessoa e bloqueio sem perda ⭐ MVP

**Acceptance Criteria**:

1. SEM-01: WHERE `--sem-perguntas` está ligado, THE SYSTEM SHALL NOT chamar `input()` no arranque (lote ou monitor) e SHALL chegar à 1ª varredura do monitor.
2. SEM-02: WHERE `--sem-perguntas` não está ligado, THE SYSTEM SHALL continuar perguntando o login da Shopee no arranque do monitor.
3. SEM-03: IF `--sem-perguntas` está ligado e há navegador aberto, THEN THE SYSTEM SHALL sair com código ≠ 0 e mensagem clara, sem fechar processo.
4. SEM-04: THE SYSTEM SHALL subir a unidade `besave-captura-lojas.service` com `--monitorar --sem-perguntas`.
5. BLQ-01: WHEN a URL final tem marca de captcha, login ou verificação de Amazon, Mercado Livre ou Shopee, THE SYSTEM SHALL classificar `bloqueado_ou_login`.
6. BLQ-02: WHEN a linha é `bloqueado_ou_login`, THE SYSTEM SHALL deixá-la em `'0'`, sem gravar a fila nem `OFERTA`, e o ponteiro SHALL NOT passar dela.
7. AFI-01: WHEN o gerador da Shopee não abre o formulário (sessão), THE SYSTEM SHALL marcar o motivo `sessao`; WHEN abre mas não devolve link, `outro`.
8. AFI-02: WHEN o motivo é `sessao`, THE SYSTEM SHALL deixar a linha em `'0'`, sem gravar a fila nem `OFERTA`, e travar o ponteiro; WHEN `outro`, THE SYSTEM SHALL gravar como hoje.
9. PAU-01: WHEN uma loja soma 3 bloqueios seguidos (página ou `sessao`), THE SYSTEM SHALL pausá-la por `bloqueio.pausa_minutos` e continuar as outras lojas na mesma varredura.
10. PAU-02: WHEN a loja tem um sucesso, THE SYSTEM SHALL zerar a contagem dela; bloqueio de uma loja SHALL NOT contar para outra.
11. PAU-03: WHEN a pausa vence, THE SYSTEM SHALL tentar uma linha: sucesso → loja volta; bloqueio → nova pausa.
12. TEL-01: WHEN a loja entra em pausa, THE SYSTEM SHALL enviar uma mensagem (loja, motivo, linhas retidas, VNC :1), lembrete a cada 6 h enquanto durar e uma de "voltou"; no máximo 1 aviso por entrada.
13. TEL-02: IF faltar token ou chat, THEN THE SYSTEM SHALL só logar; token e chat SHALL NOT aparecer em log, `print` ou exceção.
14. DOC-01: THE SYSTEM SHALL documentar em `tools/vps/README.md` o que é automático, o que chega no Telegram e como logar pela tela sem parar o robô.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SEM-01 | P1 | Execute | Done |
| SEM-02 | P1 | Execute | Done |
| SEM-03 | P1 | Execute | Done |
| SEM-04 | P1 | Execute | Done |
| BLQ-01 | P1 | Execute | Done |
| BLQ-02 | P1 | Execute | Done |
| AFI-01 | P1 | Execute | Done |
| AFI-02 | P1 | Execute | Done |
| PAU-01 | P1 | Execute | Done |
| PAU-02 | P1 | Execute | Done |
| PAU-03 | P1 | Execute | Done |
| TEL-01 | P1 | Execute | Done |
| TEL-02 | P1 | Execute | Done |
| DOC-01 | P1 | Execute | Done |

## Success Criteria

- [ ] `pytest` e `ruff check vps/ tests/` verdes em `tools/`; Verifier independente PASS; teste real do dono na inst1.
