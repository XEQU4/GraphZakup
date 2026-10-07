[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 11434,
    [ValidateSet('qwen3:4b')][string]$Model = 'qwen3:4b',
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeFolder = Join-Path $projectRoot 'artifacts/local-ai'
$markerPath = Join-Path $runtimeFolder "server-$Port.json"
$baseUrl = "http://127.0.0.1:$Port"

if ($Stop) {
    if (-not (Test-Path -LiteralPath $markerPath)) {
        Write-Output "No owned local AI server is recorded on port $Port."
        exit 0
    }
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    $ownedProcess = Get-Process -Id $marker.ProcessId -ErrorAction SilentlyContinue
    if (-not $ownedProcess) {
        Write-Output 'The owned local AI server is already stopped.'
        exit 0
    }
    $expectedStart = [DateTime]::Parse($marker.StartedAt).ToUniversalTime()
    if ($ownedProcess.Path -ne $marker.Executable -or
        [Math]::Abs(($ownedProcess.StartTime.ToUniversalTime() - $expectedStart).TotalSeconds) -gt 1) {
        throw 'Server ownership changed; no process was stopped.'
    }
    Stop-Process -Id $ownedProcess.Id
    $marker | Add-Member -NotePropertyName StoppedAt -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
    $marker | ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding UTF8
    Write-Output 'Owned local AI server stopped. Model cache retained.'
    exit 0
}

$executable = Join-Path $projectRoot 'artifacts/phase5/ollama/ollama.exe'
if (-not (Test-Path -LiteralPath $executable)) {
    $installed = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $installed) { throw 'Ollama is missing. Install Ollama for Windows, then run this command again.' }
    $executable = $installed.Source
}
$executable = (Resolve-Path -LiteralPath $executable).Path
$ready = $false
try {
    $version = Invoke-RestMethod -Uri "$baseUrl/api/version" -TimeoutSec 2
    $ready = [bool]$version.version
} catch { }

$environmentNames = @('OLLAMA_HOST', 'OLLAMA_MODELS', 'OLLAMA_NO_CLOUD', 'OLLAMA_CONTEXT_LENGTH')
$previousEnvironment = @{}
foreach ($name in $environmentNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:OLLAMA_HOST = "127.0.0.1:$Port"
    $env:OLLAMA_MODELS = Join-Path $projectRoot 'artifacts/phase5/ollama-models'
    $env:OLLAMA_NO_CLOUD = '1'
    $env:OLLAMA_CONTEXT_LENGTH = '4096'
    if (-not $ready) {
        New-Item -ItemType Directory -Path $runtimeFolder -Force | Out-Null
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')
        $server = Start-Process -FilePath $executable -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $runtimeFolder "stdout-$stamp.log") `
            -RedirectStandardError (Join-Path $runtimeFolder "stderr-$stamp.log")
        @{ProcessId=$server.Id; Executable=$executable; StartedAt=$server.StartTime.ToUniversalTime().ToString('o'); Port=$Port} |
            ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding UTF8
        for ($attempt = 0; $attempt -lt 25; $attempt++) {
            if ($server.HasExited) { throw 'Ollama could not start. Check that the selected port is available.' }
            try {
                $version = Invoke-RestMethod -Uri "$baseUrl/api/version" -TimeoutSec 1
                $ready = [bool]$version.version
                if ($ready) { break }
            } catch { }
            Start-Sleep -Milliseconds 200
        }
        if (-not $ready) { throw 'Local Ollama startup timed out.' }
    }
    $tags = Invoke-RestMethod -Uri "$baseUrl/api/tags" -TimeoutSec 5
    if (-not ($tags.models | Where-Object { $_.name -eq $Model })) {
        Write-Output "Downloading local model $Model. This can take several minutes."
        & $executable pull $Model
        if ($LASTEXITCODE -ne 0) { throw 'Local model download failed.' }
    }
    Write-Output "Local AI ready: $baseUrl; model=$Model; Ollama=$($version.version)."
} finally {
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process') }
}
