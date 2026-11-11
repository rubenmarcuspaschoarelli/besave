"""BSV-57 VIG-01..10: decisao do vigia (parado, madrugada, pid, operador, grupo morto, laco, limite, voltou).
Relogio, systemctl, cgroup, log, batimento e Telegram falsos (vigia_falso.py)."""
from datetime import timedelta

import pytest
from vigia_falso import PID, REINICIO, SCOPE, T0, UNIDADE, Mundo

BANNER = "[browser] Aguardando o WhatsApp Web carregar...\n[browser] Se aparecer o QR Code, escaneie.\n"


@pytest.fixture
def m(tmp_path):
    return Mundo(tmp_path)


def min_(n):
    return timedelta(minutes=n)


def comando_restart(robo):
    return ["systemctl", "--user", "restart", UNIDADE[robo]]


# --- VIG-01 / VIG-02: parado, fronteira e madrugada ------------------------------------------------------


def test_vig01_prazo_vencido_ha_1_min_reinicia_uma_vez_e_avisa_uma_vez(m):
    m.bater("lojas", em=T0 - min_(11))                      # prazo = T0 - 1 min
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]
    assert len(m.enviados) == 1
    assert "lojas" in m.enviados[0] and "reiniciado 1/2" in m.enviados[0] and "sem batimento ha 11 min" in m.enviados[0]


def test_vig01_fronteira_prazo_ainda_nao_vencido_nao_age(m):
    m.bater("lojas", em=T0 - min_(9))                       # prazo = T0 + 1 min
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig01_prazo_igual_ao_agora_nao_e_parado(m):         # mata `>` -> `>=`
    m.bater("lojas", em=T0 - min_(10))                      # prazo == T0
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig01_vencido_ha_1_segundo_ja_age_sem_tolerancia_extra(m):   # mata "tolerancia de 10 min"
    m.bater("lojas", em=T0 - min_(10) - timedelta(seconds=1))
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]


def test_vig02_madrugada_prazo_de_sono_no_futuro_nao_age_mesmo_com_em_antigo(m):
    m.bater("whatsapp", em=T0 - timedelta(hours=3), prazo=T0 + min_(5), fase="dormindo")
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig02_depois_do_prazo_de_sono_vira_parado(m):
    m.bater("whatsapp", em=T0 - timedelta(hours=3), prazo=T0 - min_(1), fase="dormindo")
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("whatsapp")]


def test_vig_vivo_e_quebrado_batimento_parado_no_arranque_vira_parado(m):
    # o robo (WhatsApp) segue vivo no scope, mas so o arranque bateu: voltas cegas nao renovam (BSV-57 Saida 1)
    m.bater("whatsapp", em=T0 - min_(11), fase="arranque")
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("whatsapp")]
    assert "arranque" in m.enviados[0]


# --- VIG-03: pid ----------------------------------------------------------------------------------------


def test_vig03_processo_novo_sem_batimento_dentro_de_10_min_da_partida_nao_age(m):
    m.bater("lojas", em=T0 - timedelta(hours=1), pid=999)    # batimento do pid velho
    m.inicio_scope[SCOPE["lojas"]] = T0 - min_(5)
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig03_exatamente_10_min_da_partida_ainda_nao_age(m):
    m.bater("lojas", em=T0 - timedelta(hours=1), pid=999)
    m.inicio_scope[SCOPE["lojas"]] = T0 - min_(10)
    m.rodar_vigia()
    assert m.restarts() == []


def test_vig03_mesmo_pid_velho_com_unidade_nova_ha_mais_de_10_min_e_parado(m):
    m.bater("lojas", em=T0 - timedelta(hours=1), pid=999)
    m.inicio_scope[SCOPE["lojas"]] = T0 - min_(11)
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]


