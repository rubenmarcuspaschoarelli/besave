import csv
import json

from core import registry, link_afiliado

# Campos esperados no CSV de origem (fallback caso o cabecalho nao seja lido).
ORIGEM_FIELDS = [
    'nome_do_grupo_do_whatsapp', 'tipo_anuncio', 'numero_da_captura',
    'data_hora_captura', 'nome_do_produto', 'imagem_principal', 'msg_aviso',
    'preco_de', 'preco_por', 'descricao_pagamento', 'url', 'mensagem_final',
    'cupom', 'comentario_cupom', 'loja_cupom',
]


def read_origem(path):
    # Le o CSV de origem (UTF-8 com BOM, delimitador virgula).
    # Retorna (lista_de_colunas_origem, lista_de_linhas_dict).
    with open(path, encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames or list(ORIGEM_FIELDS)
        rows = [dict(r) for r in reader]
    return fieldnames, rows


def build_header(origem_fields):
    # Cabecalho de saida = colunas de origem + loja/st_ativo/status/url_final/
    # url_besave + uniao das colunas capturadas por todas as lojas implementadas.
    # url_final  = URL real do produto (apos redirects do link curto / previa).
    # url_besave = url_final com o NOSSO codigo de afiliado (core/afiliados.py).
    # st_ativo   = '1'/'0' da coluna ST_ATIVO (loja em producao ou nao).
    # Os *_afiliado vem do widget do programa de afiliados da loja
    # (core/link_afiliado.py) -- url_afiliado e o link OFICIAL, ao contrario do
    # url_besave, que o Python calcula.
    header = (list(origem_fields)
              + ['loja', 'st_ativo', 'status_captura', 'url_final', 'url_besave']
              + list(link_afiliado.CAMPOS))
    for col in registry.union_output_columns():
        if col not in header:
            header.append(col)
    return header


def _serialize(value):
    # Listas/dicts viram JSON (ensure_ascii=False p/ manter acentos legiveis).
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return '' if value is None else value


def write_destino(path, header, rows):
    # Grava o CSV de saida (UTF-8 com BOM p/ o Excel abrir os acentos certos).
    with open(path, 'w', encoding='utf-8-sig', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=header, extrasaction='ignore', restval='')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _serialize(v) for k, v in row.items()})
