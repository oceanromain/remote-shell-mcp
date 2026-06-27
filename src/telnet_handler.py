"""
TelnetHandler: 基于 asyncio + telnetlib3 的 Telnet 连接处理器
支持: 路由器、交换机、Linux 设备的 Telnet 登录
"""

import asyncio
import logging
import re
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("telnet-handler")


class TelnetHandler:
    def __init__(self):
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False

    # ──────────────── 连接 ────────────────

    async def connect(
        self,
        host: str,
        port: int = 23,
        username: str = "",
        password: str = "",
        timeout: int = 30,
        login_prompt: str = "login:",
        passwd_prompt: str = "Password:",
    ) -> Dict[str, Any]:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )
            self._connected = True
            logger.info(f"Telnet TCP 连接成功: {host}:{port}")

            # 等待 login 提示符
            banner = await self._read_until_pattern(
                patterns=[login_prompt, passwd_prompt, r"[#$>]\s*$"],
                timeout=timeout,
            )
            logger.debug(f"Banner: {banner[:200]}")

            # 处理 login 提示
            if re.search(login_prompt, banner, re.IGNORECASE):
                await self._send(username + "\r\n")
                resp = await self._read_until_pattern(
                    patterns=[passwd_prompt, r"[#$>]\s*$"],
                    timeout=timeout,
                )
                logger.debug(f"用户名响应: {resp[:100]}")

            # 处理密码提示
            if re.search(passwd_prompt, banner + (resp if "resp" in dir() else ""), re.IGNORECASE):
                await self._send(password + "\r\n")
                resp2 = await self._read_until_pattern(
                    patterns=[r"[#$>%]\s*$", r"incorrect|failed|denied", r"\(config\)"],
                    timeout=timeout,
                )
                if re.search(r"incorrect|failed|denied", resp2, re.IGNORECASE):
                    return {"success": False, "error": "认证失败: 用户名或密码错误"}

            logger.info(f"Telnet 登录成功: {username}@{host}:{port}")
            return {"success": True}

        except asyncio.TimeoutError:
            return {"success": False, "error": f"连接超时 ({timeout}s)"}
        except ConnectionRefusedError:
            return {"success": False, "error": f"连接被拒绝: {host}:{port}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────── 命令执行 ────────────────

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        expect: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "未连接", "output": ""}

        try:
            await self._send(command + "\r\n")

            default_pattern = r"[#$>%]\s*$|--More--|---more---|\(config\)[#>]\s*$"
            output = await self._read_until_pattern(
                patterns=[expect] if expect else [default_pattern],
                timeout=timeout,
                handle_more=True,
            )
            return {"success": True, "output": self._clean(output)}

        except asyncio.TimeoutError:
            return {"success": False, "error": f"命令执行超时 ({timeout}s)", "output": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    async def send_input(
        self,
        input_text: str,
        expect: Optional[str] = None,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "未连接", "output": ""}

        try:
            await self._send(input_text + "\r\n")
            output = await self._read_until_pattern(
                patterns=[expect] if expect else [r"[#$>%]\s*$"],
                timeout=timeout,
            )
            return {"success": True, "output": self._clean(output)}
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    # ──────────────── 状态 ────────────────

    async def is_alive(self) -> bool:
        return self._connected and self._writer is not None and not self._writer.is_closing()

    async def disconnect(self):
        try:
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()
        except Exception as e:
            logger.warning(f"Telnet 断开异常: {e}")
        finally:
            self._connected = False
            self._reader = None
            self._writer = None

    # ──────────────── 内部 IO ────────────────

    async def _send(self, data: str):
        self._writer.write(data.encode("utf-8", errors="replace"))
        await self._writer.drain()

    async def _read_until_pattern(
        self,
        patterns: list,
        timeout: int = 30,
        handle_more: bool = False,
    ) -> str:
        buffer = ""
        combined = "|".join(f"(?:{p})" for p in patterns)
        more_pattern = re.compile(r"--More--|---more---", re.IGNORECASE)
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096), timeout=min(remaining, 1.0)
                )
                if not chunk:
                    break

                text = chunk.decode("utf-8", errors="replace")
                buffer += text

                # 处理分页 (--More--)
                if handle_more and more_pattern.search(buffer):
                    await self._send(" ")  # 空格翻页
                    continue

                # 检查结束标志
                lines = buffer.splitlines()
                last = lines[-1].strip() if lines else ""
                if re.search(combined, last):
                    break

            except asyncio.TimeoutError:
                # 短暂超时，检查 buffer 是否有结束标志
                lines = buffer.splitlines()
                last = lines[-1].strip() if lines else ""
                if re.search(combined, last):
                    break
                # 继续等待

        return buffer

    @staticmethod
    def _clean(text: str) -> str:
        # 移除 ANSI 转义码
        ansi = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        text = ansi.sub("", text)
        # 移除 Telnet IAC 序列残留
        text = re.sub(r"\xff[\xfb-\xfe].", "", text)
        # 规范化换行
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()