def test_vig10_pids_vem_do_cgroup_do_scope_e_nao_do_mainpid_da_unidade(m):
    tmux = 4242                                               # o MainPID da unidade e o tmux
    m.bater("lojas", em=T0 - min_(30), pid=tmux)            # batimento de pid fora do scope
    m.inicio_scope[SCOPE["lojas"]] = T0 - min_(11)
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]
    assert ["systemctl", "--user", "show", "-p", "ControlGroup", "--value", SCOPE["lojas"]] in m.cmds
    assert not any("MainPID" in " ".join(c) for c in m.cmds)


def test_vig10_pid_dentro_do_scope_e_vivo(m):
    m.scope_pids("lojas", {PID["lojas"], 201, 202})
    m.bater("lojas", em=T0 - min_(2))
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig10_so_age_por_systemctl_restart(m):
    m.bater("lojas", em=T0 - min_(11))
    m.bater("whatsapp", em=T0 - min_(11))
    m.rodar_vigia()
    for cmd in m.cmds:
        assert cmd[:2] == ["systemctl", "--user"]
        assert cmd[2] in ("is-active", "show", "restart")
    assert m.restarts() == [comando_restart("lojas"), comando_restart("whatsapp")]


# --- VIG-04: operador -----------------------------------------------------------------------------------


def test_vig04_qr_pendente_no_log_mais_recente_avisa_sem_reiniciar(m):
    m.bater("whatsapp", em=T0 - min_(11))
    m.log_whatsapp(T0 - min_(2), BANNER)
    m.rodar_vigia()
    assert m.restarts() == []
    assert len(m.enviados) == 1 and "QR" in m.enviados[0] and "operador" in m.enviados[0]


def test_vig04_banner_seguido_de_sessao_autenticada_nao_e_qr(m):
    m.bater("whatsapp", em=T0 - min_(11))
    m.log_whatsapp(T0 - min_(2), BANNER + "[browser] Sessao autenticada.\n[browser] Grupo aberto, painel pronto.\n")
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("whatsapp")]


def test_vig04_qr_so_em_log_anterior_ao_mais_recente_nao_conta(m):
    m.bater("whatsapp", em=T0 - min_(11))
    m.log_whatsapp(T0 - timedelta(hours=3), BANNER)
    m.log_whatsapp(T0 - min_(20), "[browser] Sessao autenticada.\n")
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("whatsapp")]


def test_vig04_abortado_no_log_das_lojas_avisa_sem_reiniciar(m):
    m.bater("lojas", em=T0 - min_(11))
    m.log_lojas("linha antiga\nABORTADO: perfil travado\nultima linha\n")
    m.rodar_vigia()
    assert m.restarts() == []
    assert "ABORTADO" in m.enviados[0]


def test_vig04_abortado_com_robo_saudavel_nao_incomoda(m):
    m.bater("lojas", em=T0 - min_(1))
    m.log_lojas("ABORTADO: de uma partida antiga\n")
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


# --- VIG-05: grupo morto --------------------------------------------------------------------------------


def test_vig05_grupo_falhando_ha_2h01_avisa_com_o_nome_sem_reiniciar(m):
    m.bater("whatsapp", em=T0 - min_(1), grupos={"Promos X": T0 - timedelta(hours=2, minutes=1)})
    m.rodar_vigia()
    assert m.restarts() == []
    assert len(m.enviados) == 1 and "Promos X" in m.enviados[0] and "operador" in m.enviados[0]


def test_vig05_grupo_falhando_ha_1h59_nao_avisa(m):
    m.bater("whatsapp", em=T0 - min_(1), grupos={"Promos X": T0 - timedelta(hours=1, minutes=59)})
    m.rodar_vigia()
    assert m.enviados == [] and m.restarts() == []


