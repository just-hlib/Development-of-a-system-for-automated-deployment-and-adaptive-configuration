#Requires -Version 5.1
<#
.SYNOPSIS
    AutoDeploy v2.0 — One-liner bootstrapper
    Usage: irm https://gist.githubusercontent.com/just-hlib/e19e9c7111d523c1e2795250926c8f6a/raw/7a2aee92bc8e7c2e82c469811eb27d1e7820c169/setup.ps1 | iex

.DESCRIPTION
    Checks prerequisites (Python, Git), clones the repo,
    creates venv, installs dependencies, starts the FastAPI
    server in background, and launches the Textual TUI.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION  (change before hosting)
# ─────────────────────────────────────────────────────────────
$REPO_URL    = "https://github.com/just-hlib/Development-of-a-system-for-automated-deployment-and-adaptive-configuration.git"
$INSTALL_DIR = "C:\AutoDeploy"
$SERVER_PORT = 8000
$MIN_PYTHON  = [Version]"3.10.0"

# ─────────────────────────────────────────────────────────────
#  COLOURS / HELPERS
# ─────────────────────────────────────────────────────────────
function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "  ██████╗ ██╗   ██╗████████╗ ██████╗ " -ForegroundColor Cyan
    Write-Host "  ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗" -ForegroundColor Cyan
    Write-Host "  ███████║██║   ██║   ██║   ██║   ██║" -ForegroundColor Cyan
    Write-Host "  ██╔══██║██║   ██║   ██║   ██║   ██║" -ForegroundColor Cyan
    Write-Host "  ██║  ██║╚██████╔╝   ██║   ╚██████╔╝" -ForegroundColor Cyan
    Write-Host "  ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ " -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Windows 11 Auto-Deploy System v2.0" -ForegroundColor DarkCyan
    Write-Host "  One-liner bootstrapper" -ForegroundColor DarkGray
    Write-Host ""
}

function Write-Step   { param($n,$t) Write-Host "  [$n] $t" -ForegroundColor Yellow }
function Write-OK     { param($t)    Write-Host "  [OK] $t" -ForegroundColor Green  }
function Write-Info   { param($t)    Write-Host "  [..] $t" -ForegroundColor DarkCyan }
function Write-Warn   { param($t)    Write-Host "  [!!] $t" -ForegroundColor Magenta }
function Write-Fail {
    param($t)
    Write-Host ""
    Write-Host "  [XX] $t" -ForegroundColor Red
    Write-Host ""
    Read-Host "  Press Enter to close"
    exit 1
}

# ─────────────────────────────────────────────────────────────
#  STEP 0 — Self-elevate to Administrator
# ─────────────────────────────────────────────────────────────
function Assert-Admin {
    $me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Warn "Not running as Administrator — relaunching elevated..."
        $elevArgs = "-NoProfile -ExecutionPolicy Bypass -Command `"irm '$MyInvocation.MyCommand.Path' | iex`""
        Start-Process powershell.exe -ArgumentList $elevArgs -Verb RunAs
        exit
    }
    Write-OK "Running as Administrator"
}

# ─────────────────────────────────────────────────────────────
#  STEP 1 — Detect system architecture
# ─────────────────────────────────────────────────────────────
function Get-Arch {
    $arch = (Get-WmiObject Win32_OperatingSystem).OSArchitecture
    if ($arch -match "ARM") {
        Write-Info "Architecture: ARM64"
        return "arm64"
    }
    Write-Info "Architecture: x64"
    return "x64"
}

# ─────────────────────────────────────────────────────────────
#  STEP 2 — Ensure Winget is available
# ─────────────────────────────────────────────────────────────
function Assert-Winget {
    Write-Step 2 "Checking winget..."
    try {
        $v = (winget --version 2>&1)
        Write-OK "winget $v"
    } catch {
        Write-Warn "winget not found — installing App Installer..."
        Write-Host ""
        Write-Host "  Please install 'App Installer' from the Microsoft Store," -ForegroundColor Yellow
        Write-Host "  then re-run this script." -ForegroundColor Yellow
        Write-Host "  ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1" -ForegroundColor Cyan
        Write-Host ""
        pause
        exit 1
    }
}

# ─────────────────────────────────────────────────────────────
#  STEP 3 — Ensure Python >= 3.10
# ─────────────────────────────────────────────────────────────
function Assert-Python {
    Write-Step 3 "Checking Python $MIN_PYTHON+..."

    $py = $null
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+\.\d+\.\d+)") {
                $found = [Version]$Matches[1]
                if ($found -ge $MIN_PYTHON) {
                    $script:PYTHON_CMD = $cmd
                    Write-OK "Found Python $found ($cmd)"
                    return
                } else {
                    Write-Warn "Found Python $found — too old (need $MIN_PYTHON+)"
                }
            }
        } catch {}
    }

    Write-Info "Installing Python 3.12 via winget..."
    winget install --id Python.Python.3.12 `
        --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Python install failed (exit $LASTEXITCODE)"
    }

    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")

    $script:PYTHON_CMD = "python"
    Write-OK "Python 3.12 installed"
}

