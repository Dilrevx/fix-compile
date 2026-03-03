# GeneralFixer 升级 - 修改详解

## 📋 文件修改清单

### 1. `src/fix_compile/schema.py`

**新增内容:**

- `FixType` 枚举：定义三种修复类型
  - `COMMAND`: CLI 命令修复
  - `FILE`: 文件内容修复
  - `DOCKER`: Dockerfile 修复

- `GeneralAnalysisContext` 扩展：
  - 添加 `cwd` 字段（当前工作目录）

- `FixSuggestion` 重构为多态结构：
  - 根据 `fix_type` 字段确定哪些字段有值
  - COMMAND 类型：`command`, `command_explanation`
  - FILE 类型：`file_path`, `new_content`, `file_explanation`
  - DOCKER 类型：`dockerfile_path`, `dockerfile_content`
  - 公共字段：`reason`, `confidence`, `changes_summary`

### 2. `src/fix_compile/workflows/brain.py`

**导入更新:**

```python
# 添加
from pathlib import Path
from ..schema import FixSuggestion, FixType  # 新增 FixType
```

**新增文件系统工具函数 (module-level):**

```python
def read_file_content(file_path: str, cwd: str = ".") -> str
def list_files_in_directory(dir_path: str = ".", cwd: str = ".") -> list[str]
def get_file_info(file_path: str, cwd: str = ".") -> dict
```

这些函数通过 LLM 上下文自动提供，增强 LLM 对环境的理解。

**SYSTEM_PROMPT 重构:**

- 新增对三种修复类型的详细说明
- 每种类型提供完整的 JSON 模板示例
- 强调相对路径和工作目录的重要性
- 更清晰的指导原则

**analyze() 方法改进:**

```python
# 改进点：
1. 改为处理 GeneralAnalysisContext（包含 cwd）
2. 返回结果显示 fix_type
3. 根据 fix_type 显示不同的详细信息
4. 改进的错误处理和日志
```

**_build_user_prompt() 方法改进:**

```python
# 改进点：
1. 自动获取工作目录信息
2. 列出目录中的文件（前 20 个）
3. 格式化环境上下文
4. 追踪修复尝试次数
```

**quick_analyze() 方法签名更新:**

```python
# 之前
def quick_analyze(self, error_log: str) -> FixSuggestion

# 之后
def quick_analyze(self, error_log: str, cwd: str = ".") -> FixSuggestion
```

### 3. `src/cli/main.py`

**fix 命令更新:**

```python
# 改进点：
1. 接收并传递 cwd 参数给 analyzer
2. 使用 quick_analyze(error_log, cwd) 而非 quick_analyze(error_log)
3. 根据 suggestion.fix_type 显示不同类型的建议
4. 改进的输出格式和可读性

# 输出逻辑：
- COMMAND type: 显示命令和解释
- FILE type: 显示文件路径和修改解释
- DOCKER type: 显示 Dockerfile 路径和内容
```

## 🔄 数据流变化

### 之前
```
error_log → GeneralFixer.quick_analyze()
  → FixSuggestion(file_path, new_content, ...)
  → 显示 new_content
```

### 之后
```
error_log + cwd → GeneralFixer.quick_analyze(error_log, cwd)
  → LLM 获得：error_log + cwd + file_list + 三种修复模板
  → FixSuggestion(fix_type, command?, file_path?, dockerfile_path?, ...)
  → 根据 fix_type 显示不同类型的建议
```

## 📝 LLM Prompt 变化

### COMMAND 修复示例
```json
{
    "reason": "数据库连接失败",
    "fix_type": "command",
    "command": "docker run -d -p 5432:5432 postgres:15",
    "command_explanation": "启动 PostgreSQL 容器",
    "confidence": 0.9,
    "changes_summary": "启动必需的数据库服务"
}
```

### FILE 修复示例
```json
{
    "reason": "缺少依赖包",
    "fix_type": "file",
    "file_path": "requirements.txt",
    "new_content": "numpy==1.24.0\npandas==2.0.0\n...",
    "file_explanation": "添加了缺失的依赖",
    "confidence": 0.95,
    "changes_summary": "更新了 requirements.txt"
}
```

### DOCKER 修复示例
```json
{
    "reason": "Ubuntu 镜像源已废弃",
    "fix_type": "docker",
    "dockerfile_path": "Dockerfile",
    "dockerfile_content": "FROM ubuntu:22.04\n...",
    "confidence": 0.88,
    "changes_summary": "更新了基础镜像版本"
}
```

## ✨ 关键改进点

1. **多类型支持** - 不再限于文件修复
2. **环境感知** - LLM 可以看到文件系统状态
3. **更好的 UX** - CLI 根据修复类型显示不同的信息
4. **向后兼容** - Docker 命令和 DockerAnalysisContext 不受影响
5. **可扩展性** - 易于添加新的修复类型

## 🧪 验证步骤

```bash
# 检查语法
python -m py_compile src/fix_compile/schema.py
python -m py_compile src/fix_compile/workflows/brain.py
python -m py_compile src/cli/main.py

# 导入测试
python -c "
import sys
sys.path.insert(0, 'src')
from fix_compile.schema import FixType, GeneralAnalysisContext, FixSuggestion
from fix_compile.workflows.brain import GeneralFixer
print('✓ All imports successful!')
"

# CLI 测试
fix-compile fix --text "ModuleNotFoundError: No module named 'numpy'" --cwd .
```

## 📚 新增文档

- `docs/general-fixer-usage.md` - 详细使用指南
- `docs/UPGRADE-SUMMARY.md` - 升级摘要
- `examples/general_fixer_examples.py` - 代码示例

## 🎯 使用建议

### Python API
```python
fixer = GeneralFixer()
suggestion = fixer.quick_analyze(
    error_log="错误内容",
    cwd="/path/to/project"
)

# 处理建议
match suggestion.fix_type:
    case FixType.COMMAND:
        executor.execute(suggestion.command)
    case FixType.FILE:
        Path(suggestion.file_path).write_text(suggestion.new_content)
    case FixType.DOCKER:
        Path(suggestion.dockerfile_path).write_text(suggestion.dockerfile_content)
```

### CLI
```bash
# 文本输入
fix-compile fix --text "error message" --cwd .

# 执行命令
fix-compile fix --cmd "python main.py" --cwd /path/to/project

# 日志文件
fix-compile fix --log-dir /path/to/logs
```
