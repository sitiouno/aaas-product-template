param()

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$dotenvPath = Join-Path $repoRoot ".env"

if (-not $env:STRIPE_SECRET_KEY -and (Test-Path $dotenvPath)) {
    foreach ($line in Get-Content $dotenvPath) {
        if ($line -match "^\s*STRIPE_SECRET_KEY=(.+)$") {
            $candidate = $matches[1].Trim().Trim('"').Trim("'")
            if ($candidate) {
                $env:STRIPE_SECRET_KEY = $candidate
                break
            }
        }
    }
}

if (-not $env:STRIPE_SECRET_KEY) {
    throw "STRIPE_SECRET_KEY is not configured in the environment or .env."
}

$serverEntry = Join-Path $repoRoot "mcp\stripe-server\node_modules\@stripe\mcp\dist\index.js"
& node $serverEntry
exit $LASTEXITCODE
