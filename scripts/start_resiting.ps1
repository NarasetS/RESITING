[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
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

function Ensure-Venv {
    if (Test-Path $VenvPython) {
        Write-Host "Using existing virtual environment: .env"
        return
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

function Show-Menu {
    while ($true) {
        Write-Section "RESITING Launcher"
        Write-Host "1. Install or refresh dependencies"
        Write-Host "2. Open workflow instructions"
        Write-Host "3. Open project folder"
        Write-Host "4. Exit"
        $Choice = Read-Host "Choose an option"

        switch ($Choice) {
            "1" {
                Ensure-Venv
                Install-Dependencies
                Write-Host ""
                Write-Host "Setup complete. Put input data in Data/, then follow WORKFLOW.md."
            }
            "2" {
                Start-Process (Join-Path $Root "WORKFLOW.md")
            }
            "3" {
                Start-Process explorer.exe $Root
            }
            "4" {
                return
            }
            default {
                Write-Host "Please choose 1, 2, 3, or 4."
            }
        }
    }
}

Write-Host "RESITING"
Write-Host "Project folder: $Root"
Show-Menu
