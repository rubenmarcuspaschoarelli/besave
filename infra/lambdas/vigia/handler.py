"""Vigia externo do site (BSV-15).

Confere o frescor do manifest.json no S3 e a disponibilidade pelo CloudFront, e avisa no Telegram
na transição para problema, a cada 3 h enquanto durar e na volta. Só stdlib + boto3 do runtime.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

log = logging.getLogger("vigia")
log.setLevel(logging.INFO)

BRASILIA = timezone(timedelta(hours=-3))
LEMBRETE = timedelta(hours=3)
TIMEOUT_S = 10
CHAVE_MANIFEST = "manifest.json"
CHAVE_ESTADO = "_estado/vigia.json"


@dataclass(frozen=True)
class Config:
    bucket: str
    url_manifest: str
    limiar_min: int
    param_token: str
    param_chat_id: str

    @staticmethod
    def do_ambiente(env):
        return Config(
            bucket=env["BUCKET"],
            url_manifest=env["URL_MANIFEST"],
            limiar_min=int(env.get("LIMIAR_MIN", "30")),
            param_token=env["PARAM_TOKEN"],
            param_chat_id=env["PARAM_CHAT_ID"],
        )


@dataclass(frozen=True)
class Problema:
    texto: str
    inicio: datetime


def duracao(d):
    minutos = int(d.total_seconds() // 60)
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60}h{minutos % 60:02d}"


def hora(t):
    return t.astimezone(BRASILIA).strftime("%H:%M")


def iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ler_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def codigo_erro(e):
    """Código do ClientError do botocore, ou o nome da exceção. Nunca a mensagem inteira."""
    resposta = getattr(e, "response", None)
    if isinstance(resposta, dict):
        return str(resposta.get("Error", {}).get("Code", type(e).__name__))
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    return type(e).__name__


def verificar_frescor(s3, cfg, agora):
    try:
        modificado = s3.head_object(Bucket=cfg.bucket, Key=CHAVE_MANIFEST)["LastModified"]
    except Exception as e:
        log.error("HeadObject de manifest.json falhou: %s", codigo_erro(e))
        return Problema("frescor: manifest.json inacessível no S3", agora)
    idade = agora - modificado
    if idade > timedelta(minutes=cfg.limiar_min):
        return Problema(f"frescor: site sem atualização há {duracao(idade)} (manifest.json de {hora(modificado)})", modificado)
    return None


def verificar_disponibilidade(http, cfg, agora):
    def problema(motivo):
        return Problema(f"disponibilidade: CloudFront {motivo}", agora)

    try:
        status, corpo = http(cfg.url_manifest, TIMEOUT_S)
    except TimeoutError:
        return problema(f"sem resposta (timeout de {TIMEOUT_S} s)")
    except Exception as e:
        return problema(f"com erro de rede ({type(e).__name__})")
    if status != 200:
        return problema(f"respondeu HTTP {status} em /manifest.json")
    try:
        doc = json.loads(corpo)
    except ValueError:
        doc = None
    if not isinstance(doc, dict) or "versao" not in doc:
        return problema("devolveu manifest.json sem versao")
    return None


def ler_estado(s3, cfg):
    """Estado gravado, ou {} (= ok). Sem s3:ListBucket, objeto ausente vem como AccessDenied."""
    try:
        corpo = s3.get_object(Bucket=cfg.bucket, Key=CHAVE_ESTADO)["Body"].read()
    except Exception as e:
        codigo = codigo_erro(e)
        if codigo not in ("NoSuchKey", "404", "AccessDenied", "403"):
            raise
        return {}
    try:
        estado = json.loads(corpo)
        if estado["situacao"] not in ("ok", "alerta"):
            raise ValueError(estado["situacao"])
        ler_iso(estado["desde"])
        ler_iso(estado["ultimo_aviso"])
        return estado
    except (ValueError, KeyError, TypeError):
        log.error("estado em %s inválido; tratado como ok", CHAVE_ESTADO)
        return {}


def decidir(estado, problemas, agora):
    """(mensagem, novo_estado), ou (None, None) quando não há aviso a dar."""
    em_alerta = estado.get("situacao") == "alerta"
    if problemas:
        linhas = "\n".join(f"- {p.texto}" for p in problemas)
        if not em_alerta:
            desde = min(p.inicio for p in problemas)
            novo = {"situacao": "alerta", "desde": iso(desde), "ultimo_aviso": iso(agora)}
            return f"⚠️ Besave: problema no site\n{linhas}", novo
        if agora - ler_iso(estado["ultimo_aviso"]) >= LEMBRETE:
            desde = ler_iso(estado["desde"])
            texto = f"⏰ Besave: site ainda com problema, há {duracao(agora - desde)} (desde {hora(desde)})\n{linhas}"
            return texto, {**estado, "ultimo_aviso": iso(agora)}
        return None, None
    if em_alerta:
        parado = duracao(agora - ler_iso(estado["desde"]))
        novo = {"situacao": "ok", "desde": iso(agora), "ultimo_aviso": iso(agora)}
        return f"✅ Besave: site atualizado de novo (parado por {parado})", novo
    return None, None


def executar(s3, http, segredos, enviar, agora, cfg):
    problemas = [p for p in (verificar_frescor(s3, cfg, agora), verificar_disponibilidade(http, cfg, agora)) if p]
    for p in problemas:
        log.info("problema: %s", p.texto)
    mensagem, novo = decidir(ler_estado(s3, cfg), problemas, agora)
    if mensagem is None:
        return "sem_aviso"
    try:
        token, chat_id = segredos()
        enviar(token, chat_id, mensagem)
    except Exception as e:
        log.error("envio ao Telegram falhou (%s); estado mantido, tenta no próximo ciclo", codigo_erro(e))
        return "falha_envio"
    s3.put_object(
        Bucket=cfg.bucket,
        Key=CHAVE_ESTADO,
        Body=json.dumps(novo).encode(),
        ContentType="application/json",
        CacheControl="no-store",
    )
    log.info("aviso enviado; situacao=%s", novo["situacao"])
    return "avisado"


def http_get(url, timeout):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        e.close()
        return e.code, b""
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise TimeoutError() from None
        raise


def enviar_telegram(token, chat_id, texto):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": texto}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        if json.loads(r.read()).get("ok") is not True:
            raise RuntimeError("Telegram respondeu ok != true")


def lambda_handler(event, context):
    import boto3  # do runtime da Lambda; os testes não dependem dele

    cfg = Config.do_ambiente(os.environ)
    s3 = boto3.client("s3")
    ssm = boto3.client("ssm")

    def segredos():
        ler = lambda nome: ssm.get_parameter(Name=nome, WithDecryption=True)["Parameter"]["Value"]
        return ler(cfg.param_token), ler(cfg.param_chat_id)

    agora = datetime.now(timezone.utc)
    return {"resultado": executar(s3, http_get, segredos, enviar_telegram, agora, cfg)}
