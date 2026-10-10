# WORKFLOW-AGENTES.md — como um agente executa um ticket

Extrato da skill `tlc-spec-driven` (Tech Leads Club, v3.3.0) adaptado ao Besave.
A skill é instalada **na raiz do repositório** (é o workflow, não é da stack) e vale para
todos os apps; os `CLAUDE.md` de cada app só acrescentam regras da stack.

Instalação (uma vez, na raiz): `npx @tech-leads-club/agent-skills install --skill tlc-spec-driven`
Recomendado junto: `--skill coding-guidelines` e o MCP **Context7** (docs atuais de bibliotecas).

---

## 1. O que a skill faz (e o que aproveitamos)

Quatro fases com profundidade automática pelo tamanho da tarefa:

| fase | obrigatória? | quando roda | artefato |
|---|---|---|---|
| Specify | sim | sempre | `.specs/features/<ticket>/spec.md` — requisitos testáveis (EARS), IDs rastreáveis |
| Design | não | só se há decisão de arquitetura nova | `design.md` |
| Tasks | não | só se > 3 passos ou dependências | `tasks.md` — tarefas atômicas, cada uma com `Tests` + `Gate` |
| Execute | sim | sempre | código + testes + 1 commit por tarefa |

No Besave, **Specify quase sempre é curto**: a spec do ticket (`docs/specs/BSV-nn.md`) já
traz objetivo, regras e critério de aceite; o agente converte em requisitos EARS e segue.
Design só aparece se o ticket disser "decidir" algo. Tasks aparece nos tickets de worker
e de página (F1, F2); nos pequenos, fica implícito.

Gates determinísticos (scripts Python da skill, não memória do modelo):
- `validate_spec.py` antes de fechar a spec
- `validate_tasks.py` antes de aprovar tarefas
- `check_commit.py` em cada commit (Conventional Commits)
- `validate_state.py` antes de declarar concluído (exige `validation.md` PASS com evidência `file:line`)

Verifier (automático ao fim da última tarefa, autor ≠ verificador): confere cada critério
de aceite contra o código com evidência, injeta falhas para checar se os testes as pegam
("sensor de discriminação"), escreve `validation.md`. Falhas viram tarefas de correção,
máximo 3 ciclos antes de escalar para o dono.

---

## 2. Regras herdadas (valem em todo ticket)

1. Testes derivam do critério de aceite; nunca espelham a implementação.
2. O runner decide. Nunca enfraquecer, pular ou apagar teste para passar.
3. Um commit atômico por tarefa; marcar a tarefa concluída em `tasks.md` **no mesmo commit**.
4. Aprovar spec/tarefas autoriza só implementação e commits locais. `push`, deploy, banco,
   operações destrutivas: só com ordem explícita.
5. Cadeia de verificação de conhecimento: código existente → docs do repo → Context7 → web
   → "não tenho certeza". Nunca inventar API.
6. Contexto enxuto: carregar só `spec.md` do ticket atual e os trechos do contrato que ele
   aponta; nunca várias specs ao mesmo tempo. Alvo < 40k tokens de contexto.
7. Sem narrar o processo. Entregar o artefato da fase, não "agora vou rodar a fase X".

---

## 3. Adaptações Besave (diferem do padrão da skill)

| padrão da skill | no Besave |
|---|---|
| `STATE.md` = log de decisões, qualquer agente grava | **Só o dono/arquiteto grava**, em `docs/DECISOES.md`, em `develop` via PR (AD-060). Worker em worktree relata propostas no resumo do PR. Evita conflito entre PRs paralelos. |
| `LESSONS.md` / `lessons.json` auto-alimentados pelo Verifier | Desligado nos workers por enquanto (mesmo motivo). O dono coleta lições dos `validation.md` e consolida manualmente. Reavaliar em F5. |
| Sub-agentes por lote de ~7 tarefas | Não usar: no Orca cada sessão já é um ticket (≤ 8 tarefas). Se a spec gerar mais que isso, o ticket está grande — dividir, não delegar. **Exceção: o Verifier é sempre sub-agente** (autor ≠ verificador), pedido explicitamente no prompt (§4). |
| UAT interativo em features com UI | Substituído pelo ticket `BSV-nn-TEST` (agente Tester em sessão separada) nos tickets de F2/F3 com UI. |
| Modelo por papel (tier) | Escolhido por sessão no Orca: tarefas mecânicas em modelo mais barato; contrato, worker e templates de SEO em modelo forte; Tester em modelo forte. |

---

## 4. Prompt inicial padrão (colar no Orca ao abrir a sessão)

