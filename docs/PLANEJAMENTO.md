# Besave — Visão do projeto

Documento de contexto, em linguagem simples, para quem chega agora (pessoa ou agente).
**Não é fonte de verdade.** Quando este texto e outro arquivo discordarem, valem, nesta ordem:
`docs/CONTRATO.md` (dados), `docs/MANIFEST.md` (S3/CloudFront), `docs/DECISOES.md` (por que), e a
spec do ticket em `docs/specs/`. Atualizado em 06/10/2026.

---

## 1. O que é o Besave

Um site (e depois um app) onde a pessoa encontra ofertas e cupons de Amazon, Mercado Livre e
Shopee, organizados em 10 áreas de interesse: Tech, Players, Meu Lar, Elas, Eles, Cultura,
Família & filhos, Pets, Esporte & vida e Outros. O público inicial é feminino (beleza e moda —
hoje 73% das ofertas estão em "Elas"), mas a estrutura já serve masculino, unissex e infantil.

O dinheiro vem de comissão de afiliado: quando alguém clica em "Acesse a oferta" e compra na
loja, a loja paga uma parte. Por isso todo clique passa por um endereço nosso (`/ir/{id}`) que
registra o clique e manda a pessoa para a loja.

O tráfego deve vir metade do Google (busca orgânica) e metade dos nossos canais (Telegram,
depois WhatsApp, TikTok, Instagram), onde as ofertas serão publicadas com links curtos do tipo
`besave.io/5412`.

Referência de produto: promobit.com.br. Teto de custo na AWS: US$ 40/mês.

## 2. Como funciona, em uma frase por peça

**Robôs (Python, já existem).** Capturam ofertas nas lojas e em grupos, classificam por área e
público, baixam a imagem em dois tamanhos (natural e `-small`) e gravam tudo num Oracle local.
Quando uma oferta morre, o robô marca `ST_ATIVO = 0` e a data de desativação.

**Worker (Rust, roda na sua máquina a cada 5–10 min).** Lê o Oracle e publica na AWS:
- os dados de todas as ofertas, em pacotes pequenos ("chunks") comprimidos, mais um índice
  chamado `manifest.json` que diz quais pacotes existem;
- uma página HTML pronta para cada oferta (`/oferta/{id}/`), feita para o Google indexar;
- as imagens;
- a tabela que faz o `/ir/{id}` redirecionar para a loja certa.

**AWS (só armazenamento e entrega — nenhum servidor).** Um bucket S3 privado guarda tudo;
o CloudFront entrega a partir de pontos de presença no Brasil, com cache. Não há banco de dados
nem servidor de aplicação no caminho de leitura. Isso é o que mantém o custo perto de zero e
faz o site aguentar pico sem cair.

**Site (SvelteKit, ainda não existe).** A home, as páginas de área e a busca. Ele baixa o
`manifest.json`, depois os chunks aos poucos, e mostra os cards. A busca roda no próprio
navegador, sobre todos os ~25–30 mil registros, sem chamar servidor. As imagens dos cards
carregam conforme a pessoa rola.

**App (Capacitor, depois).** O mesmo site embalado para Android e iOS, com notificação push.

**Canais (depois).** Bot do Telegram publicando ofertas novas no canal; WhatsApp só em modo
Canal (broadcast), nunca automação de grupos.

## 3. As ideias que sustentam o desenho

1. **Tudo estático.** Se não precisa de servidor, não tem servidor. Dinâmico só onde é
   inevitável: o redirect de clique (uma função de borda, sem servidor) e, no futuro, a API de
   usuários (favoritos, alertas) em Lambda + DynamoDB.
2. **Um só arquivo mutável: o `manifest.json`.** Todo o resto (chunks, imagens, páginas) é
   imutável e tem o nome ligado ao conteúdo. Quando algo muda, nasce um arquivo novo e o manifest
   passa a apontar para ele. O navegador baixa só o que mudou; o CloudFront cacheia o resto para
   sempre.
3. **Duas versões de cada oferta.** Uma compacta (~40 bytes comprimidos) que vai na lista e na
   busca, e uma completa que só existe dentro da página HTML da oferta. Nunca mandar a completa
   em lista: 30 mil × 1,2 KB não cabe no 4G nem no orçamento.
4. **A página de oferta é HTML puro, gerada pelo worker.** Sem JavaScript, com `title`,
   `schema.org`, `canonical` e imagem — é o que o Google lê. URL `/oferta/{id}/`, sem título na
   URL, para que o link curto numérico funcione nos canais.
5. **Oferta expirada não some na hora.** Fica visível 7 dias com faixa "expirada", imagem em
   cinza e sem botão de compra; depois sai do site (o registro continua no Oracle). Assim um link
   compartilhado ontem não vira erro hoje.
