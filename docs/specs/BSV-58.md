# BSV-58 · Robô das lojas: encurtadores bloqueados resolvidos por IP residencial

**Papel:** Python + shell/PowerShell · **Pasta:** `tools/capture-store-pages/` (+ `tools/vps/` só para o
túnel e o README) · **Depende de:** BSV-55 (linha retida, pausa e Telegram), **mergeada em `develop` antes
de abrir o worktree**. Lições 14, 16, 29

## Contexto
Em 06/11 (início não medido) o `amzn.promos.link` responde, para a inst1, a página do Cloudflare "Sorry, you have been
blocked". É bloqueio por IP (datacenter OCI), não captcha: o VNC não resolve, e outro IP da OCI cai na mesma
regra. Do PC do dono (IP residencial), o mesmo link responde:

```
HTTP/1.1 302 Found
location: https://www.amazon.com.br/dp/<asin>?linkCode=ogi&psc=1&tag=<afiliado-de-terceiro>&th=1
Server: cloudflare
```

Ou seja, o redirect é **HTTP 302** (não JavaScript) e só ele está bloqueado. A Amazon em si abre da inst1.

Efeito medido (`DS_URL_ORIGEM LIKE '%promos.link%'`, últimos 7 dias, 06/11): **265 linhas
`'9' loja_desconhecida`** contra 107 `ok`. Hoje o robô cai na página de bloqueio, não reconhece a loja pelo
`page.url` (`_resolver_ponte`, `main.py`) e grava `'9'`: a oferta é perdida em silêncio.

O mesmo encurtador já apontou para Amazon e para Mercado Livre: a loja só se conhece pelo destino.

## Decisão do dono (06/11)
Alternativa A: **só o redirect** dos domínios configurados sai por um IP residencial (o PC do dono, por
túnel SSH). Captura, imagens, sessões de afiliado e fila continuam na inst1. A lista de domínios é
configurável; hoje é `promos.link`, amanhã pode haver outros.

## Pré-condição (dono, antes de abrir o worktree)
Provar que o túnel funciona com o OpenSSH do Windows (encaminhamento dinâmico reverso, OpenSSH ≥ 7.6 no
cliente):
1. No PC: `ssh -i <chave> -N -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -R 127.0.0.1:1080 ubuntu@<inst1>`
2. Na inst1, outra sessão:
   `curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' --proxy socks5h://127.0.0.1:1080 https://amzn.promos.link/<codigo>`
   → `302 https://www.amazon.com.br/...`
3. O mesmo sem `--proxy` → `403` (prova que o bloqueio é do IP e que o túnel é o que resolve).

Se o passo 2 falhar, esta spec volta para o arquiteto (alternativa B: proxy residencial pago).

**Provado pelo dono em 06/11:** com o túnel, `302 https://www.amazon.com.br/dp/...`; sem ele, `403`.

## Saídas
1. **Configuração** em `conf/config.json` (e `conf/config.example.json`, com `_obs`):
   ```json
   "redirecionamento": {
     "proxy": "socks5h://127.0.0.1:1080",
     "dominios": ["promos.link"],
     "timeout_segundos": 20,
     "max_saltos": 5
   }
   ```
   - Domínio casa por sufixo de **rótulo**: `promos.link` vale para `amzn.promos.link` e `promos.link`; não
     vale para `xpromos.link` nem `promos.link.exemplo.com`.
   - Bloco ausente ou `dominios` vazio = comportamento de hoje.
2. **`core/redirecionamento.py`** (só stdlib + `curl` por `subprocess`, sem dependência Python nova):
   - Para URL de domínio da lista: `curl` pelo proxy **sem seguir redirect** (`-w '%{http_code}
     %{redirect_url}'`, `-o /dev/null`, `--max-time`), um salto por vez, enquanto o destino ainda for de
     domínio da lista, até `max_saltos`. O primeiro destino fora da lista é devolvido; **a página da loja é
     aberta pelo navegador da inst1, direto**, como hoje.
   - Resultado: `(url_destino, None)` ou `(None, motivo)`, com motivo `proxy_indisponivel` (curl não conecta
     no proxy), `bloqueado` (403/429/503 pelo proxy) ou `sem_redirect` (200 sem `Location`, saltos
     esgotados, código inesperado).
   - O comando montado é sempre uma lista (sem `shell=True`) e a URL vai como argumento único.
3. **`main.py`, antes do `_resolver_ponte`:** linha cujo `url` é de domínio da lista é resolvida pelo
   item 2.
   - Destino resolvido → segue o fluxo normal com a URL de destino (`registry.resolver_loja(destino)`); o
     log diz `redirect (proxy) -> <loja>`.
   - `proxy_indisponivel` ou `bloqueado` → status novo **`redirecionamento_indisponivel`**, em
     `STATUS_RETER`: linha fica `'0'`, `oracle=retida(0)`, ponteiro travado, igual à BSV-55.
   - `sem_redirect` → cai no fluxo de hoje (`_resolver_ponte` pelo navegador), que decide `'9'` ou não.
