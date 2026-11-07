"""BSV-58 TUN/DOC: tunel residencial no PC (ssh falso) e documentacao.

Destino e chave de teste sao ficticios (203.0.113.0/24 e reservado para documentacao).
"""
import json
import re
import shutil
import subprocess

import pytest
from conftest import TOOLS

SCRIPT = TOOLS / "vps" / "tunel_residencial.ps1"
DESTINO = "ubuntu@203.0.113.9"
SHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.fixture
def tunel(tmp_path):
    if not SHELL:
        pytest.skip("sem PowerShell")
    chave = str(tmp_path / "chaves" / "id_teste")
    chamadas = tmp_path / "chamadas.txt"
    falso = tmp_path / "ssh_falso.ps1"
    falso.write_text(
        f"Add-Content -LiteralPath '{chamadas}' -Value (($args -join '|') + '#')\nexit 255\n", encoding="utf-8")
    log = tmp_path / "tunel.log"

    def rodar(*extra, env=None):
        cmd = [SHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
               "-Log", str(log), "-Ssh", str(falso), *extra]
        r = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120, env=env)
        feitas = chamadas.read_text(encoding="utf-8-sig").split("#")[:-1] if chamadas.exists() else []
        texto = log.read_text(encoding="utf-8-sig") if log.exists() else ""
        return r, [c.strip().split("|") for c in feitas], texto, chave

    return rodar, chave


def esperado(chave, destino=DESTINO, porta="1080"):
    return ["-i", chave, "-N", "-o", "ServerAliveInterval=30", "-o", "ExitOnForwardFailure=yes",
            "-o", "BatchMode=yes", "-R", f"127.0.0.1:{porta}", destino]


def test_tun01_reconecta_com_o_comando_inteiro_e_log_sem_destino_nem_chave(tunel):
    rodar, chave = tunel
    r, chamadas, log, _ = rodar("-Destino", DESTINO, "-Chave", chave, "-EsperaSegundos", "0", "-MaxTentativas", "3")
    assert r.returncode == 0, r.stderr
    assert chamadas == [esperado(chave)] * 3
    assert log.count("tunel caiu (codigo 255)") == 3
    for segredo in ("203.0.113.9", "ubuntu@", "id_teste", "chaves"):
        assert segredo not in log and segredo not in r.stdout


def test_tun01_espera_padrao_de_30_s(tunel):
    rodar, chave = tunel
    _, chamadas, log, _ = rodar("-Destino", DESTINO, "-Chave", chave, "-MaxTentativas", "1")
    assert len(chamadas) == 1 and "nova tentativa em 30 s" in log


def test_tun01_destino_e_chave_pelo_ambiente(tunel):
    import os
    rodar, chave = tunel
    env = {**os.environ, "BESAVE_TUNEL_DESTINO": DESTINO, "BESAVE_TUNEL_CHAVE": chave}
    _, chamadas, _, _ = rodar("-EsperaSegundos", "0", "-MaxTentativas", "1", env=env)
    assert chamadas == [esperado(chave)]


def test_tun01_sem_destino_sai_com_erro_sem_chamar_o_ssh(tunel):
    import os
    rodar, chave = tunel
    env = {k: v for k, v in os.environ.items() if not k.startswith("BESAVE_TUNEL_")}
    r, chamadas, log, _ = rodar("-Chave", chave, "-MaxTentativas", "1", env=env)
    assert r.returncode == 2 and chamadas == [] and "ERRO" in log


def test_tun01_nada_de_ip_ou_chave_no_repositorio():
    for arq in (SCRIPT, TOOLS / "vps" / "README.md", TOOLS / "capture-store-pages" / "conf" / "config.example.json"):
        texto = arq.read_text(encoding="utf-8")
        # "Chrome/130.0.0.0" e versao, nao IP
        ips = set(re.findall(r"(?<![\w/.])\d{1,3}(?:\.\d{1,3}){3}\b", texto)) - {"127.0.0.1"}
        assert ips == set(), (arq.name, ips)
        assert "PRIVATE KEY" not in texto


def test_doc01_readme_e_config_de_exemplo():
    leia = (TOOLS / "vps" / "README.md").read_text(encoding="utf-8")
    for termo in ("tunel_residencial.ps1", "127.0.0.1", "PC desligado", "redirecionamento_indisponivel",
                  "redirecionamento.dominios", "BESAVE_TUNEL_DESTINO", "BESAVE_TUNEL_CHAVE",
                  "Register-ScheduledTask", "-AtLogOn", "Stop-ScheduledTask", "Disable-ScheduledTask",
                  "túnel residencial fora?", "bloqueado pelo Cloudflare"):
        assert termo in leia, termo
    exemplo = json.loads((TOOLS / "capture-store-pages" / "conf" / "config.example.json").read_text(encoding="utf-8"))
    bloco = exemplo["redirecionamento"]
    assert bloco["proxy"] == "socks5h://127.0.0.1:1080" and bloco["dominios"] == ["promos.link"]
    assert bloco["timeout_segundos"] == 20 and bloco["max_saltos"] == 5 and bloco["_obs"]
