"""BSV-58 CFG/DOM/CMD/RES/FAL: redirect dos encurtadores pelo proxy residencial, com `curl` falso.

Links redigidos (regra 11): codigo do encurtador, ASIN e tag de terceiro viram REDACTED.
"""
import os
import subprocess

import pytest

PROXY = "socks5h://127.0.0.1:1080"
CFG = {"redirecionamento": {"proxy": PROXY, "dominios": ["promos.link"], "timeout_segundos": 20,
                            "max_saltos": 5}}
CURTO = "https://amzn.promos.link/REDACTED"
AMAZON = "https://www.amazon.com.br/dp/B0REDACTED?linkCode=ogi&psc=1&tag=REDACTED-20&th=1"
ML = "https://produto.mercadolivre.com.br/MLB-REDACTED-_JM"


@pytest.fixture
def rd():
    from core import redirecionamento
    return redirecionamento


class Curl:
    """`curl` falso: responde por URL (`url -> (codigo_saida, stdout)`) e guarda os comandos."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.comandos = []
        self.kwargs = []

    def __call__(self, cmd, **kwargs):
        self.comandos.append(cmd)
        self.kwargs.append(kwargs)
        codigo, saida = self.respostas[cmd[-1]]
        return subprocess.CompletedProcess(cmd, codigo, saida, "curl: (7) Failed to connect to 127.0.0.1 port 1080")


def cfg(**k):
    return {"redirecionamento": {**CFG["redirecionamento"], **k}}


# --- CFG-01 ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("bruto", [{}, {"redirecionamento": None}, {"redirecionamento": {"proxy": PROXY}},
                                   {"redirecionamento": {"proxy": PROXY, "dominios": []}}])
def test_cfg01_bloco_ausente_ou_sem_dominios_desliga(rd, bruto):
    assert rd.ler_config(bruto) is None


def test_cfg01_bloco_completo(rd):
    c = rd.ler_config(CFG)
    assert c is not None and c.proxy == PROXY and c.timeout == 20 and c.max_saltos == 5


# --- DOM-01 ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("url,esperado", [
    ("https://amzn.promos.link/REDACTED", "promos.link"),
    ("https://promos.link/REDACTED", "promos.link"),
    ("https://AMZN.Promos.Link:443/REDACTED", "promos.link"),
    ("https://xpromos.link/REDACTED", None),
    ("https://promos.link.exemplo.com/REDACTED", None),
    ("https://www.amazon.com.br/dp/B0REDACTED", None),
    ("https://amazon.com.br/?u=promos.link", None),
    ("", None),
])
def test_dom01_sufixo_de_rotulo(rd, url, esperado):
    assert rd.ler_config(CFG).dominio(url) == esperado


# --- CMD-01 ---------------------------------------------------------------------------------------

def test_cmd01_comando_inteiro(rd):
    curl = Curl({CURTO: (0, f"302 {AMAZON}")})
    rd.resolver(CURTO, rd.ler_config(CFG), executar=curl)
    assert curl.comandos == [[
        "curl", "-sS", "-o", os.devnull, "-w", "%{http_code} %{redirect_url}",
        "--proxy", PROXY, "--max-time", "20", "--url", CURTO,
    ]]
    assert not curl.kwargs[0].get("shell")


def test_cmd01_url_com_espaco_e_traco_vai_como_um_argumento(rd):
    url = "https://promos.link/-a b;rm -rf"
    curl = Curl({url: (0, "200 ")})
    rd.resolver(url, rd.ler_config(cfg(timeout_segundos=7)), executar=curl)
    assert curl.comandos[0][-2:] == ["--url", url] and "--max-time" in curl.comandos[0]
    assert curl.comandos[0][curl.comandos[0].index("--max-time") + 1] == "7"


# --- RES-01 / RES-02 -------------------------------------------------------------------------------

def test_res01_302_para_a_amazon_devolve_o_destino(rd):
    curl = Curl({CURTO: (0, f"302 {AMAZON}")})
    assert rd.resolver(CURTO, rd.ler_config(CFG), executar=curl) == (AMAZON, None)
    assert len(curl.comandos) == 1


def test_res02_dois_saltos_pelo_proxy_ate_o_ml(rd):
    meio = "https://promos.link/REDACTED2"
    curl = Curl({CURTO: (0, f"301 {meio}"), meio: (0, f"302 {ML}")})
    assert rd.resolver(CURTO, rd.ler_config(CFG), executar=curl) == (ML, None)
    assert [c[-1] for c in curl.comandos] == [CURTO, meio]
    assert all(c[c.index("--proxy") + 1] == PROXY for c in curl.comandos)


def test_res02_max_saltos_esgotado_e_sem_redirect(rd):
    urls = [f"https://promos.link/{i}" for i in range(4)]
    curl = Curl({u: (0, f"302 {urls[i + 1]}") for i, u in enumerate(urls[:-1])})
    assert rd.resolver(urls[0], rd.ler_config(cfg(max_saltos=2)), executar=curl) == (None, "sem_redirect")
    assert len(curl.comandos) == 2


@pytest.mark.parametrize("saida", ["200 ", "404 ", "302 ", "500 "])
def test_res02_sem_location_ou_codigo_inesperado_e_sem_redirect(rd, saida):
    curl = Curl({CURTO: (0, saida)})
    assert rd.resolver(CURTO, rd.ler_config(CFG), executar=curl) == (None, "sem_redirect")


# --- FAL-01 / FAL-02 -------------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", [5, 7, 97, 28])
def test_fal01_curl_sem_conexao_com_o_proxy(rd, codigo):
    curl = Curl({CURTO: (codigo, "000 ")})
    assert rd.resolver(CURTO, rd.ler_config(CFG), executar=curl) == (None, "proxy_indisponivel")


def test_fal01_curl_ausente_ou_travado(rd):
    def sem_curl(cmd, **k):
        raise FileNotFoundError("curl")

    def travado(cmd, **k):
        raise subprocess.TimeoutExpired(cmd, 25)
    for executar in (sem_curl, travado):
        assert rd.resolver(CURTO, rd.ler_config(CFG), executar=executar) == (None, "proxy_indisponivel")


def test_fal01_sem_proxy_configurado_nem_chama_o_curl(rd):
    curl = Curl({})
    assert rd.resolver(CURTO, rd.ler_config(cfg(proxy="")), executar=curl) == (None, "proxy_indisponivel")
    assert curl.comandos == []


@pytest.mark.parametrize("http", ["403", "429", "503"])
def test_fal02_bloqueado_pelo_proxy(rd, http):
    curl = Curl({CURTO: (0, f"{http} ")})
    assert rd.resolver(CURTO, rd.ler_config(CFG), executar=curl) == (None, "bloqueado")


def test_fal02_bloqueio_no_segundo_salto(rd):
    meio = "https://promos.link/REDACTED2"
    curl = Curl({CURTO: (0, f"302 {meio}"), meio: (0, "403 ")})
    assert rd.resolver(CURTO, rd.ler_config(CFG), executar=curl) == (None, "bloqueado")


# --- SEG-01 (modulo) -------------------------------------------------------------------------------

def test_seg01_descricao_da_config_nao_traz_o_proxy(rd):
    texto = rd.descrever(rd.ler_config(CFG))
    assert "promos.link" in texto and PROXY not in texto and "1080" not in texto
