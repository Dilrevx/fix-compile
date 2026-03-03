# fix-compile Architecture

**Version**: 0.2.0
**Updated**: 2026-03-03

---

## Overview

`fix-compile` is a CLI tool that runs builds in isolated Docker environments and uses
an LLM (OpenAI / compatible) to automatically analyze compile errors and suggest fixes,
looping until the build succeeds or the attempt limit is reached.

---

## 1. Project Layout

```
fix-compile/
├── src/
│   ├── cli/                        # Typer CLI entry point
│   │   ├── main.py                 # app, all top-level commands
│   │   └── commands/               # sub-apps (config, docker)
│   │       ├── config.py           # config get/set/list/del
│   │       └── docker.py           # docker build / run fix loop
│   └── fix_compile/                # Core library (importable)
│       ├── __init__.py             # Public API, version
│       ├── config.py               # Pydantic Settings (Configs, DirConfigs)
│       ├── constants.py            # Literal constants, no imports
│       ├── executor.py             # Subprocess wrapper (Executor)
│       ├── schema.py               # All Pydantic data models
│       ├── assets/
│       │   └── templates/
│       │       └── Dockerfile-Java # Base image for Java workflow
│       ├── utils/
│       │   ├── io.py               # cmd2hash, save_exec_output
│       │   ├── prompt_builder.py   # System-prompt construction
│       │   └── ui.py               # Rich console helpers
│       ├── tools/
│       │   └── filesystem.py       # read_file / write_file LLM tools
│       └── workflows/
│           ├── general_fixer.py    # LLM brain (GeneralFixer)
│           ├── docker_fixer.py     # Docker build/run fix loop
│           └── java_fixer.py       # Java compile workflow (JavaCompileAgent)
├── tests/
│   ├── test_java_fixer.py
│   ├── test_analyzer.py
│   └── test_architecture.py
└── pyproject.toml
```

---

## 2. Component Roles

| Component | Role |
|---|---|
| `Executor` | Thin `subprocess.Popen` wrapper; streams output; saves stdout/stderr |
| `GeneralFixer` | LangChain + OpenAI; takes error log → returns `FixSuggestion` |
| `DockerFixer` | Orchestrates docker-build/run retry loop using Executor + GeneralFixer |
| `JavaCompileAgent` | Orchestrates Java Docker image build → compile → LLM fix loop → optional CodeQL |
| `Configs` | Pydantic `BaseSettings`; reads env vars, config file, CLI defaults |
| `DirConfigs` | `platformdirs`-based paths (cache / state / data) per OS |

---

## 3. CLI Commands

```
fix-compile
├── config                  # Manage persistent configuration
│   ├── set <key> <value>
│   ├── get <key>
│   ├── list
│   └── del <key>
│
├── docker                  # Docker build/run fix workflow
│   ├── build               # Fix docker build errors with LLM loop
│   └── run                 # Fix docker run errors with LLM loop
│
├── java                    # Java compile workflow (isolated Docker)
│   --dir <path>            # Java project root (required)
│   --docker                # Enable Docker isolation (required for now)
│   --compile-cmd <cmd>     # Override auto-detected build command
│   --with-codeql           # Run CodeQL after successful compile
│   --m2-settings <file>    # Mount a custom Maven settings.xml
│   --docker-arg <arg>      # Extra docker run args (repeatable)
│   --max-attempts <n>      # Max LLM auto-fix attempts (default: 3)
│   --no-fix                # Compile once, no LLM fix loop
│   --force                 # Force rebuild Docker image
│   --dev                   # Load .env for development
│
├── fix                     # One-shot LLM analysis of a log
│   --log-dir / --text / --cmd
│
├── exec                    # Execute arbitrary command and cache log
│   <cmd...>
│
└── version
```

---

## 4. Data Flow

### Java Compile Workflow (`java_fixer.py`)

```
fix-compile java --dir <project> --docker [--with-codeql]
       │
       ▼
JavaCompileAgent.run_pipeline()
       │
       ├─ 1. Validate project_dir exists
       ├─ 2. Check docker is available
       ├─ 3. Compute run_hash (project path + flags); mkdir state_dir/<hash>/
       ├─ 4. Copy Dockerfile-Java template → state_dir/<hash>/Dockerfile
       ├─ 5. Auto-detect build tool (pom.xml→Maven, build.gradle→Gradle)
       ├─ 6. Resolve .m2 settings (explicit file OR auto-generate from mirror config)
       │
       └─ Loop (max_attempts):
              │
              ├─ docker build → fix-compile-java:<hash>   (only when Dockerfile changed)
              ├─ docker run --rm \
              │        --add-host=host.docker.internal:host-gateway \
              │        -v project_dir:/workspace/project \
              │        -v state_dir:/workspace/runstate \
              │        -v host_m2:/workspace/.m2/repository \
              │        [-v settings.xml:/root/.m2/settings.xml:ro]
              │        <image> bash -lc "<compile_cmd>"
              │
              ├─ [success] → break
              ├─ [no_fix]  → break
              └─ GeneralFixer.quick_analyze(error_log)
                     │
                     ├─ FixType.COMMAND  → update compile_cmd
                     ├─ FixType.FILE     → write file to project_dir (+ .bak)
                     └─ FixType.DOCKER   → write Dockerfile, set need_rebuild=True
       │
       └─ [with_codeql & success]
              docker run <image> bash -lc "codeql database create ... && codeql database analyze ..."
              → SARIF output saved to state_dir/<hash>/attempt-N/codeql-result.sarif
```

