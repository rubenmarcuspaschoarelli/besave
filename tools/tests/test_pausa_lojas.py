"""BSV-55 PAU/TEL: pausa por loja depois de 3 bloqueios seguidos e aviso no Telegram (relogio falso)."""
import argparse
from datetime import datetime, timedelta

import pytest
from conftest import Loja

TOKEN = "123456:SEGREDO_DO_BOT_REDACTED"
CHAT = "-100REDACTED"
CFG = {"alerta": {"telegram_token": TOKEN, "telegram_chat_id": CHAT}, "bloqueio": {"pausa_minutos": 60}}
T0 = datetime(2026, 11, 5, 10, 0)

DOMINIO = {"shopee.com.br": "shopee", "mercadolivre.com.br": "mercadolivre", "amazon.com.br": "amazon"}
BLOQUEIO = "https://shopee.com.br/verify/traffic?anti_bot_tracking_id=REDACTED"


class Relogio:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t

    def andar(self, **k):
        self.t += timedelta(**k)


class Pagina:
    def __init__(self):
        self.url = ""
        self.visitas = []

    def wait_for_timeout(self, ms):
        pass

    def is_closed(self):
        return False


class Db:
    sem_conexao = False

    def __init__(self):
        self.capturas = []

    def atualizar_captura(self, id_oferta, out, ativo=False):
        self.capturas.append(id_oferta)
        return True, None

    def marcar_erro(self, *a, **k):
        return True, None

    def buscar_para_produto(self, i):
        return None

    def buscar_para_cupom(self, i):
        return None


@pytest.fixture
def ambiente(lojas, monkeypatch):
    """Lote com tres lojas; `bloqueada` = ids cuja pagina cai na tela de bloqueio da Shopee."""
    rel = Relogio()
    enviados = []
    pausa = lojas.bloqueio.PausaLojas(CFG, agora=rel, nome=lambda loja: lojas.registry.nome_loja(loja))
    pausa.avisar = lojas.bloqueio.Avisador(CFG, enviar=lambda t, c, m: enviados.append(m)).avisar

    def loja_da_url(url):
        for dominio, loja in DOMINIO.items():
            if dominio in url:
                return loja
        return None
    monkeypatch.setattr(lojas.registry, "resolver_loja", loja_da_url)
    monkeypatch.setattr(lojas.registry, "get_store", lambda loja: Loja())
    monkeypatch.setattr(lojas.registry, "nome_loja", lambda loja, url=None: loja.title())
    bloqueadas = set()

    def navegar(page, url, timeout=0):
        id_oferta = int(url.rsplit("/", 1)[1])
        page.visitas.append(id_oferta)
        page.url = BLOQUEIO if id_oferta in bloqueadas else url
    monkeypatch.setattr(lojas, "_goto_robusto", navegar)

    def rodar(linhas, db=None):
        db = db or Db()
        pagina = Pagina()
        rows = [{"ID_OFERTA": i, "url": f"https://{dom}/p/{i}", "numero_da_captura": str(i), "DS_ORIGEM": "g"}
                for i, dom in linhas]
        saidas, _, _ = lojas._processar_lote(pagina, rows, db, True, "img", set(), pausa)
        return {o["ID_OFERTA"]: o["status_captura"] for o in saidas}, pagina.visitas

    return rodar, bloqueadas, pausa, rel, enviados


S, ML, AMZ = "shopee.com.br", "mercadolivre.com.br", "amazon.com.br"


def test_pau01_tres_bloqueios_da_shopee_pausam_so_a_shopee(ambiente):
    rodar, bloqueadas, pausa, _, enviados = ambiente
    bloqueadas.update({1, 2, 4})
    status, visitas = rodar([(1, S), (2, S), (3, ML), (4, S), (5, AMZ), (6, S), (7, ML)])
    assert status[6] == "loja_pausada" and 6 not in visitas          # nem navegou
    assert status[3] == status[5] == status[7] == "ok"                  # ML e Amazon na mesma varredura
    assert pausa.em_pausa("shopee") and not pausa.em_pausa("mercadolivre")
    assert len(enviados) == 1 and "Shopee" in enviados[0] and "pagina" in enviados[0]


def test_pau01_linha_pausada_fica_em_0_e_nao_trava_o_ponteiro(ambiente, lojas):
    rodar, bloqueadas, *_ = ambiente
    db = Db()
    bloqueadas.update({1, 2, 3})
    rodar([(1, S), (2, S), (3, S)], db=db)
    lojas.ponteiro.clear()
    db2 = Db()                                    # outro "banco": sem a trava das bloqueadas
    status, _ = rodar([(8, S), (9, ML)], db=db2)
    assert status[8] == "loja_pausada" and db2.capturas == [9]
    assert lojas.ponteiro == [9]


