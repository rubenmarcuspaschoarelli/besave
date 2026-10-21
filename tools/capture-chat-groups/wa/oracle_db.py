"""
Persistencia em Oracle (best-effort): insere cada oferta capturada na tabela
OFERTA_FILA_CAPTURA chamando a stored procedure STP_OFERTA_FILA_CAPTURA_INSERT.

Driver: python-oracledb em THICK mode. O servidor e um Oracle XE 11.2, e:
  - o THIN mode so conecta em Oracle 12.1+ (nao serve p/ 11.2);
  - o THICK mode do python-oracledb atual exige Oracle Client >= 19
    (Instant Client 19c x64), apontado por conf/config.json -> db.instant_client_dir.
O Client 19c conversa normalmente com o servidor 11.2 (interoperabilidade de rede).

A gravacao e SEMPRE best-effort: se o bloco 'db' estiver ausente / habilitado=false,
se a lib ou o Instant Client nao carregarem, ou se a conexao/insert falharem, apenas
loga e segue -- o CSV continua sendo a fonte primaria e a captura nunca e derrubada.

API (pedida pelo usuario):
  db = OracleDB()
  db.conectar()                      # inicia a conexao (idempotente)
  db.inserir_oferta(linha_csv)       # -> bool (usa a SP; TRUE/FALSE)
  db.executar_stored_procedure(...)  # execucao generica de SP com OUT params
  db.desconectar()                   # encerra a conexao (idempotente)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from .storage import CAPTURA_DIR, CONFIG_PATH, LOG_DIR

# --- Saneamento de texto para as colunas VARCHAR2 ---------------------------
#
# Colunas com semantica de BYTE na tabela (USER_TAB_COLUMNS.CHAR_USED='B').
# Conferido em 28/07: o SP JA faz SUBSTR, mas SUBSTR corta CARACTERES enquanto o
# limite da coluna conta BYTES. Com o banco em AL32UTF8 cada acento vale 2 bytes
# e cada emoji 4, entao 50 caracteres acentuados viram 52 bytes e o insert cai
# com ORA-12899 (aconteceu com 3 linhas do run de 28/07 17:45). As colunas
# grandes (DS_OFERTA, DS_URL_ORIGEM, DS_IMAGEM_OFERTA...) sao CHAR e nao entram
# aqui: para elas o SUBSTR do SP ja basta.
_LIMITE_BYTES = {
    "DS_TIPO_ORIGEM": 30,
    "DS_ORIGEM": 100,
    "DS_TIPO_OFERTA": 30,
    "DS_DESCRICAO_PAGAMENTO": 50,
    # DS_CUPOM saiu daqui em 28/09/2026: virou VARCHAR2(250 CHAR) - ver _cupom.
    "DS_CUPOM_COMENTARIO": 50,
    "DS_CUPOM_LOJA": 50,
    "DS_LOJA": 100,
}

# Emoji e simbolos pictograficos. Nao toca em letra acentuada (fora destas
# faixas), entao 'Kit Óleos' continua intacto.
_RE_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"          # pictogramas, emoticons, transporte, suplementos
    "\U00002600-\U000027BF"          # simbolos diversos + dingbats (inclui o ✨)
    "\U00002190-\U000021FF"          # setas
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"          # variation selectors (o U+FE0F do 🛍️)
    "\U0000200D"                     # zero-width joiner
    "\U000020E3\U00002122\U00002139\U00002049\U0000203C\U000024C2"
    "]+",
    flags=re.UNICODE,
)


def _sem_emoji(s: str) -> str:
    """Tira emoji/pictogramas e normaliza os espacos que sobram."""
    return re.sub(r"\s{2,}", " ", _RE_EMOJI.sub("", s)).strip()


def _truncar_bytes(s: str, limite: int) -> str:
    """
    Corta a string para caber em `limite` BYTES de UTF-8, sem partir caractere
    ao meio (o decode com errors='ignore' descarta a sobra incompleta).
    """
    b = s.encode("utf-8")
    if len(b) <= limite:
        return s
    return b[:limite].decode("utf-8", errors="ignore")


def _texto(valor, coluna: str):
    """Valor do CSV -> texto pronto para o bind: sem emoji e dentro do limite de
    bytes da coluna. Devolve None quando vazio (a SP trata NULL)."""
    if valor is None:
        return None
    s = _sem_emoji(str(valor))
    if not s:
        return None
    limite = _LIMITE_BYTES.get(coluna)
    if limite:
        s = _truncar_bytes(s, limite).strip()
    return s or None


# DS_CUPOM: VARCHAR2(250 CHAR) desde 28/09/2026 (era 30 BYTE e cortava a lista
# de cupons separada por ' | ' no meio). Outro processo separa os cupons, entao
# o corte, se precisar acontecer, e no ULTIMO cupom inteiro que cabe - nunca no
# meio de um codigo - e fica registrado em log/cupom_excedido.log para
# ajustarmos o tamanho. O CSV sempre guarda a lista completa.
LIMITE_CUPOM = 250
_SEP_CUPOM = " | "
LOG_CUPOM_EXCEDIDO = LOG_DIR / "cupom_excedido.log"


def _cupom(valor, id_oferta):
    """DS_CUPOM pronto para o bind (sem emoji, ate LIMITE_CUPOM caracteres)."""
    if valor is None:
        return None
    s = _sem_emoji(str(valor))
    if len(s) <= LIMITE_CUPOM:
        return s or None
    corte = s[:LIMITE_CUPOM + len(_SEP_CUPOM)].rfind(_SEP_CUPOM)
    if corte <= 0 or corte > LIMITE_CUPOM:
        cortado = s[:LIMITE_CUPOM].rstrip(" |")
    else:
        cortado = s[:corte]
    msg = (f"ID {id_oferta}: DS_CUPOM com {len(s)} caracteres (limite {LIMITE_CUPOM}); "
           f"gravado {len(cortado)}. Completo: {s}")
    print(f"[oracle] AVISO {msg}")
    try:
        LOG_CUPOM_EXCEDIDO.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_CUPOM_EXCEDIDO, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%d/%m/%Y %H:%M:%S} {msg}\n")
    except Exception:  # noqa: BLE001 - o aviso ja foi para o log do run
        pass
    return cortado or None

try:                                 # sem a lib instalada -> seguimos so com CSV
    import oracledb
except Exception:                    # noqa: BLE001
    oracledb = None

# init_oracle_client() so pode ser chamado UMA vez por processo.
_client_iniciado = False

NOME_SP = "STP_OFERTA_FILA_CAPTURA_INSERT"

# Erros de CONEXAO (sessao morta, rede, banco fora): vale reconectar e repetir.
# Erro de dados (ORA-01400, PLS-...) nao entra: repetir nao resolve.
_ERROS_CONEXAO = re.compile(
    r"DPY-1001|DPY-4011|DPI-1010|DPI-1080|"
    r"ORA-0(?:3113|3114|3135|3136|1012|2396|0028)|"
    r"ORA-01033|ORA-01034|ORA-12(?:170|514|537|541|543|571)"
)


class ErroSemConexao(RuntimeError):
    """Nao ha conexao Oracle utilizavel (nem depois de reconectar)."""


def _erro_conexao(exc) -> bool:
    return isinstance(exc, ErroSemConexao) or bool(_ERROS_CONEXAO.search(str(exc)))


# --- Conversores de tipo (str do CSV -> tipo Oracle) ------------------------
def _preco_para_numero(s):
    """
    '182,90' / '19,9' / '3.499' -> float; '' / None / lixo -> None.
    Formato pt-BR: ponto e separador de milhar, virgula e decimal.
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _data_para_dt(s):
    """'16/07/2026 18:27' ou '17/07/2026 00:47:19' -> datetime; '' -> None."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _imagem_relativa(caminho):
    """
    Caminho absoluto salvo hoje (...\\captura\\img\\NN_x.jpeg) -> relativo a
    captura/ (img/NN_x.jpeg, com barras normais). Vazio -> ''; fora de captura/
    -> so o nome do arquivo.
    """
    if not caminho:
        return ""
    try:
        rel = Path(caminho).resolve().relative_to(CAPTURA_DIR.resolve())
        return rel.as_posix()
    except Exception:  # noqa: BLE001 - path fora de captura/ ou invalido
        return Path(caminho).name


def _carregar_cfg_db():
    """Le o bloco 'db' do conf/config.json. {} se ausente/erro."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f).get("db") or {}
    except Exception:  # noqa: BLE001
        return {}


