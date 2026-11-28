"""BSV-66 Saídas 8, 9 e 10: config.json, usuário do banco, agendamento."""

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from webapoio.config import PADROES, carregar

WEB = Path(__file__).resolve().parent.parent / 'capture-web-apoio'


def _cfg(tmp_path, dado, ambiente=None):
    p = tmp_path / 'config.json'
    p.write_text(json.dumps(dado), encoding='utf-8')
    return carregar(str(p), ambiente or {})


def test_padroes_da_spec(tmp_path):
    cfg = carregar(str(tmp_path / 'nao-existe.json'), {})
    assert (cfg['pausa_s'], cfg['por_menu'], cfg['teto_rodada'], cfg['idade_max_horas']) == ((3, 6), 5, 30, 24)
    assert cfg['sites'] == {
        'PELANDO': {'habilitado': True, 'menus': ['https://www.pelando.com.br/recentes',
                                                  'https://www.pelando.com.br/mais-baratos',
                                                  'https://www.pelando.com.br/mais-quentes']},
        'PROMOBIT': {'habilitado': True, 'menus': ['https://www.promobit.com.br/',
                                                   'https://www.promobit.com.br/promocoes/recentes/',
                                                   'https://www.promobit.com.br/promocoes/em-alta/',
                                                   'https://www.promobit.com.br/promocoes/menor-preco/']},
        'PECHINCHOU': {'habilitado': True, 'menus': ['https://pechinchou.com.br/recentes',
                                                     'https://pechinchou.com.br/destaques',
                                                     'https://pechinchou.com.br/menor-preco',
                                                     'https://pechinchou.com.br/mais-pontuados',
                                                     'https://pechinchou.com.br/pechinchas']},
    }
    assert 'Chrome' in cfg['user_agent'] and 'Windows' in cfg['user_agent']


@pytest.mark.parametrize('chave,valor', [
    ('por_menu', 0), ('por_menu', '5'), ('teto_rodada', -1), ('teto_rodada', True), ('pausa_s', [6, 3]),
    ('pausa_s', [1]), ('idade_max_horas', 0), ('user_agent', ''), ('db', 'x'), ('alerta', []),
])
def test_chave_invalida_vira_padrao_com_warn(tmp_path, caplog, chave, valor):
    with caplog.at_level(logging.WARNING, logger='captura_web'):
        cfg = _cfg(tmp_path, {chave: valor})
    padrao = tuple(PADROES[chave]) if chave == 'pausa_s' else PADROES[chave]
    assert cfg[chave] == padrao
    assert any(chave in r.getMessage() for r in caplog.records)


def test_valores_validos_sao_usados(tmp_path):
    cfg = _cfg(tmp_path, {'por_menu': 2, 'teto_rodada': 12, 'pausa_s': [1, 2.5], 'idade_max_horas': 6,
                          'sites': {'PROMOBIT': {'habilitado': False}}})
    assert (cfg['por_menu'], cfg['teto_rodada'], cfg['pausa_s'], cfg['idade_max_horas']) == (2, 12, (1, 2.5), 6)
    assert cfg['sites']['PROMOBIT']['habilitado'] is False
    assert cfg['sites']['PELANDO']['habilitado'] is True


def test_menus_fora_do_site_ou_api_ignorados(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger='captura_web'):
        cfg = _cfg(tmp_path, {'sites': {
            'PROMOBIT': {'menus': ['https://www.promobit.com.br/api/offers', 'https://www.promobit.com.br/',
                                   'https://evil.com/', 'http://www.promobit.com.br/promocoes/em-alta/']},
            'PECHINCHOU': {'menus': ['https://pechinchou.com.br/api/promos']}}})
    assert cfg['sites']['PROMOBIT']['menus'] == ['https://www.promobit.com.br/']
    assert cfg['sites']['PECHINCHOU']['menus'] == PADROES['sites']['PECHINCHOU']['menus']
    assert len([r for r in caplog.records if 'ignorado' in r.getMessage()]) == 4


