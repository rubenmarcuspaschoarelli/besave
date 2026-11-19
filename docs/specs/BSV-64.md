# BSV-64 · Envio fora da inst1 de vez (passo 3 da virada da BSV-61)

**Papel:** shell + docs · **Pasta:** `infra/vps/` (+ `docs/infra/VPS-INSTANCIA-1.md`, `apps/worker/README.md`
só na seção "Rodar no Linux") · **Depende de:** BSV-61 (em `main` desde #128). Lições 9, 14, 16

## Contexto
Desde a BSV-61 o `besave-envio` (canal do Telegram) roda na inst2. Na inst1 o timer está `disabled` e
`inactive` (conferido em 19/11), mas ainda ficam lá:
- `/etc/systemd/system/besave-envio.service`, `besave-envio.timer` e a pasta `besave-envio.service.d/` (vazia);
- o binário `/srv/besave/bin/besave-envio`, porque o papel padrão do `instalar.sh` (`ciclo`) ainda instala os 3;
- as variáveis só do envio no `/srv/besave/worker.env` da inst1, entre elas o token do bot do canal.

Um `enable --now` por engano na inst1 faz o canal receber tudo em dobro (VPS-INSTANCIA-1 §6). O roteiro
deixou esse passo como "ticket do dono" (Virada, passo 3); este é o ticket.

## Saídas
1. **`instalar.sh`, papel `ciclo`:** instala só `besave-ciclo` e `besave-worker`. O artefato continua com os
   3 binários e o `SHA256SUMS` continua conferindo os 3; só a lista de instalação muda.
2. **`instalar.sh`, papel `ciclo`, com `besave-envio` já em `BIN`:** não apaga (o instalador nunca remove
   nada); imprime um `AVISO:` dizendo que o binário sobrou e qual comando do roteiro o remove.
3. **`teste_instalar.sh`:** os casos do papel `ciclo` passam a esperar `VERSAO`, `besave-ciclo` e
   `besave-worker` em `bin/`; caso novo (INS-08) com `besave-envio` antigo em `bin/` → mantido, intacto e com
   o aviso. O papel `envio` (INS-06/07) não muda.
4. **`docs/infra/VPS-INSTANCIA-1.md`:**
   - Fase 6: inst1 só com `besave-ciclo` e o timer do ciclo; o envio aponta para "Inst2 · envio".
   - Virada, passo 3: vira o roteiro de limpeza da inst1 (abaixo, "Real"), com conferência antes de cada
     remoção e o caminho de volta. A volta deixa de ser "`enable --now` na inst1": passa a ser reinstalar o
     papel `envio` na inst1 (`instalar.sh --papel envio` + `.env` + unidades), só em emergência.
5. **`infra/vps/worker.env.example`** (o da inst1): sem as variáveis que só o `besave-envio` lê. A lista sai
   do código (`grep` das variáveis lidas por `besave-ciclo` e `besave-worker`), não de memória; variável lida
   pelos dois binários fica. `envio.env.example` (inst2) não muda.
6. **`apps/worker/README.md`, "Rodar no Linux":** a frase "`besave-ciclo` e `besave-envio` rodam na
   instância 1" passa a dizer quem roda onde (ciclo na inst1, envio na inst2).

## Regras
1. O instalador continua sem apagar arquivo e sem mexer em `/etc/systemd/system` (quem faz é o dono, como
   root, pelo roteiro).
2. Teste de comando montado compara a lista inteira de `bin/`, não item por item (lição 14).
3. Nenhum valor real em exemplo, spec ou evidência: só nomes de variável (regra 11).
4. Sem dependência nova.

## Fora de escopo
- Qualquer mudança em `besave-envio`, `besave-ciclo` ou no workflow `worker-arm64.yml`.
- Inst2 e papel `envio`.
- Revogar o token do bot do canal no BotFather (decisão do dono; a remoção do `.env` da inst1 basta para este
  ticket).

## Critério de aceite
- `bash infra/vps/teste_instalar.sh` verde no WSL e no CI, com:
  - papel `ciclo` → `bin/` = exatamente `VERSAO besave-ciclo besave-worker` (mutante que volta a instalar os
    3 morre);
  - papel `ciclo` com `besave-envio` antigo → arquivo intacto (mesmo hash) + `AVISO:` (mutante que apaga e
    mutante sem aviso morrem);
  - papel `envio` igual a hoje;
  - `SHA256SUMS` sem `besave-envio` continua falhando nos dois papéis (o artefato é um só).
- `worker.env.example`: cada variável retirada tem no PR a prova de que `besave-ciclo`/`besave-worker` não a
  leem (o `grep`).
- **Real (dono, na inst1, com a branch da PR; bloqueia o merge):**
  1. `systemctl is-enabled besave-envio.timer` → `disabled` e `is-active` → `inactive` (se não, para aqui);
  2. `instalar.sh` com o ID da execução da PR → `VERSAO` com `papel=ciclo`, aviso do `besave-envio` antigo;
  3. `sudo rm /etc/systemd/system/besave-envio.{service,timer}`, `sudo rmdir` da pasta `.service.d`,
     `sudo systemctl daemon-reload`, `sudo systemctl reset-failed`;
     `systemctl list-unit-files 'besave-*'` → sem `besave-envio`;
  4. `sudo rm /srv/besave/bin/besave-envio`;
  5. tirar do `/srv/besave/worker.env` da inst1 as variáveis da saída 5 (cópia do arquivo antes, em `600`,
     apagada depois do passo 6);
  6. dois ciclos seguidos com `Result=success`; `systemd-analyze verify` das unidades do ciclo e do
     `besave-alerta@.service` sem erro (o alerta continua usando `besave-worker`); a inst2 seguindo com o
     envio normal (relatório do `besave-envio` com `enviados` no período).

## Definition of done
PR para `develop` com o instalador, o teste, o roteiro, os exemplos, `validation.md` do Verifier
independente (com sensor de discriminação) e evidência redigida (sem IP, host, caminho de usuário ou token).
