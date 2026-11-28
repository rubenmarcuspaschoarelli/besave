# BSV-67 · Robô do WhatsApp: religar pelo celular, reiniciar antes do teto de memória e guardar a sessão

**Papel:** Python (stdlib + Playwright) e bash · **Pasta:** `tools/capture-chat-groups/` (+ `tools/vps/` para o
vigia, o reinício e as unidades; `tools/tests/`) · **Depende de:** nada (BSV-54, 57 em `main`). AD-113, AD-115;
lições 14, 29, 32, 33

## Contexto
De **26/11 10:24 a 27/11 (ainda fora no momento da spec)** o robô do WhatsApp não capturou nada:
- 10:24: o maior Chromium do perfil chegou a **3.535 MB** (scope com 3.783 MB). Bateu no `MemoryHigh=3500M` da
  BSV-54: o processo fica estrangulado e o batimento parou. Em 06/11 o crescimento medido era ~0,2 GB/h; desta
  vez passou de ~1 GB a 3,5 GB em menos de 5 h (reinício das 05:30);
- 10:34: o vigia reiniciou a unidade e o WhatsApp Web **pediu QR**: a sessão se perdeu (perfil corrompido ao ser
  estrangulado, ou aparelho desvinculado no servidor; o log não separa os dois);
- dali em diante, a cada ~5,5 min: abre, espera `#pane-side` por 5 min (`wa/browser.py`), sai com `TimeoutError`,
  o systemd religa. **254 partidas** em 23 h. O vigia acertou (não reiniciou, avisou "precisa de operador" a cada
  2 h), mas o dono estava fora, sem PC e sem VNC: não havia como ler o QR;
- a fila parou (0 linhas de WhatsApp depois de 10:2x); o canal do Telegram seguiu postando até ~22:49 com o estoque
  de ofertas publicadas de até 24 h, o que escondeu a parada.

O WhatsApp Web tem um segundo jeito de vincular: **"Entrar com número de telefone"**. A página mostra um código de
8 caracteres que o dono digita no celular (WhatsApp → Aparelhos conectados → Conectar aparelho → Conectar com número
de telefone). Não precisa de câmera, de VNC nem de outra tela: dá para fazer de qualquer lugar com o celular.

## Saídas
1. **Detectar a tela de login.** Em `wa/browser.py`, `abrir_whatsapp` espera o que vier primeiro: `#pane-side`
   (logado, segue como hoje) ou a tela de vincular (o canvas do QR ou o link "Entrar com número de telefone").
   Seletores por texto visível (pt-BR **e** en) ou `data-testid`/`aria-label`; nunca classe ofuscada (regra do
   próprio arquivo). Os seletores saem da página real (fixture da Saída 7), não de memória (regra 8). Elementos
   colhidos pelo dono na página real em 27/11 (pt-BR):

   | passo | elemento | seletor |
   |---|---|---|
   | tela do QR | `<canvas role="img" aria-label="Escaneie o QR code para conectar um dispositivo">` | `canvas[aria-label*="QR code"]` |
   | trocar para número | `<div>` com o texto `Entrar com número de telefone` | texto visível (en: confirmar na fixture) |
   | número | `<input data-testid="phone-number-input" aria-label="Insira seu número de telefone para entrar no WhatsApp." value="+55 ">` (vem com `+55 ` e o DDI aparece num `span` ao lado) | `input[data-testid="phone-number-input"]` |
   | avançar | `<span>` com o texto `Avançar` | texto visível / `role=button` |
   | código | `<div data-testid="link-with-phone-number-code-cells" data-link-code="R,H,S,D,E,V,N,N">` (8 `span`, um por caractere, e um `-` decorativo) | ler o atributo `data-link-code`, tirar as vírgulas: 8 caracteres `[A-Z0-9]`; fora disso → erro e novo pedido |
2. **Restaurar a sessão guardada, uma vez.** Tela de login e cópia da Saída 5 existente e ainda não tentada:
   fecha o contexto, move `user_data/` para `user_data.qr/` (substitui a anterior; fica para diagnóstico),
   restaura a cópia para `user_data/`, relança e volta à Saída 1. A tentativa é marcada no próprio diretório da
   cópia (`restaurada_em`), para não repetir a mesma cópia em laço. Log:
   `[sessao] tela de login; restaurando a copia de <data UTC>`. Abriu → `[sessao] copia restaurada; sessao ok` e
   Telegram `WhatsApp: sessao perdida e restaurada da copia de <data Brasilia> (sem acao).`
