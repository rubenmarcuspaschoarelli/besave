import os

from core.estado import CONFIG_PATH, _ler_config

# --- Perfil do Chrome usado na automacao --------------------------------------
# Perfil DEDICADO persistente (diretorio nao-padrao, exigido pelo Chrome p/
# remote debugging). O login da Shopee e feito UMA vez aqui (shopee_login.py) e
# fica salvo. NAO da p/ copiar o login do seu perfil real: o Chrome usa
# App-Bound Encryption e cookies copiados nao descriptografam sob automacao.
PERFIL_DIR = os.path.abspath('.chrome_perfil')
CHROME_PROFILE = 'Default'

CANAL_PADRAO = 'chrome'


def ler_canal(caminho=CONFIG_PATH):
    """Navegador da automacao: "navegador.canal" no config.json.

    "chrome" (padrao, tambem quando a chave falta ou e invalida) = Google Chrome
    instalado, necessario no PC por causa do captcha da Shopee. "" = Chromium do
    Playwright (unica opcao no Linux ARM64, onde nao existe Chrome).
    """
    valor = (_ler_config(caminho).get('navegador') or {}).get('canal')
    return valor.strip() if isinstance(valor, str) else CANAL_PADRAO


# Flags no MINIMO e SEM script de stealth: o captcha da Shopee dava "Erro de
# Carregamento" com stealth (fingerprint inconsistente) e com --disable-gpu
# (usa WebGL/canvas). Chrome real + poucos flags = captcha carrega.
def montar_kwargs(canal, headless=False):
    args = ['--disable-blink-features=AutomationControlled']
    kwargs = {
        'headless': headless,
        'no_viewport': True,          # usa o tamanho real da janela
        'args': args,
        'ignore_default_args': ['--disable-gpu', '--enable-unsafe-swiftshader'],
    }
    if canal:
        if CHROME_PROFILE:
            args.append(f'--profile-directory={CHROME_PROFILE}')
        kwargs['channel'] = canal
    return kwargs


def launch_persistent(p, headless=False):
    return p.chromium.launch_persistent_context(
        PERFIL_DIR, **montar_kwargs(ler_canal(), headless=headless))
