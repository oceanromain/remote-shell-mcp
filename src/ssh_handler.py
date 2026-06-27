"""
SSHHandler: 基于 paramiko 的 SSH 连接处理器
支持: 密码认证、私钥认证、SFTP 文件传输、交互式 shell
"""

import asyncio
import io
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any

import paramiko

logger = logging.getLogger("ssh-handler")


class SSHHandler:
    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None
        self._shell: Optional[paramiko.Channel] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    # ──────────────── 连接 ────────────────

    async def connect(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs: Dict[str, Any] = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": timeout,
                "allow_agent": False,
                "look_for_keys": False,
            }

            if private_key:
                pkey = self._load_private_key(private_key, passphrase)
                connect_kwargs["pkey"] = pkey
            elif password:
                connect_kwargs["password"] = password
            else:
                return {"success": False, "error": "必须提供 password 或 private_key"}

            # 在线程池中执行同步的 connect
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: client.connect(**connect_kwargs))

            self._client = client

            # 打开交互式 shell
            self._shell = client.invoke_shell(width=220, height=50)
            self._shell.settimeout(timeout)

            # 等待初始 banner/提示符
            await asyncio.sleep(1.5)
            self._drain()  # 清空初始输出

            logger.info(f"SSH 连接成功: {username}@{host}:{port}")
            return {"success": True}

        except paramiko.AuthenticationException as e:
            return {"success": False, "error": f"认证失败: {e}"}
        except paramiko.SSHException as e:
            return {"success": False, "error": f"SSH 错误: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _load_private_key(self, key_data: str, passphrase: Optional[str]) -> paramiko.PKey:
        """支持文件路径或直接 PEM 内容"""
        pp = passphrase.encode() if passphrase else None

        # 如果是文件路径
        if os.path.exists(key_data):
            for cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
                try:
                    return cls.from_private_key_file(key_data, password=pp)
                except Exception:
                    continue
            raise ValueError(f"无法识别私钥格式: {key_data}")

        # 否则当作 PEM 内容
        buf = io.StringIO(key_data)
        for cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.DSSKey):
            try:
                buf.seek(0)
                return cls.from_private_key(buf, password=pp)
            except Exception:
                continue
        raise ValueError("无法解析私钥内容")

    # ──────────────── 命令执行 ────────────────

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        expect: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._shell:
            return {"success": False, "error": "未连接", "output": ""}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._execute_sync, command, timeout, expect
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def _execute_sync(self, command: str, timeout: int, expect: Optional[str]) -> Dict[str, Any]:
        shell = self._shell

        # 发送命令
        shell.send(command + "\n")

        # 等待输出结束
        output = self._read_until(
            timeout=timeout,
            expect_pattern=expect,
        )

        return {"success": True, "output": self._clean_ansi(output)}

    def _read_until(self, timeout: int = 30, expect_pattern: Optional[str] = None) -> str:
        """读取直到匹配提示符或超时"""
        shell = self._shell
        buffer = ""
        deadline = time.time() + timeout

        # 默认提示符模式（Linux / Cisco / Huawei / 各类设备）
        default_pattern = (
            r"[\$#>]\s*$"          # Linux shell / 网络设备
            r"|[>\]]\s*$"          # 方括号提示
            r"|\(config\)[#>]\s*$"  # 配置模式
        )
        pattern = expect_pattern or default_pattern

        while time.time() < deadline:
            if shell.recv_ready():
                chunk = shell.recv(8192).decode("utf-8", errors="replace")
                buffer += chunk

                # 检查是否到达提示符
                lines = buffer.splitlines()
                last = lines[-1] if lines else ""
                if re.search(pattern, last):
                    break
            else:
                time.sleep(0.1)

        return buffer

    def _drain(self):
        """清空缓冲区"""
        shell = self._shell
        time.sleep(0.3)
        while shell.recv_ready():
            shell.recv(4096)

    # ──────────────── 交互式输入 ────────────────

    async def send_input(
        self,
        input_text: str,
        expect: Optional[str] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        if not self._shell:
            return {"success": False, "error": "未连接", "output": ""}

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._send_input_sync, input_text, expect, timeout
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def _send_input_sync(self, text: str, expect: Optional[str], timeout: int) -> Dict[str, Any]:
        self._shell.send(text + "\n")
        output = self._read_until(timeout=timeout, expect_pattern=expect)
        return {"success": True, "output": self._clean_ansi(output)}

    # ──────────────── SFTP 文件传输 ────────────────

    async def upload_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._upload_sync, local_path, remote_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _upload_sync(self, local_path: str, remote_path: str):
        if not self._sftp:
            self._sftp = self._client.open_sftp()
        self._sftp.put(local_path, remote_path)

    async def download_file(self, remote_path: str, local_path: str) -> Dict[str, Any]:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._download_sync, remote_path, local_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _download_sync(self, remote_path: str, local_path: str):
        if not self._sftp:
            self._sftp = self._client.open_sftp()
        # 确保本地目录存在
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self._sftp.get(remote_path, local_path)

    # ──────────────── 状态检测 ────────────────

    async def is_alive(self) -> bool:
        if not self._client or not self._shell:
            return False
        try:
            transport = self._client.get_transport()
            return transport is not None and transport.is_active()
        except Exception:
            return False

    async def disconnect(self):
        try:
            if self._sftp:
                self._sftp.close()
            if self._shell:
                self._shell.close()
            if self._client:
                self._client.close()
        except Exception as e:
            logger.warning(f"断开连接时发生异常: {e}")
        finally:
            self._sftp = None
            self._shell = None
            self._client = None

    # ──────────────── 工具 ────────────────

    @staticmethod
    def _clean_ansi(text: str) -> str:
        """移除 ANSI 转义码"""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)
