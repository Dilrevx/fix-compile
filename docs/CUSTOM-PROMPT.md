# Custom Prompt 用户指南

## 概述

Custom Prompt 功能允许用户在配置中添加自定义提示词，这些提示词会被自动附加到所有 LLM 分析请求中，确保生成的修复建议符合用户特定的环境需求。

## 配置方法

### 1. 通过环境变量配置

在 `.env` 文件中添加：

```bash
CUSTOM_PROMPT="在 172.17.0.1:7890 访问 clash 代理。所有 Dockerfile 中的软件包安装必须使用代理，在 RUN 命令中设置 http_proxy 和 https_proxy 环境变量。"
```

### 2. 通过配置文件配置

在 `config.yaml` 中添加：

```yaml
CUSTOM_PROMPT: |
  在 172.17.0.1:7890 访问 clash 代理。
  所有 Dockerfile 中的软件包安装必须使用代理。
  对于 apt-get: RUN http_proxy=http://172.17.0.1:7890 apt-get update
  对于 pip: RUN pip install --proxy http://172.17.0.1:7890 package_name
```

### 3. 通过代码配置

```python
from fix_compile import GeneralFixer

custom_prompt = """
所有网络操作必须使用代理 172.17.0.1:7890。
对于 Dockerfile:
- 设置环境变量 ENV HTTP_PROXY=http://172.17.0.1:7890 HTTPS_PROXY=http://172.17.0.1:7890
- 在所有下载包的 RUN 命令中应用代理（apt-get、pip、npm 等）
"""

fixer = GeneralFixer(custom_prompt=custom_prompt)
```

## 常见使用场景示例

### 场景 1: 代理设置

```bash
CUSTOM_PROMPT="所有网络操作必须使用 HTTP/HTTPS 代理 172.17.0.1:7890。
对于 Dockerfile:
- 设置环境变量: ENV HTTP_PROXY=http://172.17.0.1:7890 HTTPS_PROXY=http://172.17.0.1:7890
- 在所有 RUN 命令中应用代理
- 确保 wget、curl、git clone 等命令都使用代理"
```

### 场景 2: 中国镜像源

```bash
CUSTOM_PROMPT="使用中国镜像源进行包安装:
- apt: 使用清华/阿里云镜像
- pip: 使用 https://pypi.tuna.tsinghua.edu.cn/simple
- npm: 使用 https://registry.npmmirror.com
- Docker: 如果可用，使用 Docker Hub 镜像"
```

### 场景 3: 安全最佳实践

```bash
CUSTOM_PROMPT="所有修复必须遵循安全最佳实践:
- 永远不要以 root 运行容器（使用 USER 指令）
- 明确固定包版本
- 最小化层数和镜像大小
- 安装后删除构建依赖
- 尽可能使用多阶段构建"
```

### 场景 4: 时区设置

```bash
CUSTOM_PROMPT="在所有容器中设置时区为 Asia/Shanghai:
- 添加: ENV TZ=Asia/Shanghai
- 安装并配置 tzdata 包
- 创建符号链接: ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime"
```

## 工作原理

1. **配置解析**: 系统从环境变量、配置文件或代码参数中读取 `CUSTOM_PROMPT`
2. **Prompt 构建**: `PromptBuilder.build_system_prompt()` 将自定义提示词附加到基础系统提示词后
3. **LLM 集成**: 所有 Fixer（GeneralFixer、DockerFixer）在调用 LLM 时都会包含自定义提示词
4. **修复生成**: LLM 生成的修复建议会自动遵循自定义提示词中的要求

## 内置示例

代码提供了多个内置示例，可以通过以下方式查看：

```python
from fix_compile import PromptBuilder

examples = PromptBuilder.get_example_custom_prompts()
print(examples['proxy'])      # 代理配置示例
print(examples['china_mirror']) # 中国镜像源示例
print(examples['security'])    # 安全最佳实践示例
print(examples['timezone'])    # 时区设置示例
```

## 最佳实践

1. **清晰具体**: 提示词应该清晰、具体，避免模糊的描述
2. **包含示例**: 在提示词中包含具体的命令示例
3. **分层说明**: 对不同类型的修复（Dockerfile、命令、文件）分别说明
4. **测试验证**: 添加自定义提示词后，测试几个场景确保 LLM 正确遵循
5. **版本控制**: 将 custom prompt 配置纳入版本控制，确保团队一致性

## 注意事项

- Custom Prompt 会被添加到所有 LLM 请求中，会增加 token 消耗
- 过长的 custom prompt 可能影响 LLM 响应质量，建议控制在 200-300 字以内
- Custom Prompt 中的要求应该是通用的，适用于大多数修复场景
- 特定项目的特殊要求应该在项目文档中说明，而不是全局 custom prompt

## 故障排查

### 问题 1: Custom Prompt 不生效

**解决方案**:
1. 检查配置是否正确加载: 运行 `fix-compile config list` 查看当前配置
2. 确认环境变量名称正确: `CUSTOM_PROMPT`（全大写）
3. 检查配置优先级: 代码参数 > 环境变量 > 配置文件

### 问题 2: LLM 没有遵循 Custom Prompt

**解决方案**:
1. 使提示词更加明确和具体
2. 添加强调性语句，如 "必须"、"MUST"、"IMPORTANT"
3. 提供具体的命令示例
4. 检查是否与基础系统提示词冲突

## 更多示例

查看项目仓库中的 `examples/` 目录获取更多实际使用案例。
