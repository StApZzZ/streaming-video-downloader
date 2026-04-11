param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-NormalizedPath {
    param([string]$PathText)
    return [System.IO.Path]::GetFullPath($PathText)
}

function Remove-PathEntry {
    param(
        [string]$CurrentPath,
        [string]$EntryToRemove
    )

    $normalizedTarget = Get-NormalizedPath $EntryToRemove
    $parts = $CurrentPath -split ';' | Where-Object { $_.Trim() }
    $filtered = foreach ($part in $parts) {
        $normalizedPart = Get-NormalizedPath $part
        if ($normalizedPart -ne $normalizedTarget) {
            $part
        }
    }
    return ($filtered -join ';')
}

function Invoke-External {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Test-PythonCandidate {
    param([string[]]$CommandParts)

    try {
        $command = $CommandParts[0]
        $args = @()
        if ($CommandParts.Count -gt 1) {
            $args += $CommandParts[1..($CommandParts.Count - 1)]
        }
        $args += "-c"
        $args += "import sys; print(sys.executable)"
        $output = & $command @args 2>$null
        return ($LASTEXITCODE -eq 0 -and [string]::IsNullOrWhiteSpace(($output | Out-String)) -eq $false)
    }
    catch {
        return $false
    }
}

function Invoke-PythonCommand {
    param(
        [string[]]$CommandParts,
        [string[]]$Arguments
    )

    $command = $CommandParts[0]
    $args = @()
    if ($CommandParts.Count -gt 1) {
        $args += $CommandParts[1..($CommandParts.Count - 1)]
    }
    $args += $Arguments
    Invoke-External -FilePath $command -Arguments $args
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Get-NormalizedPath $scriptDir
$venvPath = Join-Path $repoRoot "venv"
$venvScripts = Join-Path $venvPath "Scripts"
$venvPython = Join-Path $venvScripts "python.exe"
$requirementsPath = Join-Path $repoRoot "requirements.txt"

if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "requirements.txt was not found in $repoRoot"
}

$env:PATH = Remove-PathEntry -CurrentPath $env:PATH -EntryToRemove $venvScripts

if ($env:VIRTUAL_ENV) {
    $activeVenv = Get-NormalizedPath $env:VIRTUAL_ENV
    $targetVenv = Get-NormalizedPath $venvPath
    if ($activeVenv -eq $targetVenv) {
        Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
    }
}

$pythonCandidates = @()

if ($PythonExe) {
    $pythonCandidates += ,@($PythonExe)
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCandidates += ,@("py", "-3.11")
    $pythonCandidates += ,@("py", "-3")
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCandidates += ,@("python")
}

$selectedPython = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-PythonCandidate -CommandParts $candidate) {
        $selectedPython = $candidate
        break
    }
}

if ($null -eq $selectedPython) {
    throw "Could not find a working base Python. Run this script with -PythonExe <full path to python.exe>."
}

Write-Step "Using Python command: $($selectedPython -join ' ')"

if (Test-Path -LiteralPath $venvPath) {
    Write-Step "Removing existing venv"
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

Write-Step "Creating fresh virtual environment"
Invoke-PythonCommand -CommandParts $selectedPython -Arguments @("-m", "venv", $venvPath)

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "venv was created, but $venvPython was not found"
}

Write-Step "Upgrading pip"
Invoke-External -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")

Write-Step "Installing project dependencies"
Invoke-External -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", $requirementsPath)

Write-Step "Installing PyInstaller"
Invoke-External -FilePath $venvPython -Arguments @("-m", "pip", "install", "pyinstaller")

Write-Host ""
Write-Host "Environment has been rebuilt successfully." -ForegroundColor Green
Write-Host "Activate it with:" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Build command:" -ForegroundColor Yellow
Write-Host "  python -m PyInstaller --noconfirm --clean --onefile --windowed --name stream-video-downloader-gui gui.py"
