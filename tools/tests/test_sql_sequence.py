"""BSV-56 SQL-01..03: o SQL da sequence e da trigger (conferido lendo o arquivo; quem aplica e o dono)."""
import re
from pathlib import Path

SQL = (Path(__file__).resolve().parent.parent / "capture-chat-groups" / "sql"
       / "BSV-56_sequence_id_oferta.sql").read_text(encoding="utf-8")
# so o que executa: linhas de comentario fora (a reversao e comentada de proposito)
CODIGO = "\n".join(linha for linha in SQL.splitlines() if not linha.lstrip().startswith("--"))
UNICO = re.sub(r"\s+", " ", CODIGO).upper()


def _bloco_da_sequence():
    i = UNICO.index("DECLARE")
    return UNICO[i:UNICO.index("END;", i)]


def test_sql01_start_with_pelo_maior_das_duas_tabelas():
    bloco = _bloco_da_sequence()
    assert re.search(r"GREATEST\( NVL\(\(SELECT MAX\(ID_OFERTA\) FROM OFERTA_FILA_CAPTURA\), 0\), "
                     r"NVL\(\(SELECT MAX\(ID_OFERTA\) FROM OFERTA\), 0\) \) \+ 1 INTO V_INICIO", bloco)
    assert "EXECUTE IMMEDIATE 'CREATE SEQUENCE SQ_OFERTA_FILA START WITH ' || TO_CHAR(V_INICIO)" in bloco


def test_sql01_incremento_um_e_nocache():
    bloco = _bloco_da_sequence()
    assert "' INCREMENT BY 1 NOCACHE NOCYCLE'" in bloco
    assert re.search(r"\bCACHE \d", UNICO) is None


def test_sql02_trigger_so_com_id_nulo():
    m = re.search(r"CREATE OR REPLACE TRIGGER TRG_OFERTA_FILA_ID (.*?) END;", UNICO)
    assert m, "trigger ausente"
    corpo = m.group(1)
    assert corpo.startswith("BEFORE INSERT ON OFERTA_FILA_CAPTURA FOR EACH ROW WHEN (NEW.ID_OFERTA IS NULL) BEGIN")
    assert ":NEW.ID_OFERTA := SQ_OFERTA_FILA.NEXTVAL;" in corpo
    assert corpo.count("WHEN") == 1


def test_sql03_conferencia_falha_se_sequence_nao_passa_o_maior():
    assert "SELECT LAST_NUMBER INTO V_PROXIMO FROM USER_SEQUENCES WHERE SEQUENCE_NAME = 'SQ_OFERTA_FILA'" in UNICO
    assert "IF V_PROXIMO > V_MAIOR AND V_STATUS = 'ENABLED' THEN" in UNICO
    assert "RAISE_APPLICATION_ERROR" in UNICO


def test_sql03_reversao_presente_e_comentada():
    comentadas = [linha.strip() for linha in SQL.splitlines() if linha.lstrip().startswith("--")]
    assert "-- DROP TRIGGER TRG_OFERTA_FILA_ID;" in comentadas
    assert "-- DROP SEQUENCE SQ_OFERTA_FILA;" in comentadas
    assert "DROP " not in UNICO  # nada de DROP executavel


def test_sql_sp_nao_muda():
    assert "STP_OFERTA_FILA_CAPTURA_INSERT" not in UNICO