# ─────────────────────────────────────────────────────────────
#  STEP 4 — Ensure Git
# ─────────────────────────────────────────────────────────────
function Assert-Git {
    Write-Step 4 "Checking Git..."
    try {
        $v = (git --version 2>&1)
        Write-OK "$v"
    } catch {
        Write-Info "Git not found — installing via winget..."
        winget install --id Git.Git `
            --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { Write-Fail "Git install failed" }

        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-OK "Git installed"
    }
}

# ─────────────────────────────────────────────────────────────
#  STEP 5 — Clone or update the repository
# ─────────────────────────────────────────────────────────────
function Get-Repo {
    Write-Step 5 "Setting up repository at $INSTALL_DIR..."

    # ── Prevent Git from hanging on credential prompts ─────────────────────
    # GIT_TERMINAL_PROMPT=0 → git fails immediately instead of waiting for input.
    # GIT_ASKPASS=echo      → if anything still asks, echo returns empty string.
    $env:GIT_TERMINAL_PROMPT = "0"
    $env:GIT_ASKPASS         = "echo"

    # ── Pre-flight: verify repo URL is reachable & public ──────────────────
    $checkUrl = $REPO_URL -replace '\.git$', ''
    Write-Info "Pre-flight check: $checkUrl"
    try {
        $resp = Invoke-WebRequest -Uri $checkUrl -UseBasicParsing -Method Head `
                    -TimeoutSec 10 -ErrorAction Stop
        Write-OK "Repository reachable (HTTP $($resp.StatusCode))"
    } catch {
        $httpCode = 0
        if ($_.Exception.PSObject.Properties['Response'] -and $_.Exception.Response) {
            $httpCode = [int]$_.Exception.Response.StatusCode
        }
        if ($httpCode -eq 404) {
            Write-Warn "Repository returned HTTP 404!"
            Write-Host ""
            Write-Host "  The repository may be PRIVATE or the URL may be wrong." -ForegroundColor Yellow
            Write-Host "  URL: $REPO_URL" -ForegroundColor DarkGray
            Write-Host "  If private, configure Git credentials before re-running." -ForegroundColor Yellow
            Write-Host ""
            Write-Fail "Cannot clone a private/missing repo without credentials."
        } else {
            # Network hiccup or other HTTP error — warn but still try git
            Write-Warn "Pre-flight failed ($($_.Exception.Message)) — attempting git anyway..."
        }
    }

    # ── Handle existing directory ──────────────────────────────────────────
    if (Test-Path "$INSTALL_DIR\.git") {
        Write-Info "Repository already exists — pulling latest changes..."
        Push-Location $INSTALL_DIR
        Write-Info "Running: git pull origin"
        # No --quiet: show every git output line so the user sees progress
        git pull origin 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        $pullExit = $LASTEXITCODE   # capture before Pop-Location resets it
        Pop-Location
        if ($pullExit -ne 0) {
            Write-Fail "git pull failed (exit $pullExit) — see output above."
        }
        Write-OK "Repository updated"

    } else {
        # ── Directory exists but is NOT a git repo ──────────────────────
        if (Test-Path $INSTALL_DIR) {
            Write-Warn "$INSTALL_DIR exists but is not a git repository."
            $choice = Read-Host "  Delete it and re-clone? [Y/N]"
            if ($choice -notmatch '^[Yy]') {
                Write-Fail "Aborted — remove '$INSTALL_DIR' manually, then re-run."
            }
            Write-Info "Removing $INSTALL_DIR..."
            try {
                Remove-Item -Recurse -Force $INSTALL_DIR -ErrorAction Stop
                Write-OK "Directory removed"
            } catch {
                Write-Fail (
                    "Could not delete '$INSTALL_DIR' — it may be locked by another process.`n" +
                    "  Close any programs using it, then re-run.`n" +
                    "  Error: $($_.Exception.Message)"
                )
            }
        }

        # ── Clone ──────────────────────────────────────────────────────
        Write-Info "Cloning from $REPO_URL..."
        Write-Info "Running: git clone --depth 1 $REPO_URL $INSTALL_DIR"
        # No --quiet: pipe both stdout and stderr so the user sees clone progress
        git clone $REPO_URL $INSTALL_DIR --depth 1 2>&1 | ForEach-Object {
            Write-Host "    $_" -ForegroundColor DarkGray
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "git clone failed (exit $LASTEXITCODE) — see output above."
        }
        Write-OK "Repository cloned"
    }
}

