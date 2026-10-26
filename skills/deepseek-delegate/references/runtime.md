# 运行入口

## 准备项目任务

以下变量由当前 Codex 对话确定，不复用历史项目路径。`PYTHON` 是已确认可用且能导入本 Skill SDK 缓存的 Python；SDK 与二进制依赖须由这个 Python 安装，不复制他人的缓存。首次配置见 [安装与环境准备](setup.md)。可用客户端 `load_workspace_dependencies` 获取当前捆绑 Python，也可使用已有兼容 Python。

```text
PYTHON scripts/prepare_task.py --project-root PROJECT_ROOT --conversation-key CONVERSATION_KEY --task-id TASK_ID --title TITLE --input PROJECT_INPUT
```

已知真实 Codex 对话 ID 时同时传 `--conversation-id`；否则仅使用持久化的本地关联键。输入参数可重复。默认模型名为 `deepseek-flash`，这是沿用的配置值，不保证在安装者当前账号上可用；用户指定其他模型时传 `--model` 并核实可用性，不静默替换。

输出的 `task_directory` 是后续调用入口。布局如下：

```text
PROJECT_ROOT/deepseek_tasks/CONVERSATION_KEY/
  .harness_home/                 当前对话下的 Harness 原始会话与运行配置
  TASK_ID/
    task.json                    当前项目、对话关联、会话、输入来源
    workspace/inputs/            带 SHA256 的输入副本
    workspace/artifacts/         DeepSeek 产物
    runs/RUN_ID/                 派发、答复、工具事件、用量、逐轮清单
    artifact_manifest.json       当前产物清单
    REVIEW.md                    Codex 的验收和维护依据
```

`scripts/project_context.py` 校验全部路径归属当前项目。输入副本用内容哈希命名，输入更新保留已有版本。同一任务重复准备保留会话 ID，禁止模型或真实 Codex 对话 ID 漂移。

## 连续协作

默认 `reasoning_effort=max`，无需用户每次重复指定。`prepare_task.py --reasoning-effort` 仅用于用户明确要求覆盖默认值；一旦任务建立，推理等级与模型一起保持固定。`run.json` 与实际 `request/header` 应记录同一等级，不能仅凭配置文件宣称已经使用 Max。

调用 `scripts/Start-Delegate.ps1 -TaskDirectory TASK_DIRECTORY -Serve -PythonPath PYTHON`。

启动器优先使用已存在的 `DEEPSEEK_API_KEY`，否则仅在显式传入 `-CredentialPath` 时读取安装者自己的 Windows DPAPI 加密凭据；未配置时停止。禁止把明文密钥放进命令、任务文件或消息。Python SDK 共用缓存位于 `CODEX_HOME/cache/deepseek-delegate/python`；可用 `-SdkDepsPath` 指定兼容安装。

已安装 Desktop CLI 默认按 `LOCALAPPDATA/Programs/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd` 发现；必要时用 `-DshPath` 指定已确认的官方入口。脚本使用官方 `sdk-minimal` 和 `bridge.patch.yml`。此发布版使用普通 `dsh-tool-pwsh`；不默认启用交互式 PTY。

服务返回 `READY` 后，按顺序写入 JSON 行；用当前执行环境的持续进程输入能力发送，保存入口 ID 便于下一轮复用：

```json
{"op":"turn","prompt":"明确派发内容"}
{"op":"turn","prompt":"Codex 检查后的具体修改反馈"}
{"op":"close"}
```

模型结果返回后检查 `finish_reason` 和实际文件；不要因为 `completed` 就宣布验收成功。适当等待并定期向用户说明实质进展；SDK 的单请求超时不是整个模型回合的硬时限，卡住时先读取运行记录和诊断，不反复重发同一任务。

也可使用 `-BatchFile` 传 UTF-8 JSON 字符串数组；适用于已确定的有序步骤，各轮共用一个实例。需要根据实际结果调整时使用 `-Serve`，不预编造复核结论。`-PromptFile` 适用于明确的一轮独立任务。

## 桌面对话同步

会话关闭、`run.json.status=CLOSED` 后调用：

```text
PYTHON scripts/sync_session.py --run RUN_DIRECTORY --title TITLE --launch-log DESKTOP_LAUNCH_LOG
```

默认本机连接配置保存在 `CODEX_HOME/cache/deepseek-delegate/connection.json`，只有正常 Desktop 启动日志的路径；也可明确指定 `--launch-log`。启动日志中的短期本机令牌通过正常 token→cookie 流程认证，不输出令牌、不伪造 cookie。Desktop 重启后旧日志可能失效，须取得新的正常启动日志；不要为此停止正在执行用户任务的 Desktop，也不改账号或安全设置。

同步脚本会读取当前任务归属、确认关闭状态、使用已安装 Harness 存储组件转换压缩格式，并核对解压后全部记录与原始日志逐字节一致。然后通过 `workspace/create` 注册当前任务准确的 workspace，并通过 `session/create` 采用关闭后的记录、`session/rename` 设置任务标题。API 登记是元数据操作，不再次请求模型。

原始 SDK 日志在项目内。桌面展示副本进入 Harness 自己的记录库；这不是业务产物目录。不要同时续写 SDK 原件和 Desktop 展示副本，后续有新的业务反馈时先检查当前会话写入归属。已有 Desktop 副本若已改变则拒绝覆盖；真实 UI 续聊不能被独立 SDK 的旧副本冲掉。

`desktop_sync.json` 保存转换校验、注册结果和 `NATIVE_UI_CHECK_PENDING`。按当前客户端可用的正式 UI 能力打开 Harness 对话，核对派发和答复，保存原生界面证据后才更新 `NATIVE_UI_VERIFIED`。API 成功不等于界面已核查。认证或工具不可用时保持未完成标签，保留完整项目内记录。

## 运行边界

- 当前可靠证据是同一进程内连续回合和实际缓存统计。跨进程恢复仍需独立验证；不要凭同名 ID 假定恢复成功。
- 桥接的路径检查和系统提示不等于对 PowerShell 每条命令建立强制文件系统隔离。用任务输入副本工作，并由 Codex 复核实际改动。
- `assistant/message` 的 usage 每个已完成请求只统计一次，stream 末尾的重复 usage 不累加。总输入为 `totalTokens-outputTokens`，命中率为 `cacheReadTokens/总输入`。
