"""
MCP Remote Shell Server
传输模式: Streamable HTTP (FastMCP >= 1.0.0)
"""

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
from connection_manager import ConnectionManager
from ssh_handler import SSHHandler
from telnet_handler import TelnetHandler

# ─── 日志 ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).parent.parent / "logs" / "mcp_server.log",
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("mcp-remote-shell")

# ─── 初始化 FastMCP ───
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8080"))

mcp = FastMCP(
    "remote-shell",
    host=HOST,
    port=PORT,
    streamable_http_path="/mcp",
)
conn_manager = ConnectionManager()


@mcp.tool()
async def ssh_connect(
    host: str,
    username: str,
    password: str = "",
    private_key: str = "",
    passphrase: str = "",
    port: int = 22,
    timeout: int = 30,
    session_id: str = "",
) -> str:
    """通过 SSH 连接到远程设备。password 与 private_key 二选一。返回会话 ID。"""
    handler = SSHHandler()
    sid = session_id or conn_manager.generate_id("ssh")
    result = await handler.connect(
        host=host, port=port, username=username,
        password=password or None,
        private_key=private_key or None,
        passphrase=passphrase or None,
        timeout=timeout,
    )
    if result["success"]:
        conn_manager.add(sid, "ssh", handler, host, username)
        logger.info(f"SSH 连接成功: {username}@{host}:{port} -> {sid}")
        return f"SSH 连接成功 | 会话ID: {sid} | 主机: {host}:{port} | 用户: {username}"
    return f"SSH 连接失败: {result['error']}"


@mcp.tool()
async def telnet_connect(
    host: str,
    username: str,
    password: str,
    port: int = 23,
    timeout: int = 30,
    login_prompt: str = "login:",
    passwd_prompt: str = "Password:",
    session_id: str = "",
) -> str:
    """通过 Telnet 连接到远程设备（路由器/交换机）。华为用 Username:/Password:。返回会话 ID。"""
    handler = TelnetHandler()
    sid = session_id or conn_manager.generate_id("telnet")
    result = await handler.connect(
        host=host, port=port, username=username, password=password,
        timeout=timeout, login_prompt=login_prompt, passwd_prompt=passwd_prompt,
    )
    if result["success"]:
        conn_manager.add(sid, "telnet", handler, host, username)
        logger.info(f"Telnet 连接成功: {username}@{host}:{port} -> {sid}")
        return f"Telnet 连接成功 | 会话ID: {sid} | 主机: {host}:{port}"
    return f"Telnet 连接失败: {result['error']}"


@mcp.tool()
async def execute_command(
    session_id: str,
    command: str,
    timeout: int = 30,
    expect: str = "",
) -> str:
    """在已连接的会话中执行命令并返回输出。expect 为可选输出结束标志（正则）。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}，请先使用 ssh_connect 或 telnet_connect"
    result = await session["handler"].execute(
        command=command, timeout=timeout, expect=expect or None,
    )
    if result["success"]:
        output = result.get("output", "").strip()
        return f"$ {command}\n{output or chr(40)+chr(41)}"
    return f"执行失败: {result['error']}\n{result.get('output', '')}"


@mcp.tool()
async def execute_commands(
    session_id: str,
    commands: list[str],
    timeout: int = 30,
    stop_on_error: bool = False,
) -> str:
    """批量按顺序执行多条命令。stop_on_error=True 时遇错停止。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}"
    parts = []
    for cmd in commands:
        result = await session["handler"].execute(command=cmd, timeout=timeout)
        output = result.get("output", "").strip()
        ok = "OK" if result["success"] else "ERR"
        parts.append(f"[{ok}] $ {cmd}\n{output or chr(40)+chr(41)}")
        if not result["success"] and stop_on_error:
            parts.append("遇到错误，已停止后续命令")
            break
    return "\n\n".join(parts)


@mcp.tool()
async def send_interactive(
    session_id: str,
    input: str,
    expect: str = "",
    timeout: int = 15,
) -> str:
    """发送交互式输入，适用于 sudo 密码、y/n 确认等。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}"
    result = await session["handler"].send_input(
        input_text=input, expect=expect or None, timeout=timeout,
    )
    if result["success"]:
        return f"已发送\n{result.get('output', '').strip()}"
    return f"发送失败: {result['error']}"


@mcp.tool()
async def disconnect(session_id: str) -> str:
    """断开并关闭指定会话。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}"
    await session["handler"].disconnect()
    conn_manager.remove(session_id)
    return f"会话 {session_id} 已断开"


@mcp.tool()
async def list_sessions() -> str:
    """列出当前所有活跃的连接会话。"""
    sessions = conn_manager.list_all()
    if not sessions:
        return "当前没有活跃会话"
    lines = ["活跃会话:"]
    for sid, info in sessions.items():
        lines.append(f"  [{sid}] {info['type'].upper()} {info['username']}@{info['host']} 连接于 {info['connected_at']}")
    return "\n".join(lines)


@mcp.tool()
async def get_session_info(session_id: str) -> str:
    """获取指定会话详细信息及连接状态。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}"
    info = {
        "session_id": session_id,
        "type": session["type"],
        "host": session["host"],
        "username": session["username"],
        "connected_at": session["connected_at"],
        "is_alive": await session["handler"].is_alive(),
    }
    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
async def upload_file(session_id: str, local_path: str, remote_path: str) -> str:
    """通过 SFTP 上传文件到远程主机（仅 SSH 会话）。local_path 为 Windows 路径。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}"
    if session["type"] != "ssh":
        return "文件传输仅支持 SSH 会话"
    result = await session["handler"].upload_file(local_path, remote_path)
    if result["success"]:
        return f"上传成功: {local_path} -> {remote_path}"
    return f"上传失败: {result['error']}"


@mcp.tool()
async def download_file(session_id: str, remote_path: str, local_path: str) -> str:
    """通过 SFTP 从远程主机下载文件（仅 SSH 会话）。local_path 为 Windows 保存路径。"""
    session = conn_manager.get(session_id)
    if not session:
        return f"会话不存在: {session_id}"
    if session["type"] != "ssh":
        return "文件传输仅支持 SSH 会话"
    result = await session["handler"].download_file(remote_path, local_path)
    if result["success"]:
        return f"下载成功: {remote_path} -> {local_path}"
    return f"下载失败: {result['error']}"


# ─── 启动 ───
def main():
    logger.info(f"MCP Remote Shell 启动: http://{HOST}:{PORT}/mcp")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
