"""BSV-65 T1: classificacao do navegador quebrado, campos do batimento, diagnostico (/proc simulado),
chave do relancamento preventivo e link de afiliado. Sem Playwright."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from core import batimento, estado, link_afiliado, navegador

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


# --- CLS-01: uma funcao so ------------------------------------------------------------------------------

@pytest.mark.parametrize("mensagem, esperado", [
    ("Page.goto: Page crashed", "Page crashed"),
    ("Error: PAGE CRASHED", "Page crashed"),
    ("Target crashed", "Target crashed"),
    ("Target page, context or browser has been closed", "Has been closed"),
    ("Page.goto: Target closed", "Target closed"),
    ("BrowserContext.new_page: Browser has been closed", "Has been closed"),
])
def test_cls01_sinais_do_navegador_quebrado(mensagem, esperado):
    assert navegador.sinal(RuntimeError(mensagem)) == esperado


@pytest.mark.parametrize("mensagem", ["seletor sumiu", "Page.goto: Timeout 60000ms exceeded",
                                      "net::ERR_NAME_NOT_RESOLVED", ""])
def test_cls01_outros_erros_nao_sao_navegador(mensagem):
    assert navegador.sinal(RuntimeError(mensagem)) is None


def test_cls01_timeout_e_pela_classe():
    assert navegador.e_timeout(TimeoutError("x"))
    assert not navegador.e_timeout(RuntimeError("Timeout 60000ms exceeded"))


# --- CLS-02 / VIG-01: batimento --------------------------------------------------------------------------

@pytest.fixture
def gravados(monkeypatch):
    registro = []
    monkeypatch.setattr(batimento, "agora_utc", lambda: T0)
    monkeypatch.setattr(batimento, "gravar_atomico", lambda caminho, dados: registro.append(dict(dados)) or True)
    monkeypatch.setattr(batimento, "_navegador", {"ultimo_ok": None, "tentativas": 0})
    return registro


def test_cls02_linha_com_page_crashed_nao_renova(gravados):
    assert batimento.bater_linha("erro: Error: Page.goto: Page crashed") is False
    assert gravados == []


def test_cls02_erro_comum_renova(gravados):
    batimento.bater_linha("erro: RuntimeError: seletor sumiu")
    assert len(gravados) == 1


def test_vig01_campos_novos_no_batimento(gravados):
    batimento.bater("varredura")
    assert gravados[0]["ultimo_ok_navegador"] == "2026-11-25T12:00:00Z"
    assert gravados[0]["tentativas_navegador"] == 0
    batimento.registrar_navegador(False)
    batimento.registrar_navegador(False)
    batimento.bater("linha")
    assert gravados[1]["tentativas_navegador"] == 2
    assert gravados[1]["ultimo_ok_navegador"] == "2026-11-25T12:00:00Z"
    batimento.registrar_navegador(True, agora=T0 + timedelta(minutes=7))
    batimento.bater("linha")
    assert gravados[2]["tentativas_navegador"] == 0
    assert gravados[2]["ultimo_ok_navegador"] == "2026-11-25T12:07:00Z"


# --- DIA-01: diagnostico --------------------------------------------------------------------------------

def _processo(proc, pid, nome, ppid, rss_kb):
    d = proc / str(pid)
    d.mkdir(parents=True)
    rss = f"VmRSS:\t{rss_kb} kB\n" if rss_kb is not None else ""
    (d / "status").write_text(f"Name:\t{nome}\nPPid:\t{ppid}\n{rss}", encoding="utf-8")


@pytest.fixture
def proc(tmp_path):
    p = tmp_path / "proc"
    p.mkdir()
    (p / "meminfo").write_text("MemTotal:  8000000 kB\nMemAvailable:  4403200 kB\n", encoding="utf-8")
    _processo(p, 100, "python3", 1, 50000)          # o robo
    _processo(p, 110, "node", 100, 40000)           # driver do Playwright
    _processo(p, 120, "chrome", 110, 300 * 1024)    # chromium principal
    _processo(p, 121, "chrome", 120, 700 * 1024)    # renderer
    _processo(p, 122, "chrome_crashpad", 120, 10 * 1024)
    _processo(p, 130, "chrome", 1, 999 * 1024)      # chrome de outro dono: fora
    (p / "self").mkdir()
    return p


def test_dia01_linha_inteira(proc):
    linha = navegador.diagnostico(95 * 60 + 30, 210, proc=proc, pid=100)
    assert linha == ("[navegador] diagnostico: mem_disponivel=4300 MB | chromium=3 | rss_chromium=1010 MB | "
                     "maior=700 MB | desde_lancamento=95 min | navegacoes=210")


def test_dia01_meminfo_ilegivel_vira_interrogacao(proc):
    (proc / "meminfo").unlink()
    (proc / "meminfo").mkdir()                      # ler um diretorio falha
    linha = navegador.diagnostico(60, 1, proc=proc, pid=100)
    assert linha.startswith("[navegador] diagnostico: mem_disponivel=? | chromium=3 |")


def test_dia01_status_ilegivel_de_um_processo_nao_derruba(proc):
    (proc / "121" / "status").unlink()
    linha = navegador.diagnostico(0, 0, proc=proc, pid=100)
    assert "chromium=2 | rss_chromium=310 MB | maior=300 MB" in linha


def test_dia01_proc_ilegivel_vira_interrogacao(proc, monkeypatch):
    original = type(proc).iterdir

    def falha(self):
        if self == proc:
            raise PermissionError("negado")
        return original(self)
    monkeypatch.setattr(type(proc), "iterdir", falha)
    linha = navegador.diagnostico(0, 0, proc=proc, pid=100)
    assert linha == ("[navegador] diagnostico: mem_disponivel=4300 MB | chromium=? | rss_chromium=? | maior=? | "
                     "desde_lancamento=0 min | navegacoes=0")


def test_dia01_fora_do_linux_so_tempo_e_navegacoes(tmp_path):
    linha = navegador.diagnostico(600, 4, proc=tmp_path / "nao-existe", pid=1)
    assert linha == "[navegador] diagnostico: desde_lancamento=10 min | navegacoes=4"


# --- PRE-01: chave opcional -----------------------------------------------------------------------------

def _cfg(tmp_path, monitor):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"monitor": monitor}), encoding="utf-8")
    return p


def test_pre01_ausente_e_padrao_sem_warn(tmp_path, capsys):
    assert estado.ler_relancar_navegador_horas(_cfg(tmp_path, {"intervalo_minutos": 3})) == 6
    assert "WARN" not in capsys.readouterr().out


@pytest.mark.parametrize("valor, esperado", [(0, 0), (0.1, 0.1), (12, 12)])
def test_pre01_valores_validos(tmp_path, valor, esperado):
    assert estado.ler_relancar_navegador_horas(_cfg(tmp_path, {"relancar_navegador_horas": valor})) == esperado


@pytest.mark.parametrize("valor", ["6", -1, True, None, [6]])
def test_pre01_invalida_e_padrao_com_warn(tmp_path, capsys, valor):
    assert estado.ler_relancar_navegador_horas(_cfg(tmp_path, {"relancar_navegador_horas": valor})) == 6
    assert "[WARN] monitor.relancar_navegador_horas invalido" in capsys.readouterr().out


# --- LIN-01: link de afiliado nao engole navegador quebrado ----------------------------------------------

def test_lin01_link_afiliado_relanca_page_crashed(monkeypatch):
    def fluxo(page, url):
        raise RuntimeError("Page.click: Page crashed")
    monkeypatch.setattr(link_afiliado, "_habilitado", True)
    monkeypatch.setitem(link_afiliado._FLUXOS, "amazon", fluxo)
    with pytest.raises(RuntimeError, match="Page crashed"):
        link_afiliado.capturar(object(), "amazon", "https://amazon.com.br/p/1")


def test_lin01_link_afiliado_segue_engolindo_erro_comum(monkeypatch):
    def fluxo(page, url):
        raise RuntimeError("botao sumiu")
    monkeypatch.setattr(link_afiliado, "_habilitado", True)
    monkeypatch.setitem(link_afiliado._FLUXOS, "amazon", fluxo)
    monkeypatch.setattr(link_afiliado, "_desistir_da_loja", lambda *a: None)
    r = link_afiliado.capturar(object(), "amazon", "https://amazon.com.br/p/1")
    assert r["url_afiliado"] == ""
