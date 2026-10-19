[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvDir = Join-Path $Root ".env"
$VenvPython = Join-Path $Root ".env\Scripts\python.exe"
$VenvActivate = Join-Path $Root ".env\Scripts\Activate.ps1"

function Write-Section {
    param([string]$Text)
    Write-Host ""
    Write-Host "== $Text =="
}

function Get-PythonCommand {
    $Candidates = @(
        @{ Command = "py"; Arguments = @("-3.11") },
        @{ Command = "python"; Arguments = @() },
        @{ Command = "python3"; Arguments = @() }
    )

    foreach ($Candidate in $Candidates) {
        $Executable = Get-Command $Candidate.Command -ErrorAction SilentlyContinue
        if (-not $Executable) {
            continue
        }

        try {
            $Version = & $Candidate.Command @($Candidate.Arguments + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
            if ($LASTEXITCODE -eq 0 -and $Version -match "^3\.(10|11|12)$") {
                return $Candidate
            }
        }
        catch {
            continue
        }
    }

    return $null
}

function Test-VenvPython {
    if (-not (Test-Path $VenvPython)) {
        return $false
    }

    try {
        & $VenvPython -c "import sys; print(sys.version)" >$null 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Move-BrokenVenv {
    if (-not (Test-Path $VenvDir)) {
        return
    }

    $ResolvedRoot = (Resolve-Path $Root).Path.TrimEnd([char[]]@("\", "/"))
    $ResolvedVenv = (Resolve-Path $VenvDir).Path
    if (-not $ResolvedVenv.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to move a virtual environment outside the project folder: $ResolvedVenv"
    }

    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupPath = Join-Path $Root ".env.broken-$Stamp"
    Write-Host "Existing .env does not run on this machine."
    Write-Host "Renaming it to: $(Split-Path $BackupPath -Leaf)"
    Move-Item -LiteralPath $VenvDir -Destination $BackupPath
}

function Ensure-Venv {
    if (Test-VenvPython) {
        Write-Host "Using existing virtual environment: .env"
        return
    }

    if (Test-Path $VenvDir) {
        Move-BrokenVenv
    }

    Write-Section "Creating Python Environment"
    $Python = Get-PythonCommand
    if (-not $Python) {
        throw "Python 3.10, 3.11, or 3.12 was not found. Install Python 3.11, then run START_RESITING.bat again."
    }

    Push-Location $Root
    try {
        & $Python.Command @($Python.Arguments + @("-m", "venv", ".env"))
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the .env virtual environment."
        }
    }
    finally {
        Pop-Location
    }
}

function Install-Dependencies {
    Write-Section "Installing Dependencies"
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip."
    }

    & $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. Geospatial packages can require native libraries; see README.md for the conda fallback."
    }

    & $VenvPython -m ipykernel install --user --name "resiting" --display-name "RESITING (.env)" | Out-Host
}

function Test-PortableLayout {
    Write-Section "Portable Copy Check"
    $Required = @(
        "START_RESITING.bat",
        "requirements.txt",
        "README.md",
        "WORKFLOW.md",
        "config\default.yaml",
        "config\data_manifest.yaml",
        "config\scenarios\base.yaml"
    )

    foreach ($Item in $Required) {
        $Path = Join-Path $Root $Item
        if (Test-Path $Path) {
            Write-Host "OK   $Item"
        }
        else {
            Write-Host "FAIL $Item"
        }
    }

    if (Test-VenvPython) {
        Invoke-ResitingTool @("portable-check")
    }
    else {
        Write-Host ""
        Write-Host "WARN .env is missing or not runnable on this machine."
        Write-Host "Run option 1 to create or repair the local environment."
    }
}

function Invoke-ResitingTool {
    param([string[]]$Arguments)

    if (-not (Test-VenvPython)) {
        Write-Host "Virtual environment is missing or not runnable. Choose option 1 first."
        return
    }

    Push-Location $Root
    try {
        & $VenvPython -m resiting @Arguments
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "The command finished with issues. Review the messages above."
        }
    }
    finally {
        Pop-Location
    }
}

function Show-Menu {
    while ($true) {
        Write-Section "RESITING Launcher"
        Write-Host "1. Install or refresh dependencies"
        Write-Host "2. Check copied folder"
        Write-Host "3. Validate replacement data files"
        Write-Host "4. Validate scenario config"
        Write-Host "5. Create a new scenario from base"
        Write-Host "6. Run workflow stage"
        Write-Host "7. Open workflow instructions"
        Write-Host "8. Open project folder"
        Write-Host "9. Exit"
        $Choice = Read-Host "Choose an option"

        switch ($Choice) {
            "1" {
                Ensure-Venv
                Install-Dependencies
                Write-Host ""
                Write-Host "Setup complete. Put input data in Data/, then follow WORKFLOW.md."
            }
            "2" {
                Test-PortableLayout
            }
            "3" {
                Invoke-ResitingTool @("validate-data")
            }
            "4" {
                $Scenario = Read-Host "Scenario name or path [base]"
                if ([string]::IsNullOrWhiteSpace($Scenario)) {
                    $Scenario = "base"
                }
                Invoke-ResitingTool @("validate-config", $Scenario)
            }
            "5" {
                $Scenario = Read-Host "New scenario name"
                if ([string]::IsNullOrWhiteSpace($Scenario)) {
                    Write-Host "Scenario name cannot be empty."
                    continue
                }
                Invoke-ResitingTool @("new-scenario", $Scenario, "--from", "base")
            }
            "6" {
                $Stage = Read-Host "Stage [weights, farm-area, apply-exclusions, visualize-si, investment-map, all]"
                if ([string]::IsNullOrWhiteSpace($Stage)) {
                    Write-Host "Stage cannot be empty."
                    continue
                }
                $Scenario = Read-Host "Scenario name or path [base]"
                if ([string]::IsNullOrWhiteSpace($Scenario)) {
                    $Scenario = "base"
                }
                Invoke-ResitingTool @("run-stage", $Stage, "--scenario", $Scenario)
            }
            "7" {
                Start-Process (Join-Path $Root "WORKFLOW.md")
            }
            "8" {
                Start-Process explorer.exe $Root
            }
            "9" {
                return
            }
            default {
                Write-Host "Please choose 1, 2, 3, 4, 5, 6, 7, 8, or 9."
            }
        }
    }
}

Write-Host "RESITING"
Write-Host "Project folder: $Root"
Show-Menu
