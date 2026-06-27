@echo off
cd /d "%~dp0"
echo ========================================
echo  MCP Remote Shell - 安装脚本
echo  工作目录: %CD%
echo ========================================
echo.

echo [步骤 1/4] 检查 uv...
where uv
if errorlevel 1 goto install_uv
echo uv 已存在 OK
goto step2

:install_uv
echo uv 未安装，开始安装...
powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 goto uv_fail
echo uv 安装完成，请关闭窗口重新打开 cmd 后再次运行 install.bat
pause
exit /b 0

:uv_fail
echo [错误] uv 安装失败
echo 请手动安装: https://docs.astral.sh/uv/
pause
exit /b 1

:step2
echo.
echo [步骤 2/4] 安装 Python 3.11...
uv python install 3.11
if errorlevel 1 goto py_fail
echo Python 3.11 OK
goto step3

:py_fail
echo [错误] Python 3.11 安装失败
pause
exit /b 1

:step3
echo.
echo [步骤 3/4] 安装依赖...
uv sync
if errorlevel 1 goto sync_fail
echo 依赖安装 OK
goto step4

:sync_fail
echo [错误] uv sync 失败，请检查网络或 pyproject.toml
pause
exit /b 1

:step4
echo.
echo [步骤 4/4] 验证安装...
if not exist logs mkdir logs
uv run python -c "import mcp; import paramiko; import uvicorn; print('验证通过')"
if errorlevel 1 goto verify_fail
echo.
echo ========================================
echo  安装成功！运行 start.bat 启动服务
echo ========================================
pause
exit /b 0

:verify_fail
echo [错误] 验证失败，请检查依赖
pause
exit /b 1
