<#
Start, stop or check Ollaya, the local model server that rule 1 (Pending check) uses.

    powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 status
    powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 start
    powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 stop

Ollaya does not start by itself: start it before the notifier (`python -m notifier run`), and keep it running.
It loads the `von` model on the first request (a few seconds) and unloads it after 5 idle minutes; that's normal.
Binaries and models live in .tools\ (git-ignored); see README "Rule-1 classifier".
#>
param([ValidateSet("start", "stop", "status")][string]$Action = "status")

$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root ".tools\ollaya\bin\ollaya.exe"
$url = "http://127.0.0.1:11435/v1/models"
$env:OLLAYA_HOST = "127.0.0.1:11435"
$env:OLLAYA_MODELS = Join-Path $root ".tools\models"
if (-not $env:OLLAYA_THREADS) { $env:OLLAYA_THREADS = "12" }  # ~3-5x faster than the default on this CPU

if (-not (Test-Path $exe)) { Write-Error "Ollaya not found at $exe (see README: Rule-1 classifier)"; exit 1 }

function Test-Ollaya {
    try { Invoke-RestMethod -Uri $url -TimeoutSec 3 -ErrorAction Stop; return $true } catch { return $false }
}

switch ($Action) {
    "status" {
        if (Test-Ollaya) {
            $models = (Invoke-RestMethod -Uri $url -TimeoutSec 3).models | ForEach-Object { $_.name }
            Write-Output "Ollaya is running at $url"
            Write-Output ("Installed models: " + ($models -join ", "))
            & $exe ps
        } else {
            Write-Output "Ollaya is NOT running. Start it with: scripts\ollaya.ps1 start"
        }
    }
    "start" {
        if (Test-Ollaya) { Write-Output "Ollaya is already running at $url"; exit 0 }
        Start-Process -FilePath $exe -ArgumentList "serve" -WindowStyle Hidden
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Milliseconds 500
            if (Test-Ollaya) { Write-Output "Ollaya started at $url (threads: $env:OLLAYA_THREADS)"; exit 0 }
        }
        Write-Error "Ollaya did not come up within 15 s"; exit 1
    }
    "stop" {
        if (-not (Test-Ollaya)) { Write-Output "Ollaya is not running"; exit 0 }
        & $exe stop
    }
}
