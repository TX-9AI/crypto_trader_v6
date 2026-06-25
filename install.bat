@echo off
:: Bypass Windows security prompt — trusted local script
if not "%1"=="elevated" (
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\" elevated' -Verb RunAs"
    exit /b
)

:: =============================================================================
:: install.bat — crypto_trader v6.0 Windows EC2 Launcher
:: Place in C:\crypto_trader\ alongside your .pem key and tarball.
:: Double-click to run. Runs elevated automatically to fix PEM permissions.
:: =============================================================================

title crypto_trader v6.0 — EC2 Installer

echo.
echo ============================================================
echo   crypto_trader v6.0 ^| Vertigo Capital
echo ============================================================
echo.

:: ── Collect inputs ────────────────────────────────────────────────────────────
set /p EC2_IP="  EC2 Public IP: "
set /p KEY_FILE="  PEM key path [C:\crypto_trader\tx-9.pem]: "
if "%KEY_FILE%"=="" set KEY_FILE=C:\crypto_trader\tx-9.pem

set /p TARBALL="  Tarball path [C:\crypto_trader\crypto_trader_v6.0.tar.gz]: "
if "%TARBALL%"=="" set TARBALL=C:\crypto_trader\crypto_trader_v6.0.tar.gz

echo.
echo   Deployment: %TARBALL% → ubuntu@%EC2_IP%
echo.

:: ── Step 1: Fix PEM permissions ───────────────────────────────────────────────
echo [1/4] Fixing PEM permissions...
icacls "%KEY_FILE%" /inheritance:r >nul 2>&1
icacls "%KEY_FILE%" /grant:r "%USERNAME%:(R)" >nul 2>&1
icacls "%KEY_FILE%" /remove "BUILTIN\Users" >nul 2>&1
icacls "%KEY_FILE%" /remove "Everyone" >nul 2>&1
icacls "%KEY_FILE%" /remove "NT AUTHORITY\Authenticated Users" >nul 2>&1
icacls "%KEY_FILE%" /remove "NT AUTHORITY\NETWORK" >nul 2>&1
echo   PEM permissions fixed.

:: ── Step 2: Test connection ───────────────────────────────────────────────────
echo.
echo [2/4] Testing EC2 connection...
ssh -i "%KEY_FILE%" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@%EC2_IP% "echo connected" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Cannot reach %EC2_IP% — check IP and security group.
    pause
    exit /b 1
)
echo   Connected.

:: ── Step 3: Upload tarball ────────────────────────────────────────────────────
echo.
echo [3/4] Uploading tarball...
scp -i "%KEY_FILE%" -o StrictHostKeyChecking=no "%TARBALL%" ubuntu@%EC2_IP%:~/crypto_trader_v6.0.tar.gz
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Upload failed.
    pause
    exit /b 1
)
echo   Upload complete.

:: ── Step 4: Run install on EC2 ────────────────────────────────────────────────
echo.
echo [4/4] Running install on EC2...
echo   (This will prompt for credentials interactively)
echo.
ssh -t -i "%KEY_FILE%" -o StrictHostKeyChecking=no ubuntu@%EC2_IP% "bash install.sh"

echo.
echo ============================================================
echo   Done. SSH in with:
echo   ssh -i "%KEY_FILE%" ubuntu@%EC2_IP%
echo ============================================================
echo.
pause
