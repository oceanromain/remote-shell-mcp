# MCP Remote Shell

**通过 SSH/Telnet 控制远程 Linux 及网络设备的 MCP 服务**

传输模式：**Streamable HTTP**（跨机器部署）
适用于：openclaw (A机器) ──HTTP──▶ MCP Server (Windows B机器) ──SSH/Telnet──▶ 目标设备

---

## 📁 目录结构

```
mcp-remote-shell/
├── src/
│   ├── server.py              # MCP 服务主入口（Streamable HTTP）
│   ├── ssh_handler.py         # SSH 连接处理器
│   ├── telnet_handler.py      # Telnet 连接处理器
│   └── connection_manager.py  # 会话管理
├── config/
│   └── openclaw_mcp_config.json  # openclaw 配置示例
├── logs/                      # 运行日志（自动创建）
├── pyproject.toml             # uv 项目配置 & 依赖
├── install.bat                # 一键安装
├── start.bat                  # 启动服务
├── install_service.bat        # 注册为 Windows 服务（可选）
└── README.md
```

---

## 🚀 部署步骤（Windows B 机器）

### 1. 安装依赖

```cmd
cd C:\mcp-remote-shell
install.bat
```

自动完成：安装 uv → Python 3.11 → `uv sync` 安装所有依赖。

### 2. 启动服务

```cmd
start.bat
```

服务监听 `http://0.0.0.0:8080/mcp`，自定义端口：

```cmd
set MCP_PORT=9090
start.bat
```

### 3. 开放防火墙端口

```cmd
netsh advfirewall firewall add rule name="MCP Remote Shell" dir=in action=allow protocol=TCP localport=8080
```

### 4. 配置 openclaw（A 机器）

在 openclaw 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "remote-shell": {
      "type": "http",
      "url": "http://<B机器IP>:8080/mcp"
    }
  }
}
```

---

## 🔧 注册为 Windows 服务（开机自启，可选）

需要先下载 [NSSM](https://nssm.cc/download) 并放入 PATH，然后：

```cmd
install_service.bat
```

管理服务：
```cmd
nssm start mcp-remote-shell
nssm stop mcp-remote-shell
nssm restart mcp-remote-shell
nssm remove mcp-remote-shell confirm
```

---

## 🛠️ 可用工具

| 工具名 | 功能 |
|--------|------|
| `ssh_connect` | SSH 连接目标设备（密码/私钥） |
| `telnet_connect` | Telnet 连接目标设备 |
| `execute_command` | 执行单条命令 |
| `execute_commands` | 批量执行命令列表 |
| `send_interactive` | 发送交互式输入（sudo、确认等） |
| `disconnect` | 断开指定会话 |
| `list_sessions` | 列出所有活跃会话 |
| `get_session_info` | 查看会话详情 |
| `upload_file` | SFTP 上传文件（仅 SSH） |
| `download_file` | SFTP 下载文件（仅 SSH） |

---

## 🐛 常见问题

**Q: openclaw 连不上 MCP Server**
- 确认 B 机器防火墙已放行端口
- 用 `curl http://B机器IP:8080/mcp` 测试连通性

**Q: Telnet 登录失败**
- 华为设备提示符：`Username:` / `Password:`
- 思科设备提示符：`Username:` / `Password:`
- 在 `telnet_connect` 中传入 `login_prompt` / `passwd_prompt` 参数覆盖默认值

**Q: 需要认证保护 HTTP 接口**
在 B 机器前面加 Nginx 反代，配置 Basic Auth 或限制来源 IP。
