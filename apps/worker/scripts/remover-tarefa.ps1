<#
.SYNOPSIS
    Remove a tarefa "Besave Worker" do Agendador de Tarefas (BSV-14). Logs, trava e alerta.json
    em %LOCALAPPDATA%\besave ficam.

.EXAMPLE
    .\remover-tarefa.ps1
#>
[CmdletBinding()]
param(
    [string] $NomeTarefa = 'Besave Worker'
)

$ErrorActionPreference = 'Stop'

if (-not (Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue)) {
    Write-Host "Tarefa '$NomeTarefa' não existe; nada a remover."
    return
}
Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
Write-Host "Tarefa '$NomeTarefa' removida."
