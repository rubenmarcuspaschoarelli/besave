# Especificação — Conversão de imagem de oferta para o S3 (`s3/ofertas/img`)

_Origem: AgenteCapturaWhatsapp, `wa/storage.py` (regra em produção desde 28/09/2026).
Destino: CaptureAmazon. Escrita em 28/09/2026._

## 1. Objetivo

Toda oferta publicada no site tem **duas imagens WEBP** numa pasta própria do bucket local:

```
E:\Work\besave\server\s3\ofertas\img\<ID_OFERTA>\<ID_OFERTA>.webp         <- principal (480x480)
E:\Work\besave\server\s3\ofertas\img\<ID_OFERTA>\<ID_OFERTA>-small.webp   <- miniatura (até 200 px)
```

O CaptureAmazon deve gerar esses dois arquivos a partir de **uma** imagem de origem
(ex.: `destino/img/<ID_OFERTA>/img_1.jpg`, que já sai com a marca d'água aplicada por
`core/images.py`), seguindo **exatamente** as mesmas regras do robô do WhatsApp, para que o
site receba imagens homogêneas, venham de qual robô vierem.

## 2. Regras

### 2.1 Imagem principal — `<ID_OFERTA>.webp`

| Regra | Valor |
|---|---|
| Formato | WEBP, `quality=90`, `method=6`, modo RGB |
| Origem com maior lado **> 480 px** | reduzir mantendo a proporção para caber em 480×480 (`Image.thumbnail`, `LANCZOS`) e **completar com fundo BRANCO `(255,255,255)` até 480×480 exatos**, imagem centralizada. Nunca cortar, nunca distorcer. |
| Origem com maior lado **≤ 480 px** | **manter a resolução original**: não ampliar e não preencher |
| Tamanho máximo | **200 KB** (204.800 bytes) |
| Se passar de 200 KB | baixar a qualidade de 5 em 5 (90 → 85 → … → 60); se ainda passar, reduzir o lado em 10% e repetir. Na prática não dispara: em 29 mil imagens reais o máximo foi 123 KB e a mediana 19 KB. |
| Gravação | **atômica**: gravar em `<arquivo>.tmp` e trocar com `os.replace`. O site nunca lê arquivo pela metade e a versão anterior some na troca. |

Exemplos: 1024×1024 → 480×480 · 1200×888 → conteúdo 480×355 centralizado num 480×480 branco
· 632×800 → conteúdo 379×480 centralizado num 480×480 branco · 440×440 → 440×440 · 72×72 → 72×72.

### 2.2 Miniatura — `<ID_OFERTA>-small.webp`

