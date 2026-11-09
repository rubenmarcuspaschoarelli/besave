<#
.SYNOPSIS
  Tunel residencial do robo das lojas (BSV-58).

.DESCRIPTION
  Roda no PC do dono (IP residencial). Mantem um encaminhamento dinamico reverso
  (`ssh -N -R 127.0.0.1:<porta>`) para a inst1: la, a porta vira um proxy SOCKS que so
  escuta no 127.0.0.1 e que o robo das lojas usa APENAS para o redirect dos dominios de
  `redirecionamento.dominios`. Caiu, reconecta depois de -EsperaSegundos.

  Destino (usuario@host) e chave nunca ficam no repositorio: vem dos parametros ou de
  BESAVE_TUNEL_DESTINO / BESAVE_TUNEL_CHAVE. O log nao traz nenhum dos dois.
  Roteiro (tarefa agendada, parar): tools/vps/README.md.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tunel_residencial.ps1
#>
[CmdletBinding()]
param(
    [string]$Destino = $env:BESAVE_TUNEL_DESTINO,
    [string]$Chave = $env:BESAVE_TUNEL_CHAVE,
    [int]$Porta = 1080,
    [string]$Log = '',
    [int]$EsperaSegundos = 30,
    [int]$MaxTentativas = 0,      # 0 = para sempre; numero > 0 so para teste
    [string]$Ssh = 'ssh'
)

$ErrorActionPreference = 'Stop'

if (-not $Log) {
    $base = $env:LOCALAPPDATA
    if (-not $base) { $base = [System.IO.Path]::GetTempPath() }
    $Log = Join-Path (Join-Path $base 'besave') 'tunel_residencial.log'
}
$pasta = Split-Path -Parent $Log
if ($pasta -and -not (Test-Path -LiteralPath $pasta)) {
    New-Item -ItemType Directory -Path $pasta -Force | Out-Null
}

function Escrever-Log([string]$texto) {
    $linha = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $texto
    Write-Host $linha
    # Log curto: passou de 1 MB, fica so com as ultimas 500 linhas.
    if ((Test-Path -LiteralPath $Log) -and (Get-Item -LiteralPath $Log).Length -gt 1MB) {
        $resto = Get-Content -LiteralPath $Log -Tail 500
        Set-Content -LiteralPath $Log -Value $resto -Encoding UTF8
    }
    Add-Content -LiteralPath $Log -Value $linha -Encoding UTF8
}

if (-not $Destino -or -not $Chave) {
    Escrever-Log 'ERRO: faltam o destino e/ou a chave (parametros -Destino/-Chave ou BESAVE_TUNEL_DESTINO/BESAVE_TUNEL_CHAVE).'
    exit 2
}

$argumentos = @(
    '-i', $Chave,
    '-N',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'BatchMode=yes',
    '-R', "127.0.0.1:$Porta",
    $Destino
)

$tentativa = 0
while ($true) {
    $tentativa++
    Escrever-Log "conectando (tentativa $tentativa, porta $Porta no 127.0.0.1 da inst1)"
    & $Ssh @argumentos
    $codigo = $LASTEXITCODE
    Escrever-Log "tunel caiu (codigo $codigo); nova tentativa em $EsperaSegundos s"
    if ($MaxTentativas -gt 0 -and $tentativa -ge $MaxTentativas) { break }
    Start-Sleep -Seconds $EsperaSegundos
}
