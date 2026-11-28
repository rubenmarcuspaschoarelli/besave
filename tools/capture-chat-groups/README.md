# capture-chat-groups — robô de captura dos grupos do WhatsApp

Histórico e notas antigas: `RESUMO.md`. Operação na VPS (unidades, reinício programado, vigia, VNC):
`tools/vps/README.md`.

## Sessão perdida: cópia, código no celular e VNC (BSV-67)

O WhatsApp Web às vezes perde a sessão (perfil corrompido quando o Chromium é estrangulado pela memória, ou
aparelho desvinculado). Em 26/11 isso parou a captura por mais de 23 h porque só dava para religar lendo o QR
na tela. Agora o robô, ao abrir o WhatsApp Web, espera o primeiro de: lista de conversas (logado) ou tela de
vincular (QR, número ou código). Na tela de vincular:

1. **Restaura a cópia guardada, uma vez.** O reinício programado (`tools/vps/reiniciar_whatsapp.sh`) guarda
   `user_data.copia/` sempre que a partida parada chegou a `Grupo aberto`. O robô fecha o navegador, grava
   `user_data.copia/restaurada_em`, move `user_data/` para `user_data.qr/` (substitui a anterior), copia
   `user_data.copia/` para `user_data/` e abre de novo. A mesma cópia nunca é restaurada duas vezes; a
   próxima cópia boa do reinício programado limpa a marca.
2. **Pede o código de pareamento.** Sem cópia, ou se a cópia também cair na tela de login, clica em "Entrar com
   número de telefone", informa `pareamento.numero`, avança e manda o código de 8 caracteres pelo Telegram.
   O robô **fica vivo** esperando (batimento `fase: "pareamento"`, prazo de 15 min); o vigia não reinicia.
3. **Sem `pareamento.numero`:** não clica em nada, avisa para ler o QR pela tela VNC `:2` e espera vivo.

### Mensagens novas no Telegram e o que fazer

| mensagem | o que fazer |
|---|---|
| `WhatsApp: sessao perdida e restaurada da copia de DD/MM HH:MM (sem acao).` | nada; a captura seguiu. Conferir depois se algo desvinculou o aparelho. |
| `WhatsApp desconectado. No celular: WhatsApp > Aparelhos conectados > Conectar aparelho > Conectar com numero de telefone e digite ABCD-EFGH (pedido as HH:MM, Brasilia).` | no celular do número configurado, seguir o caminho e digitar o código (vale ~10 min; vencido, o robô manda outro). |
| `WhatsApp: vinculado de novo pelo codigo; captura retomada.` | nada. |
| `WhatsApp desconectado: limite de codigos atingido; proximo pedido as HH:MM (Brasilia).` | esperar o horário (no máximo 3 códigos por hora cheia e 12 por dia, hora de Brasília: o WhatsApp pode bloquear vínculo por excesso de tentativas), ou ler o QR pelo VNC. |
| `WhatsApp desconectado e sem pareamento.numero no config: ler o QR pela tela VNC :2.` | abrir a tela VNC `:2` e ler o QR com o celular. Também sai quando o campo do número não ficou com o número do config (máscara da página mudou). |
| `Vigia dos robos: whatsapp aguardando vinculo pelo celular ha N h.` | lembrete do vigia a cada 6 h enquanto o robô espera; usar o último código recebido ou o VNC. |
| `Vigia dos robos: whatsapp reiniciado por memoria 2 vezes em 6 h (maior chrome: N MB).` | o Chromium está crescendo rápido; sem ação imediata (o reinício programado já rodou duas vezes). |

O número nunca vai inteiro ao log nem ao Telegram (`***1234`); o código só vai ao Telegram.

### Chave `pareamento` no `conf/config.json`

```json
"pareamento": { "numero": "5511987654321", "validade_min": 10 }
```

- `numero`: só dígitos, com DDI (formatação é ignorada). Vazio = nunca pede código; sempre o VNC.
- `validade_min`: minutos até pedir outro código se o vínculo não acontecer (padrão 10). A página voltar ao QR
  ou ao campo do número também conta como vencido.
- Forçar a leitura do QR pelo VNC: deixar `numero` vazio e reiniciar a unidade.
- A contagem do teto fica em `conf/pareamento_pedidos.json` (fora do git); apagar zera o teto.

### Pastas da sessão (todas fora do git)

| pasta | o que é |
|---|---|
| `user_data/` | perfil do Chromium em uso. O robô nunca apaga. |
| `user_data.copia/` | última cópia boa (sem caches), com `copiada_em` (UTC) e, depois de usada, `restaurada_em`. |
| `user_data.qr/` | o perfil que caiu na tela de login, guardado para diagnóstico na última restauração. |

**Restaurar à mão** (com o robô parado: `systemctl --user stop besave-captura-whatsapp`):

```bash
cd /srv/besave/repo/tools/capture-chat-groups
mv user_data user_data.manual.$(date +%Y%m%d%H%M)     # nunca apagar: guarda o perfil atual
cp -a user_data.copia user_data
rm -f user_data/copiada_em user_data/restaurada_em
systemctl --user start besave-captura-whatsapp
```

Para o robô voltar a tentar a mesma cópia sozinho: `rm user_data.copia/restaurada_em`.
