"""Estado local (`estado/vistas.json`) e trava de rodada única (BSV-66, Saídas 5 e 7)."""

import json
import logging
import os
from datetime import datetime, timedelta

log = logging.getLogger('captura_web')

DIAS_VISTA = 7


def ler_vistas(caminho, agora):
    """{`site:id`: ISO UTC} dos últimos 7 dias; arquivo ausente ou inválido -> {} (com WARN se inválido)."""
    try:
        with open(caminho, encoding='utf-8') as f:
            dado = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning('estado local ilegivel (%s); comecando vazio', type(e).__name__)
        return {}
    if not isinstance(dado, dict):
        log.warning('estado local fora do formato; comecando vazio')
        return {}
    limite = agora - timedelta(days=DIAS_VISTA)
    vistas = {}
    for chave, quando in dado.items():
        try:
            dt = datetime.fromisoformat(str(quando))
        except ValueError:
            continue
        if dt.tzinfo is not None and dt >= limite:
            vistas[str(chave)] = dt.isoformat().replace('+00:00', 'Z')
    return vistas


def gravar_vistas(caminho, vistas):
    os.makedirs(os.path.dirname(caminho) or '.', exist_ok=True)
    tmp = caminho + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(vistas, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, caminho)


class TravaOcupada(Exception):
    pass


class Trava:
    """Lock do SO num arquivo: liberado sozinho se o processo morrer."""

    def __init__(self, caminho):
        self.caminho = caminho
        self._f = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.caminho) or '.', exist_ok=True)
        f = open(self.caminho, 'a+')
        try:
            _travar(f)
        except OSError as e:
            f.close()
            raise TravaOcupada(self.caminho) from e
        self._f = f
        return self

    def __exit__(self, *exc):
        if self._f is not None:
            try:
                _destravar(self._f)
            finally:
                self._f.close()
                self._f = None
        return False


if os.name == 'nt':
    import msvcrt

    def _travar(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _destravar(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _travar(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _destravar(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
