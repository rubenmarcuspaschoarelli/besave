"""Uma rodada: lê os menus, filtra, grava na fila com cotas e rodízio (BSV-66, Saídas 3, 5, 6 e 7).

Rodízio: um turno por site (Pelando → Promobit → Pechinchou) grava no máximo uma oferta; dentro do site,
começa no menu seguinte ao da última gravação; menu esgotado passa ao próximo no mesmo turno. A lista de
um menu só é baixada quando o turno chega nele: atingido o teto, nenhuma requisição a mais.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlsplit

from . import cupons as cup
from .banco import BancoFora, ErroDado
from .extrair import EXTRATORES, url_redirect_promobit
from .http import Bloqueado, SemResposta
from .oferta import NOMES, PECHINCHOU, PELANDO, PROMOBIT
from .url import chave_loja, eh_encurtador, host, limpar, resolver_encurtador

log = logging.getLogger('captura_web')

ORDEM_SITES = (PELANDO, PROMOBIT, PECHINCHOU)
TIPO_ORIGEM = 'CAPTURA WEB'
REDIRECT_PROMOBIT = 'https://www.promobit.com.br/Redirect/to/{id}/'
DOMINIOS_PROMOBIT = ('amazon.com.br', 'mercadolivre.com.br', 'shopee.com.br')
FUTURO_MAX = timedelta(minutes=10)
TITULO_MAX = 350

# Descartes que não voltam numa rodada seguinte: entram no estado local com as gravadas.
# Fora: futura, sem_url, encurtador_nao_resolvido, erro_banco, erro_insert (podem dar certo depois).
PERMANENTES = {'gravada', 'incompleta', 'status', 'tipo', 'oculta', 'tipo_preco', 'preco_texto', 'antiga',
               'loja_fora', 'url_invalida', 'url_longa', 'vista_rodada', 'vista_fila', 'vista_oferta',
               'mesmo_titulo', 'sem_preco'}
INVALIDAS = {'incompleta', 'status', 'tipo', 'oculta', 'tipo_preco', 'preco_texto'}


def rotulo_menu(url):
    return urlsplit(url).path or '/'


@dataclass
class ResumoMenu:
    lidas: int = 0
    validas: int = 0
    gravadas: int = 0
    descartes: Counter = field(default_factory=Counter)
    ids: list = field(default_factory=list)


@dataclass
class _Menu:
    url: str
    rotulo: str
    ofertas: list | None = None
    pos: int = 0
    gravadas: int = 0
    fim: bool = False
    resumo: ResumoMenu = field(default_factory=ResumoMenu)


@dataclass
class _Site:
    chave: str
    menus: list
    ponteiro: int = 0
    parado: bool = False


@dataclass
class Resultado:
    gravadas: int = 0
    ids: list = field(default_factory=list)
    problemas: list = field(default_factory=list)   # [(site, problema)]
    banco_fora: bool = False
    resumo: dict = field(default_factory=dict)       # {(site, rotulo): ResumoMenu}
    linhas: list = field(default_factory=list)       # linhas gravadas (ou que seriam, no simular)


def mensagem(resultado):
    """Texto da mensagem única da rodada, ou None sem problema (Saída 7)."""
    n = resultado.gravadas
    if resultado.banco_fora:
        return f'Captura web: banco fora do ar; gravadas {n} oferta(s) antes da falha.'
    if not resultado.problemas:
        return None
    ordem = [NOMES[k] for k in ORDEM_SITES]
    problemas = sorted(resultado.problemas, key=lambda p: ordem.index(p[0]))  # estável: menus na ordem
    partes = '; '.join(f'{site} {problema}' for site, problema in problemas)
    return f'Captura web: {partes}. Gravadas {n} oferta(s).'


class Rodada:
    def __init__(self, cfg, http, banco, agora, vistas, simular=False):
        self.cfg = cfg
        self.http = http
        self.banco = banco
        self.agora = agora
        self.vistas = vistas          # {site:id -> ISO}: lido no início, atualizado no fim pelo chamador
        self.simular = simular
        self.novas_vistas = {}
        self.chaves_rodada = set()
        self.r = Resultado()
        self.sites = []
        for chave in ORDEM_SITES:
            s = cfg['sites'].get(chave) or {}
            if not s.get('habilitado'):
                continue
            menus = [_Menu(u, rotulo_menu(u)) for u in s.get('menus') or []]
            for m in menus:
                self.r.resumo[(NOMES[chave], m.rotulo)] = m.resumo
            if menus:
                self.sites.append(_Site(chave, menus))

    # -- laço ---------------------------------------------------------------------------------------
    def executar(self):
        teto = self.cfg['teto_rodada']
        try:
            while self.r.gravadas < teto:
                algum = False
                for site in self.sites:
                    if self.r.gravadas >= teto:
                        break
                    if self._turno(site):
                        algum = True
                if not algum:
                    break
        except BancoFora as e:
            log.error('banco fora do ar (%s); rodada interrompida', e)
            self.r.banco_fora = True
        return self.r

    def _problema(self, site, texto):
        item = (NOMES[site.chave], texto)
        if item not in self.r.problemas:
            self.r.problemas.append(item)

    def _turno(self, site):
        if site.parado:
            return False
        n = len(site.menus)
        for k in range(n):
            i = (site.ponteiro + k) % n
            menu = site.menus[i]
            if menu.fim or menu.gravadas >= self.cfg['por_menu']:
                continue
            try:
                if menu.ofertas is None:
                    self._baixar(site, menu)
                while not menu.fim and menu.pos < len(menu.ofertas):
                    oferta = menu.ofertas[menu.pos]
                    menu.pos += 1
                    if self._processar(site, menu, oferta):
                        site.ponteiro = (i + 1) % n
                        return True
                menu.fim = True
            except Bloqueado as e:
                log.warning('%s bloqueado (HTTP %s) em %s; site parado na rodada',
                            NOMES[site.chave], e.codigo, menu.rotulo)
                self._problema(site, f'bloqueado (HTTP {e.codigo})')
                site.parado = True
                return False
        return False

    def _baixar(self, site, menu):
        menu.ofertas = []
        try:
            pagina = self.http.get(menu.url)
        except SemResposta as e:
            log.warning('%s %s sem resposta (%s)', NOMES[site.chave], menu.rotulo, e)
            self._problema(site, 'sem resposta')
            menu.fim = True
            return
        extr = EXTRATORES[site.chave](pagina)
        if extr.erro:
            log.error('%s %s: estrutura mudou (%s)', NOMES[site.chave], menu.rotulo, extr.erro)
            self._problema(site, f'estrutura mudou em {menu.rotulo}')
            menu.fim = True
            return
        menu.ofertas = extr.ofertas
        menu.resumo.lidas = len(extr.ofertas)

    def _processar(self, site, menu, oferta):
        """Avalia uma oferta; True se gravou (ou gravaria, no simular)."""
        motivo, linha = self._avaliar(site, oferta)
        if motivo not in INVALIDAS:
            menu.resumo.validas += 1
        if motivo in PERMANENTES and oferta.id_origem:
            self.novas_vistas[oferta.chave_local] = self.agora().isoformat().replace('+00:00', 'Z')
        if motivo != 'gravada':
            menu.resumo.descartes[motivo] += 1
            return False
        menu.gravadas += 1
        menu.resumo.gravadas += 1
        self.r.gravadas += 1
        self.r.linhas.append(linha)
        if linha.get('id') is not None:
            menu.resumo.ids.append(linha['id'])
            self.r.ids.append(linha['id'])
        return True

    # -- filtros, na ordem da Saída 3 ----------------------------------------------------------------
    def _avaliar(self, site, oferta):
        if oferta.invalida:
            return oferta.invalida, None
        agora = self.agora()
        if oferta.publicada is None:
            return 'incompleta', None
        if agora - oferta.publicada > timedelta(hours=self.cfg['idade_max_horas']):
            return 'antiga', None
        if oferta.publicada - agora > FUTURO_MAX:
            return 'futura', None

        url = oferta.url
        if site.chave == PROMOBIT:
            if oferta.loja_origem not in DOMINIOS_PROMOBIT:
                return 'loja_fora', None
            if oferta.chave_local in self.vistas:
                return 'vista_local', None
            try:
                url = url_redirect_promobit(self.http.get(REDIRECT_PROMOBIT.format(id=oferta.id_origem)))
            except SemResposta:
                url = None
            if not url:
                return 'sem_url', None
        if eh_encurtador(url):
            url = resolver_encurtador(url, self.http.location)
            if not url:
                return 'encurtador_nao_resolvido', None
        loja, limpa, motivo = limpar(url)
        if motivo:
            if motivo == 'loja_fora':
                log.info('%s %s: loja fora (%s)', NOMES[site.chave], oferta.id_origem, host(url))
            return motivo, None

        if oferta.chave_local in self.vistas:
            return 'vista_local', None
        chave, trecho = chave_loja(limpa)
        id_produto = chave or limpa
        if id_produto in self.chaves_rodada:
            return 'vista_rodada', None
        if self.banco is not None:
            try:
                vista = self.banco.ja_vista(trecho, oferta.preco_por, loja, oferta.titulo)
            except ErroDado as e:
                log.error('consulta de ja vista falhou (%s); oferta %s pulada', e, oferta.chave_local)
                return 'erro_banco', None
            if vista:
                return vista, None

        if oferta.preco_por is None or oferta.preco_por <= 0:
            return 'sem_preco', None

        codigos = cup.separar(oferta.cupons, ref=oferta.chave_local)
        linha = {
            'origem': site.chave,
            'titulo': oferta.titulo.strip()[:TITULO_MAX],
            'preco_de': oferta.preco_de,
            'preco_por': oferta.preco_por,
            'url': limpa,
            'loja': loja,
            'cupom': cup.ds_cupom(codigos),
            'cupom_loja': loja if codigos else None,
        }
        if self.simular:
            log.info('[simular] gravaria %s %s %s R$ %s %s', NOMES[site.chave], loja, limpa,
                     oferta.preco_por, linha['titulo'])
            self.chaves_rodada.add(id_produto)
            return 'gravada', dict(linha, id=None)
        try:
            id_oferta = self.banco.gravar(linha)
        except ErroDado as e:
            log.error('INSERT falhou (%s); oferta %s pulada', e, oferta.chave_local)
            return 'erro_insert', None
        log.info('gravada ID_OFERTA=%s %s %s %s', id_oferta, NOMES[site.chave], loja, limpa)
        self.chaves_rodada.add(id_produto)
        return 'gravada', dict(linha, id=id_oferta)


def linhas_resumo(resultado):
    """Linhas do resumo para o log, por site e menu."""
    saida = []
    for (site, rotulo), r in resultado.resumo.items():
        descartes = ', '.join(f'{k}={v}' for k, v in sorted(r.descartes.items())) or '-'
        saida.append(f'[resumo] {site} {rotulo}: lidas={r.lidas} validas={r.validas} '
                     f'gravadas={r.gravadas} descartes: {descartes} ids={r.ids}')
    return saida
