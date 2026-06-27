@echo off
cd /d "%~dp0"
set SERVICE_NAME=mcp-remote-shell
set UV_PATH=%USERPROFILE%\.local\bin\uv.exe

echo 检查 NSSM...
where nssm
if errorlevel 1 goto no_nssm
goto do_install

:no_nssm
echo [错误] 未找到 nssm.exe
echo 下载地址: https://nssm.cc/download
pause
exit /b 1

:do_install
echo 注册服务: %SERVICE_NAME%
nssm install %SERVICE_NAME% "%UV_PATH%"
nssm set %SERVICE_NAME% AppParameters "run --directory \"%CD%\" python src/server.py"
nssm set %SERVICE_NAME% AppDirectory "%CD%"
nssm set %SERVICE_NAME% AppEnvironmentExtra "MCP_HOST=0.0.0.0" "MCP_PORT=8080" "PYTHONIOENCODING=utf-8" "PYTHONUNBUFFERED=1"
nssm set %SERVICE_NAME% AppStdout "%CD%\logs\stdout.log"
nssm set %SERVICE_NAME% AppStderr "%CD%\logs\stderr.log"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm start %SERVICE_NAME%
echo.
echo 服务已启动: %SERVICE_NAME%
echo 管理: nssm stop/start/restart/remove %SERVICE_NAME%
pause
