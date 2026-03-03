# GeneralFixer - 通用问题分析和修复

## 概述

`GeneralFixer` 现已升级为通用的问题分析工具，支持三种类型的修复：

1. **COMMAND** - 修改或运行 shell 命令
2. **FILE** - 修改工作目录中的文件（配置、源代码、依赖文件等）
3. **DOCKER** - 修改 Dockerfile（Docker 相关问题）

## 数据结构

### 输入：GeneralAnalysisContext

```python
from fix_compile.schema import GeneralAnalysisContext

context = GeneralAnalysisContext(
    error_log="错误日志内容",
    cwd=".",  # 当前工作目录
    previous_attempts=0  # 之前的修复尝试次数
)
```

### 输出：FixSuggestion

根据 `fix_type` 的值，返回不同的修复建议：

#### COMMAND 类型修复

```python
{
    "reason": "错误的根本原因说明",
    "fix_type": "command",
    "command": "要执行的命令",
    "command_explanation": "命令的解释",
    "confidence": 0.85,
    "changes_summary": "修改摘要"
}
```

#### FILE 类型修复

```python
{
    "reason": "错误的根本原因说明",
    "fix_type": "file",
    "file_path": "要修改的文件路径（相对于 cwd）",
    "new_content": "文件的新内容",
    "file_explanation": "文件修改的解释",
    "confidence": 0.85,
    "changes_summary": "修改摘要"
}
```

#### DOCKER 类型修复

```python
{
    "reason": "Docker 错误说明",
    "fix_type": "docker",
    "dockerfile_path": "Dockerfile 路径",
    "dockerfile_content": "新的 Dockerfile 内容",
    "confidence": 0.85,
    "changes_summary": "修改摘要"
}
```

## 使用示例

### 1. 分析通用错误

```python
from fix_compile.workflows.brain import GeneralFixer
from fix_compile.schema import GeneralAnalysisContext

fixer = GeneralFixer()

# 例如：Python 依赖缺失
error_log = """
Traceback (most recent call last):
  File "main.py", line 1, in <module>
    import numpy
ModuleNotFoundError: No module named 'numpy'
"""

context = GeneralAnalysisContext(
    error_log=error_log,
    cwd="/path/to/project"
)

suggestion = fixer.analyze(context)

if suggestion.fix_type == "file":
    print(f"修改文件: {suggestion.file_path}")
    print(f"解释: {suggestion.file_explanation}")
    print(f"新内容: {suggestion.new_content}")
```

### 2. CLI 命令使用

新的 `fix` 命令支持三种输入方式：

```bash
# 从文本输入
fix-compile fix --text "ModuleNotFoundError: No module named 'numpy'"

# 从文件读取
fix-compile fix --log-dir /path/to/error.log

# 执行命令并分析其输出
fix-compile fix --cmd "python main.py" --cwd /path/to/project
```

## 文件系统工具

GeneralFixer 提供了以下文件系统工具函数（内部使用）：

### `read_file_content(file_path, cwd=".")`
读取指定工作目录中的文件内容。

### `list_files_in_directory(dir_path=".", cwd=".")`
列出目录中的文件。

### `get_file_info(file_path, cwd=".")`
获取文件信息（是否存在、大小、行数等）。

这些工具通过 LLM 的上下文自动提供，无需显式调用。

## LLM Prompt 特性

- LLM 自动获得当前工作目录信息
- 自动列出工作目录中的文件（前 20 个）
- 支持多次修复尝试跟踪
- 针对不同修复类型提供结构化输出

## 工作流程

1. 用户输入错误日志和工作目录
2. GeneralFixer 准备上下文信息（包括文件系统状态）
3. LLM 分析错误并确定最合适的修复类型
4. 返回结构化的 FixSuggestion
5. 调用者根据 fix_type 采取相应行动

## 最佳实践

- 始终提供准确的工作目录（cwd）
- 对于文件修复，使用相对路径
- 检查 confidence 分数以评估修复质量
- 在自动应用修复前，让用户确认关键改动
