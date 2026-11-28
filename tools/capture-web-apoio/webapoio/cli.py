"""Linha de comando: `python main.py [--simular]` = uma rodada agora (BSV-66, Saída 7)."""

import argparse
import logging
import logging.handlers
import os
import sys
from datetime import UTC, datetime

from .alerta import Avisador
from .banco import Banco
from .config import carregar
from .estado import Trava, TravaOcupada, gravar_vistas, ler_vistas
from .http import Http
from .rodada import Rodada, linhas_resumo, mensagem

log = logging.getLogger('captura_web')

SAIDA_OK, SAIDA_BANCO, SAIDA_TRAVA = 0, 1, 2
MSG_BANCO_NO_INICIO = 'Captura web: banco fora do ar; gravadas 0 oferta(s) antes da falha.'


def configurar_log(base):
    """Log em `log/captura_web.log`, rotação diária, 14 dias."""
    pasta = os.path.join(base, 'log')
    os.makedirs(pasta, exist_ok=True)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    arquivo = logging.handlers.TimedRotatingFileHandler(
        os.path.join(pasta, 'captura_web.log'), when='midnight', backupCount=14, encoding='utf-8')
    arquivo.setFormatter(fmt)
    tela = logging.StreamHandler(sys.stdout)
    tela.setFormatter(fmt)
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()
    log.addHandler(arquivo)
    log.addHandler(tela)
    log.setLevel(logging.INFO)
    log.propagate = False


def _agora():
    return datetime.now(UTC)


def main(argv=None, base=None, fazer_http=None, fazer_banco=None, avisador=None, agora=None,
         configurar=True):
    p = argparse.ArgumentParser(prog='main.py', description='Captura web de apoio (BSV-66).')
    p.add_argument('--simular', action='store_true',
                   help='le, filtra e mostra o que gravaria; nao grava nem atualiza o estado local')
    args = p.parse_args(argv)
    base = base or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agora = agora or _agora
    if configurar:
        configurar_log(base)
    try:
        with Trava(os.path.join(base, 'estado', 'rodada.lock')):
            return _rodar(args, base, fazer_http, fazer_banco, avisador, agora)
    except TravaOcupada:
        log.error('outra rodada em andamento (estado/rodada.lock); saindo')
        return SAIDA_TRAVA


def _rodar(args, base, fazer_http, fazer_banco, avisador, agora):
    cfg = carregar(os.path.join(base, 'conf', 'config.json'))
    avisador = avisador or Avisador(cfg)
    caminho_vistas = os.path.join(base, 'estado', 'vistas.json')
    vistas = ler_vistas(caminho_vistas, agora())
    log.info('rodada %s; %d vista(s) no estado local', 'SIMULADA' if args.simular else 'normal',
             len(vistas))

    banco = (fazer_banco or Banco)(cfg['db'])
    if not banco.abrir():
        if not args.simular:
            avisador.avisar(MSG_BANCO_NO_INICIO)
            return SAIDA_BANCO
        log.warning('simular sem banco: consultas de ja vista no banco puladas')
        banco = None
    http = (fazer_http or Http)(cfg['user_agent'], cfg['pausa_s'])
    try:
        rodada = Rodada(cfg, http, banco, agora, vistas, simular=args.simular)
        resultado = rodada.executar()
    finally:
        if banco is not None:
            banco.fechar()

    for linha in linhas_resumo(resultado):
        log.info(linha)
    log.info('rodada encerrada: %s %d oferta(s); %d requisicao(oes)',
             'gravaria' if args.simular else 'gravadas', resultado.gravadas, http.requisicoes)
    if not args.simular:
        vistas.update(rodada.novas_vistas)
        try:
            gravar_vistas(caminho_vistas, vistas)
        except OSError as e:
            log.error('nao gravou o estado local (%s)', type(e).__name__)
    texto = mensagem(resultado)
    if texto:
        if args.simular:
            log.warning('[simular] mensagem que iria ao Telegram: %s', texto)
        else:
            avisador.avisar(texto)
    return SAIDA_BANCO if resultado.banco_fora else SAIDA_OK