```
Ticket BSV-nn. Antes de tudo: `git merge-base --is-ancestor origin/develop HEAD`; se falhar,
pare e avise (o worktree não nasceu de develop). Leia CLAUDE.md e docs/specs/BSV-nn.md, e só os trechos do
docs/CONTRATO.md / docs/MANIFEST.md que a spec aponta.
Use a skill tlc-spec-driven: specify → execute (design/tasks só se necessário).
Pedido explícito do dono: ao fim, lance o Verifier como sub-agente independente (autor ≠ verificador),
com sensor de discriminação; auto-verificação não conta como PASS. Não pergunte se pode lançar o
Verifier: lance. Entregar sem validation.md é entrega incompleta. Antes da PR, tire e olhe os prints.
Escopo = a pasta indicada na spec. Não faça push. Não grave em .specs/STATE.md nem LESSONS.md.
Ao terminar, cole o veredito do validation.md e liste: feito / como testar / fora de escopo /
decisões que propõe / bloqueia o merge (execução real do dono).
```

Para o Tester (quando o ticket tiver `-TEST`):
```
Ticket BSV-nn-TEST. Leia CLAUDE.md, docs/specs/BSV-nn.md e docs/specs/BSV-nn-TEST.md.
Você é o verificador independente da branch <nome>. Não altere código de produção.
Escreva/rode os testes do plano, compare com os critérios de aceite e os orçamentos do
MANIFEST.md §7, e produza .specs/features/BSV-nn/validation.md com PASS/FAIL e evidência file:line.
Só PASS libera a PR.
```

---

## 5. O que fica onde

| item | local | motivo |
|---|---|---|
| skill `tlc-spec-driven`, `coding-guidelines`, Context7 | raiz (`.claude/`) | workflow, independente de stack |
| regras globais + orçamentos + prompt padrão | `CLAUDE.md` raiz | carregado sempre |
| regras Rust / Svelte / Python | `apps/*/CLAUDE.md`, `tools/*/CLAUDE.md` | carregado só ao trabalhar naquela pasta |
| hooks de fmt/lint (`PostToolUse`) | `.claude/settings.json` raiz, filtrando por extensão | o agente não gasta tokens formatando |
| specs de ticket | `docs/specs/BSV-nn.md` | versionado, lido pelo agente e pelo Linear (link) |
| decisões | `docs/DECISOES.md` (só dono) | fonte única |
| artefatos da skill por ticket | `.specs/features/BSV-nn/` | gerados na branch; ficam no histórico do PR |

---

## 6. Lições de processo (BSV-10 a BSV-15, set–out/2026)

