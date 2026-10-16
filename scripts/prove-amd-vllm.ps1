# Prove live Token Factory wiring via inference /v1/profile.
# Rejects heuristic fallback — that is NOT proof of AMD inference.
# Prerequisites:
#   1. .env has VLLM_BASE_URL, VLLM_MODEL, VLLM_API_KEY (https base URL)
#   2. inference-service running and loaded those env vars
param(
    [string]$InferenceUrl = "http://localhost:8002"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== smoke Token Factory endpoint =="
& (Join-Path $root "scripts\amd-vllm-smoke.ps1")
if ($LASTEXITCODE -ne 0 -and -not $?) {
    Write-Error "Token Factory smoke failed — fix credentials/URL before proving inference."
}

Write-Host "== inference health =="
try {
    $health = Invoke-RestMethod -Uri "$InferenceUrl/healthz" -TimeoutSec 5
} catch {
    Write-Error "Cannot reach $InferenceUrl/healthz — start inference-service first."
}
Write-Host ($health | ConvertTo-Json -Compress)
if ($health.llm_configured -ne "true") {
    Write-Error "llm_configured is false. Set VLLM_* in .env and restart inference."
}

$expectedModel = $health.model
$payload = @{
    simulation_id = "proveamd01-0000-0000-0000-000000000001"
    room_width_m  = 4.0
    room_depth_m  = 3.5
    room_height_m = 2.4
    product_link  = $null
    image_key     = $null
    shopper_notes = "three-seater linen sofa, oak legs"
} | ConvertTo-Json

Write-Host "== POST $InferenceUrl/v1/profile =="
try {
    $profile = Invoke-RestMethod -Uri "$InferenceUrl/v1/profile" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 120
} catch {
    Write-Error "Inference /v1/profile failed: $($_.Exception.Message)"
}

# Compact success report (no secrets)
Write-Host ("profile source={0} provider={1} model={2} name={3}" -f `
    $profile.source, $profile.provider, $profile.model, $profile.name)

if ($profile.source -eq "heuristic") {
    Write-Error "REJECTED: source=heuristic is fallback, not AMD Token Factory proof. Check URL/key/model and inference logs."
}
if ($profile.source -ne "amd_token_factory") {
    Write-Error "Expected source=amd_token_factory, got '$($profile.source)'."
}
if ($profile.provider -ne "amd_token_factory") {
    Write-Error "Expected provider=amd_token_factory, got '$($profile.provider)'."
}
if (-not $profile.model) {
    Write-Error "Profile missing model identifier."
}
if ($expectedModel -and $expectedModel -ne "unset" -and $profile.model -ne $expectedModel) {
    Write-Warning "Profile model '$($profile.model)' differs from healthz model '$expectedModel'."
}
if (-not $profile.geometry -or -not $profile.geometry.width_cm) {
    Write-Error "Profile missing valid geometry dimensions."
}

Write-Host "PASS: AMD Token Factory inference confirmed (source=amd_token_factory)."
