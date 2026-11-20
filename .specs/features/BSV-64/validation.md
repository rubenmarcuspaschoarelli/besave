# Validation — BSV-64

**Veredicto: PASS**

Verificador: Verifier independente (sub-agente distinto do autor; auto-verificação não conta como PASS).  
Branch: `rubenmarcus/rub-52-bsv-64`  
Data: 2026-11-19  
Ciclo de verificação: **2** (ciclo 1 detectou FAIL em CA-7; autor corrigiu; este ciclo confirma PASS).

---

## Resumo

Todos os 8 critérios de aceite passam. CA-7, que falhava no ciclo 1 porque Fase 6 step 2 de
`docs/infra/VPS-INSTANCIA-1.md` ainda listava `BESAVE_ENVIO_LOCK` como variável a acrescentar,
foi corrigido: o texto agora instrui explicitamente "Sem `BESAVE_ENVIO_LOCK` nem
`TELEGRAM_CANAL_BOT_TOKEN`" (linhas 148–149). CA-1 a CA-6 e CA-8 foram verificados no ciclo 1
e permanecem inalterados; a reexecução de CA-1 no WSL confirma que a correção não quebrou nada.

---

## Critérios de aceite

### CA-1 — `bash infra/vps/teste_instalar.sh` verde no WSL

**PASS** (reconfirmado no ciclo 2)

Executado via `wsl bash /mnt/.../infra/vps/teste_instalar.sh`:

```
ok: teste_instalar
```

Código de saída: 0.

### CA-2 — papel `ciclo` → `bin/` = exatamente `VERSAO besave-ciclo besave-worker`

**PASS** (ciclo 1 — evidência mantida)

- `instalar.sh` linha 36: `BINARIOS=(besave-ciclo besave-worker)` para o papel `ciclo`.
- Função `instalado()` em `teste_instalar.sh` linhas 77–79 verifica:
  `"./VERSAO ./besave-ciclo ./besave-worker "` (ordem LC_ALL=C, sem mais nada).
- INS-01 (linha 86), INS-02 (linha 106), INS-07 (linha 179) chamam `instalado` e passam.

### CA-3 — papel `ciclo` com `besave-envio` antigo → intacto (mesmo hash) + `AVISO:` no stderr

**PASS** (ciclo 1 — evidência mantida)

- `instalar.sh` linhas 85–87: bloco `if [ "$papel" = ciclo ] && [ -f "$BIN/besave-envio" ]`
  emite `AVISO: … sobrou do papel anterior …` para stderr; não remove nem modifica o arquivo.
- INS-08 (`teste_instalar.sh` linhas 188–200) verifica:
  - `besave-envio` ainda existe (`[ -f "$T/bin/besave-envio" ]`, linha 197)
  - hash inalterado (`[ "$hash_antes" = "$hash_depois" ]`, linha 199)
  - `grep -q "^AVISO:" "$T/err"` (linha 200)
- Caso passa com código 0.

### CA-4 — papel `envio` (INS-06/07) igual a antes

**PASS** (ciclo 1 — evidência mantida)

- `instalar.sh` linhas 39–41: `BINARIOS=(besave-envio besave-worker)` e as 3 unidades para `envio`.
- INS-06 com e sem ID (`teste_instalar.sh` linhas 223–235) chamam `envio_instalado` e passam.
- INS-06 hash errado e artefato sem besave-ciclo (linhas 237–251) recusam corretamente.

### CA-5 — `SHA256SUMS` sem `besave-envio` continua falhando nos dois papéis

**PASS** (ciclo 1 — evidência mantida)

- `instalar.sh` linhas 71–74: o loop `for b in "${ARTEFATO[@]}"` (onde
  `ARTEFATO=(besave-ciclo besave-envio besave-worker)`) verifica todos os 3 no SHA256SUMS,
  independente do papel.
- `teste_instalar.sh` linhas 155–160 (INS-04 "SHA256SUMS sem besave-envio (ciclo)"): remove
  `besave-envio` do SHA256SUMS, roda `rodar 123` (papel `ciclo`), exige `codigo != 0`. Passa.
- INS-06 hash errado (linha 237) já cobre o papel `envio`.

### CA-6 — `worker.env.example` sem `BESAVE_ENVIO_LOCK` nem `TELEGRAM_CANAL_BOT_TOKEN`

**PASS** (ciclo 1 — evidência mantida)

- `infra/vps/worker.env.example`: grep retornou sem correspondências para ambas as variáveis.
- Grep em `apps/worker/src/` confirma que as variáveis existem exclusivamente no código do `besave-envio`:
  - `BESAVE_ENVIO_LOCK`: `apps/worker/src/envio/binario.rs:84` e `apps/worker/src/unidade.rs:52`.
  - `TELEGRAM_CANAL_BOT_TOKEN`: `apps/worker/src/envio/http.rs:16`.

### CA-7 — `VPS-INSTANCIA-1.md` Fase 6 e Virada passo 3 corretos

**PASS** (corrigido pelo autor após ciclo 1)