def test_vig05_lembrete_so_depois_de_2h_e_voltou_do_grupo(m):
    m.so("whatsapp")
    desde = T0 - timedelta(hours=3)
    m.bater("whatsapp", em=T0 - min_(1), grupos={"Promos X": desde})
    m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(minutes=5)
    m.bater("whatsapp", em=m.t - min_(1), grupos={"Promos X": desde})
    m.rodar_vigia()
    assert len(m.enviados) == 1                               # sem repeticao
    m.andar(hours=1, minutes=54)                              # 1 h 59 min depois do aviso
    m.bater("whatsapp", em=m.t - min_(1), grupos={"Promos X": desde})
    m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(minutes=2)                                        # 2 h 01 min depois
    m.bater("whatsapp", em=m.t - min_(1), grupos={"Promos X": desde})
    m.rodar_vigia()
    assert len(m.enviados) == 2 and "Lembrete" in m.enviados[1]
    m.andar(minutes=5)
    m.bater("whatsapp", em=m.t - min_(1))                     # saiu do mapa
    m.rodar_vigia()
    assert len(m.enviados) == 3 and "voltou" in m.enviados[2] and "Promos X" in m.enviados[2]
    m.andar(minutes=5)
    m.bater("whatsapp", em=m.t - min_(1))
    m.rodar_vigia()
    assert len(m.enviados) == 3
    assert m.restarts() == []


def test_vig05_limite_de_horas_configuravel_por_ambiente(m):
    m.amb.grupo_falha = timedelta(hours=1)
    m.bater("whatsapp", em=T0 - min_(1), grupos={"Promos X": T0 - min_(61)})
    m.rodar_vigia()
    assert len(m.enviados) == 1


# --- VIG-06: laco de partidas ---------------------------------------------------------------------------


def test_vig06_tres_logs_em_30_min_sem_grupo_aberto_avisa_operador_sem_reiniciar(m):
    m.bater("whatsapp", em=T0 - min_(1))
    for i, atras in enumerate((25, 15, 5)):
        m.log_whatsapp(T0 - min_(atras), "[monitor] partida\n", sufixo="" if i else "_2")
    m.rodar_vigia()
    assert m.restarts() == []
    assert len(m.enviados) == 1 and "partidas" in m.enviados[0] and "operador" in m.enviados[0]


def test_vig06_dois_logs_nao_e_laco(m):
    m.bater("whatsapp", em=T0 - min_(1))
    m.log_whatsapp(T0 - min_(15), "x\n")
    m.log_whatsapp(T0 - min_(5), "x\n")
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig06_tres_logs_com_grupo_aberto_no_ultimo_nao_e_laco(m):
    m.bater("whatsapp", em=T0 - min_(1))
    m.log_whatsapp(T0 - min_(25), "x\n")
    m.log_whatsapp(T0 - min_(15), "x\n")
    m.log_whatsapp(T0 - min_(5), "[browser] Grupo aberto, painel de mensagens pronto.\n")
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig06_log_com_mais_de_30_min_nao_conta(m):
    m.bater("whatsapp", em=T0 - min_(1))
    m.log_whatsapp(T0 - min_(31), "x\n")
    m.log_whatsapp(T0 - min_(15), "x\n")
    m.log_whatsapp(T0 - min_(5), "x\n")
    m.rodar_vigia()
    assert m.enviados == []


def test_vig06_idade_vem_do_nome_do_arquivo_nao_do_mtime(m):
    import os
    m.bater("whatsapp", em=T0 - min_(1))
    for atras in (120, 110, 100):                             # nomes antigos
        p = m.log_whatsapp(T0 - min_(atras), "x\n")
        os.utime(p, (T0.timestamp(), T0.timestamp()))        # mtime "agora"
    m.rodar_vigia()
    assert m.enviados == []


# --- VIG-07: limite de reinicios ------------------------------------------------------------------------


def _parado_de_novo(m, robo="lojas"):
    m.bater(robo, em=m.t - min_(30))


