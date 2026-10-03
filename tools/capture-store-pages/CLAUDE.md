# tools/capture-store-pages — Python: detalhe, classificação e consolidação em OFERTA (existente)

Código pré-existente. É a origem de `DS_LOJA`, `DS_COMUNIDADE`, `DS_PUBLICO`: qualquer valor novo precisa entrar em `packages/contract/mapeamento.json`, senão o worker rejeita.
Preenche `DT_DESATIVACAO` quando `ST_ATIVO` vai a 0 (CONTRATO.md §7). `DS_SLUG` não existe mais (AD-018). Não alterar sem ticket explícito.

## Regras de classificação (AD-039)
Oferta que não for classificada grava `DS_COMUNIDADE = 'Outros'` e `DS_PUBLICO = 'Unisex'`. Nunca deixar vazio: o worker rejeita.
`DS_URL_AFILIADO` é obrigatória para a oferta ser publicada. `DS_CUPOM` deve conter **um** código (sem ` | ` concatenando vários); se houver mais de um, gravar o primeiro.
`VL_PRECO_POR` é garantido pela captura (fallback `VR_PRECO_1` aqui, nunca no worker).

