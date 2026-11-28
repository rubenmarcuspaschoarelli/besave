<#
.SYNOPSIS
  Registra (ou remove) a tarefa "besave-captura-web" no Agendador do Windows (BSV-66).

.DESCRIPTION
  Roda "python main.py" nesta pasta nos horarios dados (padrao 08:00, 12:00 e 17:00), com o usuario
  atual e so quando ele estiver logado. PC desligado no horario = rodada perdida (sem "executar assim
  que possivel"). Sem repeticao; limite de 30 min; uma instancia por vez.

.EXAMPLE
  .\agendar.ps1
  .\agendar.ps1 -Horarios 09:00,18:00
  .\agendar.ps1 -Mostrar      # so mostra o que registraria
  .\agendar.ps1 --remover     # apaga a tarefa (tambem aceita -Remover)
#>
[CmdletBinding(PositionalBinding = $false)]
param(
    [string[]]$Horarios = @('08:00', '12:00', '17:00'),
    [string]$Python = '',
    [int]$LimiteMinutos = 30,
    [switch]$Remover,
    [switch]$Mostrar,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Resto
)

$ErrorActionPreference = 'Stop'
$Nome = 'besave-captura-web'

foreach ($a in @($Resto)) {
    if (-not $a) { continue }
    if ($a -eq '--remover') { $Remover = $true }
    else { throw "Argumento desconhecido: $a" }
}

if ($Remover) {
    if (Get-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
        Write-Host "Tarefa $Nome removida."
    } else {
        Write-Host "Tarefa $Nome nao existe."
    }
    return
}

# Com -File, "-Horarios 09:00,18:00" chega como um texto so.
$Horarios = @($Horarios | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
foreach ($h in $Horarios) {
    if ($h -notmatch '^([01]\d|2[0-3]):[0-5]\d$') { throw "Horario invalido: $h (use HH:MM)" }
}
if ($LimiteMinutos -lt 1) { throw "LimiteMinutos invalido: $LimiteMinutos" }

$Pasta = $PSScriptRoot
if (-not $Python) { $Python = Join-Path $Pasta '.venv\Scripts\python.exe' }
if (-not $Mostrar -and -not (Test-Path $Python)) {
    throw "Python nao encontrado: $Python (crie o venv, veja o README, ou passe -Python)"
}
$Usuario = "$env:USERDOMAIN\$env:USERNAME"

$acao = New-ScheduledTaskAction -Execute $Python -Argument ('"' + (Join-Path $Pasta 'main.py') + '"') `
    -WorkingDirectory $Pasta
$gatilhos = @($Horarios | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ })
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $LimiteMinutos) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $Usuario -LogonType Interactive -RunLevel Limited

if ($Mostrar) {
    Write-Host "tarefa=$Nome"
    Write-Host "horarios=$($Horarios -join ',')"
    Write-Host "executa=$($acao.Execute) $($acao.Arguments)"
    Write-Host "pasta=$($acao.WorkingDirectory)"
    Write-Host "logon=$($principal.LogonType)"
    Write-Host "start_when_available=$($config.StartWhenAvailable)"
    Write-Host "limite=$($config.ExecutionTimeLimit)"
    Write-Host "instancias=$($config.MultipleInstances)"
    Write-Host "repeticao=$(@($gatilhos | Where-Object { $_.Repetition.Interval }).Count)"
    return
}

Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $gatilhos -Settings $config -Principal $principal `
    -Description 'Besave: captura web de apoio (BSV-66)' -Force | Out-Null
Write-Host "Tarefa $Nome registrada: $($Horarios -join ', ') (usuario $Usuario, so logado, limite $LimiteMinutos min)."