class OracleDB:
    """Conexao e gravacao de ofertas em Oracle via stored procedure."""

    def __init__(self, cfg=None):
        self._cfg = cfg if cfg is not None else _carregar_cfg_db()
        # So esta "habilitado" se pedido no config E a lib estiver disponivel.
        self.habilitado = bool(self._cfg.get("habilitado")) and oracledb is not None
        self._conn = None
        # True se o ULTIMO inserir_oferta falhou por falta de conexao (o log do
        # monitor mostra "db=ERRO (sem conexao)").
        self.sem_conexao = False
        # A SP passou a receber a loja DA OFERTA em 22/09/2026. Se o banco ainda
        # estiver com a versao antiga, mandar o parametro faria TODO insert
        # falhar (PLS-00306) -- entao perguntamos ao dicionario e so mandamos se
        # existir. Assim codigo novo + banco velho continua gravando.
        self._sp_tem_ds_loja = False

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
        """Abre a conexao. Retorna True se conectou. Best-effort: em erro, loga,
        marca habilitado=False e retorna False (a captura segue so com CSV)."""
        if not self.habilitado:
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
            self._sp_tem_ds_loja = self._sp_aceita("P_DS_LOJA")
            if not self._sp_tem_ds_loja:
                print(f"[oracle] {NOME_SP} ainda nao tem P_DS_LOJA: a loja da "
                      f"oferta vai so para o CSV (coluna DS_LOJA).")
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[oracle] Falha ao conectar ({e}). Seguindo so com CSV.")
            self.habilitado = False
            self._conn = None
            return False

    def _reconectar(self) -> bool:
        """Fecha e reabre a conexao apos uma queda. Diferente de conectar() no
        arranque, uma falha aqui NAO desliga o banco: a proxima oferta tenta de novo."""
        self.desconectar()
        self.habilitado = bool(self._cfg.get("habilitado")) and oracledb is not None
        ok = self.conectar()
        if not ok:
            self.habilitado = bool(self._cfg.get("habilitado")) and oracledb is not None
        return ok

    def _sp_aceita(self, parametro: str) -> bool:
        """True se a stored procedure tem o parametro (consulta o dicionario)."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                "select count(*) from user_arguments "
                "where object_name = :sp and argument_name = :arg",
                sp=NOME_SP, arg=parametro.upper(),
            )
            achou = (cur.fetchone() or [0])[0] > 0
            cur.close()
            return bool(achou)
        except Exception as e:  # noqa: BLE001
            print(f"[oracle] Nao consegui checar {parametro} em {NOME_SP} ({e}).")
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

    # -- execucao -------------------------------------------------------------
    def executar_stored_procedure(self, nome, params, out_vars):
        """
        Executa a SP `nome` com binds nomeados: `params` (IN, dict nome->valor) e
        `out_vars` (dict nome->tipo oracledb, ex.: oracledb.DB_TYPE_VARCHAR). Faz
        commit no sucesso; devolve dict {nome_out: valor}. Levanta em erro.
        """
        try:
            return self._executar_sp(nome, params, out_vars)
        except Exception as e:  # noqa: BLE001
            if not _erro_conexao(e):
                raise
            print(f"[oracle] Conexao perdida ({e}). Reconectando...")
        if not self._reconectar():
            raise ErroSemConexao("sem conexao Oracle")
        return self._executar_sp(nome, params, out_vars)

    def _executar_sp(self, nome, params, out_vars):
        if self._conn is None:
            raise ErroSemConexao("sem conexao Oracle")
        cur = self._conn.cursor()
        try:
            binds = dict(params)
            outs = {}
            for nome_out, tipo in out_vars.items():
                var = cur.var(tipo, 4000)
                binds[nome_out] = var
                outs[nome_out] = var
            arglist = ", ".join(f"{k} => :{k}" for k in binds)
            cur.execute(f"BEGIN {nome}({arglist}); END;", binds)
            self._conn.commit()
            return {k: v.getvalue() for k, v in outs.items()}
        finally:
            cur.close()

    def inserir_oferta(self, linha):
        """
        Insere uma linha (o mesmo dict de monitor._montar_linha, chaves = colunas
        do CSV) via a SP. Retorna True se a SP devolveu 'TRUE'. Best-effort:
        qualquer falha e logada e retorna False (nunca propaga).
        """
        self.sem_conexao = False
        if not self.habilitado:
            return False
        try:
            params = {
                "P_DS_TIPO_ORIGEM": _texto(linha.get("DS_TIPO_ORIGEM"), "DS_TIPO_ORIGEM"),
                "P_DS_ORIGEM": _texto(linha.get("DS_ORIGEM"), "DS_ORIGEM"),
                "P_DS_TIPO_OFERTA": _texto(linha.get("DS_TIPO_OFERTA"), "DS_TIPO_OFERTA"),
                "P_ID_OFERTA": int(linha["ID_OFERTA"]),
                "P_DT_CAPTACAO": _data_para_dt(linha.get("DT_CAPTACAO")),
                "P_DT_OFERTA": _data_para_dt(linha.get("DT_OFERTA")),
                "P_DS_OFERTA": _texto(linha.get("DS_OFERTA"), "DS_OFERTA"),
                # Caminho de arquivo: nao passa pelo _texto (nao tem emoji e
                # cortar bytes aqui quebraria o caminho).
                "P_DS_IMAGEM_OFERTA": _imagem_relativa(linha.get("DS_IMAGEM_OFERTA")) or None,
                "P_DS_OFERTA_AVISO": _texto(linha.get("DS_OFERTA_AVISO"), "DS_OFERTA_AVISO"),
                "P_VL_PRECO_DE": _preco_para_numero(linha.get("VL_PRECO_DE")),
                "P_VL_PRECO_POR": _preco_para_numero(linha.get("VL_PRECO_POR")),
                "P_DS_DESCRICAO_PAGAMENTO": _texto(linha.get("DS_DESCRICAO_PAGAMENTO"),
                                                   "DS_DESCRICAO_PAGAMENTO"),
                # URL tambem fica fora: emoji nao aparece e o corte estragaria o link.
                "P_DS_URL_ORIGEM": linha.get("DS_URL_ORIGEM") or None,
                "P_DS_MSG_FINAL": _texto(linha.get("DS_MSG_FINAL"), "DS_MSG_FINAL"),
                "P_DS_CUPOM": _cupom(linha.get("DS_CUPOM"), linha.get("ID_OFERTA")),
                "P_DS_CUPOM_COMENTARIO": _texto(linha.get("DS_CUPOM_COMENTARIO"),
                                                "DS_CUPOM_COMENTARIO"),
                "P_DS_CUPOM_LOJA": _texto(linha.get("DS_CUPOM_LOJA"), "DS_CUPOM_LOJA"),
            }
            if self._sp_tem_ds_loja:
                params["P_DS_LOJA"] = _texto(linha.get("DS_LOJA"), "DS_LOJA")
            out = self.executar_stored_procedure(
                NOME_SP, params,
                {"PV_RETORNO": oracledb.DB_TYPE_VARCHAR,
                 "PV_ERRO": oracledb.DB_TYPE_VARCHAR},
            )
            ok = (out.get("PV_RETORNO") or "").upper() == "TRUE"
            if not ok:
                print(f"[oracle] SP retornou FALSE (ID {linha.get('ID_OFERTA')}): "
                      f"{out.get('PV_ERRO')}")
            return ok
        except Exception as e:  # noqa: BLE001
            self.sem_conexao = _erro_conexao(e)
            print(f"[oracle] Erro ao inserir ID {linha.get('ID_OFERTA')}: {e}")
            try:
                self._conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return False
