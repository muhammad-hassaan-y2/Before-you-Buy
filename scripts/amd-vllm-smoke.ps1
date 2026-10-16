# Smoke-test the AMD Token Factory OpenAI-compatible chat endpoint.
# Usage:
#   .\scripts\amd-vllm-smoke.ps1
# Reads VLLM_BASE_URL, VLLM_API_KEY, VLLM_MODEL from env or .env.
# Never prints API keys.
param(
    [string]$BaseUrl = "",
    [string]$ApiKey = "",
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"

function Read-DotEnvValue([string]$key) {
    if (-not (Test-Path $envFile)) { return $null }
    $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

if (-not $BaseUrl) { $BaseUrl = $env:VLLM_BASE_URL }
if (-not $ApiKey) { $ApiKey = $env:VLLM_API_KEY }
if (-not $Model) { $Model = $env:VLLM_MODEL }

if (-not $BaseUrl) { $BaseUrl = Read-DotEnvValue "VLLM_BASE_URL" }
if (-not $ApiKey) { $ApiKey = Read-DotEnvValue "VLLM_API_KEY" }
if (-not $Model) { $Model = Read-DotEnvValue "VLLM_MODEL" }

if (-not $BaseUrl -or -not $ApiKey -or -not $Model) {
    Write-Error "Set VLLM_BASE_URL, VLLM_API_KEY, and VLLM_MODEL from official AMD Token Factory documentation."
}

$BaseUrl = $BaseUrl.TrimEnd("/")
if ($BaseUrl -notmatch '^https://') {
    Write-Error "VLLM_BASE_URL must be an https:// OpenAI-compatible Token Factory base URL (got non-HTTPS)."
}

$url = "$BaseUrl/chat/completions"
Write-Host "POST $url"
Write-Host "model=$Model"
Write-Host "Authorization=Bearer *** (redacted)"

$body = @{
    model      = $Model
    messages   = @(@{ role = "user"; content = "Say hi in one short sentence." })
    max_tokens = 64
} | ConvertTo-Json -Depth 5

$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Bearer $ApiKey"
}

try {
    $response = Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body -TimeoutSec 120
} catch {
    $status = $null
    if ($_.Exception.Response) {
        $status = [int]$_.Exception.Response.StatusCode
    }
    if ($status -eq 401 -or $status -eq 403) {
        Write-Error "Authentication failed (HTTP $status). Check VLLM_API_KEY in .env (value not printed)."
    }
    if ($status -eq 400) {
        Write-Error "Bad request (HTTP 400). Check VLLM_MODEL id against Token Factory catalog."
    }
    Write-Error "Token Factory request failed: $($_.Exception.Message)"
}

if (-not $response.choices -or -not $response.choices[0].message.content) {
    Write-Error "Empty or invalid chat completion from Token Factory (no choices/content)."
}

$content = [string]$response.choices[0].message.content
Write-Host "OK: model responded ($($content.Length) chars)"
Write-Host "preview: $($content.Substring(0, [Math]::Min(120, $content.Length)))"