| # | regra | por quê |
|---|---|---|
| 1 | **Worktree sempre a partir de `develop`.** Conferir no início da sessão (prompt §4); PR sempre com `--base develop`. | `main` está atrás e sem CLAUDE.md, specs nem código atual: o agente implementaria sobre um repo vazio. Aconteceu duas vezes (BSV-20, BSV-12c); nas duas o agente detectou e rebaseou em `develop`, mas a regra não pode depender disso. |
| 2 | **`CARGO_TARGET_DIR=C:\cargo-target\besave` compartilhado, `CARGO_BUILD_JOBS=4`** (o Verifier pode usar 2). Nunca `cargo clean` no diretório compartilhado. | Um `target/` por worktree custa GBs e recompila tudo; a máquina tem pouca RAM. |
| 3 | **Evidência revisada por segredo antes do commit (regra 11).** Antes de commitar log, relatório ou print, buscar `C:\Users\`, token de bot (`\d+:[A-Za-z0-9_-]{30,}`), `chat_id`, ARN com conta, hostname interno → `REDACTED`, e avisar no PR. | O repositório é público; evidência de execução real é onde o segredo vaza. |
| 4 | **Contrato + worker na mesma PR (regra 10, AD-038).** | O contrato 1.3 entrou antes de `Area::Outros` e deixou `develop` vermelha. |
| 5 | **"Pendente do dono" bloqueia o merge.** Execução real (Oracle/AWS) com infra existente vai na PR em "Bloqueia o merge", não em "depois". | Achados da execução real (permissão IAM, coluna mapeada errada) entram na mesma PR. |
| 6 | **`aws cloudfront test-function` é obrigatório** para toda mudança em CloudFront Function, com os eventos de fixture; teste em Node não basta (AD-030). | O runtime `cloudfront-js-2.0` não é Node: `await` como argumento passou nos testes e quebrou na borda. |
| 7 | **Teste real fora do diretório do repo antes de agendar:** rodar o executável de `C:\besave\bin` com outro diretório de trabalho e o `.env` de produção. | O caminho relativo de `mapeamento.json` só funcionava dentro do checkout (AD-050). |
| 8 | **Tempo por fase (`t_*` no relatório) é a ferramenta de diagnóstico.** Ticket de desempenho traz `t_*` antes e depois, medidos na execução real (AD-043). | Achou a listagem da KVS (300–490 s por ciclo) que nenhum palpite apontava. |
| 9 | **Promoção para produção:** o teste real usa o binário (ou o `apply`) da **branch da PR**, antes do merge; depois do merge em `develop`, PR `develop → main` (merge commit). O que está em `C:\besave\bin` é idêntico ao que entra em `main` (AD-060). | Teste real antes do merge (lição 5) e produção rastreável a um commit, sem compilar duas vezes. |
| 10 | **O Verifier é pedido explicitamente no prompt** (§4). O validation.md diz quem verificou; "auto-verificação do autor" não é PASS. | O Claude Code não lança sub-agente sem pedido do usuário. Na BSV-14b (Sonnet) o agente seguiu essa regra, fez só auto-verificação e um mutante de fronteira sobreviveu. |
| 11 | **Mock com o mesmo valor para dois recursos não prova qual deles o código referencia.** Nesses casos a verificação lê o código (como já se faz com `prevent_destroy`), ou o mock dá valores distintos. | Na BSV-16, a distribuição curta podia usar o certificado antes da validação e o teste não pegava (ARN igual no mock). |
| 12 | **Conferir que o CI rodou** (`gh run list` / aba Checks da PR) antes de aceitar "verde". Falha em 0 s é workflow inválido, não sucesso; o merge em `develop` exige os status checks. | O `ci.yml` teve YAML inválido de 25/09 a 03/10: 40 execuções falharam em 0 s e nenhuma PR passou por CI. |
| 13 | **Verifier com mutantes em lotes de 5 a 10 e `CARGO_BUILD_JOBS=1`** quando a máquina estiver carregada; pedir isso no prompt. | Na BSV-41 o sensor de mutantes foi encerrado por falta de memória antes do primeiro resultado. |
| 14 | **Teste de comando montado compara o comando inteiro**, não flag por flag. | Na BSV-17, proibir só `--size-only` deixou passar `--no-overwrite` e `--exclude 'immutable/*'`, que reintroduziam o defeito ou quebravam o site. |
| 15 | **Teste de tempo mede com aquecimento e mediana**, nunca uma execução só. | O DES-02 (BSV-35) falha às vezes com a máquina ocupada por outras sessões, sem regressão de código. |
| 16 | **Teste que grava em produção usa prefixo de teste e apaga o que criou.** | Três arquivos de 1 byte ("x") em `elas/` e `esporte-vida/` ficaram no bucket depois de um teste de permissão e quebraram `/elas/` por horas; sem `Cache-Control`, o navegador guardou o "x" por conta própria. |
| 17 | **Não rodar teste de tempo enquanto outro worktree compila ou roda mutantes**; o Verifier roda os de tempo por último, sem carga. | DES-01/02 falharam só com a máquina ocupada (BSV-30b), sem regressão. |
| 18 | **Mutante em rota/`entries` de site estático costuma ser equivalente** (o build segue os links); registrar como equivalente, não forçar teste. | BSV-30b: matcher e `entries` redundantes não mudavam o build. |
| 19 | **Print é evidência, não enfeite: o autor olha os prints antes de abrir a PR.** | BSV-32: o botão de novas ofertas saía com altura zero; testes e mutantes passavam porque só mediam posição. O print mostrou, e o e2e passou a exigir altura mínima. |
| 20 | **Em Sonnet, o prompt manda lançar o Verifier, sem pedir confirmação.** | BSV-14b e BSV-32 (Sonnet) entregaram sem Verifier e perguntaram se podiam lançá-lo, mesmo com "pedido explícito do dono" no prompt. |
| 21 | **O Verifier roda todos os gates do job de CI que o ticket toca**, não só o principal. | BSV-18: o Verifier rodou só o `terraform test`; o `npm test` das Functions, no mesmo job `infra`, falhou só no CI. |
| 22 | **Limite relativo ("≤ 90% da área") exige no teste um segundo grupo de dados**, senão calcular sobre o total também passa. | BSV-33: mutante W5 sobreviveu na 1ª rodada. |
| 23 | **Filtro aplicado antes de uma função pura precisa de teste em quem chama.** No Windows, mutantes do worker rodam só os testes relevantes (`cargo test --test …`). | BSV-33: expiradas fora do sitemap não eram testadas; mutantes do worker levavam minutos cada. |