3. **Código de pareamento pelo Telegram.** Sem cópia, ou a cópia também cai na tela de login:
   - clica em "Entrar com número de telefone", informa `pareamento.numero` (só dígitos, com DDI; chave nova no
     `config.json`, fora do git), avança e lê o código de 8 caracteres. O campo já vem com `+55 `: o robô limpa o
     campo, digita `+` e os dígitos com DDI e confere que os dígitos do `value` final são os do config (máscara
     do campo não pode duplicar o DDI); divergente → não avança, log sem o número e mensagem do VNC (abaixo);
   - Telegram (mensagem inteira, comparada no teste):
     `WhatsApp desconectado. No celular: WhatsApp > Aparelhos conectados > Conectar aparelho > Conectar com numero de telefone e digite ABCD-EFGH (pedido as HH:MM, Brasilia).`
   - fica **vivo** esperando: não sai a cada 5 min. `#pane-side` apareceu → `[sessao] vinculado pelo codigo`,
     Telegram `WhatsApp: vinculado de novo pelo codigo; captura retomada.` e segue para o rodízio;
   - código expirou (a página voltou ao QR ou ao campo do número, ou passou `pareamento.validade_min`, padrão 10)
     → pede outro. **No máximo 3 códigos por hora e 12 por dia**; atingido o teto, espera a próxima hora cheia sem
     pedir e manda uma vez `WhatsApp desconectado: limite de codigos atingido; proximo pedido as HH:MM (Brasilia).`;
   - sem `pareamento.numero` no config → não tenta; Telegram uma vez por partida
     `WhatsApp desconectado e sem pareamento.numero no config: ler o QR pela tela VNC :2.` e espera como hoje
     (sem sair em laço: mesma espera viva da Saída 3);
   - durante toda a espera grava batimento com `fase: "pareamento"` e `prazo` de 15 min.
   - o número nunca vai inteiro ao log nem ao Telegram: só os 4 últimos dígitos (`***1234`).
4. **Vigia entende a espera.** `tools/vps/vigia_robos.py`: batimento em dia com `fase == "pareamento"` → não
   reinicia, não conta laço de partidas, não repete os avisos do robô; só lembra a cada 6 h
   `Vigia dos robos: whatsapp aguardando vinculo pelo celular ha N h.` Batimento vencido na fase `pareamento`
   segue a regra de hoje (reinício). O laço de partidas continua valendo para os outros casos.
5. **Cópia da sessão boa.** No reinício programado (`tools/vps/reiniciar_whatsapp.sh`), entre parar e partir a
   unidade (troca o `restart` por `stop` + cópia + `start`):
   - só copia se o log da partida que está sendo parada tem `Grupo aberto` (sessão sabidamente boa);
   - copia `user_data/` para `user_data.copia/` **sem** `Default/Cache`, `Default/Code Cache`, `Default/GPUCache`,
     `GPUPersistentCache`, `Default/Service Worker/CacheStorage` (o resto, ~260 MB medidos em 27/11: IndexedDB
     ~180 MB e Local Storage), primeiro em `user_data.copia.nova/` e depois troca por `mv` (cópia pela metade
     nunca vira a cópia válida); `restaurada_em` some na cópia nova;
   - tempo e tamanho no log do reinício: `[reinicio] copia da sessao: 262 MB em 4 s`; falha da cópia → aviso no
     Telegram e o robô parte mesmo assim (cópia nunca segura a captura);
   - a espera por `Grupo aberto` continua contando a partir do `start`.
6. **Reinício antes do teto de memória.** O vigia, quando o robô está saudável (fase `rodizio`, batimento em dia)
   e o maior Chromium do scope passa de `BESAVE_WHATSAPP_RSS_MAX_MB` (padrão **2500**), dispara o reinício
   programado (`systemctl --user start besave-reinicio-whatsapp.service`, que já espera `Grupo aberto`, avisa se
   não confirmar e agora faz a cópia da Saída 5). No máximo **1 por 60 min**; não conta para os 2 reinícios/h de
   robô parado. Telegram só no 2º disparo em 6 h:
   `Vigia dos robos: whatsapp reiniciado por memoria 2 vezes em 6 h (maior chrome: N MB).` Log do vigia sempre.
7. **Fixtures da página.** `tools/tests/fixtures/whatsapp/`: recorte do DOM real da tela do QR, da tela do
   número e da tela do código. Base: os elementos da tabela da Saída 1 (colhidos pelo dono, já sem o número);
   o agente confere e completa (textos em en, contêineres) num perfil **temporário** no PC (fora de
   `user_data/`) até a tela do número, **sem** pedir código. Na tela do código, `data-link-code` e os `span`
   levam um código inventado (`T,E,S,T,E,1,2,3`); número sempre `REDACTED`; elementos de extensão do navegador
   (ex.: `kpm-field-badge`, de gerenciador de senhas) saem do recorte. Os testes de página usam essas fixtures
   num simulador só de teste (como na AD-120).
