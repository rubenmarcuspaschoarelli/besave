# BSV-12c · Worker: índice local da KVS de redirects (fim da listagem por ciclo)

**Papel:** Backend Rust · **Pasta:** `apps/worker/` · **Depende de:** BSV-12, BSV-13b (tempo por fase).
MANIFEST.md §5, §6 · Tipo: correção de desempenho

## Contexto (medido pelo dono em 30/09/2026, BSV-13b)
Com as imagens corrigidas, um ciclo sem mudanças relevantes leva ~530 s, dos quais
`t_redirects_listagem` ≈ **490 s**: `Redirects::listar()` percorre a KeyValueStore inteira
(~11,6 mil chaves, paginada) a cada execução só para calcular o diff. Todas as outras fases
somam < 40 s. Com ciclo de 5 min (BSV-14) isso não cabe.

## Objetivo
Ciclo sem mudanças termina em **< 60 s**. A KVS só é listada quando o estado local não é confiável.

## Solução
1. **Índice** `_estado/redirects.json` no bucket: `{ "kvs_item_count": N, "kvs_etag": "...",
   "urls": { "<id>": "<hash16 da URL>" } }` (hash, não a URL, para não publicar links de
   afiliado num arquivo legível pela borda). `Cache-Control: no-store`, `application/json`.
2. Por ciclo: ler o índice (1 GET) e chamar `DescribeKeyValueStore` (1 chamada) para obter
   `ItemCount` e o `ETag` da KVS. **Índice confiável** = existe, é legível, e `ItemCount`/`ETag`
   batem com o que o próprio worker gravou ao fim do ciclo anterior.
   - Confiável → diff entre conjunto publicado e índice (por hash da URL); `UpdateKeys` só do diff
     (lotes de 50, como hoje).
   - Não confiável (ausente, ilegível, ou KVS alterada por fora) → caminho atual: `listar()` completo,
     diff, aplicar, e **reconstruir** o índice. Registrar `WARN` com o motivo.
3. Após aplicar o diff, gravar o índice com o `ETag` retornado pela última `UpdateKeys`
   (ou por um `DescribeKeyValueStore` final, se o SDK não o devolver) e o `ItemCount` novo.
4. Ordem de `gerar()` inalterada (KVS antes do manifest). Falha ao gravar o índice → erro e aborta
   antes do manifest (o próximo ciclo reconstrói).
5. Relatório: `redirects_modo = indice | reconstrucao`, `redirects_motivo_reconstrucao`.

## Regras
- A KVS continua sendo a verdade para o CloudFront; o índice é só otimização. Qualquer dúvida → reconstrução.
- Não armazenar URLs de afiliado no índice (só hash16 SHA-256).
- `RedirectsMemoria` passa a expor `ItemCount` e um `ETag` que muda a cada escrita, para testar a detecção.
- Sem dependência nova.

## Fora de escopo
Agendamento (BSV-14), mudança da Function, troca da KVS por outro armazenamento.

## Critério de aceite
- Índice válido e sem mudanças → 0 chamadas a `listar()`, 1 a `DescribeKeyValueStore`, 0 `UpdateKeys`.
- 3 URLs novas, 1 alterada, 2 removidas → `UpdateKeys` só com esses 6; índice atualizado.
- Índice ausente → reconstrução (1 `listar()` completo), índice criado; ciclo seguinte → modo `indice`.
- KVS alterada por fora (ETag diferente do índice) → reconstrução com motivo `etag_divergente`.
- Índice corrompido → reconstrução com motivo `indice_ilegivel`, sem abortar.
- Índice não contém nenhuma URL em claro (teste lê o JSON e procura `http`).
- `cargo fmt --check`, `clippy -D warnings`, `cargo test` sem rede.
- **Real (dono):** 1ª execução → `redirects_modo = reconstrucao` (motivo `indice_ausente`);
  2ª execução → `redirects_modo = indice`, `t_redirects` < 5 s, **tempo total < 60 s**.
  `curl -I https://<cf>/ir/<id novo>` → 302 para a loja.

## Definition of done
PR com os tempos por fase das duas execuções reais, testes verdes, README (índice `_estado/redirects.json`).