6. **Dinheiro em centavos inteiros, datas em UTC, categorias fechadas.** Texto livre do Oracle
   vira enum por uma tabela de sinônimos (`mapeamento.json`); o que não mapeia é rejeitado e
   logado, nunca publicado "mais ou menos".
7. **Nenhuma URL de loja no site.** Só `/ir/{id}`. Troca de rede de afiliado sem regerar 30 mil
   páginas, e o Google não vê link de afiliado.

## 4. Onde estamos (06/10/2026)

**O site está no ar em `besave.com.br`, indexável.** A cada 5 minutos o Agendador do Windows executa
`C:esaveinesave-ciclo.exe`, que lê o Oracle e publica na AWS só o que mudou: chunks, imagens,
páginas de oferta, sitemap e redirects. Ciclo em regime: ~25 s. Hoje são ~25 mil ofertas válidas.

Feito e no ar:
- `besave.com.br` na distribuição nova (`www` → 301 para o domínio sem www), `robots.txt` liberado,
  sitemap e Google Search Console verificado. Home e 404 ainda provisórias (BSV-30).
- Links curtos `besave.io/{id}` e `besave.me/{id}` → `/oferta/{id}/` (BSV-16).
- Uma página HTML por oferta (`/oferta/{id}/`), com imagem, preço, cupom e botão `/ir/{id}`.
- Redirect de afiliado na borda, com autocorreção quando alguém mexe na tabela por fora.
- Alertas no Telegram: ciclo que falha, site parado (vigia na AWS) e nenhuma oferta nova em 24 h.
- Canal `@besaveofertas` no ar: até 180 ofertas por dia em lotes de 2 (8–22 h), "Oferta encerrada" na
  expiração e avisos programados com página `/avisos/{id}/` (BSV-40, BSV-41).
- Cards com data de publicação no site (`dp`, contrato 1.5.0, BSV-36).
- Página da oferta com "Copiar cupom e ir para a loja" (aba nova) e filtros compactos no computador
  (BSV-37, BSV-38, 09/10).
- Camada de dados do site (BSV-35): manifest, chunks, sincronização e busca no cliente, sem UI;
  medida em produção: 25 mil cards, busca p95 ~8 ms.
- Contrato 1.5.0, 97 decisões registradas, CI funcionando desde 03/10 (YAML inválido até a PR #21).

Próximos, nesta ordem:
- **BSV-34** (página de busca), depois "dieta" do bundle se a home voltar a encostar no gate (AD-090).
- **Infra:** state do Terraform em backend S3 versionado com trava (hoje só no PC do dono; até lá, backup manual
  do `terraform.tfstate` fora do PC); desligar o protótipo (roteiro manual do dono).
- **Tickets pequenos:** DES-02 com aquecimento e mediana; limpeza do worker (literal de caminho em
  `tests/alerta.rs`, avisos no `--publicar`/`--dry-run`, `META_CSS` sem uso, MANIFEST §6 com avisos).
- **Robô:** código do robô das lojas no repositório (499 ofertas publicadas sem imagem, 1,9%); um cupom por
  oferta; marcar expiradas (`ST_ATIVO = 0`); regra Elas/Eles revista pelo dono em 09/10.
- Depois: usuários (F5), app (F6), admin (F7).

Em aberto: tamanho da imagem `-small` (200 px hoje; subir
até 320 px, o teto do contrato — AD-059), cupons da tabela CUPOM no site, e quando tirar o worker do
PC do dono.

## 5. Como o trabalho é feito

Um ticket por vez, cada um com uma spec de uma página em `docs/specs/BSV-nn.md`: objetivo,
entradas, saídas, regras, fora de escopo, critério de aceite que dá para verificar. O agente
(Claude Code, dentro do Orca, num worktree isolado) segue a skill `tlc-spec-driven`: transforma
a spec em requisitos testáveis, implementa, e um verificador independente confere cada critério
e tenta quebrar os testes injetando falhas. Só então abre a PR. O CI roda; o dono lê o diff e
o relatório de verificação; o que foi decidido no caminho vai para `docs/DECISOES.md`.

Regras que os agentes seguem sempre (estão no `CLAUDE.md`): testes vêm do critério de aceite,
nunca da implementação; nada de push, deploy ou banco sem ordem; nenhuma credencial no repo;
uma tarefa = uma pasta; dependência nova só com justificativa.

O dono faz o que exige conta ou julgamento: `terraform apply`, chaves, execução real contra o
Oracle e a AWS, merge, e as decisões de produto.

## 6. Custo esperado

S3 e CloudFront dentro das faixas gratuitas iniciais, KVS e Functions em centavos, Route53
US$ 0,50, dois CloudFronts em paralelo até a virada de DNS. Estimativa: **US$ 5–15/mês** na
fase atual. O que estouraria: imagem sem cache ou dado completo por visita — ambos eliminados
pelo desenho.
