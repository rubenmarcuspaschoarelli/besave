"""Fila ENVIO_WHATSAPP no Oracle (BSV-63; DDL em apps/worker/sql/bsv-62.sql).

Copiado e reduzido de capture-chat-groups/wa/oracle_db.py (os programas nao dividem pacote): modo thick
(Oracle XE 11.2 exige Instant Client 19+), `call_timeout` em toda conexao e uma reconexao por chamada em
erro de conexao (licao 31). Toda troca de estado e guardada pelo estado de origem (`AND ST_ENVIO = :de`):
uma linha que mudou por fora nunca e postada.
"""

import os
import re
from datetime import datetime

from .regras import Linha, Parametros

try:
    import oracledb
except Exception:  # noqa: BLE001 - sem a lib, a partida falha com ErroBanco
    oracledb = None

SQL_PARAMETROS = "SELECT QT_MAX_DIA, NR_HORA_INICIO, NR_HORA_FIM FROM PARAMETROS_ENVIO WHERE ID_CANAL = :1"
SQL_NOME_CANAL = "SELECT DS_CHAT_ID FROM CANAL_ENVIO WHERE ID_CANAL = :1"
SQL_ENVIADOS = ("SELECT COUNT(*) FROM ENVIO_WHATSAPP WHERE ID_CANAL = :1 "
                "AND ST_ENVIO IN ('E', 'D') AND DT_ENVIO >= :2")
SQL_PENDENTES = ("SELECT e.ID_ENVIO_WA, e.ID_OFERTA, e.DS_LEGENDA, e.DS_AREA_SLUG, e.DT_FILA, "
                 "CASE WHEN o.ST_ATIVO = 1 THEN 1 ELSE 0 END "
                 "FROM ENVIO_WHATSAPP e LEFT JOIN OFERTA o ON o.ID_OFERTA = e.ID_OFERTA "
                 "WHERE e.ID_CANAL = :1 AND e.ST_ENVIO = 'P'")
SQL_MARCAR = ("UPDATE ENVIO_WHATSAPP SET ST_ENVIO = :para, DS_MOTIVO = :motivo, DT_ENVIO = :dt "
              "WHERE ID_ENVIO_WA = :id AND ST_ENVIO = :de")

CALL_TIMEOUT_PADRAO_S = 30
_ERROS_CONEXAO = re.compile(
    r"DPY-1001|DPY-4011|DPI-1010|DPI-1080|"
    r"ORA-0(?:3113|3114|3135|3136|1012|2396|0028)|"
    r"ORA-01033|ORA-01034|ORA-12(?:170|514|537|541|543|571)"
)
_RE_CODIGO = re.compile(r"(?:ORA|DPY|DPI|PLS)-\d+")
_client_iniciado = False


class ErroBanco(RuntimeError):
    """Falha do Oracle; a mensagem leva so o codigo (a original pode trazer DSN/host)."""


def codigo(exc) -> str:
    m = _RE_CODIGO.search(str(exc))
    return m.group(0) if m else type(exc).__name__


def _de_conexao(exc) -> bool:
    return bool(_ERROS_CONEXAO.search(str(exc)))


def conectar_real(cfg: dict):
    """Abre a conexao com o bloco `oracle` do config. BESAVE_ORACLE_PASS vence a senha do JSON."""
    global _client_iniciado
    if oracledb is None:
        raise ErroBanco("python-oracledb nao instalado")
    if (cfg.get("modo") or "thick").lower() == "thick" and not _client_iniciado:
        oracledb.init_oracle_client(lib_dir=(cfg.get("instant_client_dir") or "").strip() or None,
                                    config_dir=(cfg.get("config_dir") or "").strip() or None)
        _client_iniciado = True
    dsn = (cfg.get("dsn") or "").strip() or oracledb.makedsn(
        (cfg.get("host") or "LOCALHOST").strip(), int(cfg.get("porta", 1521)),
        service_name=(cfg.get("servico") or "XE").strip())
    conn = oracledb.connect(user=(cfg.get("usuario") or "").strip(),
                            password=os.environ.get("BESAVE_ORACLE_PASS") or cfg.get("senha"), dsn=dsn)
    try:
        t = float(cfg.get("call_timeout_segundos", CALL_TIMEOUT_PADRAO_S))
    except (TypeError, ValueError):
        t = CALL_TIMEOUT_PADRAO_S
    conn.call_timeout = int((t if t > 0 else CALL_TIMEOUT_PADRAO_S) * 1000)
    return conn


class Fila:
    def __init__(self, conectar, log=print):
        self._conectar = conectar          # () -> conexao DB-API
        self._conn = None
        self._log = log

    def _chamar(self, f):
        """Roda `f(cursor)`; em erro de conexao reconecta uma vez e repete. Outro erro vira ErroBanco."""
        for tentativa in (1, 2):
            try:
                if self._conn is None:
                    self._conn = self._conectar()
                with self._conn.cursor() as cur:
                    return f(cur)
            except Exception as e:  # noqa: BLE001
                conexao = _de_conexao(e)
                if conexao:
                    self._fechar()
                if conexao and tentativa == 1:
                    self._log(f"[oracle] {codigo(e)}: reconectando")
                    continue
                raise ErroBanco(codigo(e)) from None
        raise ErroBanco("sem conexao")       # inalcancavel; satisfaz o leitor

    def _fechar(self):
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception as e:  # noqa: BLE001 - conexao ja morta: fechar e so higiene
            self._log(f"[oracle] fechar a conexao falhou ({codigo(e)})")
        self._conn = None

    def fechar(self):
        self._fechar()

    def parametros(self, canal: int) -> Parametros | None:
        def f(cur):
            cur.execute(SQL_PARAMETROS, [canal])
            r = cur.fetchone()
            return None if r is None else Parametros(int(r[0]), int(r[1]), int(r[2]))
        return self._chamar(f)

    def nome_canal(self, canal: int) -> str | None:
        def f(cur):
            cur.execute(SQL_NOME_CANAL, [canal])
            r = cur.fetchone()
            return None if r is None or not r[0] else str(r[0])
        return self._chamar(f)

    def enviados_desde(self, canal: int, inicio: datetime) -> int:
        def f(cur):
            cur.execute(SQL_ENVIADOS, [canal, inicio])
            return int(cur.fetchone()[0])
        return self._chamar(f)

    def pendentes(self, canal: int) -> list[Linha]:
        def f(cur):
            cur.execute(SQL_PENDENTES, [canal])
            return [Linha(id_envio=int(r[0]), id_oferta=int(r[1]), legenda=_texto(r[2]), area_slug=str(r[3]),
                          dt_fila=r[4], ativa=int(r[5]) == 1) for r in cur.fetchall()]
        return self._chamar(f)

    def marcar(self, id_envio: int, de: str, para: str, motivo: str | None, dt: datetime | None) -> bool:
        """Troca o estado so se a linha ainda esta em `de`. True = 1 linha mudou (e foi commitada)."""
        def f(cur):
            cur.execute(SQL_MARCAR, {"para": para, "motivo": motivo, "dt": dt, "id": id_envio, "de": de})
            n = cur.rowcount
            self._conn.commit()
            return n == 1
        return self._chamar(f)


def _texto(v) -> str:
    """VARCHAR2 vem como str; CLOB (se a coluna mudar) como LOB com .read()."""
    return v.read() if hasattr(v, "read") else str(v)