# ─────────────────────────────────────────────────────────────
#  STEP 6 — Create virtual environment & install deps
# ─────────────────────────────────────────────────────────────
function Install-Deps {
    Write-Step 6 "Setting up Python virtual environment..."
    Push-Location $INSTALL_DIR

    $venvPy = "$INSTALL_DIR\venv\Scripts\python.exe"

    if (-not (Test-Path $venvPy)) {
        Write-Info "Creating venv..."
        & $script:PYTHON_CMD -m venv venv
        if ($LASTEXITCODE -ne 0) { Write-Fail "venv creation failed" }
    } else {
        Write-Info "venv already exists — skipping creation"
    }

    Write-Info "Installing / upgrading requirements..."
    & $venvPy -m pip install --upgrade pip --quiet
    & $venvPy -m pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -ne 0) { Write-Fail "pip install failed" }

    Write-OK "Dependencies installed"
    Pop-Location
}

# ─────────────────────────────────────────────────────────────
#  STEP 7 — Start FastAPI server (background job)
# ─────────────────────────────────────────────────────────────
function Start-Server {
    Write-Step 7 "Starting FastAPI server on port $SERVER_PORT..."

    # Kill any stale server on the same port
    $old = Get-NetTCPConnection -LocalPort $SERVER_PORT -ErrorAction SilentlyContinue |
           Select-Object -ExpandProperty OwningProcess -Unique
    if ($old) {
        Write-Warn "Port $SERVER_PORT in use (PID $old) — stopping..."
        Stop-Process -Id $old -Force -ErrorAction SilentlyContinue
        Start-Sleep 1
    }

    $venvPy     = "$INSTALL_DIR\venv\Scripts\python.exe"
    $serverDir  = "$INSTALL_DIR\server"
    $logFile    = "$INSTALL_DIR\server.log"

    # Launch server as a detached background process
    $proc = Start-Process -FilePath $venvPy `
        -ArgumentList "-m", "uvicorn", "main:app",
                      "--host", "127.0.0.1",
                      "--port", "$SERVER_PORT",
                      "--log-level", "warning" `
        -WorkingDirectory $serverDir `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError  "$INSTALL_DIR\server_err.log" `
        -PassThru -WindowStyle Hidden

    # Wait up to 10 s for the server to become ready
    $ready    = $false
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 400
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$SERVER_PORT/" `
                                   -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
    }

    if ($ready) {
        Write-OK "Server running (PID $($proc.Id)) — http://127.0.0.1:$SERVER_PORT"
    } else {
        Write-Warn "Server did not respond in 10 s — check $logFile"
    }
}

# ─────────────────────────────────────────────────────────────
#  STEP 8 — (Optional) Apply a build file if provided
# ─────────────────────────────────────────────────────────────
function Apply-BuildFile {
    param([string]$BuildPath)
    if (-not $BuildPath) { return }

    if (-not (Test-Path $BuildPath)) {
        Write-Warn "Build file not found: $BuildPath — skipping"
        return
    }

    Write-Step 8 "Applying build file: $BuildPath"
    $venvPy = "$INSTALL_DIR\venv\Scripts\python.exe"
    Push-Location "$INSTALL_DIR\client"
    & $venvPy main.py apply --file $BuildPath
    Pop-Location
}

# ─────────────────────────────────────────────────────────────
#  STEP 9 — Launch Textual TUI
# ─────────────────────────────────────────────────────────────
function Start-TUI {
    Write-Step 9 "Launching AutoDeploy TUI..."
    Write-Host ""
    Write-Host "  Press Q inside the TUI to quit." -ForegroundColor DarkGray
    Write-Host ""

    $venvPy = "$INSTALL_DIR\venv\Scripts\python.exe"
    Push-Location "$INSTALL_DIR\client"
    & $venvPy tui.py
    Pop-Location
}

# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────
Write-Header

Assert-Admin

$arch = Get-Arch
Write-Info "System: $arch | PS $($PSVersionTable.PSVersion)"
Write-Host ""

Assert-Winget
Assert-Python
Assert-Git
Get-Repo
Install-Deps
Start-Server

# Optional: pass a build file via env var
#   $env:AUTODEPLOY_BUILD = "C:\Users\Me\my_build.json"
#   irm https://... | iex
if ($env:AUTODEPLOY_BUILD) {
    Apply-BuildFile -BuildPath $env:AUTODEPLOY_BUILD
}

Start-TUI

Write-Host ""
Write-OK "AutoDeploy session ended. Server is still running in background."
Write-Host "  Stop it any time: Stop-Process -Name python" -ForegroundColor DarkGray
Write-Host ""