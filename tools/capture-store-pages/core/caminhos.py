"""
Pastas de saida do projeto (fonte unica -- nao repetir 'destino' solto no codigo).

    destino/log/   CSVs de captura (main.py), logs/TSV de backfills, dumps HTML de diagnostico
    destino/bkp/   backups gerados antes de alterar o banco/arquivos (JSON, CSV)
                   + os zips de manutencao_arquivos.py (log_*, bkp_*, img_*_a_*)
    destino/img/   fotos capturadas por oferta: destino/img/<ID_OFERTA>/img_N.<ext>

As tres sao compactadas/arquivadas periodicamente por manutencao_arquivos.py
(controle de espaco na VPS). Os caminhos sao absolutos a partir da raiz do
projeto, entao funcionam mesmo rodando um script de programas_ajuste/.
"""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DESTINO_DIR = os.path.join(RAIZ, 'destino')
LOG_DIR = os.path.join(DESTINO_DIR, 'log')
BKP_DIR = os.path.join(DESTINO_DIR, 'bkp')
IMG_DIR = os.path.join(DESTINO_DIR, 'img')
# Zips gerados por manutencao_arquivos.py ficam junto dos backups.
ARQUIVO_DIR = BKP_DIR


def em_log(nome):
    """Caminho em destino/log/ (cria a pasta)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, nome)


def em_bkp(nome):
    """Caminho em destino/bkp/ (cria a pasta)."""
    os.makedirs(BKP_DIR, exist_ok=True)
    return os.path.join(BKP_DIR, nome)
