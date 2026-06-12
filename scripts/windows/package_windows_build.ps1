#Requires -Version 5.1
<#
.SYNOPSIS
    Package a Unity Windows64 build into a versioned ZIP archive.

.DESCRIPTION
    Collects the Unity Windows64 build output, optionally validates the EXE,
    writes a manifest, and creates a ZIP archive ready for distribution.

.PARAMETER BuildPath
    Path to the Unity build output directory.

.PARAMETER OutputPath
    Path where the packaged artifact will be written.

.PARAMETER Version
    Build version string (e.g. 1.2.3).

.PARAMETER Environment
    Build environment (development/staging/production).

.EXAMPLE
    .\package_windows_build.ps1 -BuildPath "C:\build\windows64" -OutputPath "C:\artifacts" -Version "1.0.0" -Environment "production"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BuildPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $false)]
    [ValidateSet("development", "staging", "production")]
    [string]$Environment = "development"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[package_windows] Build path: $BuildPath"
Write-Host "[package_windows] Output path: $OutputPath"
Write-Host "[package_windows] Version: $Version"
Write-Host "[package_windows] Environment: $Environment"

# Validate build path
if (-not (Test-Path $BuildPath)) {
    Write-Error "Build path does not exist: $BuildPath"
    exit 1
}

# Find main EXE
$exeFiles = Get-ChildItem -Path $BuildPath -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue
if ($exeFiles.Count -eq 0) {
    Write-Error "No .exe files found in $BuildPath"
    exit 1
}
$mainExe = $exeFiles | Sort-Object Length -Descending | Select-Object -First 1
Write-Host "[package_windows] Main executable: $($mainExe.Name) ($([Math]::Round($mainExe.Length / 1MB, 2)) MB)"

# Create output directory
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null

# Write build manifest
$manifestPath = Join-Path $BuildPath "build-manifest.json"
$manifest = @{
    version     = $Version
    environment = $Environment
    platform    = "Windows64"
    built_at    = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC)
    main_exe    = $mainExe.Name
    run_number  = $env:GITHUB_RUN_NUMBER ?? "0"
    commit      = $env:GITHUB_SHA ?? ""
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content $manifestPath -Encoding UTF8
Write-Host "[package_windows] Manifest written: $manifestPath"

# Compute directory size
$totalSize = (Get-ChildItem -Path $BuildPath -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalSizeMB = [Math]::Round($totalSize / 1MB, 2)
Write-Host "[package_windows] Total build size: $totalSizeMB MB"

# Create ZIP archive
$archiveName = "windows64-$Environment-$Version-$($env:GITHUB_RUN_NUMBER ?? '0').zip"
$archivePath = Join-Path $OutputPath $archiveName

Write-Host "[package_windows] Creating archive: $archiveName"
Compress-Archive -Path "$BuildPath\*" -DestinationPath $archivePath -CompressionLevel Optimal -Force

# Verify archive
if (-not (Test-Path $archivePath)) {
    Write-Error "Failed to create archive: $archivePath"
    exit 1
}

$archiveSize = [Math]::Round((Get-Item $archivePath).Length / 1MB, 2)
Write-Host "[package_windows] Archive created: $archiveName ($archiveSize MB)"

# Write size report
$sizeReport = @{
    archive_name     = $archiveName
    archive_size_mb  = $archiveSize
    build_size_mb    = $totalSizeMB
    version          = $Version
    environment      = $Environment
}
$sizeReportPath = Join-Path $OutputPath "size-report.json"
$sizeReport | ConvertTo-Json | Set-Content $sizeReportPath -Encoding UTF8

# GitHub Step Summary
$summaryFile = $env:GITHUB_STEP_SUMMARY
if ($summaryFile) {
    @"

### Windows64 Build Package

| Field | Value |
|-------|-------|
| Archive | ``$archiveName`` |
| Archive Size | $archiveSize MB |
| Build Size | $totalSizeMB MB |
| Version | $Version |
| Environment | $Environment |
"@ | Add-Content -Path $summaryFile
}

Write-Host "[package_windows] Packaging complete: $archivePath"
exit 0
