# BSV-60 config.json mantém a permissão ao gravar o controle Specification

Fonte: `docs/specs/BSV-60.md`. Lições 14, 29. Pasta: `tools/capture-store-pages/` (+ testes em `tools/tests/`).

## Problem Statement

`core/estado.py::_gravar_controle` grava o config num `.tmp` novo e faz `os.replace`; o `.tmp` nasce com a
`umask` do processo (`002` na inst1), então cada gravação do controle troca `600` por `664` e deixa a senha do
Oracle e o `app_secret` da Shopee legíveis por outros usuários.

## Goals

- [ ] `_gravar_controle` mantém o modo do `config.json` que encontrar, sem janela com permissão mais aberta.
- [ ] Atomicidade de hoje (`.tmp` + `fsync` + `os.replace`) preservada.
- [ ] README e `config.example.json` dizem que o arquivo fica `600` no Linux.

## Out of Scope

Backups antigos na inst1; tirar segredo do `config.json`; `umask` do processo; outros escritores (só listados
pelo Verifier); execução real na inst1 (dono, bloqueia o merge).

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| `.tmp` sobrando de execução interrompida | Apagado antes de criar com `O_EXCL` | `O_CREAT` sobre arquivo existente não troca o modo: o `.tmp` velho podia estar `664` | n |
| Windows | Sem `chmod`; `.tmp` criado com `0o600` (bit de escrita, não fica somente-leitura) | Spec saída 3; `os.replace` sobre destino somente-leitura falharia | n |
| Modo copiado | `stat.S_IMODE(st_mode) & 0o777` (sem setuid/sticky) | "só os bits de permissão" | n |

Open questions: none

---

## User Stories

### P1: Permissão do config ⭐ MVP

**Acceptance Criteria**:

1. PERM-01: WHEN `_gravar_controle` grava um config com modo `600` sob `umask 002`, THE SYSTEM SHALL deixar o arquivo em `600` com a chave nova gravada.
2. PERM-02: WHEN o config original tem outro modo (ex.: `640`), THE SYSTEM SHALL manter exatamente esse modo.
3. PERM-03: THE SYSTEM SHALL criar o `.tmp` já em `600` e SHALL NOT deixar o `.tmp` existir com bits de grupo/outros além dos do original, inclusive no momento do `os.replace`.
4. PERM-04: IF o config original não existe ao obter o modo, THEN THE SYSTEM SHALL usar `600`.
5. PERM-05: IF a escrita do `.tmp` falha, THEN THE SYSTEM SHALL deixar o `config.json` original intacto (conteúdo e modo) e remover o `.tmp`.
6. PERM-06: WHERE a plataforma é Windows, THE SYSTEM SHALL gravar como antes, sem `chmod`, e os testes de modo SHALL ser pulados.
7. PERM-07: THE SYSTEM SHALL dizer em `conf/config.example.json` e no README que o `config.json` fica `600` no Linux e que o robô mantém o modo que encontrar.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PERM-01 | Permissão do config | Execute | Done |
| PERM-02 | Permissão do config | Execute | Done |
| PERM-03 | Permissão do config | Execute | Done |
| PERM-04 | Permissão do config | Execute | Done |
| PERM-05 | Permissão do config | Execute | Done |
| PERM-06 | Permissão do config | Execute | Done |
| PERM-07 | Permissão do config | Execute | Done |
