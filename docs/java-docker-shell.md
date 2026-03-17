# Java 工作流：构建完成后进入容器

## 背景

`fix-compile java` 命令会构建一个 Docker 镜像并在其中编译项目。构建完成后，镜像会保留在本地，可以随时进入容器手动调试、重跑 CodeQL 或做其他操作。

---

## 找到镜像和运行目录

### 查看可用镜像

```bash
docker images fix-compile-java
```

输出示例：

```
REPOSITORY         TAG        IMAGE ID       CREATED         SIZE
fix-compile-java   4780f996   af468d805a04   18 minutes ago  1.94GB
fix-compile-java   6211845c   0b37f2657fa4   13 days ago     1.94GB
```

`TAG` 就是 `run_hash`，由项目路径 + 构建参数哈希生成，与运行日志目录名一一对应。

### 找到对应的日志/状态目录

```bash
ls ~/.local/state/fix-compile/*/java/
```

每次运行的状态文件（日志、CodeQL 数据库、SARIF 结果）保存在：

```
~/.local/state/fix-compile/<version>/java/<run_hash>/
```

---

## 进入容器交互式 Shell

替换 `<run_hash>` 和 `<项目绝对路径>` 后执行：

```bash
docker run -it --rm \
  --network=host \
  -v <项目绝对路径>:/workspace/project \
  -v ~/.local/state/fix-compile/<version>/java/<run_hash>:/workspace/runstate \
  -v ~/.local/state/fix-compile/<version>/java/m2/repository:/workspace/.m2/repository \
  fix-compile-java:<run_hash> \
  bash
```

**RuoYi-Cloud 实际示例：**

```bash
HASH=4780f996
docker run -it --rm \
  --network=host \
  -v /home/lhq/workspace/fix-compile/examples/RuoYi-Cloud:/workspace/project \
  -v ~/.local/state/fix-compile/0.2.0/java/${HASH}:/workspace/runstate \
  -v ~/.local/state/fix-compile/0.2.0/java/m2/repository:/workspace/.m2/repository \
  fix-compile-java:${HASH} \
  bash
```

容器内目录布局：

| 路径 | 内容 |
|---|---|
| `/workspace/project` | 项目源码（挂载自宿主机，可读写） |
| `/workspace/runstate` | 运行状态：CodeQL 数据库、SARIF 结果、日志 |
| `/workspace/.m2/repository` | Maven 本地仓库（挂载缓存，避免重复下载） |
| `/opt/codeql` | CodeQL CLI（`codeql` 已在 PATH） |

---

## 在容器内手动运行 CodeQL

> **已验证（RuoYi-Cloud，2026-03-17）**
> - `database create`：`Successfully created database at /workspace/runstate/codeql-db`
> - `database analyze`：80/80 queries evaluated，SARIF 写入成功，findings = 0（无已知漏洞）

进入容器后，按以下步骤操作：

### 1. 切换到项目目录

```bash
cd /workspace/project
```

### 2. 创建 CodeQL 数据库

```bash
codeql database create /workspace/runstate/codeql-db \
  --overwrite \
  --language=java \
  --source-root=/workspace/project \
  --command="mvn -B -DskipTests compile"
```

- `--overwrite`：允许覆盖已存在的数据库（重跑时必须加）
- `--language`：固定为 `java`
- `--source-root`：源码根目录
- `--command`：CodeQL 会执行此命令并监听编译过程以捕获字节码；**无需提前单独 `mvn compile`**

### 3. 分析数据库（查找漏洞）

```bash
codeql database analyze /workspace/runstate/codeql-db \
  --download \
  codeql/java-queries \
  --format=sarif-latest \
  --output=/workspace/runstate/codeql-result.sarif
```

- `--download`：自动下载查询包（**首次运行必须加**；包已缓存后可去掉以加速）
- `codeql/java-queries`：默认查询套件，可换成其他套件，如 `codeql/java-security-extended`
- `--format=sarif-latest`：输出 SARIF 格式，兼容主流 SAST 平台
- `--output`：SARIF 结果写入 `/workspace/runstate/`，宿主机同步可见

### 4. 查看结果（SARIF）

结果文件同步到宿主机：

```bash
cat ~/.local/state/fix-compile/0.2.0/java/<run_hash>/codeql-result.sarif | python3 -m json.tool | less
```

统计 findings 数量：

```bash
python3 -c "
import json
data = json.load(open('codeql-result.sarif'))
total = sum(len(r.get('results', [])) for r in data['runs'])
print(f'findings: {total}')
"
```

或使用 VS Code 安装 [SARIF Viewer](https://marketplace.visualstudio.com/items?itemName=MS-SarifVSCode.sarif-viewer) 扩展打开 `.sarif` 文件可视化查看。

---

## 常用 CodeQL 查询套件

| 套件名 | 说明 |
|---|---|
| `codeql/java-queries` | 标准查询（正确性 + 安全性），默认 |
| `codeql/java-security-queries` | 仅安全相关查询，结果更精简 |
| `codeql/java-security-extended` | 扩展安全查询，覆盖更广 |

切换套件只需修改 `codeql database analyze` 中的套件名参数。

---

## 快速脚本

以下脚本自动取最新镜像 hash 进入容器，适合开发时频繁调试：

```bash
#!/usr/bin/env bash
# enter-java-container.sh <项目绝对路径>
PROJECT_DIR="${1:?用法: $0 <项目绝对路径>}"
VERSION=$(ls ~/.local/state/fix-compile/ | sort -V | tail -1)
HASH=$(ls ~/.local/state/fix-compile/${VERSION}/java/ | grep -v '^m2$' | sort | tail -1)
echo "Using image fix-compile-java:${HASH}, state dir: ~/.local/state/fix-compile/${VERSION}/java/${HASH}"
docker run -it --rm \
  --network=host \
  -v "${PROJECT_DIR}:/workspace/project" \
  -v "${HOME}/.local/state/fix-compile/${VERSION}/java/${HASH}:/workspace/runstate" \
  -v "${HOME}/.local/state/fix-compile/${VERSION}/java/m2/repository:/workspace/.m2/repository" \
  "fix-compile-java:${HASH}" \
  bash
```

保存后 `chmod +x enter-java-container.sh`，使用：

```bash
./enter-java-container.sh /home/lhq/workspace/fix-compile/examples/RuoYi-Cloud
```
