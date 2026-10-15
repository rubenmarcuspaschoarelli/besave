"""
Origem e destino dos dados em Oracle (tabela OFERTA_FILA_CAPTURA).

Substitui o CSV como FONTE: lemos a fila (ST_CAPTURA = '0'), capturamos a pagina
do produto e devolvemos os campos complementares via a stored procedure
STP_OFERTA_FILA_CAPTURA_UPDATE, que forca ST_CAPTURA = '1'. O CSV continua sendo
gravado em destino/log/ como copia de seguranca.

Driver: python-oracledb em THICK mode. O servidor e um Oracle XE 11.2, e:
  - o THIN mode so conecta em Oracle 12.1+ (nao serve p/ 11.2);
  - o THICK mode do python-oracledb atual exige Oracle Client >= 19
    (Instant Client 19c x64), apontado por conf/config.json -> db.instant_client_dir.
O Client 19c conversa normalmente com o servidor 11.2 (interoperabilidade de rede).

A GRAVACAO e best-effort: falha de SP/conexao e logada e o lote continua (o CSV
guarda tudo). A LEITURA nao e: sem fila nao ha o que capturar, entao o main.py
aborta com mensagem clara.

API:
  db = OracleDB()
  db.conectar()                    # idempotente; True se conectou
  db.ler_fila(ultimo_id, limite)   # -> lista de dicts (linhas pendentes)
  db.atualizar_captura(linha)      # -> (ok: bool, erro: str|None)
  db.desconectar()
"""

import json
import os
import re

try:                                 # sem a lib instalada -> so CSV
    import oracledb
except Exception:                    # noqa: BLE001
    oracledb = None

CONFIG_PATH = os.path.join('conf', 'config.json')

# init_oracle_client() so pode ser chamado UMA vez por processo.
_client_iniciado = False

NOME_SP = "STP_OFERTA_FILA_CAPTURA_UPDATE"
NOME_SP_ERRO = "STP_OFERTA_FILA_CAPTURA_ERRO"

# Convencao de ST_CAPTURA na tabela (VARCHAR2):
#   '0' pendente (a fila le so estas) | '1' sucesso | '9' erro/problema
# O motivo fica em DS_CAPTURA (= o status_captura do main.py).
ST_PENDENTE, ST_OK, ST_ERRO = '0', '1', '9'

# Convencao de ST_ATIVO: '1' = loja que entra em producao (esta em
# conf/config.json -> "lojas_ativas"); '0' = loja capturada e mapeada, mas ainda
# fora do ar. NULL = linha nunca processada por esta versao do programa. Quem
# decide e registry.loja_ativa(); ver sql/ALTER_OFERTA_FILA_CAPTURA_ST_ATIVO.sql.
ST_ATIVO_SIM, ST_ATIVO_NAO = '1', '0'

# Colunas da fila que o loop de captura consome (origem dos dados).
COLUNAS_FILA = [
    'ID_OFERTA', 'DS_OFERTA', 'DS_URL_ORIGEM', 'DS_IMAGEM_OFERTA',
    'VL_PRECO_DE', 'VL_PRECO_POR', 'DS_TIPO_ORIGEM', 'DS_ORIGEM',
    'DS_TIPO_OFERTA', 'DT_CAPTACAO', 'DT_OFERTA', 'DS_OFERTA_AVISO',
    'DS_DESCRICAO_PAGAMENTO', 'DS_MSG_FINAL', 'DS_CUPOM',
    'DS_CUPOM_COMENTARIO', 'DS_CUPOM_LOJA',
]

