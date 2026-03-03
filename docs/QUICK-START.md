# GeneralFixer 快速开始指南

## 三种修复类型速览

| 类型 | 场景 | 输出内容 | 示例 |
|------|------|--------|------|
| **COMMAND** | 需要运行/修改命令 | `command`, `command_explanation` | `docker run postgres` |
| **FILE** | 需要修改项目文件 | `file_path`, `new_content`, `file_explanation` | `requirements.txt` |
| **DOCKER** | Docker 构建错误 | `dockerfile_path`, `dockerfile_content` | `Dockerfile` |

## CLI 使用

### 场景 1: 分析 Python 错误（文件修复）

```bash
# 错误：缺少依赖
$ fix-compile fix --text "ModuleNotFoundError: No module named 'numpy'"

# 输出示例
Reason: Missing numpy package required by application
Fix Type: file
File: requirements.txt
Explanation: Added numpy to requirements.txt
...
```

### 场景 2: 分析执行错误（命令修复）

```bash
# 在特定目录执行命令并分析错误
$ fix-compile fix --cmd "python app.py" --cwd /path/to/project

# 输出示例
Reason: Database connection failed, PostgreSQL not running
Fix Type: command
Command: docker run -d -p 5432:5432 postgres:15
Explanation: Start PostgreSQL container...
...
```

### 场景 3: 分析日志文件（多种修复）

```bash
# 从执行过程中保存的日志分析
$ fix-compile fix --log-dir /path/to/cached/logs

# 系统会自动读取 stdout.txt/stderr.txt 或 meta.json
```

## Python API 使用

### 基础使用 - quick_analyze

```python
from fix_compile.workflows.brain import GeneralFixer
from fix_compile.schema import FixType

fixer = GeneralFixer()

# 快速分析
suggestion = fixer.quick_analyze(
    error_log="ModuleNotFoundError: No module named 'numpy'",
    cwd="."
)

# 检查结果
print(f"修复类型: {suggestion.fix_type}")
print(f"置信度: {suggestion.confidence:.0%}")
print(f"摘要: {suggestion.changes_summary}")

# 根据类型处理
if suggestion.fix_type == FixType.FILE:
    print(f"修改文件: {suggestion.file_path}")
    print(f"解释: {suggestion.file_explanation}")
elif suggestion.fix_type == FixType.COMMAND:
    print(f"执行命令: {suggestion.command}")
```

### 完整使用 - analyze with context

```python
from fix_compile.workflows.brain import GeneralFixer
from fix_compile.schema import GeneralAnalysisContext, FixType
from pathlib import Path

fixer = GeneralFixer()

context = GeneralAnalysisContext(
    error_log="错误日志内容",
    cwd="/path/to/project",
    previous_attempts=0  # 这是第一次尝试
)

suggestion = fixer.analyze(context)

# 详细信息
print(f"原因: {suggestion.reason}")
print(f"类型: {suggestion.fix_type.value}")

# 自动应用修复
match suggestion.fix_type:
    case FixType.COMMAND:
        print(f"建议命令: {suggestion.command}")
        print(f"说明: {suggestion.command_explanation}")
        # 用户可选是否执行

    case FixType.FILE:
        print(f"文件路径: {suggestion.file_path}")
        # 自动应用（可选）
        file_path = Path("/path/to/project") / suggestion.file_path
        file_path.write_text(suggestion.new_content)
        print(f"✓ 已更新 {suggestion.file_path}")

    case FixType.DOCKER:
        print(f"Dockerfile 路径: {suggestion.dockerfile_path}")
        Path(suggestion.dockerfile_path).write_text(suggestion.dockerfile_content)
        print(f"✓ 已更新 Dockerfile")
```

### 高级使用 - 重试循环

