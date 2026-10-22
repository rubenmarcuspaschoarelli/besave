"""
Compacta e arquiva o que e antigo em destino/log, destino/bkp e destino/img
(controle de espaco -- rotina periodica, pensada p/ a VPS).

    destino/log/<arquivo>          -> destino/bkp/log_<AAAA-MM>.zip
    destino/bkp/<arquivo ou pasta> -> destino/bkp/bkp_<AAAA-MM>.zip
    destino/img/<ID_OFERTA>/       -> destino/bkp/img_<ID_INICIAL>_a_<ID_FINAL>.zip

Os zips ficam em destino/bkp/ junto dos backups; por isso todo .zip de
destino/bkp/ e ignorado na compactacao da propria bkp (nao zipa zip).

log/bkp: o mes do zip e o da ultima modificacao do item; o zip do mes recebe
itens novos a cada execucao (modo append).
img: as pastas que venceram sao ordenadas por ID_OFERTA e agrupadas em lotes de
--lote-img pastas; cada lote vira um zip com o 1o e o ultimo ID no nome
(ex. img_1000_a_1999.zip). Pastas com nome nao numerico ficam no disco.

Um item so e apagado do disco depois de gravado no zip e conferido (CRC +
tamanho). Sao os .zip de destino/bkp/ que devem ser copiados p/ fora da
maquina (ou use --copiar-para).

Por padrao so SIMULA (mostra o que faria). Para valer: --executar.

Cuidado com img: as fotos de destino/img/<ID_OFERTA>/ sao lidas pelos
backfills de imagem (--so-local etc.). O padrao de 60 dias fica acima da
validade das ofertas (45 dias, conf/config.json -> ofertas.validade_dias), entao
so sai do disco foto de oferta ja vencida. Para trazer de volta: --restaurar ID.

Uso:
    python manutencao_arquivos.py                       # simulacao
    python manutencao_arquivos.py --executar
    python manutencao_arquivos.py --executar --so log,bkp --dias-log 15
    python manutencao_arquivos.py --executar --copiar-para F:\\backup_besave
    python manutencao_arquivos.py --restaurar 12345      # volta destino/img/12345
"""
import argparse
import os
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta

from core.caminhos import LOG_DIR, BKP_DIR, IMG_DIR, ARQUIVO_DIR

# img ja e comprimida (jpg/webp/png): deflate so gasta CPU.
COMPRESSAO = {'log': zipfile.ZIP_DEFLATED, 'bkp': zipfile.ZIP_DEFLATED,
              'img': zipfile.ZIP_STORED}
PASTAS = {'log': LOG_DIR, 'bkp': BKP_DIR, 'img': IMG_DIR}
ZIP_IMG_RE = re.compile(r'^img_(\d+)_a_(\d+)\.zip$')


def _arquivos(caminho):
    """Lista (caminho_absoluto, nome_no_zip) de um arquivo ou de uma pasta inteira."""
    base = os.path.dirname(caminho)
    if os.path.isfile(caminho):
        return [(caminho, os.path.basename(caminho))]
    saida = []
    for raiz, _, nomes in os.walk(caminho):
        for n in nomes:
            p = os.path.join(raiz, n)
            saida.append((p, os.path.relpath(p, base).replace(os.sep, '/')))
    return saida


def _mtime(caminho):
    """Ultima modificacao do item (p/ pasta, a do arquivo mais recente dentro)."""
    if os.path.isfile(caminho):
        return os.path.getmtime(caminho)
    tempos = [os.path.getmtime(p) for p, _ in _arquivos(caminho)]
    return max(tempos) if tempos else os.path.getmtime(caminho)


def _candidatos(tipo, dias, lote_img):
    """{nome_do_zip: [itens]} com os itens de 1o nivel mais velhos que `dias`."""
    pasta = PASTAS[tipo]
    if not os.path.isdir(pasta):
        return {}
    limite = (datetime.now() - timedelta(days=dias)).timestamp()
    grupos = defaultdict(list)
    ids = []
    ignorados = 0
    with os.scandir(pasta) as it:
        for e in it:
            if tipo == 'img':
                if not e.is_dir():
                    continue
                if not e.name.isdigit():
                    ignorados += 1
                    continue
            elif e.is_file() and e.name.lower().endswith('.zip'):
                continue  # zip ja arquivado (ARQUIVO_DIR = destino/bkp)
            m = _mtime(e.path)
            if m >= limite:
                continue
            if tipo == 'img':
                ids.append(int(e.name))
            else:
                grupos[f'{tipo}_{datetime.fromtimestamp(m):%Y-%m}'].append(e.path)
    if tipo == 'img':
        if ignorados:
            print(f'  ({ignorados} pasta(s) com nome nao numerico ficam no disco)')
        ids.sort()
        for i in range(0, len(ids), lote_img):
            lote = ids[i:i + lote_img]
            grupos[f'img_{lote[0]}_a_{lote[-1]}'] = [os.path.join(pasta, str(x)) for x in lote]
    return grupos