# De-para campo capturado (dict da store) -> parametro da SP. A ordem nao importa
# (binds sao nomeados); o tipo importa e esta em _NUMERICOS/_INTEIROS abaixo.
MAPA_CAMPOS = {
    'url_final':                               'P_DS_URL_FINAL',
    'url_besave':                              'P_DS_URL_BESAVE',
    'lst_categorias':                          'P_LS_CATEGORIA',
    'lst_detalhes_produtos':                   'P_LS_DETALHES_PRODUTO',
    'lst_Product_Detalhes_tecnicos':           'P_LS_DETALHES_TECNICOS',
    'lst_Product_Informacoes_adicionais':      'P_LS_INFO_ADICIONAIS',
    'lst_Product_Detalhes':                    'P_LS_COMPLEMENTO_PRODUTO',
    'produto_titulo':                          'P_DS_TITULO',
    'produto_descricao':                       'P_DS_PRODUTO',
    'pais_origem':                             'P_DS_PAIS_ORIGEM',
    'avaliacao_nota':                          'P_NR_NOTA_AVALIACAO',
    'avaliacao_quantidade':                    'P_QT_AVALIACAO',
    'preco_com_desconto_inteiro':              'P_VR_DESCONTO_INTEIRO',
    'preco_com_desconto_fracao':               'P_VR_DESCONTO_FRACAO',
    'preco_1':                                 'P_VR_PRECO_1',
    'preco_2':                                 'P_VR_PRECO_2',
    'preco_simbolo':                           'P_DS_SIMBOLO_MOEDA',
    'preco_original':                          'P_VR_PRECO_ORIGINAL',
    'preco_por_unidade':                       'P_VR_PRECO_POR_UNIDADE',
    'preco_tipo_unidade':                      'P_DS_TIPO_UNIDADE',
    'condicoes_1':                             'P_DS_CONDICOES_1',
    'condicoes_2':                             'P_DS_CONDICOES_2',
    'preco_recorrencia_inteiro':               'P_VR_PRECO_RECORRENCIA_INTEIRO',
    'preco_recorrencia_fracao':                'P_VR_PRECO_RECORRENCIA_FRACAO',
    'recorrencia_quantidade_minima_descricao': 'P_QT_MINIMA_RECORRENCIA',
    'espere_economize':                        'P_VR_ESPERE_ECONOMIZE',
    'enviado_por':                             'P_DS_ENVIADO_POR',
    'vendido_por':                             'P_DS_VENDIDO_POR',
    'quantidade_vendida':                      'P_NR_QUANTIDADE_VENDIDA',
    # Especificos do Mercado Livre (2026-09-02): demais lojas nao preenchem
    # esses campos -> NULL nas colunas para elas.
    'quantidade_opinioes':                     'P_QT_OPINIOES',
    'avaliacao_geral':                         'P_DS_AVALIACAO_GERAL',
    # Link OFICIAL do programa de afiliados da loja, clicado no widget da
    # propria pagina (core/link_afiliado.py, 2026-09-10) -- nao confundir com
    # 'url_besave', que e CALCULADO em core/afiliados.py. Categoria/taxa/codigo
    # vem do mesmo widget e so existem em algumas lojas (ver o modulo).
    'url_afiliado':                            'P_DS_URL_AFILIADO',
    'categoria_afiliado':                      'P_DS_CATEGORIA_PROD_AFILIADO',
    # Nome do PARAMETRO abreviado: o nome completo (P_DS_TAXA_COMISSAO_PROD_
    # AFILIADO) passaria dos 30 caracteres que o Oracle 11g aceita num
    # identificador. A COLUNA continua com o nome completo (30 em ponto).
    'taxa_comissao_afiliado':                  'P_DS_TAXA_COMISSAO_PROD_AFIL',
    'id_produto_afiliado':                     'P_DS_ID_PRODUTO_AFILIADO',
}

# Campos gravados em coluna CLOB (LS_* na tabela): texto INTEIRO, sem o corte de
# _MAX_BIND_BYTES e bindados como CLOB (setinputsizes) para nao esbarrar no limite
# de 4000 bytes do bind VARCHAR2 (ORA-01461). Ver
# sql/ALTER_OFERTA_FILA_CAPTURA_LS_CLOB.sql.
_CLOB_CAMPOS = {
    'lst_categorias', 'lst_detalhes_produtos', 'lst_Product_Detalhes_tecnicos',
    'lst_Product_Informacoes_adicionais', 'lst_Product_Detalhes', 'avaliacao_geral',
}
# Nomes dos parametros CLOB da SP (para o setinputsizes do bind).
_CLOB_PARAMS = {MAPA_CAMPOS[c] for c in _CLOB_CAMPOS}

