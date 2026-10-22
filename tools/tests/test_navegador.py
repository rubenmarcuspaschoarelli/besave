"""NAV-01..03: argumentos do navegador do capture-store-pages."""
import json
from pathlib import Path

from core import browser

LOJAS = Path(__file__).resolve().parent.parent / "capture-store-pages"

FLAG = "--disable-blink-features=AutomationControlled"
IGNORADOS = ["--disable-gpu", "--enable-unsafe-swiftshader"]


def _esperado(channel, args):
    kw = {"headless": False, "no_viewport": True, "args": args, "ignore_default_args": IGNORADOS}
    if channel:
        kw["channel"] = channel
    return kw


def test_nav01_chrome_explicito():
    assert browser.montar_kwargs("chrome") == _esperado("chrome", [FLAG, "--profile-directory=Default"])


def test_nav01_sem_chave_e_chrome(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    assert browser.ler_canal(str(cfg)) == "chrome"
    cfg.write_text('{"navegador": {}}', encoding="utf-8")
    assert browser.ler_canal(str(cfg)) == "chrome"


def test_nav02_canal_vazio_e_chromium():
    assert browser.montar_kwargs("") == _esperado("", [FLAG])


def test_nav02_canal_vazio_no_config(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"navegador": {"canal": ""}}), encoding="utf-8")
    assert browser.ler_canal(str(cfg)) == ""


def test_canal_invalido_cai_em_chrome(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"navegador": {"canal": null}}', encoding="utf-8")
    assert browser.ler_canal(str(cfg)) == "chrome"


def test_launch_persistent_passa_perfil_e_kwargs(monkeypatch):
    chamadas = []

    class Chromium:
        def launch_persistent_context(self, perfil, **kw):
            chamadas.append((perfil, kw))
            return "ctx"

    class P:
        chromium = Chromium()

    monkeypatch.setattr(browser, "ler_canal", lambda *a, **k: "")
    assert browser.launch_persistent(P(), headless=False) == "ctx"
    assert chamadas == [(browser.PERFIL_DIR, _esperado("", [FLAG]))]


def test_nav03_exemplo_documenta_a_chave():
    exemplo = json.loads((LOJAS / "conf" / "config.example.json").read_text(encoding="utf-8"))
    assert exemplo["navegador"]["canal"] == "chrome"


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def test_ua01_sem_user_agent_os_argumentos_nao_mudam():
    assert browser.montar_kwargs("chrome") == browser.montar_kwargs("chrome", user_agent=None)
    assert "user_agent" not in browser.montar_kwargs("")
    assert "user_agent" not in browser.montar_kwargs("", user_agent="")


def test_ua02_com_user_agent_entra_nos_kwargs_e_o_resto_fica():
    esperado = {**_esperado("", [FLAG]), "user_agent": UA}
    assert browser.montar_kwargs("", user_agent=UA) == esperado
    esperado = {**_esperado("chrome", [FLAG, "--profile-directory=Default"]), "user_agent": UA}
    assert browser.montar_kwargs("chrome", user_agent=UA) == esperado


def test_ua03_ler_user_agent_do_config(tmp_path):
    cfg = tmp_path / "config.json"
    assert browser.ler_user_agent(str(cfg)) is None  # arquivo ausente
    for ruim in ('{}', '{"navegador": {}}', '{"navegador": {"user_agent": ""}}',
                 '{"navegador": {"user_agent": "  "}}', '{"navegador": {"user_agent": 5}}'):
        cfg.write_text(ruim, encoding="utf-8")
        assert browser.ler_user_agent(str(cfg)) is None
    cfg.write_text(json.dumps({"navegador": {"user_agent": f"  {UA} "}}), encoding="utf-8")
    assert browser.ler_user_agent(str(cfg)) == UA


def test_ua04_launch_persistent_usa_o_user_agent_do_config(monkeypatch):
    chamadas = []

    class Chromium:
        def launch_persistent_context(self, perfil, **kw):
            chamadas.append(kw)
            return "ctx"

    class P:
        chromium = Chromium()

    monkeypatch.setattr(browser, "ler_canal", lambda *a, **k: "")
    monkeypatch.setattr(browser, "ler_user_agent", lambda *a, **k: UA)
    browser.launch_persistent(P())
    assert chamadas[0]["user_agent"] == UA


def test_ua05_logins_manuais_passam_pelo_launch_persistent():
    ajuste = LOJAS / "programas_ajuste"
    for nome in ("ml_login.py", "shopee_login.py"):
        fonte = (ajuste / nome).read_text(encoding="utf-8")
        assert "launch_persistent(" in fonte and "launch_persistent_context" not in fonte


def test_ua06_exemplo_documenta_a_chave():
    exemplo = json.loads((LOJAS / "conf" / "config.example.json").read_text(encoding="utf-8"))
    assert exemplo["navegador"]["user_agent"] == ""
