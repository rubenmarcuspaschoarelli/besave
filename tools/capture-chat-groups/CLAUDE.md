# tools/capture-chat-groups — Python: captura de grupos de ofertas (existente)

Código pré-existente. Grava no Oracle local. Não alterar sem ticket explícito.
Credenciais e sessões ficam fora do git (`.gitignore`). Ao tocar: `ruff format`, `ruff check`, `pytest` se existir.

## Segredos (AD-017)
`conf/config.json` contém credenciais e **não é versionado** (`.gitignore`). Versionar apenas `conf/config.example.json` com valores vazios. Senha do Oracle deve vir de variável de ambiente (`BESAVE_ORACLE_PASS`) — ticket futuro para o robô ler env em vez do JSON.