def test_vig07_terceira_parada_em_60_min_vira_operador_e_depois_de_60_min_volta_a_reiniciar(m):
    m.so("lojas")
    _parado_de_novo(m)
    m.rodar_vigia()                                           # T0: reinicio 1
    m.andar(minutes=5)
    m.rodar_vigia()                                           # T0+5: reinicio 2
    m.andar(minutes=5)
    m.rodar_vigia()                                           # T0+10: 3a parada
    assert len(m.restarts()) == 2
    assert "reiniciado 1/2" in m.enviados[0] and "reiniciado 2/2" in m.enviados[1]
    assert "operador" in m.enviados[2] and len(m.enviados) == 3
    m.andar(minutes=49)                                       # T0+59: o 1o reinicio (59 min) ainda conta
    m.rodar_vigia()
    assert len(m.restarts()) == 2
    m.andar(minutes=2)                                        # T0+61: so o 1o saiu da janela; o 2o (56 min) conta
    m.rodar_vigia()
    assert len(m.restarts()) == 3
    assert "reiniciado 2/2" in m.enviados[-1]
    m.andar(minutes=5)                                        # T0+66: o 3o (5 min) e o 2o (61 min): so 1 conta
    m.rodar_vigia()
    assert len(m.restarts()) == 4


def test_vig07_reinicios_de_um_robo_nao_contam_para_o_outro(m):
    for robo in ("lojas", "whatsapp"):
        m.bater(robo, em=T0 - min_(30))
    m.rodar_vigia()
    m.andar(minutes=5)
    m.rodar_vigia()
    assert len(m.restarts()) == 4                             # 2 por robo


# --- VIG-08: voltou -------------------------------------------------------------------------------------


def test_vig08_batimento_novo_depois_de_ocorrencia_aberta_manda_voltou_uma_vez(m):
    m.so("lojas")
    m.bater("lojas", em=T0 - min_(15))
    m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(minutes=5)
    m.bater("lojas", em=m.t - min_(1))                        # batimento novo
    m.rodar_vigia()
    assert len(m.enviados) == 2
    assert "voltou" in m.enviados[1] and "parado por 19 min" in m.enviados[1]
    m.andar(minutes=5)
    m.bater("lojas", em=m.t - min_(1))
    m.rodar_vigia()
    assert len(m.enviados) == 2


def test_vig08_sem_ocorrencia_aberta_nao_manda_nada(m):
    m.so("lojas")
    m.bater("lojas", em=T0 - min_(1))
    m.rodar_vigia()
    m.andar(minutes=5)
    m.bater("lojas", em=m.t - min_(1))
    m.rodar_vigia()
    assert m.enviados == []


def test_vig08_processo_novo_ainda_sem_batimento_nao_fecha_a_ocorrencia(m):
    m.so("lojas")
    m.bater("lojas", em=T0 - min_(15))
    m.rodar_vigia()
    m.andar(minutes=5)
    m.bater("lojas", em=T0 - min_(15), pid=999)               # so o batimento velho; processo novo no scope
    m.inicio_scope[SCOPE["lojas"]] = m.t - min_(4)
    m.rodar_vigia()
    assert len(m.enviados) == 1                               # nem "voltou" nem novo aviso
    assert "ocorrencias" in m.estado()["robos"]["lojas"] and "parado" in m.estado()["robos"]["lojas"]["ocorrencias"]


# --- VIG-09: nada a fazer -------------------------------------------------------------------------------


def test_vig09_unidade_parada_de_proposito_nao_e_religada_nem_avisada(m):
    m.estados[UNIDADE["lojas"]] = "inactive"
    m.bater("lojas", em=T0 - timedelta(hours=5))
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig09_parar_a_unidade_fecha_a_ocorrencia_sem_voltou(m):
    m.so("lojas")
    m.bater("lojas", em=T0 - min_(15))
    m.rodar_vigia()
    m.andar(minutes=5)
    m.estados[UNIDADE["lojas"]] = "inactive"
    m.rodar_vigia()
    assert len(m.enviados) == 1
    assert m.estado()["robos"]["lojas"]["ocorrencias"] == {}


def test_vig09_reinicio_diario_do_whatsapp_em_andamento_nao_age(m):
    m.estados[REINICIO] = "active"
    m.bater("whatsapp", em=T0 - timedelta(hours=1))
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig09_reinicio_diario_nao_protege_o_robo_das_lojas(m):
    m.estados[REINICIO] = "active"
    m.bater("lojas", em=T0 - min_(30))
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]


