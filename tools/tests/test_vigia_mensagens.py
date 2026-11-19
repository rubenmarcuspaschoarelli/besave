"""BSV-57 MSG-01..03: texto do aviso, redacao de token e URL, credencial do worker.env, 1 mensagem por ocorrencia.
Telegram falso; nenhum segredo real."""
from datetime import timedelta

import pytest
from vigia_falso import CHAT, LINHA_DEPOIS, PID, T0, TOKEN, Mundo, v


@pytest.fixture
def m(tmp_path):
    mundo = Mundo(tmp_path)
    mundo.so("lojas")
    return mundo


def min_(n):
    return timedelta(minutes=n)


def _parar_lojas(m):
    m.bater("lojas", em=T0 - min_(30))


def test_msg01_sem_token_so_loga(m, capsys):
    m.amb.enviar = None
    _parar_lojas(m)
    assert m.rodar_vigia() == 0
    saida = capsys.readouterr().out
    assert "AVISO: Vigia dos robos: lojas parado" in saida and "so journal" in saida
    assert len(m.restarts()) == 1                              # sem Telegram o vigia age do mesmo jeito


def test_msg01_com_token_texto_tem_robo_motivo_acao_e_recursos(m, monkeypatch):
    enviados = []
    monkeypatch.setattr(v, "enviar_telegram", lambda token, chat, texto: enviados.append((token, chat, texto)))
    m.amb.enviar = lambda texto: v.enviar_telegram(TOKEN, CHAT, texto)
    m.scope_pids("lojas", {PID["lojas"], 300, 301, 302})
    m.processo(300, "chrome", 1572864)                         # 1536 MB: o maior
    m.processo(301, "chrome", 102400)
    m.processo(302, "python", 9999999)                         # nao e chrome
    m.processo(999, "chrome", 9999999)                         # chrome fora do scope: nao conta
    m.log_lojas("linha antiga\n[10:00:00] linha 7 | loja=AMAZON | status=erro\n")
    _parar_lojas(m)
    m.rodar_vigia()
    assert len(enviados) == 1
    token, chat, texto = enviados[0]
    assert (token, chat) == (TOKEN, CHAT)
    assert "lojas" in texto and "sem batimento ha 30 min" in texto and "reiniciado 1/2" in texto
    assert "[10:00:00] linha 7 | loja=AMAZON | status=erro" in texto
    assert "Memoria do scope: 1024 MB" in texto and "maior chrome: 1536 MB" in texto
    assert TOKEN not in texto and CHAT not in texto


def test_msg02_url_https_da_linha_do_log_e_removida(m):
    m.log_lojas("[captura 5] link https://amzn.to/abc?tag=meu-afiliado-20 falhou, veja http://x.co/y\n")
    _parar_lojas(m)
    m.rodar_vigia()
    texto = m.enviados[0]
    assert "https://" not in texto and "http://" not in texto and "afiliado" not in texto
    assert "[captura 5] link [url] falhou" in texto


def test_msg02_token_na_linha_do_log_e_redigido(m):
    m.log_lojas(f"erro ao chamar a API com {TOKEN} no corpo\n")
    _parar_lojas(m)
    m.rodar_vigia()
    assert TOKEN not in m.enviados[0] and "REDACTED" in m.enviados[0]


def test_msg02_falha_do_telegram_nao_vaza_token_nem_derruba(m, capsys):
    def quebra(texto):
        raise OSError(f"HTTP 400 em https://api.telegram.org/bot{TOKEN}/sendMessage")

    m.amb.enviar = quebra
    _parar_lojas(m)
    assert m.rodar_vigia() == 0
    saida = capsys.readouterr()
    assert TOKEN not in saida.out + saida.err and "https://" not in saida.out + saida.err
    assert "OSError" in saida.out
    assert len(m.restarts()) == 1                              # o restart nao depende do Telegram
    assert m.estado()["robos"]["lojas"]["ocorrencias"]["parado"]["sig"] == "reinicio1"


def test_msg02_segredo_conhecido_e_redigido_mesmo_sem_cara_de_token(m, monkeypatch):
    monkeypatch.setattr(v, "_SEGREDOS", ["senha-curta"])
    assert v.redigir("a senha-curta vazou em https://x.y/z") == "a REDACTED vazou em [url]"


def test_msg01_credenciais_do_worker_env(tmp_path):
    arq = tmp_path / "worker.env"
    arq.write_text("# comentario\nFOO=1\nexport TELEGRAM_BOT_TOKEN='abc:def'\nTELEGRAM_CHAT_ID=\"-100\"\n", encoding="utf-8")
    assert v.ler_credenciais(arq) == ("abc:def", "-100")
    assert v.ler_credenciais(tmp_path / "nao-existe.env") == ("", "")


def test_msg01_ambiente_real_sem_credenciais_nao_tem_telegram(tmp_path):
    amb = v.ambiente_real({"BESAVE_WORKER_ENV": str(tmp_path / "x.env"), "BESAVE_TOOLS": str(tmp_path),
                           "BESAVE_VIGIA_ESTADO": str(tmp_path / "e.json")})
    assert amb.enviar is None
    assert [r.nome for r in amb.robos] == ["lojas", "whatsapp"]
    assert amb.estado_path == tmp_path / "e.json"


