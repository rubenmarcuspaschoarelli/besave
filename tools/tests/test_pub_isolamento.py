"""BSV-63 ISO-01, CFG: o publicador nao importa os robos de captura e nao guarda segredo no repositorio."""
import importlib.util
import re
from pathlib import Path

PUB = Path(__file__).resolve().parent.parent / "publish-whatsapp-channel"
FONTES = sorted(p for p in PUB.rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".md", ".txt")
                and ".venv" not in p.parts and "__pycache__" not in p.parts)


def test_iso01_nao_importa_capture():
    assert FONTES
    for p in FONTES:
        if p.suffix == ".py":
            texto = p.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import)\s+(wa|core)\b", texto, re.MULTILINE), p
            assert "sys.path" not in texto, p                   # nada de enxertar a pasta dos robos


def test_iso01_sem_telefone_ip_token_ou_convite():
    for p in FONTES:
        texto = p.read_text(encoding="utf-8")
        assert not re.search(r"\+?55\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}", texto), p
        assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", texto), p
        assert not re.search(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b", texto), p
        assert "chat.whatsapp.com" not in texto and "whatsapp.com/channel" not in texto, p


def test_main_sem_config_sai_com_2(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("main_publicador", PUB / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.config, "CAMINHO", tmp_path / "config.json")
    assert mod.main([]) == 2