def _arquivar(tipo, nome, itens, executar):
    zip_path = os.path.join(ARQUIVO_DIR, f'{nome}.zip')
    arquivos = [a for item in itens for a in _arquivos(item)]
    tamanho = sum(os.path.getsize(p) for p, _ in arquivos)
    print(f'  {nome}.zip: {len(itens)} item(ns), {len(arquivos)} arquivo(s), '
          f'{tamanho / 1024 / 1024:.1f} MB')
    if not executar:
        return 0

    os.makedirs(ARQUIVO_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'a', compression=COMPRESSAO[tipo]) as zf:
        ja = {i.filename: i.file_size for i in zf.infolist()}
        for p, n in arquivos:
            # Ja no zip com o mesmo tamanho = execucao anterior caiu antes de
            # apagar; nao duplica a entrada, so apaga o original no fim.
            if ja.get(n) != os.path.getsize(p):
                zf.write(p, n)

    # Confere ANTES de apagar: CRC de tudo + cada arquivo presente com o tamanho certo.
    with zipfile.ZipFile(zip_path) as zf:
        ruim = zf.testzip()
        if ruim:
            print(f'    ERRO: {ruim} corrompido no zip -- nada apagado')
            return 0
        no_zip = {i.filename: i.file_size for i in zf.infolist()}
    faltando = [n for p, n in arquivos if no_zip.get(n) != os.path.getsize(p)]
    if faltando:
        print(f'    ERRO: {len(faltando)} arquivo(s) nao conferem no zip '
              f'(ex. {faltando[0]}) -- nada apagado')
        return 0

    for item in itens:
        if os.path.isdir(item):
            shutil.rmtree(item)
        else:
            os.remove(item)
    return tamanho


def _copiar(destino):
    os.makedirs(destino, exist_ok=True)
    for nome in sorted(os.listdir(ARQUIVO_DIR)):
        if not nome.lower().endswith('.zip'):
            continue
        origem = os.path.join(ARQUIVO_DIR, nome)
        alvo = os.path.join(destino, nome)
        if (os.path.exists(alvo) and os.path.getsize(alvo) == os.path.getsize(origem)
                and os.path.getmtime(alvo) >= os.path.getmtime(origem)):
            continue
        shutil.copy2(origem, alvo)
        print(f'  copiado: {nome}')


def _restaurar(id_oferta):
    """Extrai destino/img/<id>/ do zip cuja faixa de IDs no nome contem o id."""
    alvo = int(id_oferta)
    prefixo = f'{alvo}/'
    nomes = sorted(os.listdir(ARQUIVO_DIR)) if os.path.isdir(ARQUIVO_DIR) else []
    for nome in nomes:
        m = ZIP_IMG_RE.match(nome)
        if not m or not int(m.group(1)) <= alvo <= int(m.group(2)):
            continue
        with zipfile.ZipFile(os.path.join(ARQUIVO_DIR, nome)) as zf:
            membros = [n for n in zf.namelist() if n.startswith(prefixo)]
            if membros:
                zf.extractall(IMG_DIR, members=membros)
                print(f'Restaurado destino/img/{alvo}/ ({len(membros)} arquivo(s)) de {nome}')
                return True
    print(f'ID {alvo} nao encontrado em nenhum img_*_a_*.zip')
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--executar', action='store_true',
                    help='grava os zips e apaga os originais (sem isso, so simula)')
    ap.add_argument('--so', default='log,bkp,img', help='tipos, separados por virgula')
    ap.add_argument('--dias-log', type=int, default=30)
    ap.add_argument('--dias-bkp', type=int, default=30)
    ap.add_argument('--dias-img', type=int, default=60)
    ap.add_argument('--lote-img', type=int, default=1000,
                    help='pastas de oferta por zip de img (padrao 1000)')
    ap.add_argument('--copiar-para', help='copia destino/bkp/*.zip p/ esta pasta no fim')
    ap.add_argument('--restaurar', metavar='ID_OFERTA',
                    help='extrai destino/img/<ID_OFERTA>/ de volta e sai')
    args = ap.parse_args()

    if args.restaurar:
        sys.exit(0 if _restaurar(args.restaurar) else 1)
    if args.lote_img < 1:
        ap.error('--lote-img precisa ser >= 1')

    dias = {'log': args.dias_log, 'bkp': args.dias_bkp, 'img': args.dias_img}
    tipos = [t.strip() for t in args.so.split(',') if t.strip()]
    invalidos = [t for t in tipos if t not in PASTAS]
    if invalidos:
        ap.error(f'tipo(s) invalido(s): {invalidos}')

    inicio = datetime.now()
    print(f'[{inicio:%d/%m %H:%M:%S}] manutencao_arquivos '
          f'({"EXECUTANDO" if args.executar else "SIMULACAO -- use --executar"})')
    liberado = 0
    for tipo in tipos:
        grupos = _candidatos(tipo, dias[tipo], args.lote_img)
        print(f'{tipo}: {sum(map(len, grupos.values()))} item(ns) com mais de {dias[tipo]} dias')
        for nome in sorted(grupos):
            liberado += _arquivar(tipo, nome, grupos[nome], args.executar)

    if args.executar:
        print(f'Espaco liberado (antes da compressao): {liberado / 1024 / 1024:.1f} MB')
        if args.copiar_para and os.path.isdir(ARQUIVO_DIR):
            _copiar(args.copiar_para)
    print(f'Duracao: {datetime.now() - inicio}')


if __name__ == '__main__':
    main()
