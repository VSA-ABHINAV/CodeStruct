#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$body = @{
    project = @{
        root_id = "demo_root"
        relative_path = "."
    }
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/analyses" -Method Post -Body $body -ContentType "application/json"
$analysisId = $resp.analysis_id
Write-Host "ANALYSIS_ID: $analysisId"

Start-Sleep -Seconds 1
$statusResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/analyses/$analysisId" -Method Get
Write-Host "ANALYSIS_STATUS: $($statusResp.state)"

# Fetch graph
$graphResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/analyses/$analysisId/graph" -Method Get
Write-Host "NODE_COUNT: $($graphResp.nodes.Count)"
Write-Host "EDGE_COUNT: $($graphResp.edges.Count)"
Write-Host "VIEWER_URL: http://127.0.0.1:5173/?analysis_id=$analysisId"

# Verify proxy
$proxyResp = Invoke-RestMethod -Uri "http://127.0.0.1:5173/api/v1/analyses/$analysisId" -Method Get
Write-Host "PROXY_STATE: $($proxyResp.state)"
