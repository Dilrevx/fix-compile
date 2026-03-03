# GeneralFixer 升级总结

## 主要改动概述

GeneralFixer 已升级为支持**多种修复类型**的通用问题分析工具。不再仅限于 Dockerfile 修复，现在可以处理 CLI 命令、配置文件、源代码等多种类型的修复。

## 核心改动

### 1. 数据结构扩展（schema.py）

#### 新增 FixType 枚举
```python
class FixType(str, Enum):
    COMMAND = "command"  # 修改/运行 CLI 命令
    FILE = "file"        # 修改工作目录中的文件
    DOCKER = "docker"    # 修改 Dockerfile
```

#### 扩展 GeneralAnalysisContext
- 添加 `cwd` 字段：当前工作目录
- 用于确定文件路径的相对位置

#### 重构 FixSuggestion
原结构：单一文件修改

新结构：根据 `fix_type` 返回不同字段
- **COMMAND**: `command`, `command_explanation`
- **FILE**: `file_path`, `new_content`, `file_explanation`
- **DOCKER**: `dockerfile_path`, `dockerfile_content`
- **公共**: `reason`, `confidence`, `changes_summary`

### 2. LLM Prompt 改进（brain.py）

#### 新 SYSTEM_PROMPT
- 明确定义三种修复类型
- 提供每种类型的 JSON 模板
- 指导 LLM 选择最合适的修复方式

#### 环境上下文
- 自动获取工作目录信息
- 列出目录中的文件（前 20 个）
- 跟踪修复尝试次数

### 3. 文件系统工具函数（brain.py）

添加了三个内部工具函数：

```python
def read_file_content(file_path: str, cwd: str = ".") -> str
    # 读取文件内容

def list_files_in_directory(dir_path: str = ".", cwd: str = ".") -> list[str]
    # 列出目录文件

def get_file_info(file_path: str, cwd: str = ".") -> dict
    # 获取文件信息（大小、行数等）
```

这些函数通过 LLM 上下文提供，有助于 LLM 理解环境。

### 4. analyze() 方法更新

改进的输出显示：
- 显示修复类型
- 根据类型显示不同的详细信息
- 改进的日志格式

### 5. quick_analyze() 方法签名

```python
# 之前
def quick_analyze(self, error_log: str) -> FixSuggestion

# 之后
def quick_analyze(self, error_log: str, cwd: str = ".") -> FixSuggestion
```

### 6. CLI 集成（src/cli/main.py）

`fix` 命令现在：
- 接收 `cwd` 参数
- 根据 fix_type 显示不同的输出
- 支持三种修复类型的可视化展示

## 使用示例

### Python API

```python
from fix_compile.workflows.brain import GeneralFixer
from fix_compile.schema import GeneralAnalysisContext, FixType

fixer = GeneralFixer()

# 方式 1: 使用 quick_analyze
suggestion = fixer.quick_analyze(
    error_log="ModuleNotFoundError: No module named 'numpy'",
    cwd="/path/to/project"
)

# 方式 2: 使用完整 context
context = GeneralAnalysisContext(
    error_log="error details",
    cwd="/path/to/project",
    previous_attempts=1
)
suggestion = fixer.analyze(context)

# 处理结果
if suggestion.fix_type == FixType.FILE:
    print(f"修改文件: {suggestion.file_path}")
    # 应用修复: Path(suggestion.file_path).write_text(suggestion.new_content)
elif suggestion.fix_type == FixType.COMMAND:
    print(f"执行命令: {suggestion.command}")
    # 应用修复: executor.execute(suggestion.command)
elif suggestion.fix_type == FixType.DOCKER:
    print(f"修改: {suggestion.dockerfile_path}")
    # 应用修复: Path(suggestion.dockerfile_path).write_text(suggestion.dockerfile_content)
```

### CLI 使用

```bash
# 分析 Python 模块错误
fix-compile fix --text "ModuleNotFoundError: No module named 'numpy'" --cwd .

# 执行命令并分析输出
fix-compile fix --cmd "python main.py" --cwd /path/to/project

# 读取日志文件
fix-compile fix --log-dir /path/to/error.log
```

## 向后兼容性

- 原有的 `DockerAnalysisContext` 和 Docker 命令**不受影响**
- `fix` 命令现支持更多类型的错误
- `quick_analyze()` 添加了可选参数，保持向后兼容

## 新增文档

- `docs/general-fixer-usage.md` - 详细使用指南
- `examples/general_fixer_examples.py` - 代码示例

## 优势

1. **灵活性** - 支持多种修复类型，适用更多场景
2. **环境感知** - 自动获取工作目录信息，提高修复准确度
3. **可视化** - 清晰显示不同类型的修复建议
4. **可扩展性** - 易于添加新的修复类型或工具函数
5. **用户体验** - CLI 输出更加清晰，易于理解建议内容

## 后续改进方向

- [ ] 实现自动应用修复的功能
- [ ] 添加修复验证（执行后验证是否成功）
- [ ] 支持交互式修复审查
- [ ] 添加修复历史追踪
- [ ] 支持条件修复（基于用户选择的变体）
