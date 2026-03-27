param(
    [string]$Version = "0.29.0"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$binDir = Join-Path $root "mcp\bin"
$binaryPath = Join-Path $binDir "toolbox.exe"
$url = "https://storage.googleapis.com/genai-toolbox/v$Version/windows/amd64/toolbox.exe"

New-Item -ItemType Directory -Force -Path $binDir | Out-Null
& curl.exe -k -L -o $binaryPath $url

if (-not (Test-Path $binaryPath)) {
    throw "MCP Toolbox download failed."
}

Write-Host "Installed MCP Toolbox to $binaryPath"
