# Lancador da captura do WhatsApp.
#
# Uso (uma linha, do diretorio do projeto):
#     .\iniciar_captura.ps1
#
# Existe porque o lancamento a mao ja falhou 3x (14/07, 30/07, 04/08). Em 04/08 o
# bloco multi-linha com backtick perdeu o -ArgumentList no caminho ate o shell e
# subiu DOIS python.exe SEM argumento nenhum: REPL interativo girando em loop,
# 15 MB de traceback em 6 min, ZERO captura. Um arquivo .ps1 nao tem continuacao
# de linha nem citacao para o shell mastigar.
#
# O que ele garante ANTES de subir:
#   1. nenhum run_captura.py vivo   (lancar o 2o MATA o 1o - armadilha de 03/08 21:26)
#   2. nenhum chrome.exe segurando o perfil user_data
#   3. contador do config nao esta atrasado (senao REEMITE ID_OFERTA)
# E DEPOIS de subir:
#   4. o processo continua vivo e recebeu mesmo o run_captura.py na linha de comando
#      (a falha exata de 04/08)

$ErrorActionPreference = 'Stop'

$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Py = Join-Path $Raiz '.venv\Scripts\python.exe'

function Falhar($msg) {
    Write-Host ""
    Write-Host "ABORTADO: $msg" -ForegroundColor Red
    exit 1
}

Write-Host "=== Lancador da captura - $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss') ==="

if (-not (Test-Path $Py)) { Falhar "python do venv nao encontrado em $Py" }

# --- 1. outro run vivo? -------------------------------------------------------
$vivos = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
    Where-Object { $_.CommandLine -match 'run_captura\.py' })
if ($vivos.Count -gt 0) {
    Write-Host "Ja existe captura rodando:" -ForegroundColor Yellow
    $vivos | ForEach-Object { Write-Host "  PID $($_.ProcessId)  desde $($_.CreationDate)" }
    Falhar "lancar um 2o run MATA o browser do 1o e ele fica girando em falso. Encerre o atual primeiro."
}

# --- 2. Chrome segurando o perfil? -------------------------------------------
$chromes = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object { $_.CommandLine -match 'AgenteCapturaWhatsapp' })
if ($chromes.Count -gt 0) {
    Write-Host "Sobraram $($chromes.Count) chrome.exe do perfil do projeto:" -ForegroundColor Yellow
    $chromes | ForEach-Object { Write-Host "  PID $($_.ProcessId)" }
    Falhar "o perfil user_data esta travado. Encerre esses processos e tente de novo."
}

# --- 3. contador atrasado? ----------------------------------------------------
Write-Host ""
Write-Host "--- conferindo o contador (config x CSV x Oracle) ---"
& $Py (Join-Path $Raiz 'diag\checa_contador.py')
if ($LASTEXITCODE -ne 0) {
    Falhar "contador atrasado - corrija o config (com backup) antes de relancar."
}

# --- 4. nome do log (nao reaproveita arquivo de run anterior) -----------------
$base = Join-Path $Raiz ("run_captura_" + (Get-Date -Format 'dd_MM'))
$log = "$base.log"
foreach ($sufixo in 'b','c','d','e','f','g','h') {
    if (-not (Test-Path $log)) { break }
    $log = "${base}_$sufixo.log"
}
if (Test-Path $log) { Falhar "muitos logs para hoje - limpe os antigos." }
$err = "$log.err"

# --- 5. lancar ----------------------------------------------------------------
Write-Host ""
Write-Host "Lancando... log: $(Split-Path -Leaf $log)"
$proc = Start-Process -FilePath $Py -ArgumentList '-u','run_captura.py' -WorkingDirectory $Raiz -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Minimized -PassThru

# --- 6. conferir que subiu DE VERDADE ----------------------------------------
Start-Sleep -Seconds 8

$info = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue
if ($null -eq $info) {
    Write-Host ""
    Write-Host "O processo MORREU nos primeiros 8s. Ultimas linhas do .err:" -ForegroundColor Red
    if (Test-Path $err) { Get-Content $err -Tail 20 }
    Falhar "captura nao subiu."
}
if ($info.CommandLine -notmatch 'run_captura\.py') {
    Stop-Process -Id $proc.Id -Force
    Write-Host "Linha de comando recebida: $($info.CommandLine)" -ForegroundColor Red
    Falhar "o python subiu SEM o script (REPL interativo) - matei o processo. Foi a falha de 04/08."
}

$tam = 0
if (Test-Path $log) { $tam = (Get-Item $log).Length }

Write-Host ""
Write-Host "OK - captura rodando." -ForegroundColor Green
Write-Host "  PID : $($proc.Id)"
Write-Host "  log : $log  ($tam bytes ate agora)"
Write-Host "  err : $err"
Write-Host ""
Write-Host "Acompanhar:  Get-Content '$log' -Wait -Tail 20"
Write-Host "Encerrar  :  .\encerrar_captura.ps1"
