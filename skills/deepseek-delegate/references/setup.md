# 安装与环境准备

Skill 文件安装好之后，再检查运行环境。当前桥接入口和桌面同步脚本面向 Windows；其他系统可以阅读和安装 Skill，但需要先适配执行入口。

## 所需组件

- Python 3.10 或更高版本。所有 Python 依赖用实际运行桥接脚本的同一个解释器安装。
- PowerShell 7。桥接脚本会寻找标准安装位置和 `PATH` 中的 `pwsh`；也可以把 `DSH_BRIDGE_PWSH` 设置为实际可执行文件路径。
- 官方 [DeepSeek Harness Desktop](https://github.com/deepseek-ai/deepseek-harness) 的兼容版本。默认 CLI 路径为 `%LOCALAPPDATA%/Programs/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd`；非标准安装通过 `-DshPath` 指定。
- `deepseek-harness-sdk==0.1.5rc1`：这是此桥接代码沿用的 SDK 兼容基线，不是对最新版的声明。
- 安装者自己的 `DEEPSEEK_API_KEY`，或显式指定的本人 Windows DPAPI 加密凭据文件。

官方 SDK 也提供独立运行时。本发布版仍沿用 Desktop CLI 连接方式，不把独立运行时的安装成功视为此桥接已验证可用。

## 安装 Python SDK

优先复用已有兼容环境；缺少 SDK 时，在用户授权安装依赖后执行。以下命令在 PowerShell 中运行，`python` 应对应实际用于运行 Skill 的解释器：

```powershell
$delegateCodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$delegateSdkPath = Join-Path $delegateCodexRoot 'cache/deepseek-delegate/python'
python -m pip install --target $delegateSdkPath 'deepseek-harness-sdk==0.1.5rc1'
```

默认缓存位置由 `CODEX_HOME` 或当前用户目录推导，不包含作者的绝对路径。若使用独立虚拟环境，可在其中安装 SDK 后用 `-PythonPath` 选择解释器；自定义依赖目录使用 `-SdkDepsPath`。不要把别人缓存中的二进制包直接复制到不同版本 Python。

## 凭据

通过安装者自己的本机秘密配置方式向当前进程提供 `DEEPSEEK_API_KEY`。不要把实际密钥贴进 Codex 对话、公开命令示例、Git 仓库或任务材料。此 Skill 不自动读取 Harness Desktop 的账号凭据。

若已有本人生成的 Windows DPAPI 凭据文件，可通过 `-CredentialPath` 显式指定。此文件通常只对创建它的 Windows 用户与机器可用，不应分享。没有环境变量也没有显式文件时，启动器停止并说明缺少配置。

## 首次检查与运行

1. 确认 Python、PowerShell、SDK 和 Desktop CLI 的实际路径；本地导入 SDK 不等于模型连接已通过。
2. 核对当前用户的模型名称与推理等级支持。`prepare_task.py` 沿用 `deepseek-flash` / `max` 默认值；模型不存在时报告具体问题，不擅自换模型。
3. 在当前项目内准备小任务。明确启动会调用本人 API 后，再按 [运行入口](runtime.md) 启动。接收 `READY` 只说明运行入口已启动，实际回合结果和产物还要检查。
4. 相关反馈保留同一进程、同一 `session_id`。独立任务使用新的任务目录；不保证跨进程同名会话恢复或缓存命中。

## 可选的桌面对话同步

只有需要在 Harness Desktop 中查看关闭后的对话时才配置这一部分。默认连接文件位置是 `CODEX_HOME/cache/deepseek-delegate/connection.json`，格式如下：

```json
{"desktop_launch_log": "安装者自己的正常 Desktop 启动日志的绝对路径"}
```

也可直接向 `sync_session.py` 传入 `--launch-log`，不必写配置文件。启动日志需由本人正常启动 Desktop 得到，其中包含短期本机认证信息，禁止提交或分享。没有日志或接口不兼容时保留 `DESKTOP_SYNC_PENDING`，项目内原始对话仍可使用。

同步依赖 Desktop 安装中的存储组件、Electron / Node 能力和本机控制接口，版本变更后可能失效。不要为了同步覆盖别人正在续聊的记录、修改运行中索引或停止正在工作的 Desktop。API 登记成功与原生界面可见性分别记录。
