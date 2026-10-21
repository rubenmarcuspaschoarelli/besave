# BSV-47 Worker: expurgo em lotes de madrugada, limites de tempo e alerta de ciclo encerrado

Fonte: `docs/specs/BSV-47.md`. Contrato: CONTRATO §7; MANIFEST §1 e §6.

## Problem Statement

Em 20/10, 14.577 ofertas completaram 7 dias desativadas. O worker apagava uma chave por chamada
(~1h45) e o limite de 4 min do systemd matava o ciclo no meio; o seguinte recomeçava a mesma lista.
Site parado das 17:30 às 20:30, sem alerta. Houve também um ciclo preso 40 min numa conexão sem
resposta e um modelo de `.env` que levou a credencial errada.

## Goals

- [ ] Nenhum expurgo, por maior que seja, segura a publicação de ofertas novas.
- [ ] Nenhuma chamada de rede trava o ciclo.
- [ ] Toda parada do ciclo gera alerta.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Robôs de captura | BSV-48 |
| Regra de 7 dias, `410` para oferta expurgada, KVS por Lambda | spec |

## Assumptions

| Decisão | Padrão escolhido | Motivo |
| ------- | ---------------- | ------ |
| Onde vive a config do expurgo | `ConfigSite.expurgo` (lida de `BESAVE_EXPURGO_*` junto com `BESAVE_BASE_URL`) | `gerar` já recebe `ConfigSite`; evita mudar 26 chamadas |
| Chave da KVS do id na fila | Fica na KVS e no índice `_estado/redirects.json` até a janela | O `UpdateKeys` é de 50 em 50; 14,5 mil deletes seriam centenas de chamadas |
| Id cortado ao meio pela fronteira do lote | Fica na fila até a última chave; reenvia no máximo 2 chaves | `DeleteObjects` de chave ausente não falha; evita estado por chave |
| Unidade de alerta | `besave-alerta@.service`, `besave-worker --alerta-encerrado <unidade>`, variante `EncerradoPeloSistema` | Sem segredo na unidade; reusa `Alertas::falha` (2 h por variante) |
| Falha no expurgo | Erro do ciclo (alerta normal), depois do manifest | Rodou depois dos passos 1–5; o site já foi publicado |

## Requirements

| ID | Requisito (EARS) |
| -- | ---------------- |
| EXP-01 | QUANDO um id sai do conjunto publicado, O worker DEVE tirá-lo de chunks, sitemap e contagem no mesmo ciclo e pô-lo na fila `_estado/expurgo.json` (id e data de entrada), gravada antes de qualquer upload e do manifest. |
| EXP-02 | ENQUANTO `agora` (Brasília) estiver fora de `BESAVE_EXPURGO_JANELA` (padrão `02:00-05:00`), O worker NÃO DEVE fazer nenhuma chamada de remoção. |
| EXP-03 | DENTRO da janela, O worker DEVE apagar até `BESAVE_EXPURGO_MAX` ids (padrão 3000) por ciclo com `DeleteObjects` de até 1000 chaves por chamada (`ceil(chaves/1000)` chamadas) e gravar a fila depois de cada chamada. |
| EXP-04 | SE o ciclo for interrompido no meio, ENTÃO o ciclo seguinte DEVE continuar da fila gravada, sem perder chave. |
| EXP-05 | O manifest DEVE ser gravado antes de qualquer remoção. |
| EXP-06 | Imagens e páginas de ids fora do conjunto publicado e fora da fila DEVEM entrar na fila uma única vez (reconciliação). |
| EXP-07 | QUANDO um id da fila voltar ao conjunto publicado, ENTÃO ele DEVE sair da fila sem ser apagado. |
| EXP-08 | Sem mudança no Oracle e com fila vazia, O ciclo NÃO DEVE gravar nada além dos manifests nem chamar remoção. |
| EXP-09 | O relatório DEVE trazer `expurgo_enfileirados`, `expurgo_removidos`, `expurgo_pendente` e `t_expurgo`. |
| LIM-01 | O cliente AWS DEVE ter tempo de conexão, de leitura, de tentativa e de operação; servidor que aceita e não responde DEVE virar erro com a operação e a chave dentro do limite. |
| LIM-02 | O Oracle DEVE ter tempo por chamada (`BESAVE_ORACLE_TIMEOUT_S`, padrão 120 s), aplicado à conexão. |
| UNI-01 | `besave-ciclo.service` e `besave-envio.service` DEVEM ter `OnFailure=besave-alerta@%n.service` e `TimeoutStartSec=15min`. |
| UNI-02 | A unidade de alerta DEVE ler só o `.env` (`EnvironmentFile`), sem segredo, e rodar `besave-worker --alerta-encerrado %i`. |
| UNI-03 | O subcomando DEVE avisar no Telegram pelo mesmo bot e com a regra de repetição do alerta do worker (1 envio por variante a cada 2 h). |
| ENV-01 | O modelo do `.env` DEVE trazer `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, documentar aspas simples e NÃO ter `AWS_PROFILE`. |
| ENV-02 | SEM credenciais AWS, O worker DEVE falhar com "credenciais AWS ausentes" em vez de usar o serviço de metadados. |
| DOC-01 | CONTRATO §7 e MANIFEST §1 e §6 DEVEM descrever a fila, a janela e a chave `_estado/expurgo.json` na mesma PR. |

## Cobertura

Testes: `tests/expurgo.rs` (EXP-01..09), `tests/aws_limites.rs` (LIM-01, ENV-02), `tests/oracle.rs` (LIM-02),
`tests/unidade.rs` e `tests/unidades_vps.rs` (UNI-01..03, ENV-01). Ajustados para o novo
comportamento: `tests/ciclo.rs`, `tests/geracao.rs`, `tests/indice_redirects.rs`, `tests/plano.rs`,
`tests/paginas.rs`, `tests/site.rs`, `tests/dry_run.rs`, `tests/worker_env_vps.rs`.
