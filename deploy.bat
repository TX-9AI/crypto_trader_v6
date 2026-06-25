@echo off
:: =============================================================================
:: deploy.bat — Deploy updates to crypto-trader EC2
:: Usage: deploy.bat [full|code|creds|restart|status]
::   full    — git push + EC2 pull + validator curl + restart
::   code    — git push + EC2 pull + restart (no credentials)
::   creds   — SCP credentials.py only
::   restart — restart EC2 service only
::   status  — show bot status
:: =============================================================================

set EC2_IP=REPLACE_WITH_EC2_IP
set KEY=C:\crypto_trader\crypto_trader.pem
set REMOTE=ubuntu@%EC2_IP%
set INSTALL=~/crypto-trader

set MODE=%1
if "%MODE%"=="" set MODE=full

echo.
echo [deploy.bat] Mode: %MODE%
echo.

if "%MODE%"=="full" goto FULL
if "%MODE%"=="code" goto CODE
if "%MODE%"=="creds" goto CREDS
if "%MODE%"=="restart" goto RESTART
if "%MODE%"=="status" goto STATUS

echo Unknown mode: %MODE%
echo Usage: deploy.bat [full^|code^|creds^|restart^|status]
exit /b 1

:FULL
echo Pushing to GitHub...
git add .
git commit -m "deploy: update" 2>nul || echo (nothing to commit)
git push origin master

echo.
echo Pulling on EC2...
ssh -i "%KEY%" %REMOTE% "cd %INSTALL% && git pull origin master"

echo.
echo Re-applying signal validator...
ssh -i "%KEY%" %REMOTE% "curl -s https://raw.githubusercontent.com/TX-9AI/crypto_trader/master/execution/signal_validator.py -o %INSTALL%/execution/signal_validator.py"

echo.
echo Restarting service...
ssh -i "%KEY%" %REMOTE% "sudo systemctl restart cryptobot && sleep 5 && python %INSTALL%/status.py"
goto END

:CODE
echo Pushing to GitHub...
git add .
git commit -m "deploy: code update" 2>nul || echo (nothing to commit)
git push origin master

echo.
echo Pulling on EC2...
ssh -i "%KEY%" %REMOTE% "cd %INSTALL% && git pull origin master && sudo systemctl restart cryptobot && sleep 5 && python %INSTALL%/status.py"
goto END

:CREDS
echo Uploading credentials.py...
scp -i "%KEY%" C:\crypto_trader\credentials.py %REMOTE%:%INSTALL%/credentials.py
echo Done.
goto END

:RESTART
echo Restarting service...
ssh -i "%KEY%" %REMOTE% "sudo systemctl restart cryptobot && sleep 5 && python %INSTALL%/status.py"
goto END

:STATUS
ssh -i "%KEY%" %REMOTE% "python %INSTALL%/status.py"
goto END

:END
echo.
echo Done.
pause
