# Besave — Visão do projeto

Documento de contexto, em linguagem simples, para quem chega agora (pessoa ou agente).
**Não é fonte de verdade.** Quando este texto e outro arquivo discordarem, valem, nesta ordem:
`docs/CONTRATO.md` (dados), `docs/MANIFEST.md` (S3/CloudFront), `docs/DECISOES.md` (por que), e a
spec do ticket em `docs/specs/`. Atualizado em 27/09/2026.

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

## 4. Onde estamos (27/09/2026)

Feito e no ar:
- Contrato de dados (v1.3.1), layout do S3, decisões registradas (AD-001 a AD-031), CI.
- Worker: lê o Oracle real, gera chunks e manifest, publica no S3 e atualiza os redirects.
  Primeira execução real: ~25 mil ofertas, 31 chunks, 972 KB no total, 6 segundos.
- Infra em Terraform: bucket privado, CloudFront novo (ainda no domínio `*.cloudfront.net`),
  função de redirect testada, usuário IAM do worker.
- **Os dados já estão publicados no CloudFront novo.** Ainda não há tela.

Em andamento:
- BSV-13 — worker copia as imagens do robô para o S3 e aprende a área "Outros".
- BSV-20 — template HTML da página de oferta.

Próximos, nesta ordem:
- BSV-21 gerar as ~30 mil páginas + sitemap · BSV-14 agendamento e alerta no Telegram.
- BSV-30..34 site SvelteKit: shell, lista, polling do manifest, áreas, busca.
- Virada de DNS de `besave.com.br` para a distribuição nova (o protótipo antigo sai do ar).
- F4 Telegram · F5 usuários · F6 app · F7 admin · link curto `besave.io`.

O que ainda não está decidido: domínio curto (`.io` ou `.me`), ordenação padrão da home,
tamanho definitivo da imagem `-small` (200 px hoje; talvez 320 para telas de alta densidade),
como os cupons da tabela CUPOM aparecem no site.

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
