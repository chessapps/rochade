# Deploy the stack to the box through a docker context over SSH.
#
#   scripts/deploy.ps1                 # context "box", env file rochade.prod.env
#   scripts/deploy.ps1 -Context vps -EnvFile other.prod.env
#   scripts/deploy.ps1 -Plain          # show the build context transfer size
#
# One-time setup on both ends is in deploy/README.md.
param(
    [string]$Context = "workbench",
    [string]$EnvFile = "rochade.prod.env",
    [switch]$Plain
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $EnvFile)) {
    throw "$EnvFile not found. Copy .env.example to $EnvFile and set POSTGRES_PASSWORD."
}

$args = @(
    "--context", $Context, "compose",
    "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml",
    "-p", "rochade", "--env-file", $EnvFile,
    "up", "-d", "--build", "--remove-orphans"
)
if ($Plain) { $env:BUILDKIT_PROGRESS = "plain" }

docker @args
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

docker --context $Context compose -p rochade ps
