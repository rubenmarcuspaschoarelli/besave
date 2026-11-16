"""BSV-63 VIG-01: o vigia escolhe os robos pela maquina (BESAVE_VIGIA_ROBOS) e vigia o publicador na inst2."""
import json
import os
from datetime import UTC, timedelta

import pytest
from pub.batimento import Batimento
from vigia_falso import T0, iso, v

UNIDADE = "besave-publicador-whatsapp.service"
SCOPE = "besave-publicador-robo.scope"
CG = "/user.slice/app.slice/besave-publicador-robo.scope"
PID = 300


def nomes(robos):
    return [r.nome for r in robos]


def test_vig01_publicador_so_ele(tmp_path):
    robos = v.robos_da_maquina(tmp_path, "publicador")
    assert nomes(robos) == ["publicador"]
    r = robos[0]
    assert (r.unidade, r.scope, r.reinicio) == (UNIDADE, SCOPE, None)
    assert r.pasta == tmp_path / "publish-whatsapp-channel"
    assert r.batimento == tmp_path / "publish-whatsapp-channel" / "conf" / "batimento.json"


@pytest.mark.parametrize("valor", [None, "", "  "])
def test_vig01_ausente_e_lojas_whatsapp_como_hoje(tmp_path, valor):
    assert nomes(v.robos_da_maquina(tmp_path, valor)) == ["lojas", "whatsapp"]
    assert nomes(v.robos_padrao(tmp_path)) == ["lojas", "whatsapp"]


def test_vig01_lista_com_espacos_maiusculas_repetidos_e_desconhecido(tmp_path, capsys):
    assert nomes(v.robos_da_maquina(tmp_path, " Lojas , publicador,lojas, xyz")) == ["lojas", "publicador"]
    assert "xyz" in capsys.readouterr().out
    assert nomes(v.robos_da_maquina(tmp_path, "xyz")) == ["lojas", "whatsapp"]


def test_vig01_ambiente_real_le_a_variavel(tmp_path):
    env = {"BESAVE_TOOLS": str(tmp_path), "BESAVE_VIGIA_ESTADO": str(tmp_path / "e.json"),
           "BESAVE_WORKER_ENV": str(tmp_path / "nao-existe.env")}
    assert nomes(v.ambiente_real(env).robos) == ["lojas", "whatsapp"]
    assert nomes(v.ambiente_real({**env, "BESAVE_VIGIA_ROBOS": "publicador"}).robos) == ["publicador"]


# --- o publicador vigiado ----------------------------------------------------------------------------


class Inst2:
    """Mundo da inst2: so o publicador, systemctl/cgroup falsos."""

    def __init__(self, raiz):
        self.t = T0
        self.cmds = []
        self.enviados = []
        self.pasta = raiz / "tools" / "publish-whatsapp-channel"
        (self.pasta / "conf").mkdir(parents=True)
        (self.pasta / "log").mkdir()
        procs = raiz / "cgroup" / CG.lstrip("/")
        procs.mkdir(parents=True)
        (procs / "cgroup.procs").write_text(f"{PID}\n", encoding="utf-8")
        self.amb = v.Ambiente(robos=v.robos_da_maquina(raiz / "tools", "publicador"),
                              estado_path=raiz / "estado.json", agora=lambda: self.t, rodar=self.rodar,
                              enviar=self.enviados.append, cgroup_raiz=raiz / "cgroup", proc_raiz=raiz / "proc", tz=UTC)

    def rodar(self, cmd):
        self.cmds.append(cmd)
        args = cmd[2:]
        if args[0] == "is-active":
            assert args[1] == UNIDADE, cmd
            return 0, "active\n"
        if args[0] == "restart":
            return 0, ""
        if args[0] == "show":
            if "ControlGroup" in args:
                return 0, (CG + "\n") if args[-1] == SCOPE else "\n"
            if "ActiveEnterTimestamp" in args:
                return 0, f"@{int((T0 - timedelta(hours=5)).timestamp())}\n"
            return 0, "\n"
        raise AssertionError(cmd)

    def bater_publicador(self, em, dorme_s=900):
        """Batimento gravado pelo proprio publicador (pub.batimento)."""
        Batimento(self.pasta / "conf" / "batimento.json", pid=PID, log=lambda s: None).bater(em, "volta", dorme_s)

    def log(self, quando, texto):
        p = self.pasta / "log" / f"run_publicador_{quando:%d_%m_%H%M%S}.log"
        p.write_text(texto, encoding="utf-8")
        os.utime(p, (quando.timestamp(), quando.timestamp()))
        return p

    def restarts(self):
        return [c for c in self.cmds if c[2] == "restart"]


@pytest.fixture
def i2(tmp_path):
    return Inst2(tmp_path)


def test_vig01_batimento_do_publicador_e_lido_pelo_vigia(i2):
    i2.bater_publicador(T0 - timedelta(minutes=5))
    bat = v.ler_batimento(i2.pasta / "conf" / "batimento.json")
    assert bat is not None and bat.pid == PID and bat.prazo == T0 - timedelta(minutes=5) + timedelta(minutes=25)


def test_vig01_publicador_em_dia_nao_age(i2):
    i2.bater_publicador(T0 - timedelta(minutes=5))
    v.executar(i2.amb)
    assert i2.restarts() == [] and i2.enviados == []


def test_vig01_publicador_parado_reinicia_a_unidade_dele(i2):
    i2.bater_publicador(T0 - timedelta(minutes=40))              # prazo = -40 + 15 + 10 = 15 min atras
    i2.log(T0 - timedelta(hours=2), "[16/11 09:00:00] Sessao autenticada\n[volta] fila vazia\n")
    v.executar(i2.amb)
    assert i2.restarts() == [["systemctl", "--user", "restart", UNIDADE]]
    assert len(i2.enviados) == 1 and "publicador parado" in i2.enviados[0]
    assert "[volta] fila vazia" in i2.enviados[0]                 # a ultima linha vem do log do publicador


def test_vig01_publicador_com_qr_avisa_sem_reiniciar(i2):
    i2.bater_publicador(T0 - timedelta(minutes=40))
    i2.log(T0 - timedelta(hours=1), "Aguardando o WhatsApp Web carregar... (se aparecer o QR, ler pelo VNC)\n")
    v.executar(i2.amb)
    assert i2.restarts() == []
    assert len(i2.enviados) == 1 and "QR" in i2.enviados[0]


def test_vig01_rotacao_apaga_logs_velhos_do_publicador(i2):
    velho = i2.log(T0 - timedelta(days=20), "x")
    outro_velho = i2.log(T0 - timedelta(days=19), "y")
    novo = i2.log(T0 - timedelta(days=1), "z")
    i2.bater_publicador(T0 - timedelta(minutes=5))
    v.executar(i2.amb)
    assert not velho.exists() and not outro_velho.exists() and novo.exists()
    estado = json.loads(i2.amb.estado_path.read_text(encoding="utf-8"))
    assert "publicador" in estado["robos"] and iso(T0)
