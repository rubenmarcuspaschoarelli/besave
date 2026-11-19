"""
Batimento do robo do WhatsApp para o vigia externo (BSV-57).

Grava conf/batimento.json por arquivo temporario + rename (o vigia nunca le o arquivo pela
metade). So stdlib. O robo so bate quando HOUVE PROGRESSO: volta em que todos os grupos
falharam nao renova (07/11: o python girou 8,5 h so com erro e um batimento "a cada volta"
teria ficado em dia). Falha de escrita so loga: o batimento nao pode atrasar a captura.

    {"robo":"whatsapp","pid":1,"em":"...Z","prazo":"...Z","fase":"rodizio","grupos_falhando":{"g":"...Z"}}

`prazo` = (agora + tempo de sono) + 10 min. BESAVE_BATIMENTO troca o caminho (testes). Copia de capture-store-pages/core/batimento.py:
os dois robos nao compartilham pacote.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROBO = "whatsapp"
PRAZO = timedelta(minutes=10)
CAMINHO = Path(__file__).resolve().parent.parent / "conf" / "batimento.json"


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gravar_atomico(caminho, dados: dict) -> bool:
    """Escreve `dados` em `caminho` sem nunca deixar o arquivo pela metade. Falha so loga."""
    tmp = None
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = caminho.with_name(f"{caminho.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, caminho)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[batimento] Falha ao gravar o batimento ({type(e).__name__}); a captura segue.")
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


class Batimento:
    def __init__(self, caminho=None, relogio=None, pid=None):
        self.caminho = Path(caminho or os.environ.get("BESAVE_BATIMENTO") or CAMINHO)
        self.relogio = relogio
        self.pid = pid if pid is not None else os.getpid()
        self.grupos_falhando: dict[str, str] = {}

    def _agora(self) -> datetime:
        return (self.relogio or agora_utc)()

    def bater(self, fase: str, dorme_s: float = 0, agora=None) -> bool:
        """Renova o batimento. `dorme_s` = quanto o robo vai dormir: o prazo vale da hora de acordar."""
        agora = agora or self._agora()
        dados = {
            "robo": ROBO,
            "pid": self.pid,
            "em": _iso(agora),
            "prazo": _iso(agora + timedelta(seconds=max(0, dorme_s)) + PRAZO),
            "fase": fase,
        }
        if self.grupos_falhando:
            dados["grupos_falhando"] = dict(self.grupos_falhando)
        return gravar_atomico(self.caminho, dados)

    def volta(self, resultados: dict, fase: str = "rodizio", agora=None) -> bool:
        """
        Fim de uma volta do rodizio. `resultados`: nome do grupo -> True se abriu.
        Atualiza `grupos_falhando` (desde a 1a falha; sai na primeira volta em que abrir) e so
        renova se ao menos um grupo abriu.
        """
        agora = agora or self._agora()
        for nome, abriu in resultados.items():
            if abriu:
                self.grupos_falhando.pop(nome, None)
            else:
                self.grupos_falhando.setdefault(nome, _iso(agora))
        if not any(resultados.values()):
            return False
        return self.bater(fase, agora=agora)