def test_senha_do_ambiente_vence(tmp_path):
    cfg = _cfg(tmp_path, {'db': {'usuario': 'BESAVE_WEB', 'senha': 'do-arquivo'}}, {'BESAVE_WEB_SENHA': 'do-env'})
    assert cfg['db'] == {'usuario': 'BESAVE_WEB', 'senha': 'do-env'}
    cfg = _cfg(tmp_path, {'db': {'senha': 'do-arquivo'}}, {})
    assert cfg['db']['senha'] == 'do-arquivo'


def test_config_example_sem_warn_e_sem_segredo(caplog):
    caminho = WEB / 'conf' / 'config.example.json'
    with caplog.at_level(logging.WARNING, logger='captura_web'):
        cfg = carregar(str(caminho), {})
    assert caplog.records == []
    assert cfg['db']['senha'] == '' and cfg['alerta']['telegram_token'] == ''
    assert cfg['sites'] == PADROES['sites']
    assert set(json.loads(caminho.read_text(encoding='utf-8'))) - {'_obs'} == set(PADROES)


def test_config_json_fora_do_git():
    ignorado = subprocess.run(['git', 'check-ignore', '-q', str(WEB / 'conf' / 'config.json')], cwd=WEB,
                              check=False)
    assert ignorado.returncode == 0


def test_sql_do_usuario():
    texto = (WEB / 'sql' / 'bsv-66-usuario.sql').read_text(encoding='utf-8')
    comandos = [linha for linha in texto.splitlines() if linha.strip() and not linha.startswith('--')]
    assert comandos == [
        'CREATE USER BESAVE_WEB IDENTIFIED BY "&senha";',
        'GRANT CREATE SESSION TO BESAVE_WEB;',
        'GRANT SELECT, INSERT ON BESAVE.OFERTA_FILA_CAPTURA TO BESAVE_WEB;',
        'GRANT SELECT ON BESAVE.OFERTA TO BESAVE_WEB;',
    ]
    assert '-- DROP USER BESAVE_WEB CASCADE;' in texto.splitlines()


def test_nao_importa_outros_robos():
    for arq in WEB.rglob('*.py'):
        codigo = arq.read_text(encoding='utf-8')
        for proibido in ('from core', 'import core', 'from wa', 'import wa', 'from pub', 'import pub',
                         'playwright', 'requests'):
            assert proibido not in codigo, (arq.name, proibido)


@pytest.mark.skipif(sys.platform != 'win32' or not shutil.which('powershell'),
                    reason='Agendador do Windows: so no PC')
def test_agendar_mostra_a_tarefa():
    def rodar(*args):
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                            str(WEB / 'agendar.ps1'), '-Mostrar', *args], capture_output=True, text=True,
                           check=False)
        assert r.returncode == 0, r.stderr
        return r.stdout.splitlines()

    py = WEB / '.venv' / 'Scripts' / 'python.exe'
    assert rodar() == [
        'tarefa=besave-captura-web',
        'horarios=08:00,12:00,17:00',
        f'executa={py} "{WEB / "main.py"}"',
        f'pasta={WEB}',
        'logon=Interactive',
        'start_when_available=False',
        'limite=PT30M',
        'instancias=IgnoreNew',
        'repeticao=0',
    ]
    assert rodar('-Horarios', '09:00,18:30')[1] == 'horarios=09:00,18:30'


def test_agendar_registra_com_os_objetos_montados():
    texto = (WEB / 'agendar.ps1').read_text(encoding='utf-8')
    assert ("Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $gatilhos -Settings $config "
            "-Principal $principal `") in texto
    assert "$Horarios = @('08:00', '12:00', '17:00')" in texto
    assert "New-ScheduledTaskSettingsSet -StartWhenAvailable:$false `" in texto
    assert "-ExecutionTimeLimit (New-TimeSpan -Minutes $LimiteMinutos) -MultipleInstances IgnoreNew `" in texto
    assert "[int]$LimiteMinutos = 30," in texto
    assert ("New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive -RunLevel Limited") in texto
    assert "if ($a -eq '--remover') { $Remover = $true }" in texto
    assert "Unregister-ScheduledTask -TaskName $Nome -Confirm:$false" in texto
    assert 'RepetitionInterval' not in texto and '-StartWhenAvailable `' not in texto