| Regra | Valor |
|---|---|
| Formato | WEBP, RGB |
| Dimensão | **maior lado = 200 px, mantendo a proporção** (`Image.thumbnail((200,200), LANCZOS)`). **Nunca amplia.** **Não** preenche com branco. |
| Origem | a MESMA imagem de origem da principal (com marca d'água), não a principal já reduzida |
| Qualidade | 80 (no WhatsApp a miniatura é gerada em q80 e depois recodificada em q90 ao publicar; gerar direto em q80 dá o mesmo resultado visual sem dupla compressão) |

> Por essa regra, uma origem 1200×888 gera miniatura **200×148**, não 200×200. É o padrão
> das ~29 mil miniaturas atuais e foi **mantido de propósito** (decisão D2): pequenas
> variações de tamanho deixam a imagem mais apresentável do que faixas brancas numa
> miniatura.

### 2.3 Comportamento geral

- **Best-effort**: falha na conversão é logada e **nunca derruba a captura** (mesmo padrão de
  `imagens_produto.publicar_imagens_produto` no CaptureAmazon).
- A imagem de origem **nunca é alterada** (só leitura).
- **Pasta não existe → criar** (`mkdir(parents=True, exist_ok=True)`).
- **Pasta/arquivos já existem → SOBRESCREVER** os dois (`<ID_OFERTA>.webp` e
  `<ID_OFERTA>-small.webp`). A captura do CaptureAmazon sempre vence (decisão D1).
- Não gerar para IDs provisórios/temporários: só com `ID_OFERTA` definitivo.
- Parâmetros calibráveis no `conf/config.json` do CaptureAmazon (sugestão, mesmo nome do
  WhatsApp):
  ```json
  "publicacao_s3_ofertas": {
    "ativo": true,
    "destino": "E:\\Work\\besave\\server\\s3\\ofertas\\img",
    "qualidade": 90, "max_px": 480, "max_kb": 200,
    "thumb_max_px": 200, "thumb_qualidade": 80
  }
  ```

## 3. Decisões tomadas (28/09/2026)

**D1 — Criar se não existir, SOBRESCREVER se existir.** Hoje a fila `OFERTA_FILA_CAPTURA` só
tem origem `WHATSAPP`, e o robô do WhatsApp já publica `s3/ofertas/img/<ID_OFERTA>/` para toda
oferta com imagem. O CaptureAmazon processa esses mesmos `ID_OFERTA` e **substitui** os dois
arquivos pela foto da página do produto; quando a pasta não existe (oferta do WhatsApp sem
imagem, ~3%), ele a cria. Consequência a ter em mente: a foto original do anúncio do
WhatsApp deixa de estar no site para essas ofertas (continua guardada em
`AgenteCapturaWhatsapp\captura\img\`, que nunca é alterada).

**D2 — Miniatura segue o padrão atual**: maior lado 200, mantendo a proporção, sem
preenchimento. Pequenas variações de tamanho (200×148, 158×200...) são aceitas porque deixam
a imagem mais apresentável. Nenhuma mudança no robô do WhatsApp.

## 4. Código de referência (autossuficiente, só depende do Pillow)

Pode ser copiado como `core/imagens_oferta.py` no CaptureAmazon. É a mesma lógica de
`wa/storage.py` (`_webp_principal`, `_gravar_atomico`, `publicar_principal_s3`,
`gerar_thumbnail`), sem as dependências do config/captura do WhatsApp.

```python
"""
Publica a imagem de UMA oferta no bucket do site, no mesmo padrao do
AgenteCapturaWhatsapp (wa/storage.py):

    <destino>\\<ID_OFERTA>\\<ID_OFERTA>.webp        principal, 480x480 (fundo branco), <= 200 KB
    <destino>\\<ID_OFERTA>\\<ID_OFERTA>-small.webp  miniatura, maior lado 200, sem preencher

A origem (ja com marca d'agua) nunca e alterada. Best-effort: quem chama
trata a excecao / o retorno vazio.
"""

import io
import os
from pathlib import Path

from PIL import Image

S3_OFERTAS_IMG_ROOT = r"E:\Work\besave\server\s3\ofertas\img"
MAX_PX = 480
MAX_BYTES = 200 * 1024
QUALIDADE = 90
QUALIDADE_MIN = 60
THUMB_MAX_PX = 200
THUMB_QUALIDADE = 80


def webp_principal(im, qualidade=QUALIDADE, max_px=MAX_PX, max_bytes=MAX_BYTES) -> bytes:
    """> max_px: reduz + completa com branco ate max_px x max_px (centralizado).
    <= max_px: resolucao original. Garante <= max_bytes."""
    im = im.convert("RGB")
    if max(im.size) > max_px:
        im.thumbnail((max_px, max_px), Image.LANCZOS)
        if im.size != (max_px, max_px):
            fundo = Image.new("RGB", (max_px, max_px), (255, 255, 255))
            fundo.paste(im, ((max_px - im.width) // 2, (max_px - im.height) // 2))
            im = fundo
    while True:
        q = qualidade
        while True:
            buf = io.BytesIO()
            im.save(buf, format="WEBP", quality=q, method=6)
            dados = buf.getvalue()
            if len(dados) <= max_bytes or q <= QUALIDADE_MIN:
                break
            q = max(QUALIDADE_MIN, q - 5)
        if len(dados) <= max_bytes or min(im.size) <= 16:
            return dados
        im = im.resize((max(1, int(im.width * 0.9)), max(1, int(im.height * 0.9))),
                       Image.LANCZOS)


def webp_miniatura(im, max_px=THUMB_MAX_PX, qualidade=THUMB_QUALIDADE) -> bytes:
    """Maior lado max_px, mantendo a proporcao; nunca amplia; sem preenchimento."""
    im = im.convert("RGB")
    im.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="WEBP", quality=qualidade)
    return buf.getvalue()


def gravar_atomico(destino: Path, dados: bytes) -> None:
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(dados)
    os.replace(tmp, destino)


def publicar_imagem_oferta(id_oferta, caminho_origem, raiz=S3_OFERTAS_IMG_ROOT) -> str:
    """Gera <id>.webp e <id>-small.webp: cria a pasta se nao existir e
    SOBRESCREVE os dois arquivos se ja existirem (a captura mais recente vence).
    Devolve a pasta, ou '' se nao ha origem. Levanta em erro de I/O."""
    if not id_oferta or not caminho_origem or not os.path.isfile(caminho_origem):
        return ""
    pasta = Path(raiz) / str(id_oferta)
    principal = pasta / f"{id_oferta}.webp"
    pasta.mkdir(parents=True, exist_ok=True)
    with Image.open(caminho_origem) as im:
        im.load()
        dados_principal = webp_principal(im)
        dados_small = webp_miniatura(im)
    gravar_atomico(principal, dados_principal)
    gravar_atomico(pasta / f"{id_oferta}-small.webp", dados_small)
    return str(pasta)
```

### Integração sugerida no `main.py` do CaptureAmazon

Logo depois do bloco `imagens_produto.publicar_imagens_produto(...)` (≈ linha 552), no mesmo
padrão best-effort:

```python
try:
    origem = primeira_imagem(out.get('pasta_imagens'))   # img_1.* em ordem numerica
    if origem and imagens_oferta.publicar_imagem_oferta(id_oferta, origem):
        status_db += ' | img_oferta=ok'
except Exception as e:  # noqa: BLE001
    print(f'[captura {captura}] imagens_oferta: {e}')
```

`primeira_imagem` pode reusar `_chave_ordem` de `core/imagens_produto.py` (ordena `img_2`
antes de `img_10`).

## 5. Rotinas de referência no AgenteCapturaWhatsapp

| Rotina | Arquivo | Papel |
|---|---|---|
| `_webp_principal` | `wa/storage.py` | redimensiona + fundo branco + teto de 200 KB |
| `_gravar_atomico` | `wa/storage.py` | `.tmp` + `os.replace` |
| `publicar_principal_s3` / `publicar_s3` | `wa/storage.py` | monta a pasta e grava os dois arquivos |
| `gerar_thumbnail` / `_cfg_thumb` | `wa/storage.py` | miniatura (maior lado 200, nunca amplia) |
| `dimensao_principal_s3` | `wa/storage.py` | dimensão esperada, usada para conferir/pular no backfill |
| backfill `--reconverter` | `diag/publicar_s3.py` | modelo de backfill retomável (pula o que já está no padrão) |

A marca d'água **não** precisa ser portada: o CaptureAmazon já tem a sua em `core/images.py`
(portada do mesmo código), e a origem já chega marcada.

## 6. Plano de teste (para o agente do CaptureAmazon)

Usar uma pasta de rascunho como `raiz` (NUNCA o S3 real nos testes).

1. **Unitário, com imagens sintéticas** (`Image.new`):
   | Origem | Principal esperada | Miniatura esperada |
   |---|---|---|
   | 1024×1024 | 480×480 | 200×200 |
   | 1200×888 | 480×480, pixel (0,0) branco | 200×148 |
   | 632×800 | 480×480, pixel (0,0) branco | 158×200 |
   | 440×440 | 440×440 | 200×200 |
   | 150×100 | 150×100 | 150×100 (não amplia) |
   | 2000×2000 de ruído (`os.urandom`) | 480×480, ≤ 200 KB | ≤ 200 px |
2. **Caminho do teto**: chamar `webp_principal(im_ruido, max_bytes=30*1024)` e conferir que
   devolve ≤ 30 KB (no WhatsApp: 432×432, 28,8 KB).
3. **Criar e sobrescrever**: (a) com a pasta inexistente, a chamada cria a pasta e os 2
   arquivos; (b) com a pasta já contendo um `<id>.webp` e um `<id>-small.webp` antigos
   (ex.: 1024×1024 vermelhos), chamar com outra origem (azul) e conferir que **os dois**
   foram substituídos (nova dimensão/cor, `mtime` atualizado) e que não sobrou `.tmp`.
4. **Atomicidade**: após o teste, `rglob("*.tmp")` deve voltar vazio.
5. **Formato**: `Image.open(arquivo).format == "WEBP"` nos dois arquivos.
6. **Real**: rodar com 5–10 fotos reais de `destino/img/<ID_OFERTA>/` e abrir uma folha de
   contato para conferência visual (fundo branco centralizado, marca d'água visível, sem corte).
7. **Integração**: 1 captura real com `raiz` de rascunho; conferir o `status_db` e os arquivos.
   Só depois apontar para `E:\Work\besave\server\s3\ofertas\img`.

## 7. Estado atual do bucket (referência, medido em 28/09/2026)

28.999 pastas · 28.647 principais em 480×480 · 352 menores mantidas no original ·
0 acima de 480 · 0 acima de 200 KB · mediana 19 KB · máx. 123 KB · todas com `-small`.