def test_vig09_banco_fora_com_batimento_renovado_nao_e_parado(m):
    m.bater("whatsapp", em=T0 - min_(1), fase="banco fora")
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_vig09_loja_em_pausa_com_batimento_em_dia_nao_e_parada(m):
    m.bater("lojas", em=T0 - min_(1), fase="varredura")
    m.log_lojas("[10:00:00] fila vazia (3 linha(s) de loja em pausa); oracle=pausada(0)\n")
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


# --- falhas do vigia nao derrubam -----------------------------------------------------------------------


def test_batimento_ausente_ou_ilegivel_com_unidade_recente_nao_age(m):
    (m.tools / "capture-store-pages" / "conf" / "batimento.json").write_text("{nao e json", encoding="utf-8")
    m.scope_pids("lojas", set())
    m.inicio_scope[UNIDADE["lojas"]] = T0 - min_(3)
    assert m.rodar_vigia() == 0
    assert m.restarts() == []


def test_sem_processo_e_sem_batimento_ha_mais_de_10_min_e_parado(m):
    (m.tools / "capture-store-pages" / "conf" / "batimento.json").unlink()
    m.scope_pids("lojas", set())
    m.inicio_scope[UNIDADE["lojas"]] = T0 - min_(11)
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]


def test_falha_em_um_robo_nao_impede_o_outro(m, monkeypatch):
    import vigia_robos as v
    real = v.vigiar_robo

    def quebra(amb, robo, estado, agora):
        if robo.nome == "lojas":
            raise RuntimeError("log ilegivel")
        return real(amb, robo, estado, agora)

    monkeypatch.setattr(v, "vigiar_robo", quebra)
    m.bater("whatsapp", em=T0 - min_(30))
    assert m.rodar_vigia() == 0
    assert m.restarts() == [comando_restart("whatsapp")]


def test_restart_que_falha_e_dito_na_mensagem_e_conta_no_limite(m):
    m.restart_rc = 1
    m.bater("lojas", em=T0 - min_(30))
    m.rodar_vigia()
    assert "restart falhou" in m.enviados[0]
    assert len(m.estado()["robos"]["lojas"]["reinicios"]) == 1


# --- lacunas apontadas pelo Verifier (G2-G4) -----------------------------------------------------------


def test_g2_scope_vazio_com_prazo_vencido_e_parado(m):
    m.scope_pids("lojas", set())
    m.bater("lojas", em=T0 - min_(11))                        # prazo vencido ha 1 min, processo sumiu
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]
    assert "processo do robo sumiu" in m.enviados[0]


def test_g2_scope_vazio_com_prazo_igual_ao_agora_nao_age(m):
    m.scope_pids("lojas", set())
    m.bater("lojas", em=T0 - min_(10))                        # prazo == agora
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_g2_scope_vazio_com_prazo_no_futuro_espera(m):
    m.scope_pids("lojas", set())
    m.bater("lojas", em=T0 - min_(2))
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_g3_unidade_activating_e_ignorada(m):
    m.estados[UNIDADE["lojas"]] = "activating"
    m.bater("lojas", em=T0 - timedelta(hours=2))
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_g3_sem_hora_de_partida_usa_o_prazo_do_batimento_como_referencia(m):
    m.inicio_scope.pop(SCOPE["lojas"])                        # systemctl nao informa o ActiveEnterTimestamp
    m.bater("lojas", em=T0 - min_(15), prazo=T0 - min_(5), pid=999)    # prazo vencido ha 5 min: ainda nao > 10 min
    m.rodar_vigia()
    assert m.restarts() == []
    m.bater("lojas", em=T0 - min_(25), prazo=T0 - min_(15), pid=999)   # vencido ha 15 min
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")]


def test_g4_mensagem_traz_a_ultima_linha_do_log_nao_a_primeira(m):
    m.bater("lojas", em=T0 - min_(30))
    filler = "".join(f"[10:00:00] linha de enchimento numero {i} com texto comprido para encher o log\n"
                     for i in range(2000))
    m.log_lojas("PRIMEIRA-LINHA-DO-ARQUIVO\n" + filler + "ULTIMA-LINHA-REAL\n")
    assert (m.tools / "capture-store-pages" / "destino" / "log" / "main_monitorar.log").stat().st_size > 70000
    m.rodar_vigia()
    assert "ULTIMA-LINHA-REAL" in m.enviados[0] and "PRIMEIRA-LINHA" not in m.enviados[0]


def test_g4_voltou_exige_batimento_posterior_a_ultima_acao_mesmo_para_o_laco(m):
    m.so("whatsapp")
    for atras in (25, 15, 5):
        m.log_whatsapp(T0 - min_(atras), "partida sem grupo\n")
    m.bater("whatsapp", em=T0 - min_(1))
    m.rodar_vigia()                                           # laco: operador
    assert len(m.enviados) == 1 and "partidas" in m.enviados[0]
    m.andar(minutes=5)
    for p in (m.tools / "capture-chat-groups" / "log").glob("*.log"):
        p.unlink()                                            # o laco some, mas o batimento continua o mesmo
    m.rodar_vigia()
    assert len(m.enviados) == 1                               # sem batimento novo nao ha "voltou"
    m.andar(minutes=1)
    m.bater("whatsapp", em=m.t - min_(1))
    m.rodar_vigia()
    assert len(m.enviados) == 2 and "voltou" in m.enviados[1]


# --- item 3 (inst1 11/11): so unidade active/activating e religada; failed avisa; inactive e silencio -----


def test_item3_active_com_robo_parado_reinicia(m):
    m.so("lojas")
    m.estados[UNIDADE["lojas"]] = "active"
    m.bater("lojas", em=T0 - min_(30))
    m.rodar_vigia()
    assert m.restarts() == [comando_restart("lojas")] and len(m.enviados) == 1


def test_item3_failed_avisa_o_operador_sem_restart_mesmo_com_robo_parado(m):
    m.so("lojas")
    m.estados[UNIDADE["lojas"]] = "failed"
    m.bater("lojas", em=T0 - min_(30))                         # parado E failed: nao religa
    m.rodar_vigia()
    assert m.restarts() == []
    assert len(m.enviados) == 1
    assert "lojas em failed" in m.enviados[0]
    assert "unidade failed: o systemd ja desistiu" in m.enviados[0]
    assert "nenhuma (precisa de operador)" in m.enviados[0]


def test_item3_failed_1_aviso_por_ocorrencia_e_lembrete_de_2h(m):
    m.so("lojas")
    m.estados[UNIDADE["lojas"]] = "failed"
    m.rodar_vigia()
    for _ in range(3):
        m.andar(minutes=5)
        m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(hours=1, minutes=44)                               # 1 h 59 min depois do aviso
    m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(minutes=2)                                         # 2 h 01 min
    m.rodar_vigia()
    assert len(m.enviados) == 2 and "continua em failed" in m.enviados[1]
    assert m.restarts() == []


def test_item3_failed_que_vira_inactive_ou_active_fecha_a_ocorrencia_e_avisa_de_novo_se_voltar(m):
    m.so("lojas")
    m.estados[UNIDADE["lojas"]] = "failed"
    m.rodar_vigia()
    m.andar(minutes=5)
    m.estados[UNIDADE["lojas"]] = "inactive"                   # o operador resolveu: silencio
    m.rodar_vigia()
    assert len(m.enviados) == 1 and m.restarts() == []
    assert "unidade" not in m.estado()["robos"]["lojas"]["ocorrencias"]
    m.andar(minutes=5)
    m.estados[UNIDADE["lojas"]] = "active"
    m.bater("lojas", em=m.t - min_(1))
    m.rodar_vigia()                                            # active e saudavel: nada
    m.andar(minutes=5)
    m.estados[UNIDADE["lojas"]] = "failed"
    m.rodar_vigia()
    assert len(m.enviados) == 2                                # nova ocorrencia, novo aviso


