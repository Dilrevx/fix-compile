# 🔧 fix-compile

自动修复 Docker 构建和运行时错误的 CLI 工具，基于 LLM 智能分析。

## 🏗️ 架构设计

本项目采用 **"Executor vs Analyzer"（Hand vs Brain）** 的关注点分离架构：

```
┌─────────────────────────────────────────────────────────┐
│                        CLI Layer                        │
│                   (typer commands)                      │
└────────────────┬───────────────────────┬────────────────┘
                 │                       │
        ┌────────▼────────┐    ┌────────▼────────┐
        │   Executor      │    │    Analyzer     │
        │   (The Hand)    │    │   (The Brain)   │
        │                 │    │                 │
        │ • subprocess    │    │ • LLM calls     │
        │ • file I/O      │    │ • JSON parsing  │
        │ • docker cmds   │    │ • analysis      │
        └─────────────────┘    └─────────────────┘
```

### 核心模块

- **`schema.py`**: Pydantic 数据模型定义
- **`executor.py`**: The Hand - 执行命令、读写文件，不涉及 LLM
- **`brain.py`**: The Brain - 纯 LLM 交互逻辑，不涉及 subprocess
- **`main.py`**: CLI 入口，协调 Executor 和 Analyzer
- **`config.py`**: Pydantic Settings 配置管理

## 🚀 安装

```bash
# 使用 uv (推荐)
uv pip install -e .

# 或使用 pip
pip install -e .
```

## ⚙️ 配置

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`:

```env
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=sk-your-key-here
FIXER_MODEL=gpt-4o-mini
MAX_TOKENS=32768
TIMEOUT=300
```

## 📖 使用方法

### 1️⃣ 分析模式（只读）

仅分析错误并给出建议，**不执行任何操作**：

```bash
# 从日志文件分析
fix-compile analyze --log error.txt --file Dockerfile

# 从 stdin 管道分析
docker build . 2>&1 | fix-compile analyze --file Dockerfile

# 保存建议到 JSON
fix-compile analyze --log error.txt --output suggestion.json
```

### 2️⃣ Docker 自动修复模式

#### 仅构建（自动修复构建错误）

```bash
fix-compile docker . --tag myapp:latest --build-only
```

#### 构建 + 运行（自动修复构建和运行错误）

```bash
fix-compile docker . --tag myapp:latest --run-args "-p 8080:80 -e ENV=prod"
```

#### 仅运行（假设镜像已构建）

```bash
fix-compile docker --run-only --tag myapp:latest
```

#### 自动应用修复（不询问）

```bash
fix-compile docker . --tag myapp:latest --yes
```

## 🔄 工作流程

### Build Loop

```
1. 执行 docker build
2. 如果失败：
   a. 捕获 stderr
   b. 调用 Analyzer 分析错误
   c. 显示建议（可选：请求确认）
   d. 应用修复
   e. 回到步骤 1
3. 如果成功且设置了 --run：进入 Run Loop
```

### Run Loop

```
1. 执行 docker run
2. 如果失败：
   a. 捕获运行时错误
   b. 调用 Analyzer 分析
   c. 显示建议（可选：请求确认）
   d. 应用修复到 Dockerfile
   e. 重新构建镜像
   f. 回到步骤 1
3. 成功：退出
```

## 🎯 CLI 设计理念

使用顶层命令区分功能，便于未来扩展：

```
fix-compile
├── analyze          # 分析模式（Brain only）
└── docker           # Docker 自动修复
    ├── --build-only # 仅构建
    ├── --run-only   # 仅运行
    └── (default)    # 构建 + 运行
```

未来可扩展：

```
fix-compile
├── analyze
├── docker
├── kubernetes      # K8s YAML 修复
└── compose         # docker-compose 修复
```

## 📦 项目结构

```
fix-compile/
├── src/
│   └── fix_compile/
│       ├── __init__.py      # 导出主要类
│       ├── __main__.py      # 包入口
│       ├── schema.py        # 数据模型（Pydantic）
│       ├── config.py        # 配置（Pydantic Settings）
│       ├── executor.py      # The Hand（subprocess）
│       ├── brain.py         # The Brain（LLM）
│       └── main.py          # CLI（Typer）
├── pyproject.toml
├── .env.example
└── README.md
```

## 🧪 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black src/
ruff check src/

# 类型检查
mypy src/
```

## 🔧 高级用法

### 自定义重试次数

```bash
fix-compile docker . --tag myapp --retry 5
```

### 禁用缓存构建

```bash
fix-compile docker . --tag myapp --no-cache
```

### 详细输出

```bash
fix-compile docker . --tag myapp --verbose
```

### 组合使用

```bash
fix-compile docker ./backend \
  --file backend/Dockerfile \
  --tag mybackend:v1.0 \
  --run-args "-p 3000:3000 -e DB_HOST=localhost" \
  --retry 5 \
  --yes \
  --verbose
```

## 📝 示例场景

### 场景 1: 修复构建错误

```bash
$ fix-compile docker . --tag myapp:latest --build-only

Phase 1: Docker Build
Attempt 1/3

[docker build output...]
❌ Build failed (exit code 1)

🧠 Analyzing error with LLM...
✓ Analysis complete (confidence: 95%)

💡 Fix Suggestion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reason:
The base image ubuntu:20.04 repositories are deprecated...

Changes:
Updated base image from ubuntu:20.04 to ubuntu:22.04

Confidence: 95%

Apply this fix? [Y/n]: y

✓ Fix applied successfully

Attempt 2/3
[docker build output...]
✅ Build succeeded!
```

### 场景 2: 管道分析

```bash
$ docker build . 2>&1 | fix-compile analyze -f Dockerfile

🧠 Analyzing error with LLM...

🔍 Fix Suggestion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reason: Missing build dependency...
Changes: Added build-essential to apt-get install
Confidence: 88%

[显示新的 Dockerfile]
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT
