# BSV-45 · Robô das lojas: captura local para lojas com captcha, imagens para a VPS

**Papel:** Python (+ configuração de SSH na VPS) · **Pastas:** `tools/capture-store-pages/` e `tools/vps/` ·
**Depende de:** BSV-42 (PR #81) **mergeada** — mexe nos mesmos arquivos (`main.py`, `core/estado.py`,
`core/browser.py`). AD-080, AD-100, AD-104; `docs/infra/VPS-INSTANCIA-1.md`

## Contexto
O robô das lojas vai para a VPS (BSV-42), mas lojas com captcha forte não funcionam lá: no teste de 16/10 a
Shopee deu 0/10 na VPS, e no PC passa quando o dono faz o login e resolve o captcha. O banco é o mesmo para
as duas máquinas (Autonomous na nuvem, AD-100), então o PC pode gravar a captura direto. O que fica no disco
de quem captura são as **imagens** (`<s3.raiz>/ofertas/img/<id>/` e `<s3.raiz>/produtos/img/<id_produto>/`),
e na VPS o worker as envia ao S3 e o envio ao canal usa a foto local (AD-080). Oferta capturada no PC sem a
imagem na VPS sai sem foto no site e no canal.

## Objetivo
Com o mesmo código, a VPS captura todas as lojas menos as "locais" (hoje: Shopee), e o PC do dono captura só
as locais, grava no banco como hoje e entrega as imagens na VPS antes de publicar a oferta.

## Saídas
1. **Modo no `config.json`** (decisão do dono: sem parâmetro de linha de comando), bloco `captura`:
   `modo` = `"completo"` (padrão: comportamento de hoje), `"servidor"` (VPS) ou `"local"` (PC);
   `lojas_locais` (lista de nomes internos das lojas, ex. `["shopee"]`); `prazo_local_horas` (padrão 6);
   `sftp` (só no modo `local`: host, usuário, caminho da chave privada, pasta de destino). Sem o bloco, o
   robô funciona exatamente como hoje. `config.example.json` documenta tudo, sem valores reais.
2. **Divisão da fila por `DS_LOJA`** (decisão do dono, sem valor novo de `ST_CAPTURA`):
   - `servidor`: não processa linha cuja loja (pela `DS_LOJA` ou pela URL) esteja em `lojas_locais`; se só
     descobrir a loja ao seguir uma página-ponte, grava `DS_LOJA` com o nome da loja, deixa
     `ST_CAPTURA='0'` e segue para a próxima;
   - `local`: lê só `ST_CAPTURA='0'` das `lojas_locais`, **sem o ponteiro `ultimo_id_processado`** (a VPS
     devolve linhas antigas), dentro de `prazo_local_horas` pela `DT_CAPTACAO`;
   - prazo vencido: a VPS marca `ST_CAPTURA='9'` com `DS_CAPTURA='sem_captura_local'` (update condicional:
     só se ainda `'0'` e fora do prazo).
3. **Imagens por SFTP** (decisão do dono), no modo `local`, com o cliente `sftp` do Windows (OpenSSH) em modo
   lote: cada arquivo vai com nome temporário e é renomeado no destino; **a imagem sobe antes da
   publicação** da oferta no banco; falha no envio = oferta não publicada, `ST_CAPTURA` volta a `'0'` e o
   motivo vai para o log (nova tentativa na próxima varredura, dentro do prazo).
4. **Lado da VPS** (`tools/vps/`): script e README que criam o usuário `besave-upload` (só SFTP, sem shell,
   só chave, preso numa raiz que dá acesso de escrita apenas às pastas de imagens), com os arquivos
   legíveis pelo usuário `besave` (worker e envio). Bloco `Match User` do `sshd` documentado e testado com
   `sshd -t`.

## Regras
1. Sem o bloco `captura` no `config.json`, nada muda (teste prova: mesma consulta da fila, mesmo fluxo).
2. Nenhuma mudança de schema, procedure ou valor de `ST_CAPTURA`; a única escrita nova é `DS_LOJA` na
   devolução e o `'9'` do prazo.
3. Sem dependência nova de runtime: o `sftp` é chamado por `subprocess`, comando inteiro montado e testado
   (lição 14); a chave nunca aparece em log.
4. As duas máquinas nunca processam a mesma linha: teste com as duas consultas sobre os mesmos dados.
5. Nada de FTP sem criptografia, senha de SSH ou porta nova na VPS (entra pela 22 já liberada só para o IP
   do dono, Fase 0.5 do roteiro).
6. Segredos (chave, host) só no `config.json` fora do git (AD-017; regra 11).

## Fora de escopo
API de afiliados da Shopee (BSV-44), outras lojas além das que o dono puser em `lojas_locais`, IP dinâmico
de casa (atualizar a regra de rede e a lista de IPs do banco continua manual), robô do WhatsApp, worker.

## Critério de aceite
- `pytest` (sem rede, banco nem navegador): as três consultas da fila por modo; devolução pela página-ponte
  (grava `DS_LOJA`, mantém `'0'`); marcação do prazo vencido; comando `sftp` completo (lote com nome
  temporário e `rename`); falha no envio → não publica e volta a `'0'`; sem o bloco `captura` → igual a hoje.
- `shellcheck` limpo e `sshd -t` ok no que for de `tools/vps/`.
- **Real (dono):** VPS em `servidor` e PC em `local` com `["shopee"]` por 1 dia: nenhuma oferta processada
  pelas duas máquinas; ofertas da Shopee publicadas com foto no site e no canal; uma página-ponte que vira
  Shopee devolvida pela VPS e capturada no PC; com o PC desligado por mais de 6 h, as pendentes da Shopee
  viram `'9'`/`sem_captura_local`; o usuário `besave-upload` não consegue abrir shell nem gravar fora das
  pastas de imagens.

## Definition of done
PR com testes verdes, README da VPS atualizado, `validation.md` do Verifier independente e o dia de teste
real do dono antes do merge.