def test_item3_inactive_nada_mesmo_com_batimento_vencido(m):
    m.estados[UNIDADE["lojas"]] = "inactive"
    m.estados[UNIDADE["whatsapp"]] = "inactive"
    m.bater("lojas", em=T0 - timedelta(hours=5))
    m.bater("whatsapp", em=T0 - timedelta(hours=5))
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_item3_failed_do_whatsapp_tambem_nao_e_religado(m):
    m.so("whatsapp")
    m.estados[UNIDADE["whatsapp"]] = "failed"
    m.bater("whatsapp", em=T0 - timedelta(hours=1))
    m.rodar_vigia()
    assert m.restarts() == [] and len(m.enviados) == 1 and "whatsapp em failed" in m.enviados[0]


def test_item3_failed_durante_o_reinicio_diario_do_whatsapp_fica_calado(m):
    m.so("whatsapp")
    m.estados[UNIDADE["whatsapp"]] = "failed"
    m.estados[REINICIO] = "active"
    m.rodar_vigia()
    assert m.restarts() == [] and m.enviados == []


def test_g13_estado_gravado_depois_de_cada_robo_mesmo_se_o_vigia_morrer_no_seguinte(m, monkeypatch):
    import vigia_robos as v

    m.bater("lojas", em=T0 - min_(30))
    original = v.vigiar_robo

    def segundo_morre(amb, robo, estado, agora):
        if robo.nome == "whatsapp":
            raise SystemExit("morto pelo systemd")
        original(amb, robo, estado, agora)

    monkeypatch.setattr(v, "vigiar_robo", segundo_morre)
    with pytest.raises(SystemExit):
        m.rodar_vigia()
    assert len(m.estado()["robos"]["lojas"]["reinicios"]) == 1     # o teto de 2 por hora nao se perde


def test_g9_failed_que_vira_active_direto_fecha_a_ocorrencia(m):
    m.so("lojas")
    m.estados[UNIDADE["lojas"]] = "failed"
    m.rodar_vigia()
    assert len(m.enviados) == 1
    m.andar(minutes=5)
    m.estados[UNIDADE["lojas"]] = "active"                     # sem passar por inactive
    m.bater("lojas", em=m.t - min_(1))
    m.rodar_vigia()
    assert "unidade" not in m.estado()["robos"]["lojas"]["ocorrencias"]
    m.andar(minutes=5)
    m.estados[UNIDADE["lojas"]] = "failed"
    m.rodar_vigia()
    assert len(m.enviados) == 2                                # novo failed, novo aviso (nao espera o lembrete)


def test_g10_aviso_de_failed_traz_memoria_e_ultima_linha_do_log(m):
    m.so("lojas")
    m.log_lojas("antes\n[10:00:00] linha 9 | status=erro\n")
    m.estados[UNIDADE["lojas"]] = "failed"
    m.rodar_vigia()
    assert "[10:00:00] linha 9 | status=erro" in m.enviados[0]
    assert "Memoria do scope: 1024 MB" in m.enviados[0]


def test_item4_aviso_de_grupo_mostra_horario_de_brasilia_e_o_estado_segue_em_utc(m):
    m.so("whatsapp")
    desde = T0 - timedelta(hours=12, minutes=30)               # 02:30Z de 10/11 = 23:30 de 09/11 em Brasilia
    m.bater("whatsapp", em=T0 - min_(1), grupos={"Promos X": desde})
    m.rodar_vigia()
    texto = m.enviados[0]
    assert "desde 09/11 23:30 (Brasilia," in texto
    assert "2026-11-10T02:30:00Z" not in texto and "Z " not in texto
    oc = m.estado()["robos"]["whatsapp"]["ocorrencias"]["grupo:Promos X"]
    assert oc["desde"] == "2026-11-10T02:30:00Z" and oc["avisado_em"] == "2026-11-10T15:00:00Z"
