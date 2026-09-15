[CmdletBinding()]
param(
    [string]$ArchivePath,
    [switch]$IncludeData,
    [switch]$IncludeOutput,
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ProjectName = Split-Path $Root -Leaf

if (-not $ArchivePath) {
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $ArchivePath = Join-Path $Root "dist\$ProjectName-share-$Stamp.zip"
}

$ArchiveFullPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ArchivePath)
$ArchiveDirectory = Split-Path $ArchiveFullPath -Parent
New-Item -ItemType Directory -Force -Path $ArchiveDirectory | Out-Null

function Get-ReleaseRelativePath {
    param(
        [string]$BasePath,
        [string]$ChildPath
    )

    $BaseFullPath = [System.IO.Path]::GetFullPath($BasePath).TrimEnd([char[]]@("\", "/")) + [System.IO.Path]::DirectorySeparatorChar
    $ChildFullPath = [System.IO.Path]::GetFullPath($ChildPath)

    if ($ChildFullPath.StartsWith($BaseFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $ChildFullPath.Substring($BaseFullPath.Length)
    }

    return $ChildFullPath
}

$ExcludedDirectories = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(".git", ".env", ".venv", "venv", "env", "__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist") |
    ForEach-Object { [void]$ExcludedDirectories.Add($_) }

if (-not $IncludeData) {
    [void]$ExcludedDirectories.Add("Data")
    [void]$ExcludedDirectories.Add("data")
}

if (-not $IncludeOutput) {
    [void]$ExcludedDirectories.Add("Output")
    [void]$ExcludedDirectories.Add("output")
}

$ExcludedFileNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@("Thumbs.db", "desktop.ini", ".DS_Store", "cds_api.txt", "modify_cdsapi.txt") |
    ForEach-Object { [void]$ExcludedFileNames.Add($_) }

$ExcludedExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(".pyc", ".pyo", ".pyd") |
    ForEach-Object { [void]$ExcludedExtensions.Add($_) }

function Test-ReleasePath {
    param([System.IO.FileInfo]$File)

    if ($File.FullName -ieq $ArchiveFullPath) {
        return $false
    }

    if ($ExcludedFileNames.Contains($File.Name)) {
        return $false
    }

    if ($ExcludedExtensions.Contains($File.Extension)) {
        return $false
    }

    $Relative = Get-ReleaseRelativePath -BasePath $Root -ChildPath $File.FullName
    $Parts = $Relative -split "[\\/]+"
    foreach ($Part in $Parts) {
        if ($ExcludedDirectories.Contains($Part)) {
            return $false
        }
    }

    return $true
}

$Files = Get-ChildItem -Path $Root -Recurse -Force -File |
    Where-Object { Test-ReleasePath $_ } |
    Sort-Object FullName

if ($ListOnly) {
    $Files | ForEach-Object { Get-ReleaseRelativePath -BasePath $Root -ChildPath $_.FullName }
    Write-Host "Files selected: $($Files.Count)"
    exit 0
}

if (Test-Path $ArchiveFullPath) {
    Remove-Item -LiteralPath $ArchiveFullPath -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [System.IO.Compression.ZipFile]::Open($ArchiveFullPath, [System.IO.Compression.ZipArchiveMode]::Create)

try {
    foreach ($File in $Files) {
        $Relative = Get-ReleaseRelativePath -BasePath $Root -ChildPath $File.FullName
        $EntryName = ($ProjectName + "/" + $Relative).Replace("\", "/")
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $Zip,
            $File.FullName,
            $EntryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
}
finally {
    $Zip.Dispose()
}

$Archive = Get-Item -LiteralPath $ArchiveFullPath
Write-Host "Created $($Archive.FullName)"
Write-Host "Files included: $($Files.Count)"
Write-Host ("Size: {0:N2} MB" -f ($Archive.Length / 1MB))
