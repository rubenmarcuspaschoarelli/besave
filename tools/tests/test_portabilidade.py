"""POR-01..05: caminhos e processos sem padrao de Windows no Linux."""
import json
import re
import subprocess
from pathlib import Path

import pytest
from core import estado, processos
from wa import storage

TOOLS = Path(__file__).resolve().parent.parent
WIN_S3 = r"E:\Work\besave\server\s3"
WIN_IMG = r"E:\Work\besave\server\s3\ofertas\img"


def _cfg(tmp_path, dados):
    c = tmp_path / "config.json"
    c.write_text(json.dumps(dados), encoding="utf-8")
    return str(c)


def test_por01_linux_sem_s3_raiz_cita_a_chave(tmp_path):
    with pytest.raises(estado.ConfigFaltando, match=r"s3\.raiz"):
        estado.ler_raiz_s3(_cfg(tmp_path, {}), plataforma="linux")
    with pytest.raises(estado.ConfigFaltando, match=r"s3\.raiz"):
        estado.ler_raiz_s3(_cfg(tmp_path, {"s3": {"raiz": "  "}}), plataforma="linux")


def test_por01_linux_com_chave_usa_o_valor(tmp_path):
    assert estado.ler_raiz_s3(_cfg(tmp_path, {"s3": {"raiz": "/srv/s3"}}), plataforma="linux") == "/srv/s3"


def test_por02_linux_sem_destino_cita_a_chave():
    with pytest.raises(storage.ConfigFaltando, match=r"publicacao_s3\.destino"):
        storage.destino_s3({}, plataforma="linux")


def test_por02_linux_com_destino():
    assert storage.destino_s3({"destino": "/srv/s3/ofertas/img"}, plataforma="linux") == Path("/srv/s3/ofertas/img")


def test_por03_windows_mantem_os_padroes(tmp_path):
    assert estado.ler_raiz_s3(_cfg(tmp_path, {}), plataforma="win32") == WIN_S3
    assert storage.destino_s3({}, plataforma="win32") == Path(WIN_IMG)


def test_por04_fora_do_windows_nao_chama_tasklist_nem_taskkill(monkeypatch):
    def proibido(*a, **k):
        raise AssertionError("subprocess chamado fora do Windows")

    monkeypatch.setattr(subprocess, "run", proibido)
    assert processos.chrome_aberto(plataforma="linux") is False
    processos.fechar_chrome_forcado(plataforma="linux")


def test_por04_windows_usa_tasklist_e_taskkill(monkeypatch):
    chamadas = []

    def falso(cmd, **k):
        chamadas.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="chrome.exe 123", stderr="")

    monkeypatch.setattr(subprocess, "run", falso)
    assert processos.chrome_aberto(plataforma="win32") is True
    processos.fechar_chrome_forcado(plataforma="win32")
    assert chamadas == [
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
        ["taskkill", "/IM", "chrome.exe", "/F"],
    ]


def test_por05_producao_sem_comandos_de_windows():
    lojas, chat = TOOLS / "capture-store-pages", TOOLS / "capture-chat-groups"
    arquivos = [lojas / "main.py", chat / "run_captura.py"]
    arquivos += list((lojas / "core").glob("*.py")) + list((lojas / "stores").glob("*.py"))
    arquivos += list((chat / "wa").glob("*.py")) + [chat / "main.py"]
    padrao = re.compile(r"tasklist|taskkill|\w\.exe\b")
    achados = []
    for arq in arquivos:
        if arq.name == "processos.py" or not arq.exists():
            continue
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            codigo = linha.split("#", 1)[0]
            if padrao.search(codigo):
                achados.append(f"{arq.name}:{n}")
    assert achados == []


def test_por02_partida_falha_no_linux_sem_destino(monkeypatch):
    monkeypatch.setattr(storage, "_cfg_s3", dict)
    monkeypatch.setattr(storage.sys, "platform", "linux")
    with pytest.raises(storage.ConfigFaltando, match=r"publicacao_s3\.destino"):
        storage.validar_destino_s3()
    monkeypatch.setattr(storage, "_cfg_s3", lambda: {"ativo": False})
    storage.validar_destino_s3()  # publicacao desligada: nada a exigir
