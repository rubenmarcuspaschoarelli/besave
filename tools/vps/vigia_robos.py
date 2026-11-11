#!/usr/bin/env python3
"""
Vigia externo dos robos de captura (BSV-57). So stdlib; roda a cada 5 min por
besave-vigia-robos.timer (unidade --user do `besave`).

Para cada robo (lojas, whatsapp), lendo o batimento.json que o proprio robo grava so com progresso:
  1. unidade parada de proposito (inactive) -> nada; `failed` -> avisa o operador, NUNCA reinicia;
  2. reinicio diario do WhatsApp em andamento -> nada (aquele script confere e avisa sozinho);
  3. `agora > prazo` ou pid do batimento fora do scope do robo -> PARADO;
  4. parado com QR pendente ou `ABORTADO:` no log mais recente -> avisa o operador, NAO reinicia;
     grupo em `grupos_falhando` ha 2 h ou mais e laco de partidas (3 logs em 30 min sem `Grupo aberto`)
     -> operador, sem reinicio;
  5. senao `systemctl --user restart <unidade>` (no maximo 2 por robo em 60 min) e aviso;
  6. batimento novo depois de um aviso -> "voltou (parado por N min)".

So age pela unidade: nunca `kill` nem busca de processo por nome. Os pids do robo vem do `cgroup.procs`
do scope (o MainPID da unidade e o tmux). Falha do vigia (log ilegivel, Telegram fora) so vai ao journal.
Token e chat vem de TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID do worker.env; nada disso entra em log ou mensagem.

Env: BESAVE_TOOLS, BESAVE_VIGIA_ESTADO, BESAVE_WORKER_ENV, BESAVE_GRUPO_FALHA_HORAS (2),
BESAVE_LOG_DIAS (14), BESAVE_LOG_MB (50).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

PARTIDA_TOLERANCIA = timedelta(minutes=10)
MAX_REINICIOS = 2
JANELA_REINICIOS = timedelta(minutes=60)
LEMBRETE = timedelta(hours=2)
LACO_LOGS = 3
LACO_JANELA = timedelta(minutes=30)
TIMEOUT_ENVIO_S = 10
TIMEOUT_SYSTEMCTL_S = 150      # um restart da unidade das lojas espera o stop (ate ~50 s) e o ExecStartPre
CAUDA_BYTES = 65536
LINHAS_ABORTADO = 20
LINHA_MAX = 200

SAUDAVEL, PARADO, INDETERMINADO = "saudavel", "parado", "indeterminado"

PADRAO_URL = re.compile(r"https?://\S+", re.IGNORECASE)
PADRAO_TOKEN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
PADRAO_LOG_PARTIDA = re.compile(r"^run_captura_(\d{2})_(\d{2})_(\d{2})(\d{2})(\d{2})(?:_\d+)?\.log$")
PADRAO_COPIA_LOJAS = re.compile(r"^main_monitorar_\d{8}\.log$")
MARCA_BANNER_QR = "Aguardando o WhatsApp Web carregar"
MARCA_AUTENTICADO = "Sessao autenticada"
MARCA_GRUPO_ABERTO = "Grupo aberto"


def log(texto: str) -> None:
    print(f"[vigia] {redigir(texto)}", flush=True)


_SEGREDOS: list[str] = []


def redigir(texto: str) -> str:
    """Tira token (o conhecido e qualquer coisa com cara de token) e URL de qualquer texto que saia daqui."""
    for segredo in _SEGREDOS:
        if segredo:
            texto = texto.replace(segredo, "REDACTED")
    texto = PADRAO_TOKEN.sub("REDACTED", texto)
    return PADRAO_URL.sub("[url]", texto)


# ----------------------------------------------------------------------------------------------- robos


@dataclass(frozen=True)
class Robo:
    nome: str
    unidade: str
    scope: str
    pasta: Path
    reinicio: str | None = None

    @property
    def batimento(self) -> Path:
        return self.pasta / "conf" / "batimento.json"

    @property
    def pasta_log(self) -> Path:
        return self.pasta / "log" if self.nome == "whatsapp" else self.pasta / "destino" / "log"


def robos_padrao(tools: Path) -> list[Robo]:
    return [
        Robo("lojas", "besave-captura-lojas.service", "besave-lojas-robo.scope", tools / "capture-store-pages"),
        Robo("whatsapp", "besave-captura-whatsapp.service", "besave-whatsapp-robo.scope",
             tools / "capture-chat-groups", reinicio="besave-reinicio-whatsapp.service"),
    ]


def _rodar_real(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SYSTEMCTL_S, check=False)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError) as e:
        log(f"falha ao rodar {cmd[0]} ({type(e).__name__})")
        return 127, ""


@dataclass
class Ambiente:
    """Tudo o que o vigia toca fora do proprio processo; os testes trocam cada peca."""

    robos: list[Robo]
    estado_path: Path
    agora: Callable[[], datetime] = lambda: datetime.now(UTC)
    rodar: Callable[[list], tuple] = _rodar_real
    enviar: Callable[[str], None] | None = None            # enviar(texto); None = so journal
    cgroup_raiz: Path = Path("/sys/fs/cgroup")
    proc_raiz: Path = Path("/proc")
    tz: object = None                            # fuso dos nomes de log (None = o do sistema)
    grupo_falha: timedelta = timedelta(hours=2)
    log_dias: int = 14
    log_mb: int = 50
    extras: dict = field(default_factory=dict)

    def systemctl(self, *args: str) -> tuple[int, str]:
        return self.rodar(["systemctl", "--user", *args])


# ------------------------------------------------------------------------------------- leitura do sistema


def estado_unidade(amb: Ambiente, unidade: str) -> str:
    rc, out = amb.systemctl("is-active", unidade)
    texto = out.strip()
    return texto if texto else ("unknown" if rc != 0 else "inactive")


def pids_do_scope(amb: Ambiente, scope: str) -> set[int]:
    _, out = amb.systemctl("show", "-p", "ControlGroup", "--value", scope)
    cg = out.strip()
    if not cg or cg == "/":
        return set()
    try:
        texto = (amb.cgroup_raiz / cg.lstrip("/") / "cgroup.procs").read_text(encoding="utf-8")
    except OSError:
        return set()
    return {int(x) for x in texto.split() if x.isdigit()}


def _epoch_para_dt(texto: str) -> datetime | None:
    t = texto.strip()
    if t.startswith("@") and t[1:].isdigit() and int(t[1:]) > 0:
        return datetime.fromtimestamp(int(t[1:]), UTC)
    return None


def inicio_unidade(amb: Ambiente, nome: str) -> datetime | None:
    """Quando a unidade/scope ficou ativo (ActiveEnterTimestamp em epoch). None se nao souber."""
    _, out = amb.systemctl("show", "-p", "ActiveEnterTimestamp", "--timestamp=unix", "--value", nome)
    return _epoch_para_dt(out)


def memoria_scope_mb(amb: Ambiente, scope: str) -> int | None:
    _, out = amb.systemctl("show", "-p", "MemoryCurrent", "--value", scope)
    t = out.strip()
    return int(t) // (1024 * 1024) if t.isdigit() else None


def rss_maior_chrome_mb(amb: Ambiente, pids: set[int]) -> int | None:
    """RSS do maior processo `chrome` entre os pids do scope (nao por padrao de nome na maquina toda)."""
    maior = None
    for pid in pids:
        try:
            comm = (amb.proc_raiz / str(pid) / "comm").read_text(encoding="utf-8").strip().lower()
            if "chrome" not in comm:
                continue
            status = (amb.proc_raiz / str(pid) / "status").read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^VmRSS:\s+(\d+)\s*kB", status, re.MULTILINE)
        if m:
            kb = int(m.group(1))
            maior = kb if maior is None or kb > maior else maior
    return None if maior is None else maior // 1024


# ---------------------------------------------------------------------------------------- batimento


@dataclass
class Batimento:
    pid: int
    em: datetime
    prazo: datetime
    fase: str
    grupos_falhando: dict


def _iso_para_dt(valor) -> datetime:
    return datetime.strptime(str(valor), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def ler_batimento(caminho: Path) -> Batimento | None:
    try:
        d = json.loads(caminho.read_text(encoding="utf-8"))
        grupos = d.get("grupos_falhando") or {}
        return Batimento(
            pid=int(d["pid"]), em=_iso_para_dt(d["em"]), prazo=_iso_para_dt(d["prazo"]),
            fase=str(d.get("fase") or ""),
            grupos_falhando={str(k): _iso_para_dt(v) for k, v in grupos.items()},
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


# -------------------------------------------------------------------------------------------- logs


def ler_cauda(caminho: Path, n_bytes: int = CAUDA_BYTES) -> str:
    try:
        with open(caminho, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - n_bytes))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def log_mais_recente(robo: Robo) -> Path | None:
    """WhatsApp: maior mtime em log/run_captura_*.log. Lojas: destino/log/main_monitorar.log."""
    if robo.nome == "lojas":
        alvo = robo.pasta_log / "main_monitorar.log"
        return alvo if alvo.exists() else None
    try:
        logs = [p for p in robo.pasta_log.glob("run_captura_*.log") if PADRAO_LOG_PARTIDA.match(p.name)]
        return max(logs, key=lambda p: p.stat().st_mtime) if logs else None
    except OSError:
        return None


def ultima_linha_util(texto: str) -> str:
    for linha in reversed(texto.splitlines()):
        if linha.strip():
            return redigir(linha.strip())[:LINHA_MAX]
    return ""


def pede_qr(texto: str) -> bool:
    """QR pendente: o log abriu o WhatsApp Web e nao chegou em `Sessao autenticada` depois."""
    i = texto.rfind(MARCA_BANNER_QR)
    return i >= 0 and MARCA_AUTENTICADO not in texto[i:]


def tem_abortado(texto: str) -> str | None:
    linhas = [x for x in texto.splitlines() if x.strip()][-LINHAS_ABORTADO:]
    achadas = [x for x in linhas if "ABORTADO:" in x]
    return redigir(achadas[-1].strip())[:LINHA_MAX] if achadas else None


def _data_do_log(nome: str, agora_local: datetime) -> datetime | None:
    m = PADRAO_LOG_PARTIDA.match(nome)
    if not m:
        return None
    dia, mes, h, mi, s = (int(x) for x in m.groups())
    for ano in (agora_local.year, agora_local.year - 1):
        try:
            dt = datetime(ano, mes, dia, h, mi, s, tzinfo=agora_local.tzinfo)
        except ValueError:
            return None
        if dt <= agora_local + timedelta(days=1):
            return dt
    return None


def laco_de_partidas(amb: Ambiente, robo: Robo, agora: datetime) -> int:
    """Quantos logs de partida dos ultimos 30 min, se forem 3 ou mais e nenhum tiver `Grupo aberto`; senao 0.
    A idade vem do nome do arquivo (o mtime de um log ativo engana)."""
    agora_local = agora.astimezone(amb.tz)
    recentes = []
    try:
        for p in robo.pasta_log.glob("run_captura_*.log"):
            dt = _data_do_log(p.name, agora_local)
            if dt is not None and timedelta(0) <= agora_local - dt <= LACO_JANELA:
                recentes.append(p)
    except OSError:
        return 0
    if len(recentes) < LACO_LOGS:
        return 0
    for p in recentes:
        try:
            if MARCA_GRUPO_ABERTO in p.read_text(encoding="utf-8", errors="replace"):
                return 0
        except OSError:
            continue
    return len(recentes)


# ------------------------------------------------------------------------------------------- estado


def carregar_estado(caminho: Path) -> dict:
    try:
        d = json.loads(caminho.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def salvar_estado(caminho: Path, estado: dict) -> None:
    tmp = caminho.with_name(caminho.name + ".tmp")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, caminho)
    except OSError as e:
        log(f"falha ao gravar o estado do vigia ({type(e).__name__})")


BRASILIA = timezone(timedelta(hours=-3))      # offset fixo (CLAUDE.md regra 5): o operador le Brasilia


def _brasilia(dt: datetime) -> str:
    """Horario para o operador, ex.: 11/11 08:42. O estado em JSON segue em UTC (`_iso`)."""
    return dt.astimezone(BRASILIA).strftime("%d/%m %H:%M")


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------ avisos


def avisar(amb: Ambiente, texto: str) -> None:
    texto = redigir(texto)
    print(f"[vigia] AVISO: {texto}", flush=True)
    if amb.enviar is None:
        log("Telegram nao configurado (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID); so journal.")
        return
    try:
        amb.enviar(texto)
    except Exception as e:  # noqa: BLE001
        # So o tipo: a URL da API leva o token.
        log(f"falha ao enviar ao Telegram ({type(e).__name__})")


@dataclass
class Foto:
    """O que se ve do robo ANTES do restart: depois dele o scope, os pids e o log sao outros."""

    cauda: str
    mem_mb: int | None
    rss_mb: int | None


def tirar_foto(amb: Ambiente, robo: Robo, pids: set[int], texto_log: str) -> Foto:
    return Foto(ultima_linha_util(texto_log), memoria_scope_mb(amb, robo.scope), rss_maior_chrome_mb(amb, pids))


def montar_mensagem(robo: Robo, motivo: str, acao: str, foto: Foto, titulo: str = "parado") -> str:
    linhas = [
        f"Vigia dos robos: {robo.nome} {titulo}",
        f"Motivo: {motivo}",
        f"Acao: {acao}",
        f"Ultima linha do log: {foto.cauda or '(sem log)'}",
        "Memoria do scope: " + (f"{foto.mem_mb} MB" if foto.mem_mb is not None else "n/d")
        + " | maior chrome: " + (f"{foto.rss_mb} MB" if foto.rss_mb is not None else "n/d"),
    ]
    return redigir("\n".join(linhas))


def _ocorrencia_precisa_aviso(oc: dict, assinatura: str, agora: datetime) -> str | None:
    """None = nada a dizer; 'novo', 'mudou' ou 'lembrete'."""
    if not oc:
        return "novo"
    if oc.get("sig") != assinatura:
        return "mudou"
    if agora - _iso_para_dt(oc["avisado_em"]) >= LEMBRETE:
        return "lembrete"
    return None


def _abrir_ou_atualizar(ocorrencias: dict, chave: str, assinatura: str, desde: datetime, agora: datetime) -> str | None:
    """Aplica a regra 1 aviso por ocorrencia + lembrete a cada 2 h. Devolve o tipo de aviso ou None."""
    atual = ocorrencias.get(chave) or {}
    tipo = _ocorrencia_precisa_aviso(atual, assinatura, agora)
    if tipo is None:
        return None
    ocorrencias[chave] = {
        "desde": atual.get("desde") or _iso(desde),
        "aberta_em": atual.get("aberta_em") or _iso(agora),
        "avisado_em": _iso(agora),
        "ultima_acao": _iso(agora),
        "sig": assinatura,
    }
    return tipo


# ------------------------------------------------------------------------------------------ decisao


def avaliar(amb: Ambiente, robo: Robo, bat: Batimento | None, pids: set[int], agora: datetime):
    """Devolve (status, motivo, desde). `desde` = ultimo instante em que o robo estava bem (ou da deteccao)."""
    if bat is not None and bat.pid in pids:
        if agora > bat.prazo:                      # prazo == agora ainda nao e parado
            minutos = int((agora - bat.em).total_seconds() // 60)
            return PARADO, f"sem batimento ha {minutos} min (fase: {bat.fase or 'n/d'})", bat.em
        return SAUDAVEL, "", bat.em
    if pids:
        # processo vivo no scope, mas o batimento e de outro pid (ou nao existe): partida recente ou parado
        ref = inicio_unidade(amb, robo.scope)
        if ref is None and bat is not None:
            ref = bat.prazo
        if ref is not None and agora - ref > PARTIDA_TOLERANCIA:
            minutos = int((agora - ref).total_seconds() // 60)
            return PARADO, f"processo novo sem batimento ha {minutos} min", ref
        return INDETERMINADO, "partida recente", agora
    # unidade ativa e nenhum processo no scope
    if bat is not None:
        if agora > bat.prazo:
            minutos = int((agora - bat.em).total_seconds() // 60)
            return PARADO, f"processo do robo sumiu; ultimo batimento ha {minutos} min", bat.em
        return INDETERMINADO, "processo sumiu; esperando o prazo", agora
    ref = inicio_unidade(amb, robo.unidade)
    if ref is not None and agora - ref > PARTIDA_TOLERANCIA:
        minutos = int((agora - ref).total_seconds() // 60)
        return PARADO, f"sem processo nem batimento ha {minutos} min", ref
    return INDETERMINADO, "sem batimento ainda", agora


def _reinicios_recentes(registro: dict, agora: datetime) -> list[str]:
    return [t for t in registro.get("reinicios", []) if agora - _iso_para_dt(t) < JANELA_REINICIOS]


def vigiar_robo(amb: Ambiente, robo: Robo, estado: dict, agora: datetime) -> None:
    registro = estado.setdefault("robos", {}).setdefault(robo.nome, {})
    ocorrencias = registro.setdefault("ocorrencias", {})
    registro["reinicios"] = _reinicios_recentes(registro, agora)

    unidade = estado_unidade(amb, robo.unidade)
    if unidade == "inactive":                      # parado de proposito: nunca religar, nada a dizer
        ocorrencias.clear()
        return
    if unidade == "activating":
        return
    if robo.reinicio and estado_unidade(amb, robo.reinicio) in ("activating", "active"):
        return

    pids = pids_do_scope(amb, robo.scope)
    if unidade == "failed":                        # o systemd ja desistiu: religar nao e papel do vigia
        _avisar_unidade_failed(amb, robo, ocorrencias, pids, agora)
        return
    ocorrencias.pop("unidade", None)
    bat = ler_batimento(robo.batimento)
    status, motivo, desde = avaliar(amb, robo, bat, pids, agora)
    alvo_log = log_mais_recente(robo)
    texto_log = ler_cauda(alvo_log) if alvo_log is not None else ""
    foto = tirar_foto(amb, robo, pids, texto_log)     # antes de qualquer restart

    laco = laco_de_partidas(amb, robo, agora) if robo.nome == "whatsapp" else 0
    operador = None
    if laco:
        operador = f"{laco} partidas em 30 min sem abrir grupo (laco de partidas)"
    elif status == PARADO:
        if robo.nome == "whatsapp" and pede_qr(texto_log):
            operador = "o WhatsApp pede QR Code (reiniciar nao resolve)"
        else:
            abortado = tem_abortado(texto_log)
            if abortado:
                operador = f"partida abortada: {abortado}"

    if laco or status == PARADO:
        recentes = registro["reinicios"]
        if operador is None and len(recentes) >= MAX_REINICIOS:
            operador = f"{len(recentes)} reinicios nos ultimos 60 min; reiniciar de novo nao esta resolvendo"
        if operador is not None:
            acao, assinatura = "nenhuma (precisa de operador)", "operador"
        else:
            k = len(recentes) + 1
            acao, assinatura = f"reiniciado {k}/{MAX_REINICIOS}", f"reinicio{k}"
        tipo = _abrir_ou_atualizar(ocorrencias, "parado", assinatura, desde, agora)
        if operador is None:
            rc, _ = amb.systemctl("restart", robo.unidade)
            registro["reinicios"] = recentes + [_iso(agora)]
            if rc != 0:
                acao += " (o restart falhou)"
        if tipo is not None:
            rotulo = {"novo": "parado", "mudou": "parado", "lembrete": "continua parado"}[tipo]
            msg = montar_mensagem(robo, operador or motivo, acao, foto, rotulo)
            avisar(amb, msg)
        return

    if status == SAUDAVEL:
        oc = ocorrencias.get("parado")
        if oc and bat is not None and bat.em > _iso_para_dt(oc["ultima_acao"]):
            minutos = int((bat.em - _iso_para_dt(oc["desde"])).total_seconds() // 60)
            del ocorrencias["parado"]
            avisar(amb, f"Vigia dos robos: {robo.nome} voltou (parado por {minutos} min).")
        _vigiar_grupos(amb, robo, bat, ocorrencias, agora)


def _avisar_unidade_failed(amb: Ambiente, robo: Robo, ocorrencias: dict, pids: set[int], agora: datetime) -> None:
    """Unidade `failed`: 1 aviso de operador por ocorrencia, lembrete a cada 2 h, nunca restart."""
    tipo = _abrir_ou_atualizar(ocorrencias, "unidade", "operador", agora, agora)
    if tipo is None:
        return
    alvo_log = log_mais_recente(robo)
    foto = tirar_foto(amb, robo, pids, ler_cauda(alvo_log) if alvo_log is not None else "")
    rotulo = "continua em failed" if tipo == "lembrete" else "em failed"
    avisar(amb, montar_mensagem(robo, "unidade failed: o systemd ja desistiu",
                                "nenhuma (precisa de operador)", foto, rotulo))


def _vigiar_grupos(amb: Ambiente, robo: Robo, bat: Batimento, ocorrencias: dict, agora: datetime) -> None:
    for nome, desde in bat.grupos_falhando.items():
        if agora - desde < amb.grupo_falha:
            continue
        tipo = _abrir_ou_atualizar(ocorrencias, f"grupo:{nome}", "operador", desde, agora)
        if tipo is not None:
            horas = int((agora - desde).total_seconds() // 3600)
            texto = (f"Vigia dos robos: grupo {nome!r} do WhatsApp falha em todas as voltas desde "
                     f"{_brasilia(desde)} (Brasilia, ~{horas} h); o nome mudou ou o numero saiu do grupo? "
                     "Acao: nenhuma (precisa de operador); o robo segue capturando os outros grupos.")
            if tipo == "lembrete":
                texto = "Lembrete. " + texto
            avisar(amb, texto)
    for chave in [c for c in ocorrencias if c.startswith("grupo:")]:
        nome = chave[len("grupo:"):]
        if nome not in bat.grupos_falhando:
            minutos = int((bat.em - _iso_para_dt(ocorrencias[chave]["desde"])).total_seconds() // 60)
            del ocorrencias[chave]
            avisar(amb, f"Vigia dos robos: grupo {nome!r} do WhatsApp voltou a abrir (falhou por {minutos} min).")


# ------------------------------------------------------------------------------------------ rotacao


def rotacionar_logs(amb: Ambiente, estado: dict, agora: datetime) -> None:
    """Uma vez por dia (marca no estado). So `run_captura_*.log` e `main_monitorar*.log`, so nas pastas de log."""
    hoje = agora.astimezone(amb.tz).strftime("%Y-%m-%d")
    if estado.get("rotacao_em") == hoje:
        return
    estado["rotacao_em"] = hoje
    limite = agora - timedelta(days=amb.log_dias)
    apagados = 0
    for robo in amb.robos:
        try:
            if robo.nome == "whatsapp":
                logs = [p for p in robo.pasta_log.glob("run_captura_*.log") if PADRAO_LOG_PARTIDA.match(p.name)]
                recente = max(logs, key=lambda p: p.stat().st_mtime) if logs else None
                for p in logs:
                    if p != recente and datetime.fromtimestamp(p.stat().st_mtime, UTC) < limite:
                        p.unlink()
                        apagados += 1
            else:
                principal = robo.pasta_log / "main_monitorar.log"
                if principal.exists() and principal.stat().st_size > amb.log_mb * 1024 * 1024:
                    copia = robo.pasta_log / f"main_monitorar_{agora.astimezone(amb.tz):%Y%m%d}.log"
                    with open(principal, "rb") as src, open(copia, "ab") as dst:
                        shutil.copyfileobj(src, dst)
                    with open(principal, "r+b") as f:   # mesmo inode: o `tee -a` do robo segue escrevendo
                        f.truncate(0)
                    log(f"main_monitorar.log copiado para {copia.name} e truncado")
                for p in robo.pasta_log.glob("main_monitorar_*.log"):
                    if PADRAO_COPIA_LOJAS.match(p.name) and datetime.fromtimestamp(p.stat().st_mtime, UTC) < limite:
                        p.unlink()
                        apagados += 1
        except OSError as e:
            log(f"rotacao de logs de {robo.nome} falhou ({type(e).__name__})")
    log(f"rotacao de logs: {apagados} arquivo(s) apagado(s)")


# --------------------------------------------------------------------------------------- execucao


def executar(amb: Ambiente) -> int:
    estado = carregar_estado(amb.estado_path)
    agora = amb.agora()
    for robo in amb.robos:
        try:
            vigiar_robo(amb, robo, estado, agora)
        except Exception as e:  # noqa: BLE001
            log(f"falha ao vigiar {robo.nome} ({type(e).__name__}: {e})")
        salvar_estado(amb.estado_path, estado)     # o restart ja feito nao se perde se o vigia for morto depois
    try:
        rotacionar_logs(amb, estado, agora)
    except Exception as e:  # noqa: BLE001
        log(f"falha na rotacao de logs ({type(e).__name__})")
    salvar_estado(amb.estado_path, estado)
    return 0


def ler_credenciais(caminho: Path) -> tuple[str, str]:
    """TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID do worker.env (KEY=VALUE, `export` e aspas aceitos)."""
    valores = {}
    try:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.removeprefix("export ").split("=", 1)
            valores[k.strip()] = v.strip().strip("'\"")
    except OSError:
        return "", ""
    return valores.get("TELEGRAM_BOT_TOKEN", ""), valores.get("TELEGRAM_CHAT_ID", "")


def enviar_telegram(token: str, chat_id: str, texto: str) -> None:
    corpo = json.dumps({"chat_id": chat_id, "text": texto}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=corpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_ENVIO_S) as r:
        r.read()


def ambiente_real(env=None) -> Ambiente:
    env = os.environ if env is None else env
    tools = Path(env.get("BESAVE_TOOLS") or Path(__file__).resolve().parent.parent)
    estado = Path(env.get("BESAVE_VIGIA_ESTADO") or Path.home() / ".local" / "state" / "besave" / "vigia_robos.json")
    token, chat = ler_credenciais(Path(env.get("BESAVE_WORKER_ENV") or "/srv/besave/worker.env"))
    _SEGREDOS[:] = [token, chat]
    amb = Ambiente(
        robos=robos_padrao(tools), estado_path=estado,
        grupo_falha=timedelta(hours=float(env.get("BESAVE_GRUPO_FALHA_HORAS") or 2)),
        log_dias=int(env.get("BESAVE_LOG_DIAS") or 14), log_mb=int(env.get("BESAVE_LOG_MB") or 50),
    )
    if token and chat:
        amb.enviar = lambda texto: enviar_telegram(token, chat, texto)
    return amb


def main() -> int:
    try:
        return executar(ambiente_real())
    except Exception as e:  # noqa: BLE001
        log(f"falha do vigia ({type(e).__name__}); nada foi derrubado")
        return 0


if __name__ == "__main__":
    sys.exit(main())
