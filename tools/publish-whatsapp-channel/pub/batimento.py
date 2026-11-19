"""Batimento do publicador para o vigia externo (formato da BSV-57).

Copia reduzida de capture-chat-groups/wa/batimento.py. Grava por temporario + rename; so depois de uma
volta concluida (progresso). `prazo` = agora + sono + 10 min. BESAVE_BATIMENTO troca o caminho (testes).

    {"robo":"publicador","pid":1,"em":"...Z","prazo":"...Z","fase":"volta"}
"""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROBO = "publicador"
PRAZO = timedelta(minutes=10)
CAMINHO = Path(__file__).resolve().parent.parent / "conf" / "batimento.json"


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Batimento:
    def __init__(self, caminho=None, pid=None, log=print):
        self.caminho = Path(caminho or os.environ.get("BESAVE_BATIMENTO") or CAMINHO)
        self.pid = pid if pid is not None else os.getpid()
        self._log = log

    def bater(self, agora: datetime, fase: str, dorme_s: float = 0) -> bool:
        dados = {"robo": ROBO, "pid": self.pid, "em": _iso(agora),
                 "prazo": _iso(agora + timedelta(seconds=max(0.0, dorme_s)) + PRAZO), "fase": fase}
        tmp = self.caminho.with_name(f"{self.caminho.name}.{os.getpid()}.tmp")
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(dados, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.caminho)
            return True
        except OSError as e:
            self._log(f"[batimento] falha ao gravar ({type(e).__name__}); o publicador segue.")
            try:
                tmp.unlink()
            except OSError:
                pass
            return False
