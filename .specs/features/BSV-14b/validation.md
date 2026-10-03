# BSV-14b — validation

**Veredito: PASS** (auto-verificação do autor, sem sub-agente; não é verificação independente — o Tester/dono deve repetir o item "Real").

Gate: `cargo fmt --check` ok · `cargo clippy --all-targets -- -D warnings` ok · `cargo test` ok (sem rede).
Diff: `31f7274..2d80265`.

| Critério de aceite | Evidência |
|---|---|
| 23 h → 0; 25 h → aviso; até 23h55 → 0; +24 h lembrete; +48 h; "de novo"; ciclo seguinte 0 | `tests/alerta_sem_novas.rs` `aviso_lembretes_e_volta`; lógica `src/alerta.rs:338-395` |
| Lembrete 0 → só aviso e volta; lembrete 6 → a cada 6 h | `lembrete_zero_so_avisa_e_volta`, `lembrete_de_seis_horas` |
| Aviso que falha → retenta; lembrete conta do entregue | `aviso_que_falha_tenta_de_novo_e_lembrete_conta_do_entregue`, `volta_que_falha_tenta_no_proximo_ciclo` |
| Limiar 0 nunca avalia; `abc`/`-1` → código 2 | `limiar_zero_desliga`, `config_do_env`; binário: `tests/cli_ciclo.rs` `alerta_sem_novas_invalido_sai_com_2`; `src/ciclo.rs:231` |
| Card: média ≤ 200 B, título 200 acentuados > 220 B aceito | `tests/card.rs:95` e `card_com_titulo_longo_acentuado_e_aceito` |
| `alerta.json` BSV-14 carrega e preserva `falhas`/`envios` | `arquivo_antigo_preserva_falhas_e_envios`; `#[serde(default)]` em `src/alerta.rs:230` |
| Falha de ciclo não mexe em `sem_novas`; recuperação parada → só "recuperado" | `falha_de_ciclo_nao_mexe_em_sem_novas`; `src/alerta.rs:328` |
| Telegram falhando → WARN, estado não avança, código igual | testes de envio falho acima; `concluir` ignora retorno (`src/execucao.rs:193`) |
| Mensagens sem `http`/token/`C:\Users\`, com `-03:00` | `mensagens_limpas` |
| Conjunto vazio → `última: —` | `conjunto_vazio_alerta_com_traco` |
| `dt_max`/`horas_sem_novas` no relatório, `--dry-run` e `--publicar` | `tests/execucao.rs` `relatorio_traz_dt_max_e_horas_sem_novas`; `tests/dry_run.rs` `dry_run_imprime_dt_max_e_horas_sem_novas`; `src/execucao.rs:149` |
| Integração no ciclo (ok parado → aviso; falha não avalia) | `tests/execucao.rs` `ciclo_ok_parado_alerta_e_falha_nao_avalia` |
| Real (dono) | **Pendente** — fora do alcance do agente. |

## Sensor de discriminação
- Mutante: `sucesso()` zera `sem_novas` na recuperação → **morto** (`falha_de_ciclo_nao_mexe_em_sem_novas`).
- Mutante: limiar deslocado em +1 h (`>= limite + 1 h`) → **sobrevive**. A spec só fixa 23 h → 0 e 25 h → 1; a fronteira exata (24 h) não está definida. Decisão: `agora - dt > limiar` (estritamente mais velho). Gap de precisão da spec, não de teste.