### Docker Build/Run Fix Loop (`docker_fixer.py`)

```
fix-compile docker build <dockerfile> <context> [--tag <tag>]
       │
       ▼
DockerFixer.fix_build_loop()
       │
       └─ Loop (max_retries):
              ├─ docker build → capture stderr on failure
              ├─ [success] → done
              └─ GeneralFixer.analyze() → apply fix
                     ├─ FixType.FILE    → patch Dockerfile
                     └─ FixType.COMMAND → update build cmd
```

### One-shot Analysis (`fix` command)

```
fix-compile fix [--text | --log-dir | --cmd]
       │
       └─ GeneralFixer.analyze(error_log) → print FixSuggestion
```

---

## 5. Configuration

Priority (highest → lowest):

1. CLI arguments
2. Config file: `~/.config/fix-compile/<version>/config.yaml`
3. Environment variables
4. `.env` file (dev mode only, `--dev` flag)
5. Pydantic field defaults

Key config keys (set with `fix-compile config set <KEY> <VALUE>`):

| Key | Default | Purpose |
|---|---|---|
| `FIXER_MODEL` | `gpt-4o` | LLM model name |
| `OPENAI_API_KEY` | — | OpenAI / compatible API key |
| `OPENAI_BASE_URL` | (openai default) | Custom base URL for compatible APIs |
| `CUSTOM_PROMPT` | (built-in) | Override system prompt |
| `JAVA_MAX_FIX_ATTEMPTS` | `3` | Max LLM fix loops for java workflow |
| `JAVA_DOCKER_IMAGE_PREFIX` | `fix-compile-java` | Docker image name prefix |
| `JAVA_M2_MIRROR_URL` | `https://maven.aliyun.com/...` | Maven mirror (auto-generates settings.xml) |
| `JAVA_M2_MIRROR_ID` | `aliyun-public` | Mirror ID in generated settings.xml |
| `JAVA_M2_MIRROR_OF` | `*` | Mirror pattern |

---

## 6. Persistent Storage (`platformdirs`)

All paths are OS-appropriate and version-scoped under `<app>/0.2.0/`.

| Purpose | Linux path | Config key (DirConfigs) |
|---|---|---|
| Config file | `~/.config/fix-compile/0.2.0/config.yaml` | — |
| Logs | `~/.local/state/fix-compile/0.2.0/log/` | `log_dir` |
| Exec cache | `~/.cache/fix-compile/0.2.0/` | `cache_dir` |
| Java state | `~/.local/state/fix-compile/0.2.0/java/` | `java_state_dir` |
| Java m2 repo | `~/.local/share/fix-compile/0.2.0/java/m2/repository/` | `java_data_dir` |
| Java m2 settings | `~/.local/share/fix-compile/0.2.0/java/m2/settings.xml` | (generated) |

---

## 7. Schema Models (`schema.py`)

```
FixType          (COMMAND | FILE | DOCKER)
OperationType    (BUILD | RUN | COMPILE | ...)

FixSuggestion
  ├─ fix_type: FixType
  ├─ command: str | None
  ├─ file_path: str | None
  ├─ new_content: str | None
  └─ dockerfile_content: str | None

GeneralAnalysisContext
  ├─ error_log: str
  ├─ cwd: str
  └─ previous_attempts: int

JavaBuildTool    (MAVEN | GRADLE | UNKNOWN)

JavaFixConfig
  ├─ project_dir: str
  ├─ use_docker: bool
  ├─ with_codeql: bool
  ├─ no_fix: bool
  ├─ force_rebuild: bool
  ├─ max_attempts: int
  ├─ compile_command: str | None
  ├─ passthrough_args: list[str]
  ├─ docker_run_args: list[str]
  └─ m2_settings_file: str | None

JavaFixResult
  ├─ success: bool
  ├─ attempts: int
  ├─ build_tool: JavaBuildTool
  ├─ build_command: str
  ├─ codeql_command: str | None
  ├─ image_tag: str
  └─ logs_dir: str
```

---

## 8. Security Notes

- API keys stored as Pydantic `SecretStr` — never printed in logs or REPL
- Subprocess commands built with `shlex.join()` — no shell injection
- Docker proxy URLs: `127.0.0.1` / `localhost` are automatically translated to
  `host.docker.internal` (with `--add-host=host.docker.internal:host-gateway`)
  so host-side proxies are reachable from inside containers on Linux

---

## 9. Testing

```bash
uv run pytest tests/ -q                      # all tests
uv run pytest tests/test_java_fixer.py -q   # java workflow unit tests only
```

Tests use `tmp_path` fixtures and mock `Configs` — no real Docker or API calls needed.

---

## 10. Development Setup

```bash
uv sync                           # install dependencies
uv pip install -e ".[dev]"        # editable install with dev extras

# local CLI
uv run . java --dir <path> --docker --no-fix --dev

# format / lint
black src/
ruff check src/
mypy src/
```

---

## 11. References

- [Typer Documentation](https://typer.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [LangChain Documentation](https://python.langchain.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [platformdirs](https://platformdirs.readthedocs.io/)