def test_msg01_ambiente_real_com_credenciais_envia_pelo_telegram(tmp_path, monkeypatch):
    (tmp_path / "w.env").write_text(f"TELEGRAM_BOT_TOKEN={TOKEN}\nTELEGRAM_CHAT_ID={CHAT}\n", encoding="utf-8")
    chamadas = []
    monkeypatch.setattr(v, "enviar_telegram", lambda t, c, x: chamadas.append((t, c, x)))
    amb = v.ambiente_real({"BESAVE_WORKER_ENV": str(tmp_path / "w.env"), "BESAVE_TOOLS": str(tmp_path)})
    monkeypatch.setattr(v, "_SEGREDOS", [])
    amb.enviar("oi")
    assert chamadas == [(TOKEN, CHAT, "oi")]


def test_msg03_uma_mensagem_por_ocorrencia_e_lembrete_a_cada_2h(m):
    m.log_lojas("ABORTADO: perfil travado\n")  # operador: a acao nao muda entre as rodadas
    m.bater("lojas", em=T0 - min_(30))
    m.rodar_vigia()
    assert len(m.enviados) == 1
    for _ in range(3):
        m.andar(minutes=5)
        m.rodar_vigia()
    assert len(m.enviados) == 1                                # mesma ocorrencia, mesma acao: nada
    m.andar(hours=1, minutes=44)                               # 1 h 59 min depois do aviso
    m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(minutes=2)                                         # 2 h 01 min
    m.rodar_vigia()
    assert len(m.enviados) == 2 and "continua parado" in m.enviados[1]
    assert m.restarts() == []
    assert m.estado()["robos"]["lojas"]["ocorrencias"]["parado"]["sig"] == "operador"   # estado em arquivo


def test_msg03_escalada_do_reinicio_ao_operador_avisa_a_cada_mudanca_de_acao(m):
    _parar_lojas(m)
    for _ in range(3):
        m.rodar_vigia()
        m.andar(minutes=5)
    assert len(m.enviados) == 3
    assert "reiniciado 1/2" in m.enviados[0] and "reiniciado 2/2" in m.enviados[1] and "operador" in m.enviados[2]


def test_g5_avisar_redige_token_e_url_antes_de_enviar(m):
    v.avisar(m.amb, f"falha com {TOKEN} em https://api.telegram.org/bot{TOKEN}/x")
    assert m.enviados == ["falha com REDACTED em [url]"]


def test_g5_log_do_vigia_redige_token(m, capsys):
    v.log(f"erro com {TOKEN} em https://x.y/z")
    saida = capsys.readouterr().out
    assert TOKEN not in saida and "https://" not in saida


def test_g5_excecao_com_token_nao_vaza_no_journal(m, monkeypatch, capsys):
    def quebra(amb, robo, estado, agora):
        raise RuntimeError(f"falhou {TOKEN}")

    monkeypatch.setattr(v, "vigiar_robo", quebra)
    assert m.rodar_vigia() == 0
    assert TOKEN not in capsys.readouterr().out


def test_item1_mensagem_traz_memoria_e_log_de_antes_do_restart_nos_dois_robos(tmp_path):
    for robo in ("lojas", "whatsapp"):
        m = Mundo(tmp_path / robo)
        m.so(robo)
        m.scope_pids(robo, {PID[robo], 300})
        m.processo(300, "chrome", 2097152)                     # 2048 MB, so existe antes do restart
        if robo == "lojas":
            m.log_lojas("[10:00:00] linha 7 | loja=AMAZON | status=erro\n")
        else:
            m.log_whatsapp(T0 - min_(40), "[10:00:00] aguardando a lista de conversas\n")
        m.bater(robo, em=T0 - min_(30))
        m.rodar_vigia()
        assert len(m.restarts()) == 1 and len(m.enviados) == 1
        texto = m.enviados[0]
        assert "Memoria do scope: 1024 MB | maior chrome: 2048 MB" in texto, robo
        assert "status=erro" in texto or "aguardando a lista de conversas" in texto
        assert LINHA_DEPOIS not in texto and "n/d" not in texto
        # o mundo de depois do restart e outro: o mesmo calculo agora daria n/d e a linha da finalizacao
        alvo = v.log_mais_recente(next(x for x in m.amb.robos if x.nome == robo))
        assert v.memoria_scope_mb(m.amb, f"besave-{robo}-robo.scope") is None
        assert v.ultima_linha_util(v.ler_cauda(alvo)) == LINHA_DEPOIS


def test_item1_lembrete_sem_restart_tambem_usa_a_foto_do_momento(m):
    m.log_lojas("ABORTADO: perfil travado\n")                  # operador: sem restart
    _parar_lojas(m)
    m.rodar_vigia()
    m.andar(hours=2, minutes=1)
    m.rodar_vigia()
    assert len(m.enviados) == 2 and "Memoria do scope: 1024 MB" in m.enviados[1]