4. **Pausa e aviso por domínio:** a `PausaLojas` da BSV-55 recebe como chave o domínio configurado (ex.:
   `promos.link`) quando a falha é de redirecionamento. 3 seguidas → pausa, Telegram ("promos.link em pausa:
   túnel residencial fora? N linha(s) retida(s)"), lembrete de 6 h e "voltou". Linhas desse domínio em pausa
   ficam `pausada(0)` sem chamar o `curl`; as outras lojas seguem.
5. **Bloqueio do Cloudflare em domínio fora da lista:** se o navegador cair numa página de bloqueio do
   Cloudflare (título `Attention Required! | Cloudflare` ou texto `Sorry, you have been blocked` /
   `you have been blocked`), a linha fica **retida** (`redirecionamento_indisponivel`), não `'9'`, e o log
   e o Telegram dizem: `<dominio> bloqueado pelo Cloudflare; incluir em redirecionamento.dominios?`. É assim
   que um encurtador novo aparece, sem perder oferta.
6. **Túnel no PC:** `tools/vps/tunel_residencial.ps1`: laço que mantém o `ssh -N -R` da pré-condição
   (reconecta em 30 s quando cai, `ServerAliveInterval`, `ExitOnForwardFailure`), log curto em arquivo, sem
   IP nem chave no repositório (lidos de variável de ambiente ou parâmetro). README com a tarefa agendada
   do Windows (ao logar) e como parar.
7. **README** (`tools/vps/README.md`): o que é o túnel, que a porta fica só no `127.0.0.1` da inst1, o que
   acontece com o PC desligado (linhas retidas + aviso, nada perdido) e como incluir um domínio.

## Regras
1. Só os domínios da lista passam pelo proxy, e só o redirect. Nenhuma página de loja, imagem ou login sai
   pelo PC.
2. Falha do túnel nunca vira `'9'`. Sem proxy configurado e domínio na lista → retida + aviso.
3. A URL de destino carrega `tag=` de terceiro; não muda nada: o CTA usa o nosso `DS_URL_AFILIADO`
   (gerado na captura, como hoje). Não regravar `DS_URL_ORIGEM`.
4. Sem dependência nova (Python ou pacote do sistema; `curl` já está na inst1). Sem IP, host, chave ou
   usuário no repositório nem na evidência (regra 11).
5. O robô do WhatsApp não muda.

## Fora de escopo
- Proxy residencial pago (alternativa B) e segunda instância do robô das lojas (alternativa C).
- Reprocessar as 265 linhas antigas: SQL entregue ao dono no PR (abaixo), aplicado por ele.
- Vigia do túnel além do aviso por pausa (a BSV-57 vigia os robôs, não o túnel).

## Reprocessamento (SQL no PR, aplicado pelo dono)
Só linhas recentes valem a pena (oferta velha já passou):
```sql
UPDATE OFERTA_FILA_CAPTURA SET ST_CAPTURA = '0'
 WHERE ST_CAPTURA = '9' AND DS_CAPTURA = 'loja_desconhecida'
   AND LOWER(DS_URL_ORIGEM) LIKE '%promos.link%' AND DT_OFERTA >= SYSDATE - 1;
```
Com `SELECT COUNT(*)` antes, e só depois do teste real passar.

## Critério de aceite
Testes com `curl` e navegador falsos, no padrão de `tools/tests/`. Nenhum espelha a implementação.

- **Domínio:** `amzn.promos.link` e `promos.link` casam; `xpromos.link`, `promos.link.exemplo.com` e
  `amazon.com.br` não.
- **Comando:** comparado inteiro (lição 14): `--proxy` com o valor da config, sem `-L`, com `--max-time`,
  URL como argumento único.
- **Resolução:** 302 → Amazon: destino devolvido e a página aberta pelo navegador é a da Amazon, **sem**
  proxy; 302 → outro domínio da lista → 302 → ML: dois saltos pelo proxy; `max_saltos` esgotado →
  `sem_redirect`.
- **Falha:** curl sem conexão com o proxy → `retida(0)`, nada em `OFERTA`, ponteiro travado; 3 seguidas →
  pausa por domínio + 1 aviso; volta → "voltou" e a linha retida processada. 403 pelo proxy → `retida(0)`.
- **Sem config:** bloco ausente → fluxo de hoje (o mutante que sempre usa proxy falha).
- **Cloudflare fora da lista:** página de bloqueio → `retida(0)` com a sugestão no log, não `'9'`; página
  comum de domínio desconhecido continua `'9' loja_desconhecida` (discrimina).
- **Segredo:** nenhuma saída capturada contém o valor de `proxy` além do log de configuração.
- **Gates:** `cd tools && python -m pytest -q`, ruff do CI de `tools/`, `shellcheck tools/vps/*.sh`.
- **Real (dono, bloqueia o merge), na inst1 com a branch:**
  1. túnel no ar: uma linha `promos.link` nova → `redirect (proxy) -> amazon`, `oracle=ok`, oferta publicada
     com o nosso afiliado;
  2. túnel derrubado (fechar o PowerShell): as linhas `promos.link` ficam `retida(0)`, depois pausa e
     Telegram; Amazon/ML/Shopee diretos seguem `ok`;
  3. túnel de volta: "voltou" e as retidas processadas;
  4. `SELECT` das linhas do teste: nenhuma `'9' loja_desconhecida` de `promos.link` depois do deploy.

## Definition of done
PR para `develop` com config, módulo, integração, script do túnel, README, testes, `validation.md` do
Verifier independente (com sensor de discriminação), evidência redigida e as decisões propostas (túnel SSH
pelo PC, lista por sufixo de rótulo, Cloudflare fora da lista vira retida) para o `docs/DECISOES.md`.
