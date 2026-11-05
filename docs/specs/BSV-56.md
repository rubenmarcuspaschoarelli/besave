# BSV-56 · `ID_OFERTA` por sequence no Oracle (fim do contador em arquivo)

**Papel:** Python + SQL · **Pasta:** `tools/capture-chat-groups/` (+ `tools/vps/iniciar_captura.sh` e
`tools/capture-chat-groups/iniciar_captura.ps1`, só a remoção da conferência do contador) ·
**Depende de:** BSV-54 (reinício diário; esta spec tira dele o risco do contador). Lições 28, 29, 31

## Contexto
O `ID_OFERTA` nasce no robô do WhatsApp: `controle.ultimo_id_processado` do `config.json`, somado em 1 a
cada mensagem (`wa/monitor.py:1381` no modo ao vivo, `:806` no catch-up), e gravado no `finally`. Parada
que não é Ctrl+C (queda da máquina, `SIGKILL`, OOM, desligar a instância) deixa o contador atrás do que já
foi gravado.

Por isso a partida roda `diag/checa_contador.py` e **recusa subir** com contador atrasado
(`tools/vps/iniciar_captura.sh`, passo 3), e a unidade fica em laço até alguém corrigir o arquivo à mão.
Isso impede qualquer reinício automático (BSV-54, BSV-57). Também impede um segundo produtor na fila: o
robô de sites (Pelando, Promobit, Pechinchou) não teria de onde tirar id sem disputar o arquivo.

## Decisões do dono (05/11)
- O id é gerado por uma **sequence no banco**, com **trigger** no insert da `OFERTA_FILA_CAPTURA`.
- **Banco fora do ar:** o robô **avisa no Telegram e espera** o banco voltar. Não gera id local.
- Novos produtores (robô de sites) gravam na mesma fila, com as mesmas regras.

## Desenho (e por que não só a trigger)
O robô do WhatsApp usa o id **antes** do insert: ele é o nome do arquivo da imagem
(`storage.salvar_imagem(…, numero, …)`, `storage.renomear_imagem` no catch-up) e a linha do CSV. Com a
trigger sozinha, o id seria conhecido só depois do insert, e a imagem já estaria salva com outro número.
Então:
- o robô pede **`SQ_OFERTA_FILA.NEXTVAL`** imediatamente antes de salvar ou renomear a imagem;
- a **trigger** preenche `ID_OFERTA` **só quando ele vem nulo**. É o caminho de quem não precisa do id
  antes, como o robô de sites, e uma rede de segurança.

## Saídas
1. **SQL** `tools/capture-chat-groups/sql/BSV-56_sequence_id_oferta.sql` (aplicado pelo dono, como
   `BESAVE`, com o robô parado):
   - `SQ_OFERTA_FILA` criada por bloco PL/SQL com `START WITH` = `GREATEST(MAX(ID_OFERTA) da fila, MAX(ID_OFERTA) da OFERTA) + 1`
     (`EXECUTE IMMEDIATE`, porque `START WITH` exige literal), `INCREMENT BY 1 NOCACHE`. `NOCACHE`: volume
     de ~1000/dia; evita buracos grandes e mantém a ordem.
   - Trigger `TRG_OFERTA_FILA_ID` `BEFORE INSERT … FOR EACH ROW WHEN (NEW.ID_OFERTA IS NULL)`.
   - Bloco de conferência (sequence ≥ maior id existente) e bloco de reversão comentado (`DROP TRIGGER`,
     `DROP SEQUENCE`).
   - A SP `STP_OFERTA_FILA_CAPTURA_INSERT` não muda: continua recebendo `P_ID_OFERTA`.
2. **`wa/oracle_db.py`:** `proximo_id()` → `NEXTVAL`, com a reconexão que já existe. Erro de conexão
   depois de reconectar → exceção própria (não devolve número).
3. **`wa/monitor.py`, nos dois caminhos que numeram:**
   - **Fluxo:** o id vem de `proximo_id()`; a imagem é salva ou renomeada com ele; CSV e insert seguem
     como hoje.
   - **Banco fora:** a mensagem **não é processada** e o **marcador do grupo não avança**. Assim, ela é
     relida pelo catch-up quando o banco voltar.
   - **Aviso e espera:** o robô avisa no Telegram (`wa/alerta.py`, uma vez por ocorrência, lembrete a cada
     2 h, "voltou" ao normalizar) e tenta de novo a cada `db.espera_segundos` (padrão 60).
   - **Ordem dos grupos:** os outros grupos não andam enquanto o banco está fora. Sem id não se grava
     nada.
