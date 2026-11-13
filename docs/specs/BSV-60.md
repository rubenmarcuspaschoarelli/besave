# BSV-60 · Robô das lojas: `config.json` mantém a permissão ao gravar o controle

**Papel:** Python · **Pasta:** `tools/capture-store-pages/` · **Depende de:** nada (pode correr junto da
BSV-59; toca outra função). Lições 14, 29

## Contexto
Em 11/11, no teste real da BSV-59, o `conf/config.json` do robô das lojas na inst1 estava com permissão
`664`. O dono pôs `600`; minutos depois voltou a `664`. Causa: `core/estado.py::_gravar_controle` grava
`controle.<chave>` num `.tmp` novo e faz `os.replace`, e o `.tmp` nasce com a `umask` do processo
(`002`). Cada gravação do controle troca o arquivo e a permissão vai junto.

O arquivo guarda a senha do Oracle e, desde a BSV-59, o `app_secret` da API de afiliados da Shopee. A inst1
tem outros usuários (`ubuntu`, `opc`); `/srv/besave/repo` é `775`, então `664` deixa o segredo legível.

O robô do WhatsApp não tem o problema (conferido em 12/11: `600` estável; ele não regrava o próprio config).

## Saídas
1. **`_gravar_controle`** preserva o modo do arquivo existente: o `.tmp` recebe o mesmo modo do
   `config.json` (`os.stat(...).st_mode`, só os bits de permissão) **antes** do `os.replace`, sem janela em
   que o conteúdo novo exista com permissão mais aberta (criar o `.tmp` já restrito, com `os.open(...,
   0o600)`, e então aplicar o modo original).
2. Arquivo original inexistente (não acontece hoje: a função sai se o config vier vazio) → `.tmp` em `600`.
3. No Windows (`os.chmod` só mexe em somente-leitura), o comportamento não muda e nada quebra.
4. `conf/config.example.json` e README: uma linha dizendo que o `config.json` deve ficar `600` no Linux e
   que o robô mantém o modo que encontrar.

## Regras
1. Atomicidade de hoje continua (`.tmp` + `fsync` + `os.replace`; incidente de 09/10).
2. Sem dependência nova. Sem mudar a `umask` do processo inteiro (imagens e logs continuam como estão).
3. Outros escritores de arquivo com segredo no mesmo robô: o Verifier lista os `os.replace`/`open(..., 'w')`
   de `core/` e `main.py` e diz se algum grava segredo. Só `_gravar_controle` entra no código; achado
   novo vai para o PR, não para o escopo.

## Fora de escopo
- Permissão dos backups antigos na inst1 (`config.json.bak-*`): operação do dono.
- Tirar segredo do `config.json` (variável de ambiente, cofre): ticket próprio se o dono quiser.

## Critério de aceite
Testes no padrão de `tools/tests/` (ou `tools/capture-store-pages/tests/`), com `tmp_path`; os de modo
marcados para pular só no Windows.

- **Mantém 600:** config `600`, `umask 002` no teste → depois de `_gravar_controle`, `600` e a chave nova
  gravada. O mutante sem o `chmod` falha.
- **Mantém outro modo:** config `640` → continua `640` (discrimina do mutante que força `600`).
- **Sem janela aberta:** o `.tmp` nunca existe com bits de grupo/outros além dos do original (observar o modo
  no momento do `os.replace`, por exemplo envolvendo `os.replace` no teste).
- **Atomicidade:** falha simulada na escrita → `config.json` original intacto, com o modo original.
- **Gates:** `cd tools && python -m pytest -q`, ruff do CI de `tools/`.
- **Real (dono, bloqueia o merge), na inst1 com a branch:** `chmod 600 conf/config.json`, reiniciar as
  lojas, esperar 3 linhas processadas → `stat -c %a conf/config.json` = `600`.

## Definition of done
PR para `develop` com a correção, testes, README/exemplo, `validation.md` do Verifier independente (com
sensor de discriminação) e evidência redigida (sem caminho de usuário nem host).
