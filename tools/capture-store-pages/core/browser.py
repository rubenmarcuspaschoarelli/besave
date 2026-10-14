import os

# --- Perfil do Chrome usado na automacao --------------------------------------
# Perfil DEDICADO persistente (diretorio nao-padrao, exigido pelo Chrome p/
# remote debugging). O login da Shopee e feito UMA vez aqui (shopee_login.py) e
# fica salvo. NAO da p/ copiar o login do seu perfil real: o Chrome usa
# App-Bound Encryption e cookies copiados nao descriptografam sob automacao.
PERFIL_DIR = os.path.abspath('.chrome_perfil')
CHROME_PROFILE = 'Default'

# Flags no MINIMO e SEM script de stealth: o captcha da Shopee dava "Erro de
# Carregamento" com stealth (fingerprint inconsistente) e com --disable-gpu
# (usa WebGL/canvas). Chrome real + poucos flags = captcha carrega.
def launch_persistent(p, headless=False):
    args = ['--disable-blink-features=AutomationControlled']
    if CHROME_PROFILE:
        args.append(f'--profile-directory={CHROME_PROFILE}')
    ctx = p.chromium.launch_persistent_context(
        PERFIL_DIR,
        channel='chrome',
        headless=headless,
        no_viewport=True,          # usa o tamanho real da janela
        args=args,
        ignore_default_args=['--disable-gpu', '--enable-unsafe-swiftshader'],
    )
    return ctx