```python
from fix_compile.workflows.brain import GeneralFixer
from fix_compile.schema import GeneralAnalysisContext, FixType
from fix_compile.executor import Executor

fixer = GeneralFixer()
executor = Executor()
max_attempts = 3

for attempt in range(max_attempts):
    # 分析错误
    context = GeneralAnalysisContext(
        error_log=error_log,
        cwd=cwd,
        previous_attempts=attempt
    )

    suggestion = fixer.analyze(context)

    # 根据类型应用修复
    if suggestion.fix_type == FixType.COMMAND:
        result = executor.execute(suggestion.command, cwd=cwd)
        if result.success:
            print("✓ 修复成功！")
            break
        error_log = result.stderr or result.stdout

    elif suggestion.fix_type == FixType.FILE:
        # 应用文件修改
        Path(suggestion.file_path).write_text(suggestion.new_content)
        # 重新执行以验证
        result = executor.execute(original_command, cwd=cwd)
        if result.success:
            print("✓ 修复成功！")
            break
        error_log = result.stderr or result.stdout

    else:
        print(f"无法自动应用 {suggestion.fix_type} 类型的修复")
        break
else:
    print("❌ 经过所有尝试后仍未成功")
```

## 文件系统工具

GeneralFixer 内部提供了文件系统工具（通过 LLM 上下文）：

### read_file_content
```python
from fix_compile.workflows.brain import read_file_content

content = read_file_content("requirements.txt", cwd="/path/to/project")
print(content)
```

### list_files_in_directory
```python
from fix_compile.workflows.brain import list_files_in_directory

files = list_files_in_directory(".", cwd="/path/to/project")
print(files)  # ['file1.py', 'file2.py', ...]
```

### get_file_info
```python
from fix_compile.workflows.brain import get_file_info

info = get_file_info("requirements.txt", cwd="/path/to/project")
print(info)
# {
#     'exists': True,
#     'path': 'requirements.txt',
#     'is_dir': False,
#     'size_bytes': 256,
#     'lines': 12
# }
```

## 最佳实践

### ✅ 推荐做法

1. **提供准确的工作目录**
   ```python
   context = GeneralAnalysisContext(
       error_log=error_log,
       cwd=str(Path.cwd())  # 使用实际的工作目录
   )
   ```

2. **使用相对路径**
   ```python
   # ✓ 好
   file_path = "src/config.py"

   # ✗ 避免
   file_path = "/absolute/path/to/src/config.py"
   ```

3. **检查置信度**
   ```python
   if suggestion.confidence < 0.7:
       print("⚠️ 置信度较低，建议人工检查")
   ```

4. **跟踪修复次数**
   ```python
   context = GeneralAnalysisContext(
       error_log=error_log,
       cwd=cwd,
       previous_attempts=attempt_count  # LLM 会更谨慎
   )
   ```

### ❌ 避免做法

1. 忽略工作目录
   ```python
   # ✗ 不好，无法确定文件相对位置
   suggestion = fixer.quick_analyze(error_log)
   ```

2. 使用绝对路径
   ```python
   # ✗ 不好，降低可移植性
   file_path = "/home/user/project/requirements.txt"
   ```

3. 无限重试
   ```python
   # ✗ 不好，应该设置最大尝试次数
   while True:
       ...
   ```

## 常见场景解决方案

### Python 依赖问题
```bash
fix-compile fix --text "ModuleNotFoundError: No module named 'numpy'" --cwd .
```
预期：FILE 类型修复，修改 requirements.txt

### 数据库连接问题
```bash
fix-compile fix --text "ConnectionRefusedError: [Errno 111] Connection refused" --cwd .
```
预期：COMMAND 类型修复，提示启动数据库

### Docker 构建失败
```bash
fix-compile docker build . --retry 3
```
预期：DOCKER 类型修复，修改 Dockerfile

## 故障排除

### 问题：LLM 返回空响应
- 检查 API 密钥配置
- 检查网络连接
- 尝试简化错误日志内容

### 问题：置信度过低
- 增加错误日志的详细程度
- 提供完整的 traceback
- 确保错误信息清晰

### 问题：修复类型不符预期
- 提供更多上下文信息
- 改进错误日志的格式
- 考虑多次迭代

## 下一步

- 阅读 [详细修改说明](MODIFICATION-DETAILS.md)
- 查看 [API 文档](general-fixer-usage.md)
- 运行 [示例代码](../examples/general_fixer_examples.py)
