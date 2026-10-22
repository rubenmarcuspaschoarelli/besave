# BSV-47 · Worker: expurgo em lotes de madrugada, limites de tempo e alerta de ciclo encerrado

**Papel:** Backend Rust · **Pastas:** `apps/worker/`, `infra/vps/` (+ `docs/MANIFEST.md` §1 e §6,
`docs/CONTRATO.md` §7, mesma PR) · **Depende de:** BSV-43 (PR #80) mergeada.
CONTRATO §7; MANIFEST §6; AD-028, AD-041, AD-044, AD-060, AD-104

## Contexto
Primeiro dia na VPS (20/10). Em 13/10, 14.577 ofertas foram desativadas de uma vez; em 20/10 completaram
os 7 dias e saíram do conjunto publicado. O worker apaga uma chave por chamada (`DeleteObject`, ~140 ms):
14,5 mil páginas antes do manifest (`paginas.rs`) e 29 mil imagens depois (`geracao.rs`), ~1h45. Com o
limite de 4 min do systemd, cada ciclo era encerrado no meio e o seguinte recomeçava a mesma lista (o
índice só é gravado no fim): site parado de 17:30 a 20:30, sem alerta do worker (processo morto pelo
systemd não avisa). Contornado adiando o expurgo para as 02:00 de 21/10. Outros achados do dia: um ciclo
preso 40 min numa conexão HTTPS sem resposta (sem limite de tempo nas chamadas); a imagem expurgada depois
do manifest se perde para sempre se o ciclo cair nesse trecho (o próximo compara com um manifest que já
não tem o id); o modelo `worker.env.example` levou a `AWS_PROFILE` inexistente e a senha com `$` lida
vazia.

## Objetivo
Nenhum expurgo, por maior que seja, segura a publicação de ofertas novas; nenhuma chamada de rede trava o
ciclo; toda parada do ciclo gera alerta.

## Saídas
1. **Expurgo diferido e em lotes.** Id que sai do conjunto publicado sai no mesmo ciclo dos chunks, do
   sitemap e da contagem; a remoção da página, das duas imagens e da chave na KVS vai para uma fila
   persistida em `_estado/expurgo.json` (id e data de entrada). A fila só é executada na janela
   `BESAVE_EXPURGO_JANELA` (padrão `02:00-05:00`, hora de Brasília) e até `BESAVE_EXPURGO_MAX` ids por
   ciclo (padrão 3000), com `DeleteObjects` de até 1000 chaves por chamada; o estado é gravado depois de
   cada lote (ciclo interrompido retoma de onde parou, sem repetir). Fora da janela, nada é apagado.
2. **Reconciliação única de órfãs:** imagens em `img/ofertas/` e páginas em `oferta/` de ids fora do
   conjunto publicado e fora da fila entram na fila (sobras das execuções interrompidas de 20/10).
3. **Limites de tempo:** AWS com tempo de conexão, de tentativa e de operação configurados no cliente;
   Oracle com tempo por chamada; estouro vira erro com a operação e a chave no log e alerta normal.
4. **Alerta de ciclo encerrado pelo sistema:** `OnFailure=` nas unidades `besave-ciclo` e
   `besave-envio` dispara uma unidade que avisa no Telegram pelo mesmo bot e com a mesma regra de
   repetição do alerta do worker (subcomando do próprio binário; nenhum segredo na unidade).
   `TimeoutStartSec=15min` nas duas unidades.
5. **Modelo do `.env`:** `AWS_ACCESS_KEY_ID` e `AWS_SECRET_ACCESS_KEY` no lugar de `AWS_PROFILE`;
   `AWS_REGION=...`; aspas simples documentadas para valores com caractere especial; falha clara
   ("credenciais AWS ausentes") em vez de cair no serviço de metadados de instância.
6. Docs na mesma PR: CONTRATO §7 (expurgo na janela noturna, em lotes) e MANIFEST §1 e §6 (nova chave
   `_estado/expurgo.json`, passo 7 com janela).

## Regras
1. Idempotência mantida (AD-028): sem mudança no Oracle, nenhum objeto muda além dos manifests; fila
   vazia fora da janela não faz chamada nenhuma.
2. O manifest nunca espera o expurgo: publicar ofertas novas vem antes de apagar as velhas.
3. Expurgo diário normal (~400 ofertas) cabe numa noite; um lote acima do máximo continua nas noites
   seguintes e aparece no relatório (`expurgo_pendente=`).
4. Sem dependência nova (o SDK da AWS e a crate `oracle` já têm os limites).
5. Teste de tempo com aquecimento e mediana (lição 15); mutantes em lotes com `CARGO_BUILD_JOBS=1`.

## Fora de escopo
Robôs (BSV-48), mudança da regra de 7 dias, `410` para oferta expurgada, KVS por Lambda.

## Critério de aceite
- Com publicador simulado: 14.577 ids saindo → nenhuma remoção fora da janela; na janela, no máximo
  `ceil(chaves/1000)` chamadas por lote; interrupção no meio de um lote e novo ciclo → continua sem repetir
  e sem perder chave; manifest publicado antes de qualquer remoção.
- Órfãs: imagem e página de id fora do conjunto entram na fila uma vez.
- Limites: servidor local que aceita a conexão e não responde → erro dentro do limite configurado (AWS e
  Oracle simulados); configuração conferida inteira.
- `OnFailure`: `systemd-analyze verify` limpo; a unidade de alerta lê só o `.env`; teste do subcomando.
- Gates: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`; workflow ARM verde.
- **Real (dono):** na VPS, uma noite com a fila cheia (sobras de 21/10), relatório de manhã com
  `expurgo_pendente=0`; durante o dia, uma desativação nova sai da lista na hora e o arquivo só some de
  madrugada; ciclo encerrado à força (`TimeoutStartSec` curto por 10 min) gera alerta no Telegram.

## Definition of done
PR com testes verdes no x86 e no ARM, CONTRATO e MANIFEST atualizados, `validation.md` do Verifier
independente e a noite de teste real antes do merge.
