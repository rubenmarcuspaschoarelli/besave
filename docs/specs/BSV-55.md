# BSV-55 · Robô das lojas: partida sem perguntas e bloqueio que não perde oferta

**Papel:** Python · **Pasta:** `tools/capture-store-pages/` (+ `tools/vps/systemd/besave-captura-lojas.service`
e `tools/vps/README.md`, só a linha de comando e a documentação) · **Depende de:** BSV-52 (mergeada).
AD-107; lições 28, 29

## Contexto
Incidente de 02–05/11: depois do restart das instâncias, o robô das lojas subiu pelo `systemd` e ficou
**3 dias** parado em `Login na Shopee agora? [S/N/Q]` (`main.py:188`, `_gate_login_shopee_arranque`), com a
unidade `active (running)`. Ninguém responde `input()` numa partida automática. Reiniciar não adianta, e o
vigia externo (BSV-57) também não adiantaria.

Na volta, em 05/11, mais duas perdas silenciosas:
- **Shopee sem sessão de afiliado:** `formulario do custom_link nao abriu` → `afiliado=-`, linha gravada
  como sucesso (`ST_CAPTURA='1'`). Oferta sem `DS_URL_AFILIADO` não vai ao site (CONTRATO §10.1): a oferta
  some e a linha sai da fila.
- **Captcha do Mercado Livre** (`/captcha/wall/logged`): não está em `MARCAS_BLOQUEIO` (`main.py:62`, só
  `verify/` e `account-verification`), então virou `pagina_sem_produto` → `ST_CAPTURA='9'`, que o código
  trata como definitivo.

`bloqueado_ou_login` também vai para `'9'` hoje: sessão caída queima a fila inteira daquela loja até alguém
logar.

## Decisões do dono (05/11)
- Uma opção para o robô **não fazer pergunta nenhuma**, assumindo todas as lojas logadas (inclusive a
  Shopee).
- O que não dá para fazer sem pessoa (login, captcha) **avisa no Telegram**.

## Saídas
1. **`--sem-perguntas`** em `main.py`. Com ela, nenhum `input()` é chamado em caminho nenhum:
   - pergunta da Shopee no arranque: segue como o `N` de hoje (a sessão salva no perfil continua valendo);
   - gates de login de afiliado: pulados (como `_pode_perguntar()` falso);
   - `_gate_fechar_navegadores` (`main.py:77`, "Fechou tudo?"): com navegador do **próprio perfil** aberto,
     sai com código ≠ 0 e mensagem clara (o `Restart=on-failure` tenta de novo). Nunca mata processo por
     conta própria.
   A unidade `besave-captura-lojas.service` passa a usar `--monitorar --sem-perguntas`. Sem a opção, o
   comportamento atual (PC, operador no terminal) não muda.
2. **Captcha é bloqueio:** `captcha` entra em `MARCAS_BLOQUEIO`. Conferir também as telas de login e
   verificação conhecidas das três lojas; cada marca nova vem com o exemplo de URL **redigido** no teste.
3. **Bloqueio não sai da fila:** `bloqueado_ou_login` e **sessão de afiliado ausente** (Saída 4) deixam a
   linha em `ST_CAPTURA='0'`, sem gravar `OFERTA`, e o ponteiro não passa dela (mesma regra da BSV-52).
4. **Sessão de afiliado ausente é um motivo distinto:** `link_afiliado` passa a dizer por que não devolveu
   link (`sessao` = formulário/página de login não abriu; `outro` = gerador não devolveu link para essa
   URL). Só `sessao` segura a linha. `outro` mantém o comportamento de hoje.
5. **Pausa por loja:** depois de **3 bloqueios seguidos da mesma loja** (página ou afiliado), o robô
   **pausa aquela loja** por `bloqueio.pausa_minutos` (padrão 60). As linhas dela ficam em `'0'` e são
   puladas, e **as outras lojas continuam**. Ao fim da pausa, ele tenta **uma** linha. Se passar, a loja
   volta. Se falhar, pausa de novo. Sem isso, uma sessão caída gira a fila para sempre (60–100 s por linha).
