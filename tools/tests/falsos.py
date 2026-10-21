"""Modulos falsos (playwright, oracledb, requests) para importar os laços dos robos sem as dependencias."""
import importlib.util
import sys
import types


class _Falso(types.ModuleType):
    """Qualquer atributo pedido vira uma classe (excecao) vazia."""

    def __getattr__(self, nome):
        if nome.startswith("__"):
            raise AttributeError(nome)
        return type(nome, (Exception,), {})


def instalar(monkeypatch, *nomes):
    for nome in nomes or ("playwright", "playwright.sync_api", "oracledb", "requests"):
        monkeypatch.setitem(sys.modules, nome, _Falso(nome))


def importar(monkeypatch, nome_modulo, caminho):
    """Importa `caminho` sob `nome_modulo` e remove do cache ao fim do teste."""
    spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, nome_modulo, mod)
    spec.loader.exec_module(mod)
    return mod
