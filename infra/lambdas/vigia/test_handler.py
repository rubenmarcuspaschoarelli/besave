"""Testes do vigia (BSV-15): sem rede, sem boto3, com dublês de S3/HTTP/SSM/Telegram."""

import io
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

import handler

T0 = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)  # 12:00 em Brasília
URL = "https://d111111abcdef8.cloudfront.net/manifest.json"
TOKEN = "123456:SEGREDO-DO-BOT"
CHAT = "-1009876543210"
CFG = handler.Config(
    bucket="besave-site",
    url_manifest=URL,
    limiar_min=30,
    param_token="/besave/telegram/token",
    param_chat_id="/besave/telegram/chat_id",
)


class ErroCliente(Exception):
    """Formato do botocore.exceptions.ClientError."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.response = {"Error": {"Code": codigo}}


class S3Memoria:
    def __init__(self, codigo_ausente="NoSuchKey"):
        self.objetos = {}
        self.puts = []
        self.codigo_ausente = codigo_ausente

    def gravar(self, chave, corpo, modificado):
        self.objetos[chave] = (corpo, modificado)

    def head_object(self, Bucket, Key):
        if Key not in self.objetos:
            raise ErroCliente("404")
        return {"LastModified": self.objetos[Key][1]}

    def get_object(self, Bucket, Key):
        if Key not in self.objetos:
            raise ErroCliente(self.codigo_ausente)
        return {"Body": io.BytesIO(self.objetos[Key][0])}

    def put_object(self, **kw):
        self.puts.append(kw)
        self.objetos[kw["Key"]] = (kw["Body"], None)

    def estado(self):
        return json.loads(self.objetos["_estado/vigia.json"][0])


class Cenario:
    """Um S3 em memória + site + Telegram, reutilizado entre execuções."""

    def __init__(self):
        self.s3 = S3Memoria()
        self.http = (200, json.dumps({"versao": 20261001150000}).encode())
        self.http_erro = None
        self.timeouts = []
        self.enviadas = []
        self.telegram_falha = False
        self.segredos_lidos = 0

    def manifest_com_idade(self, agora, minutos):
        self.s3.gravar("manifest.json", b"{}", agora - timedelta(minutes=minutos))

    def http_get(self, url, timeout):
        assert url == URL
        self.timeouts.append(timeout)
        if self.http_erro:
            raise self.http_erro
        return self.http

    def segredos(self):
        self.segredos_lidos += 1
        return TOKEN, CHAT

    def enviar(self, token, chat_id, texto):
        assert (token, chat_id) == (TOKEN, CHAT)
        if self.telegram_falha:
            raise urllib.error.URLError("rede")
        self.enviadas.append(texto)

    def rodar(self, agora):
        return handler.executar(self.s3, self.http_get, self.segredos, self.enviar, agora, CFG)


class SequenciaDoCriterioDeAceite(unittest.TestCase):
    """10 min → ok; 31 min → alerta; ainda velho → 0; 3 h depois → lembrete; fresco → voltou."""

    def test_sequencia_completa(self):
        c = Cenario()
        c.manifest_com_idade(T0, 10)
        self.assertEqual(c.rodar(T0), "sem_aviso")
        self.assertEqual(c.enviadas, [])
        self.assertEqual(c.s3.puts, [])  # AVI-01: nada gravado

        t1 = T0 + timedelta(minutes=21)  # manifest com 31 min
        self.assertEqual(c.rodar(t1), "avisado")
        self.assertEqual(len(c.enviadas), 1)
        self.assertIn("31 min", c.enviadas[0])
        estado = c.s3.estado()
        self.assertEqual(estado["situacao"], "alerta")
        self.assertEqual(estado["ultimo_aviso"], "2026-10-01T15:21:00Z")
        # desde = LastModified do manifest (14:50 UTC)
        self.assertEqual(estado["desde"], "2026-10-01T14:50:00Z")

        t2 = t1 + timedelta(minutes=10)
        self.assertEqual(c.rodar(t2), "sem_aviso")
        self.assertEqual(len(c.enviadas), 1)
        self.assertEqual(len(c.s3.puts), 1)

        t3 = t1 + timedelta(hours=3)
        self.assertEqual(c.rodar(t3), "avisado")
        self.assertEqual(len(c.enviadas), 2)
        lembrete = c.enviadas[1]
        self.assertIn("ainda", lembrete)
        self.assertIn("11:50", lembrete)  # desde, em Brasília
        estado = c.s3.estado()
        self.assertEqual(estado["situacao"], "alerta")
        self.assertEqual(estado["desde"], "2026-10-01T14:50:00Z")
        self.assertEqual(estado["ultimo_aviso"], "2026-10-01T18:21:00Z")

        t4 = T0 + timedelta(hours=3, minutes=30)  # 18:30 UTC
        c.manifest_com_idade(t4, 1)
        self.assertEqual(c.rodar(t4), "avisado")
        self.assertEqual(c.enviadas[2], "✅ Besave: site atualizado de novo (parado por 3h40)")
        self.assertEqual(c.s3.estado(), {
            "situacao": "ok", "desde": "2026-10-01T18:30:00Z", "ultimo_aviso": "2026-10-01T18:30:00Z",
        })

        self.assertEqual(c.rodar(t4 + timedelta(minutes=10)), "sem_aviso")
        self.assertEqual(len(c.enviadas), 3)


class Frescor(unittest.TestCase):
    def test_exatamente_no_limiar_e_ok(self):  # VER-01 / edge
        c = Cenario()
        c.manifest_com_idade(T0, 30)
        self.assertEqual(c.rodar(T0), "sem_aviso")

    def test_limiar_configuravel(self):
        c = Cenario()
        c.manifest_com_idade(T0, 20)
        cfg = handler.Config(**{**CFG.__dict__, "limiar_min": 15})
        handler.executar(c.s3, c.http_get, c.segredos, c.enviar, T0, cfg)
        self.assertEqual(len(c.enviadas), 1)

    def test_manifest_inacessivel_e_problema_de_frescor(self):  # VER-02
        c = Cenario()
        c.rodar(T0)
        self.assertEqual(len(c.enviadas), 1)
        self.assertIn("manifest.json inacessível no S3", c.enviadas[0])
        self.assertEqual(c.s3.estado()["desde"], "2026-10-01T15:00:00Z")

    def test_config_do_ambiente(self):
        cfg = handler.Config.do_ambiente({
            "BUCKET": "b", "URL_MANIFEST": "u", "PARAM_TOKEN": "t", "PARAM_CHAT_ID": "c",
        })
        self.assertEqual(cfg.limiar_min, 30)
        self.assertEqual(handler.Config.do_ambiente({
            "BUCKET": "b", "URL_MANIFEST": "u", "PARAM_TOKEN": "t", "PARAM_CHAT_ID": "c", "LIMIAR_MIN": "45",
        }).limiar_min, 45)


class Disponibilidade(unittest.TestCase):
    def alerta(self, preparar):
        c = Cenario()
        c.manifest_com_idade(T0, 5)
        preparar(c)
        self.assertEqual(c.rodar(T0), "avisado")
        self.assertEqual(len(c.enviadas), 1)
        self.assertEqual(c.s3.estado()["desde"], "2026-10-01T15:00:00Z")
        return c.enviadas[0]

    def test_http_403(self):  # VER-04
        msg = self.alerta(lambda c: setattr(c, "http", (403, b"")))
        self.assertIn("HTTP 403", msg)
        self.assertNotIn("manifest.json inacessível no S3", msg)
        self.assertNotIn("sem atualização", msg)

    def test_status_diferente_de_200(self):  # VER-04: 2xx que não é 200 também é problema
        msg = self.alerta(lambda c: setattr(c, "http", (204, b'{"versao": 1}')))
        self.assertIn("HTTP 204", msg)
        msg = self.alerta(lambda c: setattr(c, "http", (500, b"")))
        self.assertIn("HTTP 500", msg)

    def test_timeout(self):  # VER-04
        msg = self.alerta(lambda c: setattr(c, "http_erro", TimeoutError()))
        self.assertIn("timeout", msg)

    def test_erro_de_rede(self):
        msg = self.alerta(lambda c: setattr(c, "http_erro", urllib.error.URLError("dns")))
        self.assertIn("erro de rede", msg)

    def test_json_sem_versao(self):
        msg = self.alerta(lambda c: setattr(c, "http", (200, b'{"contrato": "1.3.0"}')))
        self.assertIn("sem versao", msg)

    def test_corpo_nao_json(self):
        msg = self.alerta(lambda c: setattr(c, "http", (200, b"<html>")))
        self.assertIn("sem versao", msg)

    def test_json_nao_objeto(self):
        msg = self.alerta(lambda c: setattr(c, "http", (200, b'["versao"]')))
        self.assertIn("sem versao", msg)

    def test_textos_distintos_de_frescor(self):
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        c.http = (403, b"")
        c.rodar(T0)
        msg = c.enviadas[0]
        self.assertIn("HTTP 403", msg)
        self.assertIn("45 min", msg)
        self.assertEqual(c.s3.estado()["desde"], "2026-10-01T14:15:00Z")

    def test_timeout_de_10_s(self):  # VER-05
        c = Cenario()
        c.manifest_com_idade(T0, 5)
        c.rodar(T0)
        self.assertEqual(c.timeouts, [10])


class HttpGetReal(unittest.TestCase):
    def test_status_de_erro_vira_codigo(self):
        erro = urllib.error.HTTPError(URL, 403, "Forbidden", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            self.assertEqual(handler.http_get(URL, 10), (403, b""))

    def test_timeout_na_conexao_vira_timeout(self):
        erro = urllib.error.URLError(TimeoutError("timed out"))
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            with self.assertRaises(TimeoutError):
                handler.http_get(URL, 10)

    def test_repassa_timeout(self):
        resposta = mock.MagicMock()
        resposta.__enter__.return_value.status = 200
        resposta.__enter__.return_value.read.return_value = b"{}"
        with mock.patch("urllib.request.urlopen", return_value=resposta) as urlopen:
            self.assertEqual(handler.http_get(URL, 10), (200, b"{}"))
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)


class Estado(unittest.TestCase):
    def test_gravado_com_tipo_e_sem_cache(self):
        c = Cenario()
        c.rodar(T0)
        put = c.s3.puts[0]
        self.assertEqual(put["Bucket"], "besave-site")
        self.assertEqual(put["Key"], "_estado/vigia.json")
        self.assertEqual(put["ContentType"], "application/json")
        self.assertEqual(put["CacheControl"], "no-store")
        self.assertEqual(set(c.s3.estado()), {"situacao", "desde", "ultimo_aviso"})

    def test_estado_invalido_conta_como_ok(self):
        c = Cenario()
        c.manifest_com_idade(T0, 5)
        c.s3.gravar("_estado/vigia.json", b"{nao json", None)
        self.assertEqual(c.rodar(T0), "sem_aviso")
        c.s3.gravar("_estado/vigia.json", b'{"situacao": "alerta"}', None)
        self.assertEqual(c.rodar(T0), "sem_aviso")

    def test_falha_ao_gravar_estado_loga_so_o_codigo(self):  # AVI-08
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        arn = "arn:aws:sts::111111111111:assumed-role/besave-vigia/besave-vigia"

        def put_negado(**kw):
            erro = ErroCliente("AccessDenied")
            erro.args = (f"User: {arn} is not authorized",)
            raise erro

        c.s3.put_object = put_negado
        with self.assertLogs("vigia", "INFO") as logs:
            self.assertEqual(c.rodar(T0), "falha_estado")
        texto = "\n".join(logs.output)
        self.assertIn("AccessDenied", texto)
        self.assertNotIn("arn:", texto)

    def test_erro_inesperado_ao_ler_estado_nao_vaza_mensagem(self):  # AVI-08
        c = Cenario()
        c.manifest_com_idade(T0, 5)
        c.s3.gravar("_estado/vigia.json", b"{}", None)

        def get_falha(**kw):
            erro = ErroCliente("SlowDown")
            erro.args = ("arn:aws:iam::111111111111:role/besave-vigia",)
            raise erro

        c.s3.get_object = get_falha
        with self.assertLogs("vigia", "ERROR") as logs, self.assertRaises(RuntimeError) as ctx:
            c.rodar(T0)
        self.assertNotIn("arn:", "\n".join(logs.output) + str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)

    def test_estado_ausente_com_403_conta_como_ok(self):
        # sem s3:ListBucket, o S3 responde AccessDenied para objeto inexistente
        c = Cenario()
        c.s3.codigo_ausente = "AccessDenied"
        c.manifest_com_idade(T0, 45)
        self.assertEqual(c.rodar(T0), "avisado")
        self.assertEqual(len(c.enviadas), 1)

    def test_lembrete_antes_de_3_h_nao_sai(self):  # AVI-03
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        c.rodar(T0)
        self.assertEqual(c.rodar(T0 + timedelta(hours=2, minutes=59)), "sem_aviso")
        self.assertEqual(c.rodar(T0 + timedelta(hours=3)), "avisado")
        self.assertEqual(len(c.enviadas), 2)

    def test_segredos_so_lidos_quando_ha_aviso(self):
        c = Cenario()
        c.manifest_com_idade(T0, 5)
        c.rodar(T0)
        self.assertEqual(c.segredos_lidos, 0)


class Duracao(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(handler.duracao(timedelta(minutes=45)), "45 min")
        self.assertEqual(handler.duracao(timedelta(minutes=59, seconds=59)), "59 min")
        self.assertEqual(handler.duracao(timedelta(hours=1)), "1h00")
        self.assertEqual(handler.duracao(timedelta(hours=1, minutes=40)), "1h40")
        self.assertEqual(handler.duracao(timedelta(hours=26, minutes=5)), "26h05")

    def test_recuperacao_menos_de_1_h(self):
        c = Cenario()
        c.http = (403, b"")
        c.manifest_com_idade(T0, 5)
        c.rodar(T0)
        c.http = (200, b'{"versao": 1}')
        c.rodar(T0 + timedelta(minutes=20))
        self.assertEqual(c.enviadas[1], "✅ Besave: site atualizado de novo (parado por 20 min)")


class FalhaTelegram(unittest.TestCase):
    def test_estado_nao_avanca_e_proxima_tenta_de_novo(self):  # AVI-06
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        c.telegram_falha = True
        with self.assertLogs("vigia", "ERROR"):
            self.assertEqual(c.rodar(T0), "falha_envio")
        self.assertEqual(c.s3.puts, [])
        c.telegram_falha = False
        self.assertEqual(c.rodar(T0 + timedelta(minutes=10)), "avisado")
        self.assertEqual(len(c.enviadas), 1)
        self.assertEqual(c.s3.estado()["situacao"], "alerta")

    def test_recuperacao_falhando_mantem_alerta(self):
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        c.rodar(T0)
        c.manifest_com_idade(T0, 1)
        c.telegram_falha = True
        self.assertEqual(c.rodar(T0 + timedelta(minutes=10)), "falha_envio")
        self.assertEqual(c.s3.estado()["situacao"], "alerta")
        c.telegram_falha = False
        c.rodar(T0 + timedelta(minutes=20))
        self.assertTrue(c.enviadas[-1].startswith("✅ Besave: site atualizado de novo"))

    def test_falha_no_ssm_nao_avanca(self):
        c = Cenario()
        c.manifest_com_idade(T0, 45)

        def sem_segredo():
            raise ErroCliente("ParameterNotFound")

        resultado = handler.executar(c.s3, c.http_get, sem_segredo, c.enviar, T0, CFG)
        self.assertEqual(resultado, "falha_envio")
        self.assertEqual(c.s3.puts, [])


class EnviarTelegramReal(unittest.TestCase):
    def resposta(self, corpo):
        r = mock.MagicMock()
        r.__enter__.return_value.read.return_value = corpo
        return r

    def test_post_para_send_message(self):
        with mock.patch("urllib.request.urlopen", return_value=self.resposta(b'{"ok": true}')) as urlopen:
            handler.enviar_telegram(TOKEN, CHAT, "oi")
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, f"https://api.telegram.org/bot{TOKEN}/sendMessage")
        self.assertEqual(json.loads(req.data), {"chat_id": CHAT, "text": "oi"})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)

    def test_ok_false_e_falha(self):
        with mock.patch("urllib.request.urlopen", return_value=self.resposta(b'{"ok": false}')):
            with self.assertRaises(Exception):
                handler.enviar_telegram(TOKEN, CHAT, "oi")

    def test_log_de_falha_sem_token_nem_chat(self):  # AVI-08
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        erro = urllib.error.HTTPError(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 401, "Unauthorized", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            with self.assertLogs("vigia", "INFO") as logs:
                r = handler.executar(c.s3, c.http_get, c.segredos, handler.enviar_telegram, T0, CFG)
        self.assertEqual(r, "falha_envio")
        texto = "\n".join(logs.output)
        self.assertIn("401", texto)
        self.assertNotIn(TOKEN, texto)
        self.assertNotIn("SEGREDO", texto)
        self.assertNotIn(CHAT, texto)


class Mensagens(unittest.TestCase):
    def test_sem_segredo_nem_arn_nem_url(self):  # AVI-08
        c = Cenario()
        c.manifest_com_idade(T0, 45)
        c.http = (403, b"")
        c.rodar(T0)
        c.rodar(T0 + timedelta(hours=3))
        c.manifest_com_idade(T0 + timedelta(hours=4), 1)
        c.http = (200, b'{"versao": 1}')
        c.rodar(T0 + timedelta(hours=4))
        self.assertEqual(len(c.enviadas), 3)
        for m in c.enviadas:
            self.assertNotIn(TOKEN, m)
            self.assertNotIn(CHAT, m)
            self.assertNotIn("arn:", m)
            self.assertNotIn("http", m.lower().replace("http 403", ""))

    def test_horario_em_brasilia(self):  # AVI-07
        c = Cenario()
        c.manifest_com_idade(T0, 45)  # 14:15 UTC = 11:15 em Brasília
        c.rodar(T0)
        self.assertIn("11:15", c.enviadas[0])
        self.assertNotIn("14:15", c.enviadas[0])


class LambdaHandler(unittest.TestCase):
    def test_monta_clientes_e_le_parametros(self):
        s3 = S3Memoria()
        s3.gravar("manifest.json", b"{}", datetime.now(timezone.utc) - timedelta(hours=2))
        ssm = mock.MagicMock()
        ssm.get_parameter.side_effect = lambda Name, WithDecryption: {
            "Parameter": {"Value": {"/besave/telegram/token": TOKEN, "/besave/telegram/chat_id": CHAT}[Name]}
        }
        boto3 = mock.MagicMock()
        boto3.client.side_effect = lambda nome: {"s3": s3, "ssm": ssm}[nome]
        ambiente = {
            "BUCKET": "besave-site", "URL_MANIFEST": URL, "LIMIAR_MIN": "30",
            "PARAM_TOKEN": "/besave/telegram/token", "PARAM_CHAT_ID": "/besave/telegram/chat_id",
        }
        enviadas = []
        with mock.patch.dict("sys.modules", {"boto3": boto3}), \
                mock.patch.dict("os.environ", ambiente, clear=True), \
                mock.patch.object(handler, "http_get", return_value=(200, b'{"versao": 1}')), \
                mock.patch.object(handler, "enviar_telegram", lambda t, c, m: enviadas.append((t, c, m))):
            r = handler.lambda_handler({}, None)
        self.assertEqual(r, {"resultado": "avisado"})
        self.assertEqual(enviadas[0][:2], (TOKEN, CHAT))
        self.assertTrue(all(c.kwargs["WithDecryption"] for c in ssm.get_parameter.call_args_list))


if __name__ == "__main__":
    unittest.main()