def test_pau02_dois_bloqueios_e_um_sucesso_nao_pausam(ambiente):
    rodar, bloqueadas, pausa, _, enviados = ambiente
    bloqueadas.update({1, 2, 4})
    status, visitas = rodar([(1, S), (2, S), (3, S), (4, S), (5, S)])
    assert status[3] == status[5] == "ok" and 5 in visitas
    assert not pausa.em_pausa("shopee") and enviados == []


def test_pau02_bloqueio_de_uma_loja_nao_conta_para_outra(ambiente):
    rodar, bloqueadas, pausa, _, enviados = ambiente
    bloqueadas.update({1, 2, 3})
    rodar([(1, S), (2, S), (3, ML)])
    assert not pausa.em_pausa("shopee") and not pausa.em_pausa("mercadolivre") and enviados == []


def test_pau03_fim_da_pausa_com_sucesso_avisa_voltou(ambiente):
    rodar, bloqueadas, pausa, rel, enviados = ambiente
    bloqueadas.update({1, 2, 3})
    rodar([(1, S), (2, S), (3, S)])
    rel.andar(minutes=59)
    status, visitas = rodar([(4, S)])
    assert status[4] == "loja_pausada" and visitas == []
    rel.andar(minutes=2)
    status, visitas = rodar([(4, S), (5, S)])
    assert status[4] == status[5] == "ok" and visitas == [4, 5]
    assert len(enviados) == 2 and "voltou" in enviados[1]
    assert not pausa.em_pausa("shopee")


def test_pau03_fim_da_pausa_com_falha_pausa_de_novo_sem_voltou(ambiente):
    rodar, bloqueadas, pausa, rel, enviados = ambiente
    bloqueadas.update({1, 2, 3, 4})
    rodar([(1, S), (2, S), (3, S)])
    rel.andar(minutes=61)
    status, visitas = rodar([(4, S), (5, S)])
    assert status[4] == "bloqueado_ou_login" and status[5] == "loja_pausada"
    assert visitas == [4]                                               # uma linha so
    assert pausa.em_pausa("shopee")
    assert len(enviados) == 1 and not any("voltou" in m for m in enviados)


def test_tel01_lembrete_so_depois_de_6h_e_um_aviso_por_entrada(ambiente):
    rodar, bloqueadas, pausa, rel, enviados = ambiente
    bloqueadas.update(range(1, 20))
    rodar([(1, S), (2, S), (3, S), (4, S)])
    assert len(enviados) == 1
    for _ in range(5):                       # sondas falham a cada hora: nenhum aviso novo
        rel.andar(minutes=61)
        rodar([(10, S)])
        pausa.lembrar()
    assert len(enviados) == 1                # 5 h 05 min
    rel.andar(minutes=54)
    pausa.lembrar()
    assert len(enviados) == 1                # 5 h 59 min
    rel.andar(minutes=1)
    pausa.lembrar()
    pausa.lembrar()
    assert len(enviados) == 2 and "continua em pausa" in enviados[1]


def test_tel01_mensagem_de_entrada_traz_loja_motivo_retidas_e_vnc(ambiente):
    rodar, bloqueadas, *_, enviados = ambiente
    bloqueadas.update({1, 2, 3})
    rodar([(1, S), (2, S), (3, S), (4, S), (5, S)])
    msg = enviados[0]
    assert "Shopee" in msg and "pagina" in msg and "5 linha(s) retida(s)" in msg and "VNC :1" in msg


def test_tel01_sessao_de_afiliado_conta_como_bloqueio_com_motivo_afiliado(ambiente, lojas, monkeypatch):
    rodar, _, pausa, _, enviados = ambiente
    from core import link_afiliado
    monkeypatch.setattr(lojas.link_afiliado, "capturar",
                        lambda *a: {**link_afiliado.vazio(), link_afiliado.MOTIVO: link_afiliado.SESSAO})
    rodar([(1, S), (2, S), (3, S)])
    assert pausa.em_pausa("shopee") and "afiliado" in enviados[0]


def test_tel02_sem_token_so_loga(lojas, capsys):
    enviados = []
    av = lojas.bloqueio.Avisador({}, enviar=lambda *a: enviados.append(a))
    av.avisar("teste")
    assert enviados == [] and "so log" in capsys.readouterr().out


def test_tel02_token_e_chat_nunca_aparecem_na_saida(ambiente, lojas, capsys):
    def falha(token, chat, texto):
        raise RuntimeError(f"https://api.telegram.org/bot{token}/sendMessage chat={chat}")
    rodar, bloqueadas, pausa, rel, _ = ambiente
    pausa.avisar = lojas.bloqueio.Avisador(CFG, enviar=falha).avisar
    bloqueadas.update({1, 2, 3})
    rodar([(1, S), (2, S), (3, S)])
    rel.andar(hours=7)
    pausa.lembrar()
    bloqueadas.clear()
    rodar([(4, S)])
    saida = capsys.readouterr()
    texto = saida.out + saida.err
    assert "Falha ao enviar" in texto
    assert TOKEN not in texto and CHAT not in texto and "SEGREDO" not in texto


