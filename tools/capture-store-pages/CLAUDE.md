# capture-store-pages (Antiga CaptureAmazon) -- regras do projeto

Estrutura e regras completas em `README.md`. Resumo obrigatório:

- **Core x ajuste**: na raiz só o que roda todo dia (`main.py`,
  `manutencao_arquivos.py`, `core/`, `stores/`). Todo programa de ajuste,
  backfill, correção, diagnóstico, login manual ou teste novo vai em
  `programas_ajuste/` e começa com `import _raiz` antes de importar
  `core`/`main`/`stores`.
- **Saídas**: usar `core/caminhos.py` -- CSV/log/TSV/dump em `em_log()`
  (`destino/log/`), backups em `em_bkp()` (`destino/bkp/`), fotos em `IMG_DIR`
  (`destino/img/`). Nunca gravar solto em `destino/` nem em `conf/`.
- **Backup antes de alterar dados** (banco ou arquivos): sempre em `destino/bkp/`.
- **Git**: `conf/config.json` (senha do banco), `destino/`, `.chrome_perfil*`
  não são versionados. Config nova → refletir em `conf/config.example.json`.
- **Um processo Playwright por vez** (`.chrome_perfil` compartilhado por todas as lojas).
