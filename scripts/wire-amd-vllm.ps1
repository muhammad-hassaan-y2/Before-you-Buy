# Write official AMD Token Factory values into local .env (do not invent URLs/models).
# Usage:
#   .\scripts\wire-amd-vllm.ps1 -BaseUrl "https://..." -Model "..." -ApiKey "..."
# API key is written to .env only — never printed.
param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,
    [Parameter(Mandatory = $true)]
    [string]$Model,
    [Parameter(Mandatory = $true)]
    [string]$ApiKey,
    [int]$TimeoutS = 60
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"
$example = Join-Path $root ".env.example"

$BaseUrl = $BaseUrl.Trim().TrimEnd("/")
if ($BaseUrl -notmatch '^https://') {
    Write-Error "BaseUrl must be https:// (AMD Token Factory OpenAI-compatible endpoint)."
}
if ([string]::IsNullOrWhiteSpace($Model) -or [string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Error "Model and ApiKey are required."
}

if (-not (Test-Path $envPath)) {
    Copy-Item $example $envPath
}

$raw = Get-Content $envPath -Raw

function Set-EnvLine([string]$text, [string]$key, [string]$value) {
    $pattern = "(?m)^\s*#?\s*$key\s*=.*$"
    $line = "$key=$value"
    if ($text -match $pattern) {
        return [regex]::Replace($text, $pattern, $line, 1)
    }
    return $text.TrimEnd() + "`r`n$line`r`n"
}

$raw = Set-EnvLine $raw "VLLM_BASE_URL" $BaseUrl
$raw = Set-EnvLine $raw "VLLM_MODEL" $Model
$raw = Set-EnvLine $raw "VLLM_API_KEY" $ApiKey
$raw = Set-EnvLine $raw "VLLM_TIMEOUT_S" "$TimeoutS"
$raw = Set-EnvLine $raw "VLLM_SUPPORTS_VISION" "false"

Set-Content -Path $envPath -Value $raw -NoNewline
Write-Host "Updated $envPath for AMD Token Factory"
Write-Host "  VLLM_BASE_URL=$BaseUrl"
Write-Host "  VLLM_MODEL=$Model"
Write-Host "  VLLM_API_KEY=*** (written, not printed)"
Write-Host "Restart inference-service, then:"
Write-Host "  .\scripts\amd-vllm-smoke.ps1"
Write-Host "  .\scripts\prove-amd-vllm.ps1"
