[CmdletBinding()]
param([ValidateSet('Start', 'Status', 'Stop')][string]$Action = 'Start')

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeFolder = Join-Path $projectRoot 'artifacts/background'
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
$helper = Join-Path $PSScriptRoot 'background_process.py'
$markerPath = Join-Path $runtimeFolder 'processes.json'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run uv sync first.' }

function Get-OwnedProcess($record) {
    $candidate = Get-Process -Id $record.Id -ErrorAction SilentlyContinue
    if (-not $candidate) { return $null }
    if ($candidate.Path -ne $record.Executable -or
        [Math]::Abs(($candidate.StartTime.ToUniversalTime() - [DateTime]::Parse($record.StartedAt).ToUniversalTime()).TotalSeconds) -gt 1) {
        # Windows may reuse a stopped process ID. That process is not ours.
        return $null
    }
    return $candidate
}

$records = @()
if (Test-Path -LiteralPath $markerPath) {
    # Windows PowerShell 5 emits a JSON array as one pipeline object.
    foreach ($entry in (Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json)) {
        $records += $entry
    }
}
if ($Action -eq 'Status') {
    foreach ($record in $records) {
        $owned = Get-OwnedProcess $record
        Write-Output ($record.Role + ': ' + $(if ($owned) { 'running' } else { 'stopped' }))
    }
    & $python $helper status
    exit $LASTEXITCODE
}
if ($Action -eq 'Stop') {
    # Stop beat first. Only this helper's recorded processes are touched.
    foreach ($role in @('beat', 'worker')) {
        foreach ($record in @($records | Where-Object Role -eq $role)) {
            $owned = Get-OwnedProcess $record
            if ($owned) { Stop-Process -Id $owned.Id }
        }
    }
    $beatPidFile = Join-Path $runtimeFolder 'beat.pid'
    if (Test-Path -LiteralPath $beatPidFile) { Remove-Item -LiteralPath $beatPidFile }
    Write-Output 'Owned worker and beat stopped. Redis, PostgreSQL and saved data are retained.'
    exit 0
}
foreach ($record in $records) {
    if (Get-OwnedProcess $record) { throw 'A background process is already running. Use -Action Status or Stop first.' }
}
& $python $helper ping
if ($LASTEXITCODE -ne 0) { throw 'Redis is unavailable. Start your local Redis service or Docker Desktop first.' }
New-Item -ItemType Directory -Path $runtimeFolder -Force | Out-Null
$records = @()
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')
foreach ($role in @('worker', 'beat')) {
    $pidRecordPath = Join-Path $runtimeFolder "$role-pid.json"
    # The helper writes its actual Python PID, including through the venv launcher.
    $startedAfter = [DateTime]::UtcNow
    $launcher = Start-Process -FilePath $python -ArgumentList @('"' + $helper + '"', $role) -WorkingDirectory $projectRoot `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeFolder "$role-$stamp.out.log") `
        -RedirectStandardError (Join-Path $runtimeFolder "$role-$stamp.err.log")
    $owned = $null
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ((Test-Path -LiteralPath $pidRecordPath) -and (Get-Item -LiteralPath $pidRecordPath).LastWriteTimeUtc -ge $startedAfter) {
            $pidRecord = Get-Content -LiteralPath $pidRecordPath -Raw | ConvertFrom-Json
            $owned = Get-Process -Id $pidRecord.pid -ErrorAction SilentlyContinue
            if ($owned) { break }
        }
        if ($launcher.HasExited) { throw "$role exited. Check artifacts/background logs." }
        Start-Sleep -Milliseconds 250
    }
    if (-not $owned) { throw "$role did not start. Check artifacts/background logs." }
    $records += @{Role=$role; Id=$owned.Id; Executable=$owned.Path; StartedAt=$owned.StartTime.ToUniversalTime().ToString('o')}
    ConvertTo-Json -InputObject @($records) | Set-Content -LiteralPath $markerPath -Encoding UTF8
}
Start-Sleep -Seconds 3
foreach ($record in $records) {
    if (-not (Get-OwnedProcess $record)) { throw 'A helper exited during startup. Check artifacts/background logs.' }
}
& $python $helper kick
if ($LASTEXITCODE -ne 0) { throw 'Processes started, but first-cycle submission failed. Check Status and logs before retrying.' }
Write-Output 'Background collection started. Settings apply only to these processes; .env is unchanged.'
Write-Output 'Status: .\scripts\background.ps1 -Action Status'
Write-Output 'Stop:   .\scripts\background.ps1 -Action Stop'
