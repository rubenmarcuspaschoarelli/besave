# BSV-61 · Envio do Telegram na inst2 (imagens pelo site, sem disco compartilhado)

**Papel:** Backend Rust + shell · **Pasta:** `apps/worker/` (+ `infra/vps/` para as unidades e o instalador da
inst2, `docs/infra/` para o roteiro) · **Depende de:** nada. Abre a sequência BSV-61 → BSV-62 → BSV-63
(publicação no canal do WhatsApp). BSV-40, BSV-41, AD-104. Lições 9, 14, 16, 29, 30

## Contexto
A inst2 (`bsv-agent-2026`, 1 OCPU, 4 GB, ARM64; 3,4 GB livres em 13/11) é a máquina de **mensageria**
(`docs/infra/VPS-INSTANCIA-1.md`). A inst1 fica com a captura e o ciclo, onde os dois navegadores já
pesam nos 8 GB. O `besave-envio` (Telegram) passa para a inst2; a BSV-63 põe ali o publicador do
WhatsApp, com outro número e outro navegador.

O envio hoje lê arquivos locais da inst1 (lição 30):
- foto da oferta: `BESAVE_IMAGENS_DIR/{id}.webp`, o espelho que os robôs gravam (`envio/foto.rs`);
- foto do aviso: `BESAVE_AVISOS_DIR/{DS_IMAGEM}`, a pasta onde o dono põe a imagem (`envio/aviso.rs`), que
  o ciclo também lê para publicar `img/avisos/{id}.{webp|jpg}`.

Na inst2 esses arquivos não existem. Os dois já estão **publicados no site** antes de o envio poder
usá-los: a oferta só é candidata com `OFERTA.DT_PUBLICACAO_SITE` preenchida (MANIFEST §6: imagens no passo
1, manifest no 5), e o aviso só sai com `AVISO.DT_PUBLICACAO_SITE` preenchida (`aviso.rs:24`).

## Saídas
1. **Foto da oferta por HTTPS:** com `BESAVE_IMAGENS_URL` (ex.: `https://besave.com.br/img/ofertas/`), a foto é
   `GET {base}{id}.webp` pelo cliente `hyper` que o envio já usa (`telegram::cliente_https`). Timeout 15 s,
   no máximo 5 MB, só `200` com corpo decodificável. Qualquer outra coisa → placeholder da área, com WARN
   (`id`, status ou motivo), como hoje com o arquivo ausente. O resto da foto (quadrado 800×800 JPEG) não
   muda.
2. **Foto do aviso por HTTPS:** com `BESAVE_AVISOS_URL` (ex.: `https://besave.com.br/img/avisos/`), `GET
   {base}{id}.{ext}`, com `ext` vinda de `DS_IMAGEM` (`webp` ou `jpg`, regra da BSV-41). Falha → aviso sem
   foto (`sendMessage`), como hoje.
3. **Precedência:** URL configurada vence a pasta; nenhuma das duas → o comportamento de hoje (placeholder, ou
   aviso sem foto). Pasta e URL juntas → usa a URL e dá um INFO no início da execução.
4. **Inst2 (`infra/vps/`):** o instalador ganha o papel `envio`:
   - só `besave-envio.service`/`.timer` e `besave-alerta@`;
   - sem ciclo, sem robôs, sem `BESAVE_IMAGENS_DIR`;
   - `.env` de exemplo próprio (`envio.env.example`) com `BESAVE_IMAGENS_URL`, `BESAVE_AVISOS_URL`,
     `TNS_ADMIN`, `BESAVE_LOG_DIR`, `BESAVE_ENVIO_LOCK` e os nomes das variáveis do bot (sem valor).

   O papel padrão continua sendo o da inst1, e `teste_instalar.sh` cobre os dois.
5. **Roteiro** em `docs/infra/` (seção nova "Inst2 · envio"): Instant Client ARM64 e wallet (como a Fase 4 da
   inst1), binário do commit de `main` (AD-060), `.env` em `600`, e a virada da Saída 6.
6. **Virada (dono):**
   1. `systemctl --user disable --now besave-envio.timer` na **inst1**;
   2. só então `enable --now` na **inst2**;
   3. remover o timer da inst1 no instalador do papel padrão.

   Nunca os dois ao mesmo tempo (VPS-INSTANCIA-1 §6).

## Regras
1. Sem dependência nova: o cliente HTTPS, o `image` e o placeholder embutido já existem.
2. Só o host configurado e só HTTPS; a URL montada não leva nada além do id e da extensão do contrato.
3. Falha de imagem nunca impede o post da oferta (placeholder) nem do aviso (sem foto). Isso já é regra hoje.
4. Nenhum token, chat_id, IP ou host interno no repositório nem na evidência (regra 11).

## Fora de escopo
- Mover o ciclo ou os robôs.
- Fila do WhatsApp (BSV-62) e publicador (BSV-63).
- CDN própria para o envio: usa a do site.

## Critério de aceite
Fakes de HTTP (servidor local ou trait), sem rede real nos testes.
- **Oferta:** `200` webp → foto da oferta, 800×800 e sem placeholder; `404`, timeout, corpo não-imagem e
  corpo > 5 MB → placeholder da área + WARN com o motivo. O mutante que ignora o tamanho máximo falha.
- **URL:** base com e sem `/` no fim → mesma URL final, comparada inteira (lição 14).
- **Aviso:** `DS_IMAGEM = x.jpg` → `GET {base}{id}.jpg`; falha → `sendMessage`, sem foto.
- **Precedência:** só pasta → lê a pasta (os testes de hoje continuam verdes); URL e pasta → só a URL é
  chamada (o fake da pasta conta 0 leituras); nenhuma → placeholder.
- **Instalador:** papel `envio` instala só as unidades do envio; papel padrão segue igual
  (`teste_instalar.sh`).
- **Gates:** `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`; `shellcheck
  infra/vps/*.sh`; job `worker-arm64` verde (lição 12).
- **Real (dono, bloqueia o merge), com o binário da branch na inst2:**
  1. `besave-envio --sim` mostra oferta com foto vinda do site e um aviso com imagem;
  2. virada da Saída 6, depois um dia de envio normal (lotes, cota, silêncio fora de 9–21 h, "Oferta
     encerrada"); na inst1, o timer desabilitado e nenhum post vindo de lá;
  3. `free -m` na inst2 antes e depois da virada.

## Definition of done
PR para `develop` com código, testes, instalador, roteiro, `validation.md` do Verifier independente (com
sensor de discriminação), evidência redigida, e as decisões propostas para o `docs/DECISOES.md`: inst2 =
mensageria; o envio lê imagens pelo site, não por disco.
