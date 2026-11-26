"""Oracle: consulta de "já vista" e INSERT na fila (BSV-66, Saídas 5, 6 e 9).

Usuário próprio (`BESAVE_WEB`), tabelas sempre com `BESAVE.`. Conexão como no robô das lojas
(`modo` thick/thin, `dsn`, `config_dir`, `instant_client_dir`). Erro de conexão: uma reconexão e uma
repetição; falhou de novo -> `BancoFora` (a rodada para).
"""

import logging
import re
import time
import unicodedata
from decimal import Decimal

log = logging.getLogger('captura_web')

_UM_MENOS, _UM_MAIS = Decimal('0.99'), Decimal('1.01')

AGORA_BRT = "CAST(SYSTIMESTAMP AT TIME ZONE '-03:00' AS DATE)"

SQL_INSERT = (
    "INSERT INTO BESAVE.OFERTA_FILA_CAPTURA (DS_TIPO_ORIGEM, DS_ORIGEM, DS_TIPO_OFERTA, DT_OFERTA, "
    "DT_CAPTACAO, DS_OFERTA, VL_PRECO_DE, VL_PRECO_POR, DS_URL_ORIGEM, DS_LOJA, DS_CUPOM, DS_CUPOM_LOJA, "
    "ST_CAPTURA) VALUES ('CAPTURA WEB', :origem, 'PRODUTO', "
    f"{AGORA_BRT}, {AGORA_BRT}, "
    ":titulo, :preco_de, :preco_por, :url, :loja, :cupom, :cupom_loja, '0') "
    "RETURNING ID_OFERTA INTO :id"
)

_SQL_CHAVE = (
    "SELECT 'F', NULL FROM BESAVE.OFERTA_FILA_CAPTURA "
    f"WHERE DT_OFERTA >= {AGORA_BRT} - 1 AND DS_URL_ORIGEM LIKE '%' || :chave || '%' "
    "UNION ALL "
    "SELECT 'O', NULL FROM BESAVE.OFERTA "
    "WHERE ST_ATIVO = 1 AND DS_URL_FINAL LIKE '%' || :chave || '%' AND VL_PRECO_POR <= :preco "
    "UNION ALL "
)
_SQL_TITULO = (
    "SELECT 'T', DS_OFERTA FROM BESAVE.OFERTA_FILA_CAPTURA "
    f"WHERE DT_OFERTA >= {AGORA_BRT} - 1 AND DS_LOJA = :loja AND VL_PRECO_POR BETWEEN :pmin AND :pmax"
)
SQL_VISTA_COM_CHAVE = _SQL_CHAVE + _SQL_TITULO
SQL_VISTA_SEM_CHAVE = _SQL_TITULO

# Erros de CONEXAO (sessão morta, rede, banco fora): vale reconectar. Mesma lista do robô das lojas.
_ERROS_CONEXAO = re.compile(
    r"DPY-1001|DPY-4011|DPI-1010|DPI-1080|"
    r"ORA-0(?:3113|3114|3135|3136|1012|2396|0028)|"
    r"ORA-01033|ORA-01034|ORA-12(?:170|514|537|541|543|571)"
)


class BancoFora(Exception):
    pass


class ErroDado(Exception):
    """Erro do banco que não é de conexão (repetir não resolve)."""


def erro_conexao(exc):
    return bool(_ERROS_CONEXAO.search(str(exc)))


_client_iniciado = False


