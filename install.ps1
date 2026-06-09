# SFC Installer for Windows
# One-line install (PowerShell):
#   irm https://raw.githubusercontent.com/Heysh1n/sfc/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$REPO         = "Heysh1n/sfc"
$DOWNLOAD_URL = "https://github.com/$REPO/releases/latest/download/sfc.pyz"
$INSTALL_DIR  = if ($env:SFC_INSTALL_DIR) { $env:SFC_INSTALL_DIR } else { "$env:USERPROFILE\.local\bin" }
$INSTALL_PYZ  = "$INSTALL_DIR\sfc.pyz"
$INSTALL_BAT  = "$INSTALL_DIR\sfc.bat"

# ── Colors ─────────────────────────────────────────────
function Write-Magenta($text)      { Write-Host $text -ForegroundColor Magenta }
function Write-BrightMagenta($text){ Write-Host $text -ForegroundColor Magenta }
function Write-Dim($text)          { Write-Host $text -ForegroundColor DarkGray }
function Write-Info($text)         { Write-Host "-> " -ForegroundColor Magenta -NoNewline; Write-Host $text }
function Write-Success($text)      { Write-Host "v  " -ForegroundColor Green -NoNewline; Write-Host $text }
function Write-Warn($text)         { Write-Host "!  " -ForegroundColor Yellow -NoNewline; Write-Host $text }
function Write-Err($text)          { Write-Host "x  " -ForegroundColor Red -NoNewline; Write-Host $text }
function Write-Line                { Write-Host "----------------------------------------------" -ForegroundColor DarkGray }

# ── Logo / Header ──────────────────────────────────────
function Show-Logo {
    $pad = "    "
    Write-Host ""
    Write-Host "${pad}######## ######## ######  " -ForegroundColor White
    Write-Host "${pad}##       ##      ##       " -ForegroundColor Gray
    Write-Host "${pad}#######  #####   ##       " -ForegroundColor Magenta
    Write-Host "${pad}      ## ##      ##       " -ForegroundColor Magenta
    Write-Host "${pad}####### ##        ######  " -ForegroundColor DarkMagenta
    Write-Host ""
}

function Show-Header {
    Clear-Host
    $pad = "    "
    Write-Host ""
    Write-Host "${pad}+--------------------------------------------+" -ForegroundColor Magenta
    Write-Host "${pad}|              " -ForegroundColor Magenta -NoNewline
    Write-Host "SFC Installer" -ForegroundColor White -NoNewline
    Write-Host "               |" -ForegroundColor Magenta
    Write-Host "${pad}+--------------------------------------------+" -ForegroundColor Magenta
    Show-Logo
    Write-Host "${pad}      Smart File Collector" -ForegroundColor DarkGray
    Write-Host ""
}

function Pause-Screen {
    Write-Host ""
    Write-Host "Press Enter to continue..." -ForegroundColor DarkGray -NoNewline
    $null = Read-Host
}

# ── Python check ───────────────────────────────────────
function Get-PythonCmd {
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python 3\.(\d+)") {
                $minor = [int]$Matches[1]
                if ($minor -ge 10) { return $cmd }
                Write-Warn "Found $ver but Python 3.10+ required"
            }
        } catch { }
    }
    return $null
}

# ── PATH helpers ───────────────────────────────────────
function Test-InPath($dir) {
    $current = [Environment]::GetEnvironmentVariable("PATH", "User")
    return $current -split ";" -contains $dir
}

function Add-ToUserPath($dir) {
    $current = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($current -split ";" -contains $dir) {
        Write-Warn "PATH entry already exists"
        return
    }
    $new = "$dir;$current"
    [Environment]::SetEnvironmentVariable("PATH", $new, "User")
    $env:PATH = "$dir;$env:PATH"
    Write-Success "Added $dir to user PATH"
    Write-Warn "Restart terminal for PATH to take effect"
}

