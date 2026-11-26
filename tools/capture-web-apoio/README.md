# Captura web de apoio (BSV-66)

Programa auxiliar que roda no **PC do dono** (Windows, IP residencial). Lê três sites de ofertas
(Pelando, Promobit, Pechinchou) e põe na `BESAVE.OFERTA_FILA_CAPTURA` algumas ofertas de Amazon, Mercado Livre
e Shopee, como uma linha do WhatsApp (`DS_TIPO_ORIGEM = 'CAPTURA WEB'`). O robô das lojas faz o resto: abre a
página da loja, cadastra produto e imagem, gera o **nosso** link de afiliado e aplica as regras de sempre.
Serve de complemento e de reserva quando o WhatsApp cai.

- Sem navegador: as ofertas vêm do JSON dentro do HTML da lista (`urllib`). Uma requisição por menu; no
  Promobit, mais uma por oferta escolhida (`/Redirect/to/{id}/`). Nada de `/api/*`.
- Pausa aleatória de 3–6 s entre todas as requisições; 403/429 para o site na rodada.
- Grava só a URL **limpa** da loja (`/dp/{ASIN}`, ML sem query, `/product/{shop}/{item}`): marca de afiliado
  de terceiro (`tag=`, `matt_`, `utm_`...) nunca vai para o banco nem para o log.
- Cotas: até 5 por menu e 30 por rodada, em rodízio entre os sites (cerca de 10 cada).
- Pula oferta já vista: estado local de 7 dias (`estado/vistas.json`), mesma rodada, mesmo produto na fila
  (24 h) ou numa oferta ativa com preço igual ou menor, mesmo título na fila (24 h, mesma loja, preço ±1%).
  Mais barata que a publicada **entra** (a duplicidade do robô das lojas desativa a mais cara).

## Instalação (Windows)

Python 3.11 ou mais novo. Na pasta `tools\capture-web-apoio`:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy conf\config.example.json conf\config.json
```

Edite `conf\config.json` (fora do git): bloco `db` como no robô das lojas (`modo`, `instant_client_dir`,
`config_dir`/`dsn` do wallet) com `usuario` = `BESAVE_WEB`; bloco `alerta` com o mesmo bot/chat do robô das
lojas (vazio = só log). A senha fica de preferência na variável `BESAVE_WEB_SENHA` (vence a do arquivo):

```powershell
[Environment]::SetEnvironmentVariable('BESAVE_WEB_SENHA', '<senha>', 'User')
```

Chave inválida no `config.json` cai no padrão com WARN no log.

### Usuário do banco

Uma vez, como ADMIN: `sql\bsv-66-usuario.sql` (pede a senha na variável `&senha`). Cria `BESAVE_WEB` com
`CREATE SESSION`, `SELECT, INSERT` na fila e `SELECT` em `OFERTA`. Reversão comentada no fim do arquivo.

## Uso

```powershell
.\.venv\Scripts\python main.py --simular   # lê, filtra e mostra o que gravaria; não grava nem muda o estado
.\.venv\Scripts\python main.py             # uma rodada agora
```

No `--simular` as consultas de "já vista" no banco rodam (só leitura); sem banco, elas são puladas com WARN.
Uma rodada por vez: a segunda instância sai com código 2. Saída 1 = banco fora do ar.

### Agendamento

```powershell
powershell -ExecutionPolicy Bypass -File .\agendar.ps1            # 08:00, 12:00 e 17:00
powershell -ExecutionPolicy Bypass -File .\agendar.ps1 -Horarios 09:00,18:00
powershell -ExecutionPolicy Bypass -File .\agendar.ps1 -Mostrar   # só mostra o que registraria
powershell -ExecutionPolicy Bypass -File .\agendar.ps1 --remover
```

Tarefa `besave-captura-web`: usuário atual, só quando logado, sem "executar assim que possível" (PC desligado
no horário = rodada perdida), sem repetição, limite de 30 min. Usa `.venv\Scripts\python.exe` (ou `-Python`).

## Como ler o log

`log\captura_web.log` (rotação diária, 14 dias). No fim de cada rodada, uma linha por site e menu:

```
[resumo] Promobit /: lidas=8 validas=5 gravadas=3 descartes: loja_fora=1, vista_local=1 ids=[41230, 41231, 41233]
```

| descarte | significado |
|---|---|
| `status`, `tipo`, `oculta`, `tipo_preco`, `preco_texto`, `incompleta` | inválida pela tabela do site (encerrada, cupom sem produto, preço "a partir de"...) |
| `antiga` / `futura` | publicada há mais de `idade_max_horas` (24) / mais de 10 min no futuro |
| `loja_fora`, `url_invalida`, `url_longa` | não é Amazon/ML/Shopee, URL sem produto, URL limpa > 350 |
| `sem_url`, `encurtador_nao_resolvido` | redirect do Promobit sem link; encurtador sem `Location` em 3 saltos |
| `vista_local`, `vista_rodada`, `vista_fila`, `vista_oferta`, `mesmo_titulo` | já vista (os 4 casos) |
| `sem_preco` | preço ausente ou zero |
| `erro_banco`, `erro_insert` | erro do banco que não é de conexão; a oferta é tentada na próxima rodada |

## Avisos no Telegram (uma mensagem por rodada, só com problema)

| aviso | o que fazer |
|---|---|
| `<site> estrutura mudou em <menu>` | O site mudou o HTML. Baixe a página de novo, refaça o recorte em `tools/tests/fixtures/web/` (veja o README de lá) e atualize o extrator em `webapoio/extrair.py`. Até lá o site só gera esse aviso. |
| `<site> bloqueado (HTTP 403/429)` | O site recusou o IP. Normalmente passa sozinho; se repetir, desligue o site (`sites.<SITE>.habilitado: false`) ou aumente `pausa_s`. |
| `<site> sem resposta` | Timeout ou erro 5xx duas vezes. Se repetir, confira a internet do PC e o site no navegador. |
| `banco fora do ar; gravadas N oferta(s) antes da falha` | Confira wallet, senha e rede. As já gravadas ficam; a próxima rodada tenta de novo. |

Site que leu tudo e não achou oferta válida não gera aviso (só log).