# Colunas NUMBER que recebem valor com casas decimais (o programa ja normaliza
# preco para "." decimal via text_utils.normalize_price).
_NUMERICOS = {
    'avaliacao_nota', 'preco_1', 'preco_2', 'preco_original',
    'preco_por_unidade', 'espere_economize',
}
# Colunas NUMBER que sao inteiras por definicao: fragmentos de preco
# ("1.234" = milhar, NUNCA decimal) e contadores.
_INTEIROS = {
    'preco_com_desconto_inteiro', 'preco_com_desconto_fracao',
    'preco_recorrencia_inteiro', 'preco_recorrencia_fracao',
}
# Contadores que a loja escreve por extenso ("1,8mil", "4mil+", "(2.443)").
_CONTADORES = {'avaliacao_quantidade', 'quantidade_vendida', 'quantidade_opinioes'}


# --- Conversores (texto capturado -> tipo Oracle) ---------------------------
def _num(s):
    """
    Numero com decimais. Aceita os dois formatos que aparecem nos campos ja
    normalizados: "1234.56" (padrao do normalize_price) e "1.234,56" (pt-BR, se
    algum campo escapar da normalizacao). Faixas ("10.99 - 11.99") viram o menor
    valor. Vazio/lixo -> None.
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.split('-')[0].strip()          # faixa de precos -> primeiro valor
    if ',' in s:                         # pt-BR: ponto=milhar, virgula=decimal
        s = s.replace('.', '').replace(',', '.')
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _num_inteiro(s):
    """Inteiro: todo separador e milhar ("1.234" -> 1234, "27," -> 27)."""
    if s is None:
        return None
    digitos = re.sub(r'\D', '', str(s))
    return int(digitos) if digitos else None


def _num_contador(s):
    """
    Contador escrito por extenso pelas lojas:
      "(2.443)" -> 2443 | "1,8mil" -> 1800 | "4mil+" -> 4000 | "2 mil" -> 2000
    Vazio/lixo -> None.
    """
    if s is None:
        return None
    s = str(s).strip().lower()
    if not s:
        return None
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(mil|k)?', s)
    if not m:
        return None
    base = m.group(1)
    if ',' in base:                      # "1,8" -> 1.8 (aqui virgula E decimal)
        base = base.replace('.', '').replace(',', '.')
    elif m.group(2) is None:
        base = base.replace('.', '')     # "2.443" sem sufixo -> milhar
    try:
        valor = float(base)
    except ValueError:
        return None
    if m.group(2):                       # sufixo "mil"/"k"
        valor *= 1000
    return int(valor)


def _item_texto(item):
    """
    Um item de lista -> texto. As tabelas/pares das stores vem como
    {'key': rotulo, 'value': conteudo} (BaseStore.get_table / get_pairs) e viram
    "rotulo: conteudo"; qualquer outro dict vira "chave: valor" separado por "; ".
    """
    if isinstance(item, dict):
        if 'key' in item and 'value' in item:
            chave = str(item.get('key') or '').strip()
            valor = str(item.get('value') or '').strip()
            return f'{chave}: {valor}' if chave and valor else (chave or valor)
        return '; '.join(f'{k}: {x}' for k, x in item.items() if x not in (None, ''))
    return '' if item is None else str(item).strip()


# Teto de bytes no bind VARCHAR2. O limite do bind SQL do Oracle e 4000 bytes:
# acima disso o cliente recusa com ORA-01461 ("can bind a LONG value only...")
# ANTES de a SP rodar -> o corte por coluna (CORTA_BYTES / 600 CHAR) da SP nunca
# e alcancado. Como a coluna LS_ mais larga e VARCHAR2(600 CHAR) (<=2400 bytes),
# 3900 e um teto seguro que nunca descarta dado que a SP teria preservado.
_MAX_BIND_BYTES = 3900


def _cortar_bytes(s, limite=_MAX_BIND_BYTES):
    """Corta a string para caber em `limite` bytes UTF-8 sem partir um caractere."""
    b = s.encode('utf-8')
    if len(b) <= limite:
        return s
    return b[:limite].decode('utf-8', 'ignore')


def _texto(v, sep=' | ', cortar=True):
    """
    Valor capturado -> texto para coluna VARCHAR2. Listas viram itens unidos por
    " | " (decisao do usuario: texto legivel no banco, em vez do JSON usado no
    CSV). Vazio -> None (NULL e melhor que string vazia para relatorios).
    Por padrao corta a _MAX_BIND_BYTES para nao estourar o limite de bind do
    Oracle; `cortar=False` nos campos CLOB (bindados como CLOB, sem esse limite).
    """
    if v is None:
        return None
    if isinstance(v, dict):
        v = _item_texto(v)
    elif isinstance(v, (list, tuple)):
        v = sep.join(t for t in (_item_texto(i) for i in v) if t)
    v = str(v).strip()
    if not v:
        return None
    return _cortar_bytes(v) if cortar else v


def _st_ativo(valor):
    # bool -> '1'/'0' da coluna ST_ATIVO. None passa direto: a SP usa
    # NVL(P_ST_ATIVO, ST_ATIVO) e nao mexe na coluna quando nada e informado.
    if valor is None:
        return None
    return ST_ATIVO_SIM if valor else ST_ATIVO_NAO


def _valor_bind(campo, valor):
    """Converte um campo capturado para o tipo da coluna Oracle correspondente."""
    if campo in _NUMERICOS:
        return _num(valor)
    if campo in _INTEIROS:
        return _num_inteiro(valor)
    if campo in _CONTADORES:
        return _num_contador(valor)
    # QT_MINIMA_RECORRENCIA e NUMBER, mas o campo capturado e a DESCRICAO da
    # recorrencia ("Assine 2 ou mais e economize") -> extrai a quantidade.
    if campo == 'recorrencia_quantidade_minima_descricao':
        return _num_inteiro(valor)
    # Campos CLOB: texto inteiro (sem o corte de _MAX_BIND_BYTES).
    return _texto(valor, cortar=campo not in _CLOB_CAMPOS)


def _recorrencia(capturado):
    """VR_RECORRENCIA/ST_RECORRENCIA a partir dos 2 fragmentos capturados na
    pagina (Amazon, 'Assine e economize'): preco_recorrencia_inteiro="18" +
    preco_recorrencia_fracao="99" -> 18.99. Sem o inteiro (produto sem essa
    opcao, ou loja que nao tem o campo) -> (None, 0) -- ST_RECORRENCIA=0."""
    inteiro = _num_inteiro(capturado.get('preco_recorrencia_inteiro'))
    if inteiro is None:
        return None, 0
    fracao = _num_inteiro(capturado.get('preco_recorrencia_fracao')) or 0
    return inteiro + fracao / 100, 1


def _carregar_cfg_db(caminho=CONFIG_PATH):
    """Le o bloco 'db' do conf/config.json. {} se ausente/erro."""
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f).get("db") or {}
    except Exception:  # noqa: BLE001
        return {}


class OracleDB:
    """Leitura da fila e gravacao dos complementos via stored procedure."""

    def __init__(self, cfg=None):
        self._cfg = cfg if cfg is not None else _carregar_cfg_db()
        # So esta "habilitado" se pedido no config E a lib estiver disponivel.
        self.habilitado = bool(self._cfg.get("habilitado")) and oracledb is not None
        self._conn = None

    # -- ciclo de vida --------------------------------------------------------
    def _montar_dsn(self):
        # 'dsn' (alias do tnsnames.ora; banco com wallet) vence host/porta/servico.
        dsn = (self._cfg.get("dsn") or "").strip()
        if dsn:
            return dsn
        # .strip() defensivo: um espaco extra vindo do config (ex.: editor) nao
        # deve quebrar o host/servico.
        host = (self._cfg.get("host") or "LOCALHOST").strip()
        porta = int(self._cfg.get("porta", 1521))
        servico = (self._cfg.get("servico") or "").strip()
        sid = (self._cfg.get("sid") or "").strip()
        if sid and not servico:
            return oracledb.makedsn(host, porta, sid=sid)
        return oracledb.makedsn(host, porta, service_name=servico or "XE")

    def conectar(self):
        """Abre a conexao. True se conectou; em erro loga, marca habilitado=False
        e retorna False."""
        if not self.habilitado:
            if oracledb is None:
                print('[oracle] lib python-oracledb nao instalada.')
            else:
                print('[oracle] desabilitado em conf/config.json (db.habilitado).')
            return False
        global _client_iniciado
        modo = (self._cfg.get("modo") or "thick").lower()
        try:
            if modo == "thick" and not _client_iniciado:
                # .strip() defensivo: espacos extras no caminho (ex.: vindos do
                # editor) fariam o init apontar p/ pasta inexistente (DPI-1047).
                lib = (self._cfg.get("instant_client_dir") or "").strip() or None
                # config_dir: pasta do tnsnames.ora/sqlnet.ora (wallet); sem ela vale
                # ORACLE_HOME/TNS_ADMIN da maquina.
                cfg_dir = (self._cfg.get("config_dir") or "").strip() or None
                oracledb.init_oracle_client(lib_dir=lib, config_dir=cfg_dir)
                _client_iniciado = True
            dsn = self._montar_dsn()
            self._conn = oracledb.connect(
                user=(self._cfg.get("usuario") or "").strip(),
                password=self._cfg.get("senha"),
                dsn=dsn,
            )
            print(f"[oracle] Conectado ({modo}) em {dsn}.")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[oracle] Falha ao conectar: {e}")
            self.habilitado = False
            self._conn = None
            return False

    def desconectar(self):
        """Fecha a conexao (idempotente, best-effort)."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    def __enter__(self):
        self.conectar()
        return self

    def __exit__(self, *_exc):
        self.desconectar()
        return False

    # -- leitura da fila ------------------------------------------------------
    def ler_fila(self, ultimo_id=0, limite=0):
        """
        Linhas pendentes: ST_CAPTURA = '0' AND ID_OFERTA > ultimo_id, em ordem de
        ID. `limite` > 0 corta o lote (util para testes). Retorna lista de dicts
        com as chaves de COLUNAS_FILA.
        """
        if self._conn is None:
            raise RuntimeError("sem conexao Oracle")
        cols = ", ".join(COLUNAS_FILA)
        sql = (f"SELECT {cols} FROM OFERTA_FILA_CAPTURA "
               f"WHERE ST_CAPTURA = '{ST_PENDENTE}' AND ID_OFERTA > :ultimo_id "
               f"ORDER BY ID_OFERTA")
        if limite and limite > 0:
            # ROWNUM tem que ser aplicado DEPOIS do ORDER BY -> subquery.
            sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :limite"
        cur = self._conn.cursor()
        try:
            binds = {"ultimo_id": int(ultimo_id or 0)}
            if limite and limite > 0:
                binds["limite"] = int(limite)
            cur.execute(sql, binds)
            nomes = [d[0] for d in cur.description]
            return [dict(zip(nomes, linha)) for linha in cur]
        finally:
            cur.close()

    # Colunas de OFERTA_FILA_CAPTURA usadas pelo cadastro de produtos
    # (core/produtos.py): a fonte e sempre o que FOI GRAVADO no banco (numeros
    # ja convertidos, LS_* ja no texto "rotulo: valor | ..."), nunca os dados
    # "crus" do Python antes do bind -- assim o cadastro ao vivo (main.py, logo
    # apos o commit) e o backfill (cadastrar_produtos.py) leem exatamente a
    # mesma coisa, sem duplicar a logica de conversao de tipo do _valor_bind.
    COLUNAS_PARA_PRODUTO = [
        'DS_TITULO', 'DS_OFERTA', 'DS_PRODUTO', 'VL_PRECO_POR', 'VR_PRECO_1', 'VR_RECORRENCIA',
        'VR_ESPERE_ECONOMIZE', 'DS_URL_AFILIADO', 'LS_CATEGORIA', 'QT_OPINIOES', 'DS_AVALIACAO_GERAL',
        'LS_DETALHES_PRODUTO', 'LS_DETALHES_TECNICOS', 'LS_INFO_ADICIONAIS', 'LS_COMPLEMENTO_PRODUTO',
    ]

    def buscar_para_produto(self, id_oferta):
        """Le de volta 1 linha ja gravada (por ID_OFERTA), so as colunas que o
        cadastro de produtos consome. None se o ID nao existir."""
        if self._conn is None:
            raise RuntimeError("sem conexao Oracle")
        cols = ", ".join(self.COLUNAS_PARA_PRODUTO)
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT {cols} FROM OFERTA_FILA_CAPTURA WHERE ID_OFERTA = :id",
                        {"id": int(id_oferta)})
            row = cur.fetchone()
            if row is None:
                return None
            nomes = [d[0] for d in cur.description]
            return dict(zip(nomes, row))
        finally:
            cur.close()

    # Colunas usadas por core/ofertas.py (tabela BESAVE.OFERTA) -- mesmo
    # principio de COLUNAS_PARA_PRODUTO: le o que FOI GRAVADO, nunca o dado
    # cru do Python.
    COLUNAS_PARA_OFERTA = [
        'DS_TITULO', 'DS_IMAGEM_OFERTA', 'DS_URL_BESAVE', 'DS_URL_FINAL',
        'VL_PRECO_DE', 'VL_PRECO_POR', 'VR_PRECO_1', 'DS_CUPOM',
        'DS_CUPOM_COMENTARIO', 'NR_NOTA_AVALIACAO', 'QT_AVALIACAO',
        'DT_OFERTA', 'DT_CAPTACAO',
        'DS_URL_AFILIADO', 'DS_CATEGORIA_PROD_AFILIADO',
        'DS_TAXA_COMISSAO_PROD_AFILIADO', 'DS_ID_PRODUTO_AFILIADO',
        'VR_RECORRENCIA', 'ST_RECORRENCIA', 'QT_MINIMA_RECORRENCIA',
        'VR_ESPERE_ECONOMIZE', 'ST_ESPERE_ECONOMIZE',
    ]

    def buscar_para_oferta(self, id_oferta):
        """Le de volta 1 linha ja gravada (por ID_OFERTA), so as colunas que a
        publicacao em OFERTA consome. None se o ID nao existir."""
        if self._conn is None:
            raise RuntimeError("sem conexao Oracle")
        cols = ", ".join(self.COLUNAS_PARA_OFERTA)
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT {cols} FROM OFERTA_FILA_CAPTURA WHERE ID_OFERTA = :id",
                        {"id": int(id_oferta)})
            row = cur.fetchone()
            if row is None:
                return None
            nomes = [d[0] for d in cur.description]
            return dict(zip(nomes, row))
        finally:
            cur.close()

    # Colunas usadas por core/cupons.py (tabela BESAVE.CUPOM). DS_CUPOM e o
    # codigo do cupom, DS_CUPOM_COMENTARIO a descricao/condicao e
    # DS_CUPOM_LOJA a loja associada AO CUPOM (ja gravadas na fila antes da
    # captura, nao vem do scraping) -- ver cabecalho de sql/CREATE_TABLE_CUPOM.sql.
    COLUNAS_PARA_CUPOM = ['ID_OFERTA', 'DS_CUPOM', 'DS_CUPOM_COMENTARIO', 'DS_CUPOM_LOJA']

    def buscar_para_cupom(self, id_oferta):
        """Le de volta 1 linha ja gravada (por ID_OFERTA), so as colunas que o
        cadastro de cupons consome. None se o ID nao existir."""
        if self._conn is None:
            raise RuntimeError("sem conexao Oracle")
        cols = ", ".join(self.COLUNAS_PARA_CUPOM)
        cur = self._conn.cursor()
        try:
            cur.execute(f"SELECT {cols} FROM OFERTA_FILA_CAPTURA WHERE ID_OFERTA = :id",
                        {"id": int(id_oferta)})
            row = cur.fetchone()
            if row is None:
                return None
            nomes = [d[0] for d in cur.description]
            return dict(zip(nomes, row))
        finally:
            cur.close()

    # -- gravacao -------------------------------------------------------------
    def executar_stored_procedure(self, nome, params, out_vars, clob_params=None):
        """
        Executa a SP `nome` com binds nomeados: `params` (IN, dict nome->valor) e
        `out_vars` (dict nome->tipo oracledb). Faz commit no sucesso; devolve
        dict {nome_out: valor}. Levanta em erro.
        `clob_params`: nomes de params a bindar como CLOB (texto > 4000 bytes, que
        o Oracle recusaria como VARCHAR2 com ORA-01461).
        """
        if self._conn is None:
            raise RuntimeError("sem conexao Oracle")
        cur = self._conn.cursor()
        try:
            binds = dict(params)
            outs = {}
            for nome_out, tipo in out_vars.items():
                var = cur.var(tipo, 4000)
                binds[nome_out] = var
                outs[nome_out] = var
            if clob_params:
                cur.setinputsizes(**{p: oracledb.DB_TYPE_CLOB
                                     for p in clob_params if p in binds})
            arglist = ", ".join(f"{k} => :{k}" for k in binds)
            cur.execute(f"BEGIN {nome}({arglist}); END;", binds)
            self._conn.commit()
            return {k: v.getvalue() for k, v in outs.items()}
        finally:
            cur.close()

    def _chamar_sp(self, nome, params, clob_params=None):
        """Executa a SP e traduz PV_RETORNO/PV_ERRO em (ok, erro). Best-effort:
        nunca propaga excecao -- o CSV e a rede de seguranca e o lote nao pode
        parar por causa do banco."""
        if not self.habilitado or self._conn is None:
            return False, 'sem conexao Oracle'
        try:
            out = self.executar_stored_procedure(
                nome, params,
                {"PV_RETORNO": oracledb.DB_TYPE_VARCHAR,
                 "PV_ERRO": oracledb.DB_TYPE_VARCHAR},
                clob_params=clob_params,
            )
            ok = (out.get("PV_RETORNO") or "").upper() == "TRUE"
            return ok, (None if ok else out.get("PV_ERRO"))
        except Exception as e:  # noqa: BLE001
            try:
                self._conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return False, str(e)

    def atualizar_captura(self, id_oferta, capturado, descricao='ok', ativo=None):
        """
        Sucesso: grava os complementos da linha `id_oferta` (dict `capturado` =
        saida da store, chaves = colunas do CSV). A SP forca ST_CAPTURA = '1' e
        grava `descricao` em DS_CAPTURA. Retorna (ok, erro).

        `ativo` (bool) vira ST_ATIVO '1'/'0'; None deixa a coluna como esta.
        """
        params = {'P_ID_OFERTA': int(id_oferta), 'P_DS_CAPTURA': _texto(descricao),
                  'P_ST_ATIVO': _st_ativo(ativo)}
        for campo, param in MAPA_CAMPOS.items():
            params[param] = _valor_bind(campo, capturado.get(campo))
        params['P_VR_RECORRENCIA'], params['P_ST_RECORRENCIA'] = _recorrencia(capturado)
        params['P_ST_ESPERE_ECONOMIZE'] = 1 if (params.get('P_VR_ESPERE_ECONOMIZE') or 0) > 0 else 0
        return self._chamar_sp(NOME_SP, params, clob_params=_CLOB_PARAMS)

    def marcar_erro(self, id_oferta, descricao, url_final=None, ativo=None):
        """
        Falha: marca a linha com ST_CAPTURA = '9' e o motivo em DS_CAPTURA (o
        status_captura do main.py), preservando as colunas de captura. A linha
        sai da fila -- para reprocessar, devolva ST_CAPTURA para '0'.
        Retorna (ok, erro).

        `ativo` como em atualizar_captura: mesmo em erro a loja costuma ser
        conhecida, e saber se ela e ativa ajuda a priorizar o reprocessamento.
        """
        return self._chamar_sp(NOME_SP_ERRO, {
            'P_ID_OFERTA': int(id_oferta),
            'P_DS_CAPTURA': _texto(descricao),
            'P_DS_URL_FINAL': _texto(url_final),
            'P_ST_ATIVO': _st_ativo(ativo),
        })
