# BSV-49 Backup diário do banco — Specification

Fonte: `docs/specs/BSV-49.md` (PR #88, ainda não em `develop`). Pastas: `infra/backup/`, `infra/backup.tf`.

## Requisitos (EARS)

| ID | Requisito | Teste |
|----|-----------|-------|
| BKP-01 | QUANDO o timer das 03:30 disparar, o sistema DEVE exportar o schema `BESAVE` por Data Pump direto para o bucket da OCI (`besave-AAAAMMDD-*.dmp` + `besave-AAAAMMDD.log`) e copiar tudo para `s3://besave-backup/db/AAAAMMDD/` com `SHA256SUMS`, subindo o log por último | `teste_backup.sh` BKP-01 |
| BKP-02 | SE o backup do dia já existe (log no bucket / no S3), ENTÃO nada DEVE ser exportado, enviado nem apagado, e o histórico não muda | BKP-02, BKP-03 |
| BKP-03 | O sistema DEVE manter 7 dias na OCI (apaga só `besave-AAAAMMDD…` mais velhos) e 30 no S3 (ciclo de vida) | BKP-04; `tests/backup.tftest.hcl` BKP-05 |
| BKP-04 | SE qualquer etapa (export, cópia, retenção) falhar, ENTÃO o sistema DEVE alertar no Telegram, registrar a falha e sair com código ≠ 0, sem avançar para as etapas seguintes | BKP-05..08 |
| BKP-05 | Segredos DEVEM ficar só no `backup.env` (600); o token do Telegram e a senha do banco NÃO DEVEM aparecer em argumentos de processo | BKP-09, BKP-12 |
| BKP-06 | O bucket DEVE ser privado, criptografado, versionado e com expiração de 30 dias; o usuário IAM SÓ grava/lê/lista `db/` e apagar é negado | `backup.tftest.hcl` BKP-01..09 |
| RST-01 | NO dia 1 às 05:00 o sistema DEVE importar o último dump completo em `BESAVE_RESTORE`, comparar contagens por tabela (tolerância 5%/mín. 20) e objetos inválidos, e apagar o schema de teste, inclusive quando o teste falha | RST-01..06 |
| ALR-01 | SE uma unidade morrer sem o script ter alertado, ENTÃO o `OnFailure=` DEVE alertar; SE o script já alertou, NÃO DEVE repetir | ALR-01..04 |
| RES-01 | Toda segunda o sistema DEVE enviar "N/7 ok, último X MB" | RES-01..03 |
| DOC-01 | `README.md` DEVE trazer restaurar tabela, schema em banco novo e a ordem de parada | revisão |
