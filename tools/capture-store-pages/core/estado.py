"""
Controle de retomada: guarda em conf/config.json ("controle.ultimo_id_processado")
o ultimo ID_OFERTA capturado com sucesso, para o programa continuar de onde parou
se cair no meio de um lote.

A leitura da fila filtra por ST_CAPTURA = '0' AND ID_OFERTA > ultimo_id. Linhas
que falharam continuam com ST_CAPTURA = '0', mas ficam ATRAS do ponteiro -> para
reprocessa-las, rode com --desde 0 (ou zere o valor no config.json).

A gravacao preserva o resto do config.json (reescreve o arquivo inteiro a partir
do dict lido) e e best-effort: falha ao salvar so imprime aviso.
"""

import json
import os
import sys

CONFIG_PATH = os.path.join('conf', 'config.json')

# Pasta local espelhada no bucket S3 do site (o worker besave-ciclo sobe dali).
PADRAO_RAIZ_S3 = r'E:\Work\besave\server\s3'

# Fallback de "lojas_ativas" (config.json) quando a chave sumir do arquivo.
PADRAO_LOJAS_ATIVAS = ('Amazon', 'Mercado Livre', 'Shopee')


def _ler_config(caminho=CONFIG_PATH):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        print(f'[estado] Nao consegui ler {caminho}: {e}')
        return {}


def ler_ultimo_id(caminho=CONFIG_PATH):
    """Ultimo ID_OFERTA processado (0 se ausente/invalido)."""
    try:
        return int((_ler_config(caminho).get('controle') or {}).get('ultimo_id_processado') or 0)
    except (TypeError, ValueError):
        return 0


def ler_intervalo_monitor(caminho=CONFIG_PATH, padrao=3):
    """Minutos entre as varreduras da fila no modo --monitorar.

    Vem de "monitor.intervalo_minutos" no config.json; ausente/invalido/<=0 cai
    no padrao (3 minutos). Aceita decimal (ex.: 0.5 = 30 segundos).
    """
    try:
        valor = float((_ler_config(caminho).get('monitor') or {}).get('intervalo_minutos'))
    except (TypeError, ValueError):
        return padrao
    return valor if valor > 0 else padrao


def ler_lojas_ativas(caminho=CONFIG_PATH, padrao=PADRAO_LOJAS_ATIVAS):
    """Nomes COMERCIAIS das lojas que entram em producao (ST_ATIVO = '1').

    Vem de "lojas_ativas" no config.json. As demais lojas continuam sendo
    capturadas normalmente -- so nascem com ST_ATIVO = '0'. Para ativar uma
    loja ja mapeada basta acrescentar o nome aqui e reprocessar; nao ha codigo
    a mexer. Chave ausente/invalida cai no padrao (nunca em "lista vazia", que
    marcaria a fila inteira como inativa).
    """
    valor = _ler_config(caminho).get('lojas_ativas')
    if not isinstance(valor, list):
        return list(padrao)
    nomes = [str(x).strip() for x in valor if str(x).strip()]
    return nomes or list(padrao)


def ler_link_afiliado(caminho=CONFIG_PATH, padrao=True):
    """Capturar o link OFICIAL de afiliado a cada captura? (core/link_afiliado.py)

    Vem de "link_afiliado.habilitado" no config.json; ausente/invalido = True
    (o comportamento normal de producao). Desligar e util p/ rodar a fila sem
    depender das 3 sessoes de afiliado logadas -- a captura do produto nao
    precisa delas. A linha de comando (--sem-link-afiliado) tem prioridade.
    """
    valor = (_ler_config(caminho).get('link_afiliado') or {}).get('habilitado')
    return padrao if valor is None else bool(valor)


def ler_validade_ofertas(caminho=CONFIG_PATH, padrao=45):
    """Dias de vida de uma oferta (DT_OFERTA) antes de ser desativada sozinha
    (core/validade.py). Vem de "ofertas.validade_dias" no config.json;
    ausente/invalido = padrao (45, decisao do usuario 2026-10-13); 0 = nunca
    vence (regra desligada)."""
    try:
        valor = int((_ler_config(caminho).get('ofertas') or {}).get('validade_dias'))
    except (TypeError, ValueError):
        return padrao
    return max(valor, 0)


class ConfigFaltando(RuntimeError):
    """Chave obrigatoria ausente do config.json (sem padrao seguro na plataforma)."""


def ler_raiz_s3(caminho=CONFIG_PATH, padrao=PADRAO_RAIZ_S3, plataforma=None):
    """Pasta local que espelha o S3 do site ("s3.raiz" no config.json).
    Dentro dela: ofertas/img/<ID_OFERTA>/ e produtos/img/<ID_PRODUTO>/.
    Ausente/vazio -> padrao no Windows (a pasta da maquina local); no Linux nao
    ha padrao e o robo para dizendo qual chave falta."""
    valor = (_ler_config(caminho).get('s3') or {}).get('raiz')
    if valor and str(valor).strip():
        return str(valor).strip()
    if (plataforma or sys.platform) == 'win32':
        return padrao
    raise ConfigFaltando(
        f'Falta "s3.raiz" em {caminho}: pasta local que espelha o S3 do site '
        '(ex.: /home/ubuntu/s3). Sem padrao fora do Windows.')


def usa_imagem_loja(ds_origem, caminho=CONFIG_PATH):
    """A imagem original (enviada no grupo do WhatsApp) deve ser SUBSTITUIDA
    pela foto capturada na pagina do produto (core/imagens_oferta.py)?

    Decisao POR GRUPO de origem (OFERTA_FILA_CAPTURA.DS_ORIGEM), vinda de
    "grupos" no config.json:
        "grupos": {"@achadinhoscomcarol 9": {"usa_imagem_loja": true}, ...}
    Grupo ausente/nao configurado, ou ds_origem vazio -> False (conservador:
    so substitui quem foi explicitamente marcado)."""
    if not ds_origem:
        return False
    grupos = _ler_config(caminho).get('grupos') or {}
    cfg_grupo = grupos.get(ds_origem) or {}
    return bool(cfg_grupo.get('usa_imagem_loja'))


def grupos_com_imagem_loja(caminho=CONFIG_PATH):
    """Nomes de DS_ORIGEM marcados com "usa_imagem_loja": true em
    conf/config.json -> "grupos" (ver usa_imagem_loja acima). Usado pelo
    backfill (backfill_imagens_oferta.py) para achar as ofertas a reprocessar."""
    grupos = _ler_config(caminho).get('grupos') or {}
    return [nome for nome, cfg in grupos.items()
            if isinstance(cfg, dict) and cfg.get('usa_imagem_loja')]


def gravar_ultimo_id(valor, caminho=CONFIG_PATH):
    """Anota o ultimo ID processado, preservando o resto do config.json."""
    cfg = _ler_config(caminho)
    if not cfg:
        return
    cfg.setdefault('controle', {})['ultimo_id_processado'] = int(valor)
    # Grava num .tmp e so entao troca (os.replace e atomico): se o disco encher
    # no meio da gravacao, o config.json original fica intacto em vez de vazio
    # (incidente 2026-10-09: disco E: cheio zerou o arquivo).
    tmp = caminho + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)
    except Exception as e:  # noqa: BLE001
        print(f'[estado] Nao consegui gravar {caminho}: {e}')
        try:
            os.remove(tmp)
        except OSError:
            pass
