"""BSV-54 AVI-01..04: wa.avisar (ponto de entrada de linha de comando do aviso no Telegram)."""
import json

from wa import avisar

TOKEN = "123456:SEGREDO-DO-BOT"


def _cfg(tmp_path, alerta):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"alerta": alerta} if alerta is not None else {}), encoding="utf-8")
    return p


def _nunca(*_):
    raise AssertionError("nao deveria enviar")


def test_sem_token_so_loga_e_sai_com_zero(tmp_path, capsys):  # AVI-01
    rc = avisar.avisar("oi", _cfg(tmp_path, {"telegram_token": "", "telegram_chat_id": ""}), enviar=_nunca)
    assert rc == 0
    assert "so log" in capsys.readouterr().out


def test_sem_bloco_alerta_ou_sem_arquivo(tmp_path):  # AVI-01b
    assert avisar.avisar("oi", _cfg(tmp_path, None), enviar=_nunca) == 0
    assert avisar.avisar("oi", tmp_path / "nao-existe.json", enviar=_nunca) == 0


def test_com_token_chama_o_envio_com_o_texto(tmp_path):  # AVI-02
    enviados = []
    rc = avisar.avisar("reinicio falhou", _cfg(tmp_path, {"telegram_token": TOKEN, "telegram_chat_id": "-100"}),
                       enviar=lambda t, c, m: enviados.append((t, c, m)))
    assert rc == 0 and enviados == [(TOKEN, "-100", "reinicio falhou")]


def test_token_nao_aparece_na_saida_nem_em_falha(tmp_path, capsys):  # AVI-03
    def falha(token, chat, texto):
        raise RuntimeError(f"https://api.telegram.org/bot{token}/sendMessage")

    rc = avisar.avisar("x", _cfg(tmp_path, {"telegram_token": TOKEN, "telegram_chat_id": "-100"}), enviar=falha)
    saida = capsys.readouterr()
    assert rc == 0
    assert TOKEN not in saida.out + saida.err and "RuntimeError" in saida.out


def test_main_junta_os_argumentos(monkeypatch):  # AVI-04
    visto = []
    monkeypatch.setattr(avisar, "avisar", lambda texto, *a, **k: visto.append(texto) or 0)
    assert avisar.main(["um", "dois"]) == 0 and visto == ["um dois"]
