"""
Importado no topo de cada script desta pasta (`import _raiz`).

Os programas de ajuste moram em programas_ajuste/, mas usam o pacote core/,
stores/, main.py e caminhos relativos (conf/, .chrome_perfil, destino/) da raiz
do projeto. Este modulo coloca a raiz no sys.path e como diretorio atual, entao
tanto `python programas_ajuste/x.py` (da raiz) quanto `python x.py` (de dentro
desta pasta) funcionam igual.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