**Fase 6 step 2 (`docs/infra/VPS-INSTANCIA-1.md` linhas 148–149): PASS.**  
O texto corrigido instrui: "e acrescentando `BESAVE_LOG_DIR=/srv/besave/logs` e `BESAVE_LOCK`
(no Linux não existe `LOCALAPPDATA`). Sem `BESAVE_ENVIO_LOCK` nem `TELEGRAM_CANAL_BOT_TOKEN`
— essas são do `besave-envio`, que fica na inst2 (BSV-64)."  
A instrução é agora consistente com `worker.env.example` (CA-6) e com a Virada passo 3.

**Fase 6 step 1 (`docs/infra/VPS-INSTANCIA-1.md` linhas 143–144): PASS** (não mudou).  
Instrui a instalar o papel `ciclo` ("só `besave-ciclo` e `besave-worker`, AD-060; `besave-envio`
fica na inst2 — ver [Inst2 · envio], BSV-64"). Correto.

**Virada passo 3 (`docs/infra/VPS-INSTANCIA-1.md` linhas 219–230): PASS** (não mudou).  
Bloco "Limpeza da inst1 (BSV-64)" correto: parar e remover as unidades do envio, apagar o
binário, remover `BESAVE_ENVIO_LOCK` e `TELEGRAM_CANAL_BOT_TOKEN` do `worker.env` da inst1,
verificar dois ciclos com `Result=success`.

### CA-8 — `README.md` frase de abertura de "Rodar no Linux" correta

**PASS** (ciclo 1 — evidência mantida)

`apps/worker/README.md` linha 773:

> `` `besave-ciclo` roda na instância 1 da OCI (Ubuntu 24.04 ARM64) e `besave-envio` na instância 2 (BSV-61; ver [Inst2 · envio](../../docs/infra/VPS-INSTANCIA-1.md#inst2--envio-bsv-61)), ambos pelo `systemd`, com o mesmo comportamento do Agendador do Windows. ``

Correto: ciclo na inst1, envio na inst2.

---

## Sensor de discriminação (mutantes)

Executado no ciclo 1 (inalterado; os arquivos de teste não foram modificados).

### M1 — `BINARIOS=(besave-ciclo besave-envio besave-worker)` para ciclo

**Morreu.**

8 falhas: INS-01, INS-02 (todos os subitens), INS-07 e INS-08. `bin/` ficou com
`besave-envio` além do esperado; INS-08 viu "besave-envio foi modificado" (sobrescrito pelo
artefato). Evidência: `FALHOU: INS-01 sem argumento: bin/ inesperado: VERSAO\nbesave-ciclo\nbesave-envio\nbesave-worker`.

### M2 — Remoção do bloco `if "$papel" = ciclo && -f "$BIN/besave-envio"` (sem AVISO)

**Morreu.**

1 falha: `FALHOU: INS-08 ciclo com besave-envio antigo: sem AVISO: em stderr:`. INS-08
linha 200 (`grep -q "^AVISO:" "$T/err"`) falhou porque o stderr ficou vazio.

### M3 — Bloco AVISO substituído por `rm -f "$BIN/besave-envio"`

**Morreu.**

3 falhas: `besave-envio foi apagado` (linha 197), `besave-envio foi modificado`
(`sha256sum` falhou com "No such file or directory"), `sem AVISO: em stderr:`.

### M4 — INS-04 "SHA256SUMS sem besave-envio (ciclo)": `rodar 123` → `rodar --papel envio 123`

**Equivalente.**

O conjunto voltou `ok: teste_instalar` (exit 0). Com `--papel envio 123` e SHA256SUMS
sem `besave-envio`, o script ainda aborta com código ≠ 0 pelo mesmo motivo: o loop
`for b in "${ARTEFATO[@]}"` (linhas 71–74 do `instalar.sh`) exige os 3 no SHA256SUMS
independente do papel. A proteção existe em ambos os papéis, mas o caso não prova
especificamente que o ciclo rejeita — o comportamento é idêntico, o mutante é equivalente.

---

## Arquivos verificados

| arquivo | linhas relevantes |
|---|---|
| `infra/vps/instalar.sh` | 36 (BINARIOS ciclo), 71–74 (ARTEFATO check), 85–87 (bloco AVISO) |
| `infra/vps/teste_instalar.sh` | 70–83 (instalado), 86–95 (INS-01), 155–160 (INS-04 sem besave-envio ciclo), 179–185 (INS-07), 188–200 (INS-08) |
| `infra/vps/worker.env.example` | arquivo inteiro (ausência de BESAVE_ENVIO_LOCK e TELEGRAM_CANAL_BOT_TOKEN) |
| `docs/infra/VPS-INSTANCIA-1.md` | 143–144 (Fase 6 step 1 ✓), 148–149 (Fase 6 step 2 ✓ — corrigido no ciclo 2), 219–230 (Virada passo 3 ✓) |
| `apps/worker/README.md` | 773 (frase "Rodar no Linux" ✓) |
| `apps/worker/src/envio/binario.rs` | 84 (BESAVE_ENVIO_LOCK — só no envio) |
| `apps/worker/src/envio/http.rs` | 16 (TELEGRAM_CANAL_BOT_TOKEN — só no envio) |