def conectar_oracle(cfg):
    """Abre a conexão com python-oracledb (import tardio: os testes não precisam da lib)."""
    global _client_iniciado
    import oracledb

    modo = (cfg.get('modo') or 'thick').strip().lower()
    cfg_dir = (cfg.get('config_dir') or '').strip() or None
    extra = {}
    if modo == 'thick':
        if not _client_iniciado:
            lib = (cfg.get('instant_client_dir') or '').strip() or None
            oracledb.init_oracle_client(lib_dir=lib, config_dir=cfg_dir)
            _client_iniciado = True
    elif cfg_dir:
        # thin com wallet: tnsnames.ora e ewallet.pem na mesma pasta.
        extra = {'config_dir': cfg_dir, 'wallet_location': cfg_dir}
        if cfg.get('wallet_senha'):
            extra['wallet_password'] = cfg['wallet_senha']
    dsn = (cfg.get('dsn') or '').strip()
    if not dsn:
        dsn = oracledb.makedsn((cfg.get('host') or 'LOCALHOST').strip(), int(cfg.get('porta') or 1521),
                               service_name=(cfg.get('servico') or 'XE').strip())
    return oracledb.connect(user=(cfg.get('usuario') or '').strip(), password=cfg.get('senha'), dsn=dsn,
                            **extra)


def normalizar_titulo(texto):
    t = unicodedata.normalize('NFKD', texto or '').lower()
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t).split())


class Banco:
    def __init__(self, cfg, conectar=None, dormir=time.sleep):
        self.cfg = cfg or {}
        self._conectar = conectar or (lambda: conectar_oracle(self.cfg))
        self.dormir = dormir
        self.conn = None

    def abrir(self):
        """True se conectou (uma repetição em erro)."""
        for tentativa in range(2):
            try:
                self.conn = self._conectar()
                return True
            except Exception as e:  # noqa: BLE001
                # Só o tipo e o código: a mensagem do driver pode trazer o DSN.
                log.error('falha ao conectar no Oracle (%s): %s', type(e).__name__, _codigo(e))
                self.conn = None
                if tentativa == 0:
                    self.dormir(2)
        return False

    def fechar(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception as e:  # noqa: BLE001 - conexão já morta
                log.debug('close falhou (%s)', type(e).__name__)
            self.conn = None

    def _executar(self, fazer):
        """Roda `fazer(conn)`; erro de conexão -> reconecta e repete uma vez; de novo -> BancoFora."""
        for tentativa in range(2):
            if self.conn is None and not self.abrir():
                raise BancoFora('sem conexão')
            try:
                return fazer(self.conn)
            except Exception as e:
                if not erro_conexao(e):
                    raise ErroDado(_codigo(e)) from e
                log.warning('conexao perdida (%s); reconectando', _codigo(e))
                self.fechar()
                if tentativa == 1:
                    raise BancoFora(_codigo(e)) from e
        raise BancoFora('sem conexão')

    def ja_vista(self, trecho, preco, loja, titulo):
        """'vista_fila' | 'vista_oferta' | 'mesmo_titulo' | None, numa consulta só."""
        binds = {'loja': loja, 'pmin': None if preco is None else preco * _UM_MENOS,
                 'pmax': None if preco is None else preco * _UM_MAIS}
        if trecho:
            sql = SQL_VISTA_COM_CHAVE
            binds.update(chave=trecho, preco=preco)
        else:
            sql = SQL_VISTA_SEM_CHAVE

        def fazer(conn):
            cur = conn.cursor()
            try:
                cur.execute(sql, binds)
                return cur.fetchall()
            finally:
                cur.close()

        linhas = self._executar(fazer)
        tipos = {t for t, _ in linhas}
        if 'F' in tipos:
            return 'vista_fila'
        if 'O' in tipos:
            return 'vista_oferta'
        alvo = normalizar_titulo(titulo)
        if any(t == 'T' and normalizar_titulo(d) == alvo for t, d in linhas):
            return 'mesmo_titulo'
        return None

    def gravar(self, linha):
        """INSERT + COMMIT; devolve o ID_OFERTA gerado pela trigger."""
        def fazer(conn):
            cur = conn.cursor()
            try:
                var_id = cur.var(int)
                cur.execute(SQL_INSERT, dict(linha, id=var_id))
                conn.commit()
                valor = var_id.getvalue()
            finally:
                cur.close()
            if isinstance(valor, list):
                valor = valor[0] if valor else None
            return int(valor) if valor is not None else None

        return self._executar(fazer)


def _codigo(e):
    m = re.search(r'\b(?:ORA|DPY|DPI)-\d+', str(e))
    return m.group(0) if m else type(e).__name__