8. **README** de `capture-chat-groups`: o que fazer com cada mensagem nova, a chave `pareamento`, como forçar a
   leitura do QR pelo VNC (`pareamento.numero` vazio), onde ficam `user_data.copia/` e `user_data.qr/` e como
   restaurar à mão. `config.example.json` com `pareamento: {numero: "", validade_min: 10, _obs}`.

## Regras
1. Nada de código ou número no log inteiro (Saída 3); fixtures redigidas (regra 11).
2. A cópia nunca é lida enquanto o Chromium usa o perfil: só com a unidade parada (Saída 5) ou com o contexto
   fechado pelo próprio robô (Saída 2).
3. Teste de mensagem compara a mensagem inteira (lição 14).
4. Sem dependência nova. Sem mudança de banco. Mudança de unidade só se o `stop` + `start` exigir (justificar).
5. Pedidos de código têm teto (Saída 3): o WhatsApp pode bloquear vínculo por excesso de tentativas.
6. O robô nunca apaga `user_data/`: move para `user_data.qr/`.

## Fora de escopo
- Publicador do canal do WhatsApp (`tools/publish-whatsapp-channel/`, inst2): mesmo problema, outro perfil e
  outro número; ticket próprio reaproveitando o desenho depois do teste real desta.
- Causa do crescimento de memória do Chromium (versão, flags, grupos com mídia): segue medido pela Saída 6.
- Captura de grupos do Telegram (segunda fonte) e captura web fora do PC: tickets próprios.

## Critério de aceite
- Testes (sem WhatsApp real; página simulada sobre as fixtures; relógio, `systemctl` e `ps` simulados):
  - tela de login com cópia não tentada → restaura uma vez e marca `restaurada_em`; cópia já tentada → código;
    `user_data/` movido para `user_data.qr/`, nunca apagado;
  - código lido da fixture → mensagem inteira com `***` + 4 dígitos e sem o número; 4º pedido na mesma hora não
    sai; 13º no dia não sai; virou a hora → sai;
  - sem `pareamento.numero` → mensagem do VNC, sem clicar em nada, sem sair do processo;
  - batimento com `fase: "pareamento"` a cada volta da espera; vigia: `pareamento` em dia → sem reinício e sem
    aviso de laço; `pareamento` vencido → reinício como hoje; lembrete só depois de 6 h;
  - reinício: log sem `Grupo aberto` → não copia; com → copia sem os caches da lista, troca por `mv`; cópia
    falhando → aviso e `start` mesmo assim; a ordem é `stop`, cópia, `start` (comando inteiro comparado);
  - vigia: RSS 2501 MB saudável → dispara; 2499 → não; 2501 com batimento vencido → regra de parado, não a de
    memória; 2º disparo em 50 min → não; aviso só no 2º em 6 h;
  - mutantes: tirar o teto de códigos, trocar `>` por `>=` no RSS, copiar sem checar `Grupo aberto`.
- `pytest` e `ruff` do job `tools` verdes; os testes do vigia e do script rodam também no WSL (lição 32).
- **Real (dono, inst1, branch da PR; bloqueia o merge):**
  1. reinício programado à mão (`systemctl --user start besave-reinicio-whatsapp.service`): log com a linha da
     cópia (tamanho e tempo), `Grupo aberto` depois;
  2. com o robô parado, renomear `user_data/` para `user_data.teste/` (simula sessão perdida) e partir: restaura a
     cópia, abre grupo, Telegram da Saída 2;
  3. desvincular o aparelho pelo celular: o robô cai na tela de login, a cópia não resolve (já tentada ou sessão
     desvinculada no servidor), chega o código no Telegram, o dono digita no celular, `Grupo aberto` e Telegram
     de vinculado; o dono confere que a fixture da tela do código bate com a página do dia (redigida);
  4. `BESAVE_WHATSAPP_RSS_MAX_MB=500` no vigia (só no teste): reinício por memória com cópia e `Grupo aberto`;
     volta ao padrão;
  5. `journalctl` do vigia sem reinício durante o passo 3.

## Definition of done
PR para `develop` com código, testes, fixtures redigidas, README, `validation.md` do Verifier independente
(sensor de discriminação) e evidência redigida; decisão proposta para `docs/DECISOES.md` no resumo da PR.
