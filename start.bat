@echo off
cd /d "%~dp0"
if "%MCP_HOST%"=="" set MCP_HOST=0.0.0.0
if "%MCP_PORT%"=="" set MCP_PORT=8080
echo ========================================
echo  MCP Remote Shell 启动
echo  地址: http://%MCP_HOST%:%MCP_PORT%/mcp
echo  Ctrl+C 停止服务
echo ========================================
echo.
uv run python src/server.py
pause
