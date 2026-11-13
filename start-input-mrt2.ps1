param([int]$Port = 4197, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repoPath = $PSScriptRoot
$linuxPath = (& wsl.exe -d Ubuntu --exec wslpath -a ($repoPath -replace '\\','/')).Trim()
$serviceUrl = "http://127.0.0.1:$Port"
try {
    $ready = Invoke-RestMethod "$serviceUrl/api/ready" -TimeoutSec 2
} catch {
    $ready = $null
}
if ($ready -and ($ready.root -ne $linuxPath -or $ready.implementation -ne 'workspace')) {
    throw "Port $Port belongs to a different checkout. Choose another -Port."
}
if (!$ready) {
    $logDir = Join-Path $repoPath 'tmp'
    New-Item -ItemType Directory -Force $logDir | Out-Null
    $server = Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','--exec','bash',"`"$linuxPath/scripts/start_input_mrt2_wsl.sh`"",$Port) -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir 'mrt2-server.log') -RedirectStandardError (Join-Path $logDir 'mrt2-server-errors.log')
    $server.Id | Set-Content (Join-Path $logDir 'mrt2-server.pid')
    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        try {
            $ready = Invoke-RestMethod "$serviceUrl/api/ready" -TimeoutSec 1
            break
        } catch {
            if ($server.HasExited) { throw 'MRT2 server exited; check tmp/mrt2-server-errors.log.' }
            Start-Sleep -Milliseconds 300
        }
    }
    if (!$ready) { throw 'Server did not become ready; check tmp/mrt2-server-errors.log.' }
    if ($ready.root -ne $linuxPath -or $ready.implementation -ne 'workspace') {
        throw "Unexpected server on port $Port."
    }
}
Write-Output $serviceUrl
if (!$NoBrowser) { Start-Process $serviceUrl }
