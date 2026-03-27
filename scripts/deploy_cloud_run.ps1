param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$Repository = "mvp-factory",
    [string]$ImageName = "mvp-factory-studio",
    [string]$ServiceName = "mvp-factory-studio",
    [string]$ServiceAccountId = "mvp-factory-runner",
    [string]$CloudSqlInstance = "quien-prod",
    [string]$DatabaseName = "mvp_factory",
    [string]$DatabaseUser = "svc_mvp_factory",
    [string]$ArtifactBucket = "",
    [string]$PublicBaseUrl = "https://mvpfactory.studio",
    [string]$FirebaseProjectId = "test-agents-ai-app",
    [string]$FirebaseWebApiKey = $env:FIREBASE_WEB_API_KEY,
    [string]$FirebaseAuthDomain = "test-agents-ai-app.firebaseapp.com",
    [string]$FirebaseAppId = "1:418791284533:web:b4eb0ae9cb9948833f767c",
    [string]$FirebaseMeasurementId = "",
    [string]$GoogleOAuthClientId = "a27d1fe5a-ae52-4ff2-bcdc-72cb5d409fb5",
    [string]$WebsiteName = "MVP Factory Studio",
    [string]$WebsiteTaglineEn = "Bilingual AI startup research for angels and funds.",
    [string]$WebsiteTaglineEs = "Investigacion bilingue de startups con IA para angels y fondos.",
    [string]$CompanyLegalName = "MVP Factory Studio",
    [string]$SupportEmail = "support@mvpfactory.studio",
    [string]$AppSessionSecretName = "app-session-secret",
    [string]$StripePublishableKey = "",
    [string]$StripePriceReport = "",
    [string]$StripePriceSolo = "",
    [string]$StripePriceTeam = "",
    [string]$StripePriceCreditPack5 = "",
    [string]$StripePriceCreditPack25 = "",
    [string]$StripeSecretKeySecretName = "",
    [string]$StripeWebhookSecretName = ""
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Test-GcloudSecret {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    gcloud.cmd secrets describe $Name --project $ProjectId --format="value(name)" 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

gcloud.cmd config set project $ProjectId | Out-Null

$image = "$Region-docker.pkg.dev/$ProjectId/$Repository/$ImageName"
$instanceConnectionName = "${ProjectId}:${Region}:${CloudSqlInstance}"
$serviceAccountEmail = "$ServiceAccountId@$ProjectId.iam.gserviceaccount.com"

gcloud.cmd artifacts repositories describe $Repository --location $Region --project $ProjectId 1>$null 2>$null
if ($LASTEXITCODE -ne 0) {
    gcloud.cmd artifacts repositories create $Repository --repository-format=docker --location=$Region --project $ProjectId
}

gcloud.cmd builds submit --tag $image --project $ProjectId

$deployArgs = @(
    "run", "deploy", $ServiceName,
    "--image", $image,
    "--platform", "managed",
    "--region", $Region,
    "--allow-unauthenticated",
    "--service-account", $serviceAccountEmail,
    "--memory", "2Gi",
    "--cpu", "2",
    "--timeout", "1800",
    "--min-instances", "1",
    "--max-instances", "10",
    "--set-env-vars", "HOST=0.0.0.0",
    "--set-env-vars", "PUBLIC_BASE_URL=$PublicBaseUrl",
    "--set-env-vars", "GOOGLE_CLOUD_PROJECT=$ProjectId",
    "--set-env-vars", "GOOGLE_CLOUD_LOCATION=$Region",
    "--set-env-vars", "CLOUD_SQL_INSTANCE_CONNECTION_NAME=$instanceConnectionName",
    "--set-env-vars", "CLOUD_SQL_IP_TYPE=public",
    "--set-env-vars", "DATABASE_NAME=$DatabaseName",
    "--set-env-vars", "DATABASE_USER=$DatabaseUser",
    "--set-env-vars", "RUN_RATE_LIMIT_WINDOW_SECONDS=300",
    "--set-env-vars", "RUN_RATE_LIMIT_MAX_REQUESTS=6",
    "--set-env-vars", "PREVIEW_RATE_LIMIT_WINDOW_SECONDS=300",
    "--set-env-vars", "PREVIEW_RATE_LIMIT_MAX_REQUESTS=3",
    "--set-env-vars", "PREVIEW_MONTHLY_LIMIT_PER_EMAIL=1",
    "--set-env-vars", "MAX_CONCURRENT_RUNS=2",
    "--set-env-vars", "MVP_FACTORY_ENABLE_DEV_AUTH=false",
    "--set-env-vars", "MVP_FACTORY_DEFAULT_ORG_NAME=$WebsiteName",
    "--set-env-vars", "MVP_FACTORY_DEFAULT_USER_EMAIL=owner@mvpfactory.studio",
    "--set-env-vars", "MVP_FACTORY_DEFAULT_LANGUAGE=en",
    "--set-env-vars", "MVP_FACTORY_COORDINATOR_MODEL=gemini-3-flash-preview",
    "--set-env-vars", "MVP_FACTORY_SEARCH_MODEL=gemini-3.1-pro-preview",
    "--set-env-vars", "MVP_FACTORY_REASONING_MODEL=gemini-3.1-pro-preview",
    "--set-env-vars", "MVP_FACTORY_REPORT_MODEL=gemini-3-flash-preview",
    "--set-env-vars", "FIREBASE_PROJECT_ID=$FirebaseProjectId",
    "--set-env-vars", "FIREBASE_WEB_API_KEY=$FirebaseWebApiKey",
    "--set-env-vars", "FIREBASE_AUTH_DOMAIN=$FirebaseAuthDomain",
    "--set-env-vars", "FIREBASE_APP_ID=$FirebaseAppId",
    "--set-env-vars", "GOOGLE_OAUTH_CLIENT_ID=$GoogleOAuthClientId",
    "--set-env-vars", "WEBSITE_NAME=$WebsiteName",
    "--set-env-vars", "WEBSITE_TAGLINE_EN=$WebsiteTaglineEn",
    "--set-env-vars", "WEBSITE_TAGLINE_ES=$WebsiteTaglineEs",
    "--set-env-vars", "COMPANY_LEGAL_NAME=$CompanyLegalName",
    "--set-env-vars", "SUPPORT_EMAIL=$SupportEmail",
    "--set-env-vars", "STRIPE_PORTAL_RETURN_URL=$PublicBaseUrl/en/app",
    "--set-secrets", "GOOGLE_API_KEY=google-api-key:latest",
    "--set-secrets", "DATABASE_PASSWORD=mvp-factory-db-password:latest"
)

if ($ArtifactBucket) {
    $deployArgs += @("--set-env-vars", "MVP_FACTORY_GCS_BUCKET=$ArtifactBucket")
    $deployArgs += @("--set-env-vars", "MVP_FACTORY_GCS_PREFIX=artifacts")
}

if ($FirebaseMeasurementId) {
    $deployArgs += @("--set-env-vars", "FIREBASE_MEASUREMENT_ID=$FirebaseMeasurementId")
}

if ($AppSessionSecretName -and (Test-GcloudSecret -Name $AppSessionSecretName)) {
    $deployArgs += @("--set-secrets", "APP_SESSION_SECRET=$AppSessionSecretName:latest")
}

if ($StripePublishableKey) {
    $deployArgs += @("--set-env-vars", "STRIPE_PUBLISHABLE_KEY=$StripePublishableKey")
}

if ($StripePriceReport) {
    $deployArgs += @("--set-env-vars", "STRIPE_PRICE_REPORT=$StripePriceReport")
}

if ($StripePriceSolo) {
    $deployArgs += @("--set-env-vars", "STRIPE_PRICE_SOLO=$StripePriceSolo")
}

if ($StripePriceTeam) {
    $deployArgs += @("--set-env-vars", "STRIPE_PRICE_TEAM=$StripePriceTeam")
}

if ($StripePriceCreditPack5) {
    $deployArgs += @("--set-env-vars", "STRIPE_PRICE_CREDIT_PACK_5=$StripePriceCreditPack5")
}

if ($StripePriceCreditPack25) {
    $deployArgs += @("--set-env-vars", "STRIPE_PRICE_CREDIT_PACK_25=$StripePriceCreditPack25")
}

if ($StripeSecretKeySecretName -and (Test-GcloudSecret -Name $StripeSecretKeySecretName)) {
    $deployArgs += @("--set-secrets", "STRIPE_SECRET_KEY=$StripeSecretKeySecretName:latest")
}

if ($StripeWebhookSecretName -and (Test-GcloudSecret -Name $StripeWebhookSecretName)) {
    $deployArgs += @("--set-secrets", "STRIPE_WEBHOOK_SECRET=$StripeWebhookSecretName:latest")
}

& gcloud.cmd @deployArgs
