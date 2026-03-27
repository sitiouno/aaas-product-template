param(
    [string]$Version = "0.3.1"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $root "mcp\stripe-server"

Push-Location $serverDir
try {
    npm install "@stripe/mcp@$Version"
}
finally {
    Pop-Location
}

Write-Host "Installed Stripe MCP server in $serverDir"
