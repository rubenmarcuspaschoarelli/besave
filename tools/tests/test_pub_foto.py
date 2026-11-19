"""BSV-63 FOT-01..03: quadrado 800x800 JPEG branco, placeholder da area, sem foto -> None."""
import io
import urllib.error

import pytest
from PIL import Image
from pub import foto


def _imagem(w, h, cor=(200, 0, 0, 255), fmt="WEBP"):
    im = Image.new("RGBA", (w, h), cor)
    b = io.BytesIO()
    im.save(b, format=fmt)
    return b.getvalue()


def _abrir(caminho):
    im = Image.open(caminho)
    im.load()
    return im


def _servidor(respostas):
    pedidos = []

    def obter(url):
        pedidos.append(url)
        r = respostas.get(url)
        if r is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if isinstance(r, Exception):
            raise r
        return r

    return obter, pedidos


def test_fot01_retrato_vira_quadrado_branco_com_proporcao(tmp_path):
    obter, _ = _servidor({foto.url_oferta(7): _imagem(400, 200)})     # 2:1 -> 800x400 no meio
    saida = foto.preparar(7, "elas", tmp_path / "7.jpg", obter, log=lambda s: None)
    im = _abrir(saida)
    assert im.format == "JPEG" and im.size == (800, 800) and im.mode == "RGB"
    assert im.getpixel((400, 10)) == pytest.approx((255, 255, 255), abs=3)      # faixa de cima branca
    assert im.getpixel((400, 790)) == pytest.approx((255, 255, 255), abs=3)     # faixa de baixo branca
    assert im.getpixel((5, 400))[0] > 150 and im.getpixel((5, 400))[1] < 60      # a imagem toca as bordas laterais
    # proporcao: a parte vermelha tem 400 px de altura (200..600)
    assert im.getpixel((400, 205))[1] < 60 and im.getpixel((400, 195))[1] > 200
    assert im.getpixel((400, 595))[1] < 60 and im.getpixel((400, 605))[1] > 200


def test_fot01_transparencia_vira_branco(tmp_path):
    obter, _ = _servidor({foto.url_oferta(8): _imagem(100, 100, cor=(0, 0, 0, 0), fmt="PNG")})
    im = _abrir(foto.preparar(8, "elas", tmp_path / "8.jpg", obter, log=lambda s: None))
    assert im.getpixel((400, 400)) == pytest.approx((255, 255, 255), abs=3)


def test_fot02_404_da_oferta_usa_placeholder_da_area_da_linha(tmp_path):
    avisos = []
    obter, pedidos = _servidor({foto.url_placeholder("meu-lar"): _imagem(300, 300, cor=(0, 0, 255, 255))})
    saida = foto.preparar(9, "meu-lar", tmp_path / "9.jpg", obter, log=avisos.append)
    assert pedidos == ["https://besave.com.br/img/ofertas/9.webp", "https://besave.com.br/img/placeholder/meu-lar.webp"]
    im = _abrir(saida)
    assert im.size == (800, 800) and im.getpixel((400, 400))[2] > 200
    assert any("WARN" in a and "placeholder" in a for a in avisos)


@pytest.mark.parametrize("falha", [TimeoutError("timed out"), b"nao e imagem"])
def test_fot02_timeout_ou_imagem_invalida_usa_placeholder(tmp_path, falha):
    obter, _ = _servidor({foto.url_oferta(10): falha, foto.url_placeholder("pets"): _imagem(10, 10)})
    assert foto.preparar(10, "pets", tmp_path / "10.jpg", obter, log=lambda s: None) is not None


def test_fot03_sem_oferta_e_sem_placeholder_none_e_nada_gravado(tmp_path):
    obter, pedidos = _servidor({})
    assert foto.preparar(11, "tech", tmp_path / "11.jpg", obter, log=lambda s: None) is None
    assert len(pedidos) == 2 and not (tmp_path / "11.jpg").exists()
