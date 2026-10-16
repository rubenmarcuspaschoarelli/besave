"""
Validade das ofertas (regra do usuario, 2026-10-13): oferta com DT_OFERTA
(data da mensagem original) mais antiga que N dias sai do site sozinha --
OFERTA.ST_ATIVO = 0 + DT_DESATIVACAO. N = conf/config.json ->
"ofertas.validade_dias" (padrao 45; 0 desliga, ver core/estado.py).

  * desativar_vencidas: varredura do main.py (a cada ciclo do --monitorar e
    no fim de uma execucao normal);
  * vencida: checada em core/ofertas.publicar_oferta, para nenhum backfill
    republicar (e reativar) uma oferta vencida.
A fila (OFERTA_FILA_CAPTURA) nao muda -- a captura em si foi ok.
"""

from datetime import datetime, timedelta

from core import estado

MOTIVO = 'vencida'


def vencida(dt_oferta, dias=None, agora=None):
    """A oferta ja passou da validade? Sem data -> nao (na duvida, publica)."""
    dias = estado.ler_validade_ofertas() if dias is None else dias
    if not dias or dt_oferta is None:
        return False
    return dt_oferta < (agora or datetime.now()) - timedelta(days=dias)


def desativar_vencidas(db, dias=None):
    """Desativa as ofertas ativas vencidas. Devolve quantas."""
    dias = estado.ler_validade_ofertas() if dias is None else dias
    if not dias:
        return 0
    cur = db._conn.cursor()
    try:
        cur.execute("UPDATE OFERTA SET ST_ATIVO = 0, DT_DESATIVACAO = SYSDATE "
                    " WHERE ST_ATIVO = 1 AND DT_OFERTA < SYSDATE - :dias", dias=int(dias))
        n = cur.rowcount
        db._conn.commit()
        return n
    except Exception:
        db._conn.rollback()
        raise
    finally:
        cur.close()