def test_pausa_minutos_do_config(lojas):
    ler = lojas.bloqueio.ler_pausa_minutos
    assert ler({}) == 60
    assert ler({"bloqueio": {"pausa_minutos": 30}}) == 30
    assert ler({"bloqueio": {"pausa_minutos": "x"}}) == 60


def test_monitor_com_so_linhas_em_pausa_dorme_em_vez_de_reler(lojas, monkeypatch):
    rel = Relogio()
    pausa = lojas.bloqueio.PausaLojas(CFG, agora=rel, avisar=lambda m: None)
    for i in (1, 2, 3):
        pausa.registrar_bloqueio("shopee", "pagina", i)
    monkeypatch.setattr(lojas, "_pausa_padrao", lambda: pausa)
    monkeypatch.setattr(lojas.registry, "resolver_loja", lambda url: "shopee" if "shopee" in url else None)
    leituras, pausas, lotes = [], [], []
    filas = iter([[{"ID_OFERTA": 9, "url": "https://shopee.com.br/p/9"}]])

    def ler(*a, **k):
        leituras.append(1)
        try:
            return next(filas)
        except StopIteration:
            raise KeyboardInterrupt from None
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", pausas.append)
    monkeypatch.setattr(lojas, "_varrer_validade", lambda db: None)
    monkeypatch.setattr(lojas, "_recuperar_publicacoes", lambda *a: None)
    monkeypatch.setattr(lojas, "_processar_lote", lambda *a, **k: lotes.append(a) or ([], 0, 0))

    class Aba:
        def is_closed(self):
            return False
    lojas._monitorar(None, Aba(), None, argparse.Namespace(desde=None, limite=0), [], None, 3, None)
    assert lotes == [] and pausas == [180]


def test_doc01_readme_da_vps_explica_sem_perguntas_pausa_e_telegram():
    from conftest import TOOLS
    leia = (TOOLS / "vps" / "README.md").read_text(encoding="utf-8")
    for termo in ("--sem-perguntas", "bloqueio.pausa_minutos", "telegram_token", "telegram_chat_id",
                  "VNC :1", "voltou", "6 h", "sem parar o robô"):
        assert termo in leia, termo
    exemplo = (TOOLS / "capture-store-pages" / "conf" / "config.example.json").read_text(encoding="utf-8")
    assert '"pausa_minutos": 60' in exemplo and '"telegram_token": ""' in exemplo


def test_pau01_tel01_monitor_mantem_a_pausa_entre_varreduras_e_lembra(ambiente, lojas, monkeypatch):
    """Laco real do --monitorar com o _processar_lote real (licao 23): a pausa vale nas varreduras seguintes
    e o lembrete de 6 h sai do proprio monitor."""
    _, bloqueadas, pausa, rel, enviados = ambiente
    bloqueadas.update({1, 2, 3})
    monkeypatch.setattr(lojas, "_pausa_padrao", lambda: pausa)
    for nome in ("_gravar_csv", "_resumo_oracle", "_varrer_validade", "_recuperar_publicacoes"):
        monkeypatch.setattr(lojas, nome, lambda *a, **k: None)

    def linha(i):
        return {"ID_OFERTA": i, "url": f"https://shopee.com.br/p/{i}", "numero_da_captura": str(i), "DS_ORIGEM": "g"}
    filas = iter([[linha(1), linha(2), linha(3)], [linha(4)]])

    def ler(*a, **k):
        try:
            return next(filas)
        except StopIteration:
            raise KeyboardInterrupt from None
    monkeypatch.setattr(lojas, "_ler_pendentes_resiliente", ler)
    monkeypatch.setattr(lojas, "_esperar", lambda s: rel.andar(hours=6))
    pagina = Pagina()
    lojas._monitorar(None, pagina, Db(), argparse.Namespace(desde=None, limite=0), [], "img", 3, None)
    assert pagina.visitas == [1, 2, 3]          # a 4 (2a varredura) nao navegou: loja seguiu pausada
    assert len(enviados) == 2 and "em pausa por" in enviados[0] and "continua em pausa" in enviados[1]


@pytest.mark.parametrize("bloco", [{"telegram_token": TOKEN}, {"telegram_chat_id": CHAT}])
def test_tel02_so_uma_das_chaves_so_loga(lojas, capsys, bloco):
    enviados = []
    lojas.bloqueio.Avisador({"alerta": bloco}, enviar=lambda *a: enviados.append(a)).avisar("teste")
    saida = capsys.readouterr().out
    assert enviados == [] and "so log" in saida and TOKEN not in saida