4. **Contador do `config.json`:** `ultimo_id_processado` vira só informativo (último id usado, para log e
   diagnóstico) e **não** é mais lido para numerar.
   - `diag/checa_contador.py` deixa de ser chamado na partida (`iniciar_captura.sh` passo 3 e
     `iniciar_captura.ps1`); o arquivo fica, com nota de que é histórico.
   - A frase "Retomando contador de ofertas em …" sai do log.
5. **README** do robô e de `tools/vps`: a ordem de virada (abaixo) e o fim da conferência do contador.

## Ordem de virada (vai no README e no PR)
1. Parar o robô do WhatsApp (Ctrl+C / `systemctl stop`). Conferir que nenhum `run_captura.py` está vivo.
2. Aplicar o SQL e rodar a conferência.
3. Atualizar o código na inst1 (branch da PR) e subir o robô.
4. Conferir no log a 1ª captura com id = valor inicial da sequence e `db=ok`.

Não pode haver dois robôs do WhatsApp (PC e VPS) em versões diferentes: o antigo continuaria numerando
pelo arquivo e colidiria com a sequence.

## Regras
1. Nenhum caminho de código numera sem `NEXTVAL`; nenhum id é gerado fora do banco.
2. Mensagem sem id não é gravada em lugar nenhum (nem CSV) e não move marcador. Sem fila local.
3. O robô das lojas não muda: no modo monitor ele lê a fila desde 0 por `ID_OFERTA` (`main.py:807`), então
   id fora de ordem de chegada (dois produtores) não é perdido. **Conferir e citar no PR** que isso
   continua verdade.
4. Buracos na numeração são aceitos: o manifest usa `floor(id/1000)` e "oferta nova" é id nunca exibido
   (MANIFEST §2, §3.1).
5. Sem dependência nova. Token e chat nunca em log.

## Fora de escopo
- Robô de sites (ticket próprio, depois do detalhamento do dono). Esta spec só garante que ele pode inserir
  com `ID_OFERTA` nulo.
- Vigia externo (BSV-57). Partida sem perguntas das lojas (BSV-55).
- Renumerar ou corrigir ids existentes.

## Critério de aceite
Testes com Oracle falso e sem Playwright, no padrão dos testes de `tools/capture-chat-groups`.

- **Ao vivo:** 2 mensagens → ids `N` e `N+1` vindos de `proximo_id()`; nome da imagem, linha do CSV e
  `P_ID_OFERTA` com o mesmo id. O `config.json` com um `ultimo_id_processado` absurdo (ex.: 5) **não**
  influencia o id (prova que o arquivo não é mais lido).
- **Catch-up:** a imagem temporária é renomeada com o id do `NEXTVAL`, na ordem cronológica.
- **Banco fora:** `proximo_id()` falha → mensagem não processada, marcador do grupo inalterado, nada no
  CSV, 1 aviso. Banco volta → a mesma mensagem é processada com id novo e chega o "voltou". Lembrete só
  depois de 2 h (relógio falso).
- **Partida:** `iniciar_captura.sh` não chama mais o `checa_contador.py` (teste de comando montado
  inteiro, lição 14). As outras conferências (run vivo, perfil travado) continuam.
- **SQL**, conferido pelo Verifier lendo o arquivo:
  - `START WITH` calculado por `GREATEST` das duas tabelas;
  - trigger só com `WHEN (NEW.ID_OFERTA IS NULL)`;
  - `NOCACHE`;
  - bloco de reversão presente.
- **Gates:** `python -m unittest discover -s tests`, ruff do CI de `tools/`, `shellcheck tools/vps/*.sh`.
- **Real (dono, bloqueia o merge), na inst1 seguindo a ordem de virada:**
  1. 1ª captura com o id inicial da sequence;
  2. `INSERT` de teste com `ID_OFERTA` nulo numa transação (`ROLLBACK` no fim), para provar a trigger;
  3. `KILL SESSION` da conexão do robô seguido de `systemctl restart` com `SIGKILL` (`kill -9` no
     `run_captura.py`): o robô sobe sem conferência de contador e o id seguinte vem da sequence, sem
     repetir.

## Definition of done
PR para `develop` com SQL, código, scripts de partida, README, testes, `validation.md` do Verifier
independente (com sensor de discriminação), evidência da execução real redigida (regra 11) e as decisões
propostas (`NOCACHE`, espera de 60 s, marcador parado com o banco fora) para o `docs/DECISOES.md`.
