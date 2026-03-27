param(
    [string]$Region = "us-central1",
    [string]$Repository = "mvp-factory",
    [string]$BucketSuffix = "quien-artifacts",
    [string]$InstanceName = "quien-prod",
    [string]$DatabaseName = "mvp_factory",
    [string]$DatabaseUser = "svc_mvp_factory"
)

$ErrorActionPreference = "Stop"

$project = (gcloud.cmd config get-value project).Trim()
if (-not $project) {
    throw "No active gcloud project configured."
}

$bucket = "$project-$BucketSuffix"
$serviceAccountId = "mvp-factory-runner"
$serviceAccountEmail = "$serviceAccountId@$project.iam.gserviceaccount.com"
$envLines = Get-Content (Join-Path (Split-Path -Parent $PSScriptRoot) ".env")
$apiKeyLine = $envLines | Where-Object { $_ -match "^GOOGLE_API_KEY=" } | Select-Object -First 1
if (-not $apiKeyLine) {
    throw "GOOGLE_API_KEY not found in .env"
}
$googleApiKey = ($apiKeyLine -replace "^GOOGLE_API_KEY=", "").Trim()
if (-not $googleApiKey) {
    throw "GOOGLE_API_KEY is empty in .env"
}

function New-RandomSecret([int]$Length = 32) {
    $chars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789".ToCharArray()
    return -join (1..$Length | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

function Add-SecretVersion([string]$Name, [string]$Value) {
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -LiteralPath $tmp -Value $Value -NoNewline
        gcloud.cmd secrets versions add $Name --data-file=$tmp --project $project | Out-Null
    }
    finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function Ensure-Secret([string]$Name, [string]$Value, [bool]$RequireShellSafe = $false) {
    $exists = cmd /c "gcloud secrets describe $Name --project $project --format=value(name) 2>NUL"
    if (-not $exists) {
        $tmp = [System.IO.Path]::GetTempFileName()
        try {
            Set-Content -LiteralPath $tmp -Value $Value -NoNewline
            gcloud.cmd secrets create $Name --replication-policy=automatic --data-file=$tmp --project $project | Out-Null
        }
        finally {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        return $Value
    }
    $currentValue = (gcloud.cmd secrets versions access latest --secret=$Name --project $project).Trim()
    if ($RequireShellSafe -and ($currentValue -notmatch "^[A-Za-z0-9]+$")) {
        Add-SecretVersion $Name $Value
        return $Value
    }
    return $currentValue
}

Write-Host "Project: $project"
Write-Host "Enabling required services..."
gcloud.cmd services enable run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com compute.googleapis.com iam.googleapis.com storage.googleapis.com --project $project

Write-Host "Ensuring Artifact Registry repository..."
$repoExists = cmd /c "gcloud artifacts repositories describe $Repository --location $Region --project $project --format=value(name) 2>NUL"
if (-not $repoExists) {
    gcloud.cmd artifacts repositories create $Repository --repository-format=docker --location=$Region --project $project
}

Write-Host "Ensuring artifacts bucket..."
$bucketExists = cmd /c "gcloud storage buckets describe gs://$bucket --project $project --format=value(name) 2>NUL"
if (-not $bucketExists) {
    gcloud.cmd storage buckets create "gs://$bucket" --location=$Region --project $project
}

Write-Host "Ensuring Cloud Run service account..."
$saExists = cmd /c "gcloud iam service-accounts describe $serviceAccountEmail --project $project --format=value(email) 2>NUL"
if (-not $saExists) {
    gcloud.cmd iam service-accounts create $serviceAccountId --display-name="Due Diligence Cloud Run" --project $project
}

Write-Host "Granting service account roles..."
gcloud.cmd projects add-iam-policy-binding $project --member="serviceAccount:$serviceAccountEmail" --role=roles/cloudsql.client --quiet | Out-Null
gcloud.cmd projects add-iam-policy-binding $project --member="serviceAccount:$serviceAccountEmail" --role=roles/secretmanager.secretAccessor --quiet | Out-Null
gcloud.cmd storage buckets add-iam-policy-binding "gs://$bucket" --member="serviceAccount:$serviceAccountEmail" --role=roles/storage.objectAdmin | Out-Null

Write-Host "Ensuring secrets..."
$rootPassword = Ensure-Secret "mvp-factory-db-root-password" (New-RandomSecret 36) $true
$appPassword = Ensure-Secret "mvp-factory-db-password" (New-RandomSecret 36) $true
$null = Ensure-Secret "google-api-key" $googleApiKey

Write-Host "Ensuring Cloud SQL instance..."
$instanceExists = cmd /c "gcloud sql instances describe $InstanceName --project $project --format=value(name) 2>NUL"
if (-not $instanceExists) {
    gcloud.cmd sql instances create $InstanceName --project $project --database-version=POSTGRES_16 --edition=enterprise --cpu=1 --memory=3840MiB --region=$Region --storage-size=10 --availability-type=zonal --backup-start-time=03:00 --enable-point-in-time-recovery --maintenance-release-channel=production --maintenance-window-day=SUN --maintenance-window-hour=4 --deletion-protection --assign-ip --connector-enforcement=REQUIRED --root-password=$rootPassword --timeout=3600
}

Write-Host "Ensuring application database..."
$dbExists = cmd /c "gcloud sql databases list --instance $InstanceName --project $project --filter=name:$DatabaseName --format=value(name) 2>NUL"
if (-not $dbExists) {
    gcloud.cmd sql databases create $DatabaseName --instance=$InstanceName --project $project | Out-Null
}

Write-Host "Ensuring application database user..."
$userList = cmd /c "gcloud sql users list --instance $InstanceName --project $project --format=value(name) 2>NUL"
if ($userList -notcontains $DatabaseUser) {
    gcloud.cmd sql users create $DatabaseUser --instance=$InstanceName --password=$appPassword --project $project | Out-Null
}
else {
    gcloud.cmd sql users set-password $DatabaseUser --instance=$InstanceName --password=$appPassword --project $project | Out-Null
}

Write-Host "BOOTSTRAP_READY project=$project bucket=$bucket service_account=$serviceAccountEmail instance=$InstanceName database=$DatabaseName user=$DatabaseUser repository=$Repository"
