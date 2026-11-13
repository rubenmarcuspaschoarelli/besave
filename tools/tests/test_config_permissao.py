"""BSV-60: gravar o controle no config.json mantem a permissao do arquivo (senha do Oracle e
app_secret da Shopee) e continua atomico (.tmp + fsync + os.replace)."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest
from core import estado

so_posix = pytest.mark.skipif(sys.platform == "win32", reason="modo POSIX nao existe no Windows")


@pytest.fixture
def umask_002():
    antiga = os.umask(0o002)
    yield
    os.umask(antiga)


def _config(tmp_path, modo=None):
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps({"db": {"senha": "s"}, "controle": {"ultimo_id_processado": 1}}),
                       encoding="utf-8")
    if modo is not None:
        os.chmod(caminho, modo)
    return str(caminho)


def _modo(caminho):
    return stat.S_IMODE(os.stat(caminho).st_mode)


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def modos_no_replace(monkeypatch):
    """Modo do .tmp no instante do os.replace (a janela em que o conteudo novo existe)."""
    vistos = []
    original = os.replace

    def espiao(origem, destino):
        vistos.append(_modo(origem))
        return original(origem, destino)

    monkeypatch.setattr(estado.os, "replace", espiao)
    return vistos


@so_posix
def test_mantem_600_com_umask_002(tmp_path, umask_002):
    caminho = _config(tmp_path, 0o600)
    estado.gravar_ultimo_id(42, caminho)
    assert _modo(caminho) == 0o600
    cfg = _ler(caminho)
    assert cfg["controle"]["ultimo_id_processado"] == 42
    assert cfg["db"]["senha"] == "s"


@so_posix
def test_mantem_640(tmp_path, umask_002):
    caminho = _config(tmp_path, 0o640)
    estado.gravar_publicacao_pendente([7, 3], caminho)
    assert _modo(caminho) == 0o640
    assert _ler(caminho)["controle"]["publicacao_pendente"] == [3, 7]


@so_posix
@pytest.mark.parametrize("original", [0o600, 0o640, 0o400])
def test_tmp_nunca_mais_aberto_que_o_original(tmp_path, umask_002, modos_no_replace, monkeypatch, original):
    caminho = _config(tmp_path, original)
    criados = []
    abrir = os.open

    def espiao_open(path, flags, mode=0o777, *a, **k):
        fd = abrir(path, flags, mode, *a, **k)
        if str(path).endswith(".tmp"):
            criados.append(stat.S_IMODE(os.fstat(fd).st_mode))
        return fd

    monkeypatch.setattr(estado.os, "open", espiao_open)
    estado.gravar_ultimo_id(5, caminho)
    monkeypatch.undo()
    assert criados == [0o600]                      # nasce restrito, nao com a umask
    assert modos_no_replace == [original]          # e chega ao replace com o modo do original
    assert all(m & ~original & 0o077 == 0 for m in criados + modos_no_replace)


@so_posix
def test_tmp_velho_aberto_nao_vaza(tmp_path, umask_002, modos_no_replace):
    caminho = _config(tmp_path, 0o600)
    velho = caminho + ".tmp"
    with open(velho, "w") as f:
        f.write("sobra de execucao interrompida")
    os.chmod(velho, 0o666)
    estado.gravar_ultimo_id(9, caminho)
    assert modos_no_replace == [0o600]
    assert _modo(caminho) == 0o600
    assert _ler(caminho)["controle"]["ultimo_id_processado"] == 9


@so_posix
def test_original_sumiu_ao_obter_modo_usa_600(tmp_path, umask_002, monkeypatch, modos_no_replace):
    caminho = _config(tmp_path, 0o644)
    stat_real = os.stat

    def stat_sem_config(path, *a, **k):
        if str(path) == caminho:
            raise FileNotFoundError(path)
        return stat_real(path, *a, **k)

    monkeypatch.setattr(estado.os, "stat", stat_sem_config)
    estado.gravar_ultimo_id(11, caminho)
    monkeypatch.setattr(estado.os, "stat", stat_real)
    assert modos_no_replace == [0o600]
    assert _modo(caminho) == 0o600


def test_falha_na_escrita_deixa_original_intacto(tmp_path, monkeypatch):
    caminho = _config(tmp_path, None if sys.platform == "win32" else 0o600)
    antes = Path(caminho).read_text(encoding="utf-8")

    def dump_quebrado(obj, f, **k):
        f.write('{"pela met')
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(estado.json, "dump", dump_quebrado)
    estado.gravar_ultimo_id(99, caminho)
    assert Path(caminho).read_text(encoding="utf-8") == antes
    assert not os.path.exists(caminho + ".tmp")
    if sys.platform != "win32":
        assert _modo(caminho) == 0o600


def test_grava_em_qualquer_plataforma(tmp_path):
    """No Windows nao ha chmod de modo; a gravacao segue funcionando e atomica."""
    caminho = _config(tmp_path)
    estado.gravar_ultimo_id(3, caminho)
    estado.gravar_ultimo_id(4, caminho)
    assert _ler(caminho)["controle"]["ultimo_id_processado"] == 4
    assert not os.path.exists(caminho + ".tmp")
    assert os.access(caminho, os.W_OK)
