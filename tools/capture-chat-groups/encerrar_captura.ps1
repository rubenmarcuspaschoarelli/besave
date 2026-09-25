# Encerra a captura e libera o perfil do Chrome.
#
# Uso:  .\encerrar_captura.ps1
#
# Cuidados que ele embute:
#   - filtra por 'run_captura.py' / 'AgenteCapturaWhatsapp' no CommandLine.
#     NUNCA matar todo python.exe: o CaptureAmazon (outro projeto) roda junto.
#   - matar o python NAO fecha o Chrome; sobram processos que travam o perfil
#     user_data e derrubam o proximo run.
#
# ATENCAO: Stop-Process nao roda o `finally` da captura, que e quem salva o estado.
# O contador do config fica ATRASADO em relacao ao CSV/Oracle. Por isso o
# iniciar_captura.ps1 roda o diag\checa_contador.py antes de subir o proximo run.
# Para uma parada limpa, prefira Ctrl+C na janela da captura.

$ErrorActionPreference = 'Stop'

$pythons = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
    Where-Object { $_.CommandLine -match 'run_captura\.py' })
$chromes = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object { $_.CommandLine -match 'AgenteCapturaWhatsapp' })

if ($pythons.Count -eq 0 -and $chromes.Count -eq 0) {
    Write-Host "Nada rodando - nenhum run_captura.py, nenhum chrome.exe do perfil."
    exit 0
}

Write-Host "Encerrando $($pythons.Count) python (captura) e $($chromes.Count) chrome.exe (perfil)..."
foreach ($p in $pythons) {
    Write-Host "  python PID $($p.ProcessId)"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
foreach ($c in $chromes) {
    Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

$restaPy = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
    Where-Object { $_.CommandLine -match 'run_captura\.py' }).Count
$restaCh = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object { $_.CommandLine -match 'AgenteCapturaWhatsapp' }).Count

Write-Host ""
Write-Host "Restantes: python=$restaPy  chrome=$restaCh"
if ($restaPy -eq 0 -and $restaCh -eq 0) {
    Write-Host "OK - perfil liberado."
    Write-Host "Antes de relancar, o iniciar_captura.ps1 vai conferir o contador sozinho."
} else {
    Write-Host "ATENCAO: sobrou processo - confira antes de relancar." -ForegroundColor Yellow
}
