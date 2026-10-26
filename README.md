# Codex Delegate Skills

让 Codex 指挥 ChatGPT Chat 和 DeepSeek：整理材料、派发任务、接收结果、继续反馈，并由 Codex 复核和维护产物。

## 复制一句话，让 Codex 安装

把下面这一整句话复制给 **Codex**：

```text
请使用 $skill-installer 从 GitHub 仓库 https://github.com/20020605Zzh1/codex-delegate-skills 安装 skills/chat-delegate 和 skills/deepseek-delegate 这两个 Skill；安装后读取各自的 SKILL.md，检查当前环境并告诉我还缺哪些运行依赖，已有同名 Skill 时先保留原版，不覆盖。
```

这句话会让 Codex 安装两个 Skill 的说明、脚本和参考文件。使用时需要的浏览器连接、ChatGPT 登录、DeepSeek Harness 和个人凭据由安装者自己的环境提供；安装 Skill 不会自动获得这些访问能力，也不会发起模型请求。

只需要其中一个时，复制相应的一句话：

**只安装指挥 Chat 的 Skill：**

```text
请使用 $skill-installer 从 https://github.com/20020605Zzh1/codex-delegate-skills 安装 skills/chat-delegate，安装后读取 SKILL.md 并检查运行前提；已有同名 Skill 时先保留原版，不覆盖。
```

**只安装指挥 DeepSeek 的 Skill：**

```text
请使用 $skill-installer 从 https://github.com/20020605Zzh1/codex-delegate-skills 安装 skills/deepseek-delegate，安装后读取 SKILL.md 和 references/setup.md 并检查运行前提；已有同名 Skill 时先保留原版，不覆盖。
```

安装完成后可直接在后续消息中使用。如果没有出现在 Skill 列表中，重新打开 Codex 再查看。官方说明见 [Build skills](https://learn.chatgpt.com/docs/build-skills)。

## 两个 Skill 分别做什么

| Skill | 交给谁 | 主要工作 | 使用前提 |
|---|---|---|---|
| [chat-delegate](skills/chat-delegate/SKILL.md) | 普通 ChatGPT Chat | 把长材料打包为真实 Markdown 附件；用简短正文派发；默认核实高思考等级；取回完整回复并复核 | Codex 有受支持的浏览器操作能力，浏览器已登录 ChatGPT，Python 3.10+ 用于本地附件脚本 |
| [deepseek-delegate](skills/deepseek-delegate/SKILL.md) | 官方 DeepSeek Harness | 在当前项目内建立任务目录；默认 Max；同一进程和会话内连续反馈；保存对话与产物，由 Codex 验收；支持关闭后的桌面对话同步 | 当前脚本面向 Windows，需 Python 3.10+、PowerShell 7、兼容的 Harness Desktop CLI、Python SDK 和自己的 DeepSeek API 凭据 |

Chat 版操作实际网页，依赖宿主提供浏览器工具；附件打包脚本本身不会发送消息。DeepSeek 版通过 Harness 执行任务；实际运行会使用安装者自己的 API 账户。

## 安装后的用法

### 让 Codex 指挥 Chat

```text
使用 $chat-delegate，把当前项目的“材料.md”作为附件发给这个 Chat：https://chatgpt.com/c/你的对话ID，请它检查论证结构，思考等级用高；读取完整回复后，由你核对并给我修改建议。
```

续接同一任务：

```text
继续刚才那个 Chat，把你发现的三个具体问题反馈给它，让它修改；保留同一个对话，取回结果后再检查一次。
```

请提供你实际要使用的 Chat 链接、准确标题或明确的新建要求。长材料放在附件中，正文保留本轮任务和输出要求。模型、思考等级和上传状态以实际界面为准。

### 让 Codex 指挥 DeepSeek

```text
使用 $deepseek-delegate，把当前项目里“示例模块”的代码审查交给 DeepSeek，默认 Max；只读指定文件，把问题和修改建议放在当前项目的任务目录里，由你复核。
```

继续反馈：

```text
在刚才同一个 Harness 进程和会话里继续，把第2条建议的边界条件补充给 DeepSeek，让它修改后交给你复核。
```

第一次使用先让 Codex 按 [DeepSeek 环境准备](skills/deepseek-delegate/references/setup.md) 检查本机。默认模型配置值是 `deepseek-flash`，运行前应确认当前账号是否支持；不同模型需由用户指定，不静默替换。

## 文件结构

```text
skills/
  chat-delegate/
    SKILL.md
    agents/openai.yaml
    references/browser-workflow.md
    scripts/prepare_packet.py
  deepseek-delegate/
    SKILL.md
    agents/openai.yaml
    requirements.txt
    references/setup.md
    references/runtime.md
    scripts/...
tests/
  test_local_helpers.py
```

每个 Skill 都可以单独安装，相关参考文件随该 Skill 一起提供。仓库发布的是 Skill 源文件；没有把浏览器工具、Harness 程序或第三方 SDK 打包进来。

## 兼容性与验证

发布前在 Windows / Python 3.12 环境执行了 Skill 格式检查、本地附件打包与项目任务准备测试，以及 PowerShell 启动器的解析和离线检查。测试不会连接 ChatGPT 或 DeepSeek，也不请求模型。

本次发布未重新执行浏览器上传、DeepSeek 模型回合或 Harness 桌面对话同步。这些能力依赖安装者的工具、登录状态和 Harness 版本，安装成功后仍需在自己的环境验证。桌面对话同步用到了已安装 Harness 的存储组件和本机控制接口，升级后可能需要适配。

本地检查命令：

```text
python -m unittest discover -s tests -v
```

## 任务与数据边界

任务材料、对话记录和结果保存在使用者当前项目中；本仓库不包含作者的历史任务、浏览器登录、API Key、DPAPI 凭据、桌面启动日志或运行缓存。派发给外部模型的内容按每次任务授权选择，模型答复由 Codex 复核后采用。

DeepSeek 桥接脚本的路径检查用于管理任务文件归属，不构成对外部模型执行命令的强制沙箱。首次运行适合使用独立工作目录和可恢复的输入副本。

## 许可与相关项目

本仓库内容使用 [MIT License](LICENSE)。第三方应用、SDK 和工具按各自的许可及服务规则使用。

- [OpenAI Skills](https://github.com/openai/skills)：Skill Creator / Skill Installer。
- [OpenAI 官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills)：Skill 结构、发现与安装。
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 与 [Python SDK 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/python-sdk.md)：DeepSeek 版运行依赖。

这是个人工作流分享项目，与 OpenAI、ChatGPT 或 DeepSeek 的官方发行无隶属关系。
