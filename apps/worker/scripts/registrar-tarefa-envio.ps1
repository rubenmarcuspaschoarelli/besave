<#
.SYNOPSIS
    Registra (ou atualiza) a tarefa "Besave Envio" no Agendador de Tarefas (BSV-40).

.DESCRIPTION
    Roda `besave-envio --env-file <EnvFile>` a cada 5 minutos, indefinidamente, e também 1 minuto
    após o logon: posta o lote devido no canal do Telegram e edita as ofertas expiradas.
    `besave-envio.exe` não abre janela de console: só o log em arquivo e o código de saída.
    Mesmas regras da tarefa "Besave Worker" (BSV-14): não inicia nova instância se a anterior
    ainda estiver rodando; para a execução que passar de 20 minutos; roda com o usuário atual,
    somente quando ele está conectado; nenhuma senha é pedida ou gravada. Rodar de novo atualiza
    a tarefa existente.

.PARAMETER Executavel
    Caminho do besave-envio.exe de release (`cargo build --release`).

.PARAMETER EnvFile
    Caminho do .env fora do repositório (pode ser o mesmo do ciclo, com TELEGRAM_CANAL_BOT_TOKEN).

.EXAMPLE
    .\registrar-tarefa-envio.ps1 -Executavel 'C:\besave\bin\besave-envio.exe' -EnvFile 'C:\besave\worker.env'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Executavel,
    [Parameter(Mandatory = $true)] [string] $EnvFile,
    [string] $NomeTarefa = 'Besave Envio'
)

$ErrorActionPreference = 'Stop'

$Executavel = (Resolve-Path -LiteralPath $Executavel).Path
$EnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
$nomeExe = Split-Path -Leaf $Executavel
if ($nomeExe -ne 'besave-envio.exe') {
    throw "Use o besave-envio.exe (sem janela de console), não $nomeExe."
}
if ($Executavel -match '\\debug\\') {
    Write-Warning "O executável parece ser de debug: $Executavel. Use o de release (cargo build --release)."
}
$usuario = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$acao = New-ScheduledTaskAction `
    -Execute $Executavel `
    -Argument "--env-file `"$EnvFile`"" `
    -WorkingDirectory (Split-Path -Parent $Executavel)

# Sem -RepetitionDuration: repete indefinidamente.
$aCada5Min = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)
$aposLogon = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$aposLogon.Delay = 'PT1M'

$config = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# Interactive = "Executar somente quando o usuário estiver conectado"; dispensa senha.
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $NomeTarefa `
    -Description 'Besave: posta ofertas no canal do Telegram a cada 5 min (besave-envio, sem console). BSV-40.' `
    -Action $acao `
    -Trigger @($aCada5Min, $aposLogon) `
    -Settings $config `
    -Principal $principal `
    -Force | Out-Null

$t = Get-ScheduledTask -TaskName $NomeTarefa
Write-Host "Tarefa '$NomeTarefa' registrada para $usuario (estado: $($t.State))."
Write-Host "Executável: $Executavel"
Write-Host "Env file:   $EnvFile"
Write-Host "Próximas execuções: Get-ScheduledTaskInfo -TaskName '$NomeTarefa'"