6. **Telegram:** bloco `alerta` no `config.json` do robô (`telegram_token`, `telegram_chat_id`; fora do
   git, opcional: sem as chaves, só log), com o mesmo formato e a mesma regra de nunca logar o token de
   `capture-chat-groups/wa/alerta.py`.
   - **Quando avisa:** uma mensagem quando a loja entra em pausa (loja, motivo `pagina`/`afiliado`, linhas
     retidas, "entrar no VNC :1 e logar"), lembrete a cada 6 h enquanto durar, e uma de "voltou".
   - **Sem repetição:** no máximo 1 aviso por loja por ocorrência.
7. `tools/vps/README.md`: o que é feito sozinho, o que chega no Telegram, como logar pela tela sem parar
   o robô.

## Regras
1. Nenhuma mudança de schema ou de SP. Os motivos de status continuam em `DS_CAPTURA`.
2. Linhas da pausa ficam em `'0'` de propósito, como `STATUS_MANTER_PENDENTE`: não seguram o ponteiro
   além do que já seguram hoje no modo monitor (que lê a fila desde 0).
3. Sem dependência nova. Token e chat nunca em log, `print` ou exceção.
4. Contagem de "seguidos" é por loja: um sucesso da loja zera a dela; o bloqueio de uma loja não conta
   para outra.

## Fora de escopo
- Vigia externo de batimento e reinício automático: **BSV-57**.
- Reinício diário do WhatsApp: BSV-54. `ID_OFERTA` por sequence: BSV-56.
- Recuperar as linhas de 02–05/11 (decisão já tomada: descartadas com `descartada_atraso_bsv`).
- Login automático (senha/OTP/captcha): continua manual, pela tela.

## Critério de aceite
Testes com página e Oracle falsos (padrão dos testes existentes do robô). Nenhum espelha a implementação.

- **Sem perguntas:** com `--sem-perguntas` e `stdin` que falha se lido, o arranque completo do modo
  monitor chega à 1ª varredura. Sem a opção, a pergunta da Shopee continua sendo feita.
- **Navegador do perfil aberto** com `--sem-perguntas` → código ≠ 0, nenhum processo morto.
- **Captcha do ML** (URL de exemplo redigida) → `bloqueado_ou_login`, linha em `'0'`, `OFERTA` não gravada.
- **Afiliado `sessao`** → linha em `'0'`, `OFERTA` não gravada. **Afiliado `outro`** → comportamento de
  hoje (prova as duas metades).
- **Pausa:** 3 bloqueios seguidos da Shopee → Shopee pausada, linhas de ML e Amazon na mesma varredura
  processadas. 2 bloqueios + 1 sucesso → sem pausa. Fim da pausa com sucesso → "voltou". Fim com falha →
  nova pausa e nenhum "voltou".
- **Telegram:** 1 mensagem por entrada em pausa, lembrete só depois de 6 h (relógio falso), sem token →
  só log, token ausente de toda saída capturada.
- **Gates:** `python -m unittest discover -s tests` e o lint do CI de `tools/` (ruff) verdes.
- **Real (dono, bloqueia o merge):** na inst1 com a branch:
  1. parar a unidade, instalar a `.service` nova e subir **sem** responder nada; conferir no log que a
     varredura começou;
  2. deslogar a Shopee de afiliado no navegador (pela tela) e conferir a pausa, o Telegram e as linhas da
     Shopee em `'0'`;
  3. logar de novo e conferir o "voltou" e as linhas processadas.

## Definition of done
PR para `develop` com código, unidade, README, testes, `validation.md` do Verifier independente (com
sensor de discriminação), a evidência da execução real redigida (regra 11) e as decisões propostas
(limiar de 3, pausa de 60 min, lembrete de 6 h) para o `docs/DECISOES.md`.
