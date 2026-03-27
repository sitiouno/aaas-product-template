param(
    [string]$Version = "0.5.3"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $root "mcp\gcloud-server"

Push-Location $serverDir
try {
    npm install "@google-cloud/gcloud-mcp@$Version"
}
finally {
    Pop-Location
}

Write-Host "Installed gcloud MCP server in $serverDir"
