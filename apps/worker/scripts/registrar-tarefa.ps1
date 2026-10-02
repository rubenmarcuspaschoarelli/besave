<#
.SYNOPSIS
    Registra (ou atualiza) a tarefa "Besave Worker" no Agendador de Tarefas (BSV-14).

.DESCRIPTION
    Roda `besave-ciclo --env-file <EnvFile>` a cada 5 minutos, indefinidamente, e também 1 minuto
    após o logon. `besave-ciclo.exe` é o mesmo ciclo do `besave-worker --ciclo`, sem janela de
    console: só o log em arquivo e o código de saída. Não inicia nova instância se a anterior
    ainda estiver rodando; para a execução que passar de 20 minutos. Roda com o usuário atual,
    somente quando ele está conectado (o Oracle XE e a pasta de imagens estão no perfil dele).
    Nenhuma senha é pedida ou gravada. Rodar de novo atualiza a tarefa existente.

.PARAMETER Executavel
    Caminho do besave-ciclo.exe de release (`cargo build --release`).

.PARAMETER EnvFile
    Caminho do .env fora do repositório.

.EXAMPLE
    .\registrar-tarefa.ps1 -Executavel 'C:\besave\besave-ciclo.exe' -EnvFile 'C:\besave\worker.env'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Executavel,
    [Parameter(Mandatory = $true)] [string] $EnvFile,
    [string] $NomeTarefa = 'Besave Worker'
)

$ErrorActionPreference = 'Stop'

$Executavel = (Resolve-Path -LiteralPath $Executavel).Path
$EnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
$nomeExe = Split-Path -Leaf $Executavel
if ($nomeExe -ne 'besave-ciclo.exe') {
    throw "Use o besave-ciclo.exe (sem janela de console), não $nomeExe."
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
    -Description 'Besave: publica ofertas no S3 a cada 5 min (besave-ciclo, sem console). BSV-14.' `
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
