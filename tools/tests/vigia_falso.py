"""Mundo falso do vigia (BSV-57): relogio, systemctl, cgroup, /proc, logs, batimentos e Telegram.
Tudo em diretorio temporario; nada real e reiniciado nem enviado."""
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

VPS = Path(__file__).resolve().parent.parent / "vps"
if str(VPS) not in sys.path:
    sys.path.insert(0, str(VPS))

import vigia_robos as v

T0 = datetime(2026, 11, 10, 15, 0, 0, tzinfo=UTC)
TOKEN = "123456789:AAFakeTokenParaTesteNaoEReal_abcdefghij"
CHAT = "-1001234567890"

CG = {"lojas": "/user.slice/app.slice/besave-lojas-robo.scope", "whatsapp": "/user.slice/app.slice/besave-whatsapp-robo.scope"}
SCOPE = {"lojas": "besave-lojas-robo.scope", "whatsapp": "besave-whatsapp-robo.scope"}
UNIDADE = {"lojas": "besave-captura-lojas.service", "whatsapp": "besave-captura-whatsapp.service"}
REINICIO = "besave-reinicio-whatsapp.service"
PID = {"lojas": 200, "whatsapp": 100}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class Mundo:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.tools = raiz / "tools"
        self.t = T0
        self.cmds: list[list[str]] = []
        self.enviados: list[str] = []
        self.estados = {UNIDADE["lojas"]: "active", UNIDADE["whatsapp"]: "active", REINICIO: "inactive"}
        self.inicio_scope = {}               # nome -> instante de ativacao do scope/unidade
        self.restart_rc = 0
        self.cgroup = raiz / "cgroup"
        self.proc = raiz / "proc"
        for robo in ("lojas", "whatsapp"):
            self.scope_pids(robo, {PID[robo]})
            self.inicio_scope[SCOPE[robo]] = T0 - timedelta(hours=5)
            self.inicio_scope[UNIDADE[robo]] = T0 - timedelta(hours=5)
        (self.tools / "capture-store-pages" / "conf").mkdir(parents=True)
        (self.tools / "capture-store-pages" / "destino" / "log").mkdir(parents=True)
        (self.tools / "capture-chat-groups" / "conf").mkdir(parents=True)
        (self.tools / "capture-chat-groups" / "log").mkdir(parents=True)
        self.amb = v.Ambiente(
            robos=v.robos_padrao(self.tools), estado_path=raiz / "estado" / "vigia_robos.json",
            agora=lambda: self.t, rodar=self.rodar, enviar=self.enviados.append,
            cgroup_raiz=self.cgroup, proc_raiz=self.proc, tz=UTC,
        )
        for robo in ("lojas", "whatsapp"):                  # por padrao os dois robos estao bem
            self.bater(robo, em=T0 - timedelta(minutes=1))

    # --- relogio e execucao -----------------------------------------------------------------------
    def andar(self, **k):
        self.t += timedelta(**k)

    def so(self, robo):
        """Deixa so `robo` sendo vigiado: a unidade do outro fica parada de proposito."""
        outro = "whatsapp" if robo == "lojas" else "lojas"
        self.estados[UNIDADE[outro]] = "inactive"

    def rodar_vigia(self):
        return v.executar(self.amb)

    # --- systemctl falso --------------------------------------------------------------------------
    def rodar(self, cmd):
        self.cmds.append(list(cmd))
        assert cmd[:2] == ["systemctl", "--user"], cmd
        args = cmd[2:]
        if args[0] == "is-active":
            est = self.estados.get(args[1], "unknown")
            return (0 if est == "active" else 3), est + "\n"
        if args[0] == "restart":
            return self.restart_rc, ""
        if args[0] == "show":
            nome = args[-1]
            if "ControlGroup" in args:
                for robo, scope in SCOPE.items():
                    if nome == scope:
                        return 0, CG[robo] + "\n"
                return 0, "\n"
            if "ActiveEnterTimestamp" in args:
                dt = self.inicio_scope.get(nome)
                assert "--timestamp=unix" in args
                return 0, (f"@{int(dt.timestamp())}\n" if dt else "\n")
            if "MemoryCurrent" in args:
                return 0, "1073741824\n"
        raise AssertionError(f"comando inesperado: {cmd}")

    def restarts(self):
        return [c for c in self.cmds if c[2] == "restart"]

    # --- processos --------------------------------------------------------------------------------
    def scope_pids(self, robo, pids):
        pasta = self.cgroup / CG[robo].lstrip("/")
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "cgroup.procs").write_text("".join(f"{p}\n" for p in sorted(pids)), encoding="utf-8")

    def processo(self, pid, comm, rss_kb):
        d = self.proc / str(pid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "comm").write_text(comm + "\n", encoding="utf-8")
        (d / "status").write_text(f"Name:\t{comm}\nVmRSS:\t{rss_kb} kB\n", encoding="utf-8")

    # --- batimento e logs -------------------------------------------------------------------------
    def pasta(self, robo):
        return self.tools / ("capture-store-pages" if robo == "lojas" else "capture-chat-groups")

    def bater(self, robo, em, prazo=None, pid=None, fase="rodizio", grupos=None):
        prazo = prazo if prazo is not None else em + timedelta(minutes=10)
        d = {"robo": robo, "pid": pid if pid is not None else PID[robo], "em": iso(em), "prazo": iso(prazo),
             "fase": fase}
        if grupos:
            d["grupos_falhando"] = {k: iso(x) for k, x in grupos.items()}
        (self.pasta(robo) / "conf" / "batimento.json").write_text(json.dumps(d), encoding="utf-8")

    def log_lojas(self, texto):
        p = self.tools / "capture-store-pages" / "destino" / "log" / "main_monitorar.log"
        p.write_text(texto, encoding="utf-8")
        return p

    def log_whatsapp(self, quando: datetime, texto="", sufixo=""):
        nome = f"run_captura_{quando:%d_%m_%H%M%S}{sufixo}.log"
        p = self.tools / "capture-chat-groups" / "log" / nome
        p.write_text(texto, encoding="utf-8")
        import os
        os.utime(p, (quando.timestamp(), quando.timestamp()))
        return p

    def estado(self):
        return json.loads(self.amb.estado_path.read_text(encoding="utf-8"))