# ── Install ────────────────────────────────────────────
function Install-SFC {
    Show-Header
    Write-Host "Installing / Updating SFC`n" -ForegroundColor White

    # Python check
    $pyCmd = Get-PythonCmd
    if (-not $pyCmd) {
        Write-Err "Python 3.10+ not found"
        Write-Host ""
        Write-Host "  Download Python from: https://python.org/downloads" -ForegroundColor Cyan
        Write-Host "  Make sure to check 'Add Python to PATH' during install" -ForegroundColor DarkGray
        Write-Host ""
        Pause-Screen
        return
    }
    Write-Info "Python: $pyCmd"

    # Create install dir
    if (-not (Test-Path $INSTALL_DIR)) {
        New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
    }
    Write-Info "Install path: $INSTALL_PYZ"

    # Download
    Write-Info "Downloading latest release..."
    $TMP = "$INSTALL_DIR\sfc.tmp.pyz"
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Headers["User-Agent"] = "sfc-installer"
        $wc.DownloadFile($DOWNLOAD_URL, $TMP)
    } catch {
        Write-Err "Failed to download SFC: $_"
        Write-Host ""
        Write-Host "  Expected URL:" -ForegroundColor DarkGray
        Write-Host "  $DOWNLOAD_URL" -ForegroundColor Magenta
        if (Test-Path $TMP) { Remove-Item $TMP -Force }
        Pause-Screen
        return
    }

    Move-Item -Force $TMP $INSTALL_PYZ

    # Create sfc.bat wrapper
    $batContent = "@echo off`r`n$pyCmd `"%~dp0sfc.pyz`" %*"
    Set-Content -Path $INSTALL_BAT -Value $batContent -Encoding ASCII

    Write-Host ""
    Write-Line
    Write-Success "SFC installed successfully"
    Write-Line
    Write-Host ""

    # PATH
    if (-not (Test-InPath $INSTALL_DIR)) {
        Write-Warn "$INSTALL_DIR is not in your PATH"
        Write-Host ""
        $ans = Read-Host "Add it automatically? [Y/n]"
        if ($ans -notmatch "^[nN]") {
            Add-ToUserPath $INSTALL_DIR
            Write-Host ""
            Write-Host "Run after restarting terminal:" -ForegroundColor White
            Write-Host "  sfc" -ForegroundColor Magenta
        } else {
            Write-Host ""
            Write-Host "Direct run now:" -ForegroundColor White
            Write-Host "  $pyCmd `"$INSTALL_PYZ`"" -ForegroundColor Magenta
        }
    } else {
        Write-Host "Run:" -ForegroundColor White
        Write-Host "  sfc" -ForegroundColor Magenta
    }

    Write-Host ""
}

# ── Uninstall ──────────────────────────────────────────
function Uninstall-SFC {
    Show-Header
    Write-Host "Uninstall SFC`n" -ForegroundColor White

    Write-Info "Install path: $INSTALL_PYZ"

    if (-not (Test-Path $INSTALL_PYZ)) {
        Write-Warn "SFC is not installed at this path"
        Pause-Screen
        return
    }

    Write-Host ""
    $ans = Read-Host "Remove SFC from this system? [y/N]"
    if ($ans -match "^[yY]") {
        Remove-Item -Force $INSTALL_PYZ -ErrorAction SilentlyContinue
        Remove-Item -Force $INSTALL_BAT -ErrorAction SilentlyContinue
        Write-Success "Removed $INSTALL_DIR\sfc.*"
    } else {
        Write-Info "Cancelled"
    }

    Pause-Screen
}

# ── Show location ──────────────────────────────────────
function Show-Location {
    Show-Header
    Write-Host "Install location`n" -ForegroundColor White

    Write-Info $INSTALL_PYZ

    if (Test-Path $INSTALL_PYZ) {
        Write-Success "SFC is installed"
    } else {
        Write-Warn "SFC is not installed yet"
    }

    Write-Host ""
    Write-Host "PATH status:" -ForegroundColor White
    if (Test-InPath $INSTALL_DIR) {
        Write-Success "$INSTALL_DIR is in PATH"
    } else {
        Write-Warn "$INSTALL_DIR is not in PATH"
    }

    Pause-Screen
}

# ── Menu ───────────────────────────────────────────────
function Show-Menu {
    while ($true) {
        Show-Header

        Write-Host "Select action:`n" -ForegroundColor White
        Write-Host "  " -NoNewline; Write-Host "1" -ForegroundColor Magenta -NoNewline; Write-Host ") Install / Update SFC locally"
        Write-Host "  " -NoNewline; Write-Host "2" -ForegroundColor Magenta -NoNewline; Write-Host ") Show install location"
        Write-Host "  " -NoNewline; Write-Host "3" -ForegroundColor Magenta -NoNewline; Write-Host ") Uninstall SFC"
        Write-Host "  " -NoNewline; Write-Host "4" -ForegroundColor Magenta -NoNewline; Write-Host ") Exit"
        Write-Host ""

        $action = Read-Host "Choice"

        switch ($action) {
            "1" { Install-SFC; return }
            "2" { Show-Location }
            "3" { Uninstall-SFC }
            { $_ -in "4","0","q","Q" } {
                Write-Host ""
                Write-Info "Exit."
                return
            }
            default {
                Write-Host ""
                Write-Err "Invalid option"
                Pause-Screen
            }
        }
    }
}

# ── Entry point ────────────────────────────────────────
$cmd = if ($args.Count -gt 0) { $args[0] } else { "" }

switch ($cmd) {
    { $_ -in "install","update","--install","-i" } { Install-SFC }
    { $_ -in "uninstall","remove","--uninstall" }  { Uninstall-SFC }
    { $_ -in "location","path","--location","--path" } { Show-Location }
    { $_ -in "help","--help","-h" } {
        Write-Host "SFC Installer`n"
        Write-Host "Usage:"
        Write-Host "  .\install.ps1              Open menu"
        Write-Host "  .\install.ps1 install      Install / update"
        Write-Host "  .\install.ps1 uninstall    Uninstall"
        Write-Host "  .\install.ps1 location     Show install location"
    }
    "" { Show-Menu }
    default {
        Write-Err "Unknown option: $cmd"
        Write-Host "Run: .\install.ps1 --help"
        exit 1
    }
}
