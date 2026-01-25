# fix-compile CLI Reference

This document describes the unified CLI commands for `fix-compile`.

## Overview

- `fix-compile exec`: Execute any command and cache its log.
- `fix-compile docker build`: Build Docker images with optional auto-fix.
- `fix-compile docker run`: Run Docker images with optional auto-fix.
- `fix-compile fixer`: Analyze a log file and produce a single-round suggestion.

All run-related commands support `--dev` to enable dev mode (load `.env`). Logs are cached under the user log directory following a timestamped pattern.

## Commands

### exec
Execute an arbitrary command and cache its log.

Usage:
```
fix-compile exec [OPTIONS] CMD...
```

Options:
- `--cwd PATH`: Working directory for the command.
- `--dev`: Enable dev mode (.env).
- `-v, --verbose`: Verbose output.

Behavior:
- Streams command output.
- Caches combined stdout+stderr to a timestamped log file.
- Prints success/warning based on exit code.

### docker build
Run `docker build` with optional auto-fix loop.

Usage:
```
fix-compile docker build [OPTIONS] [CONTEXT]
```

Options:
- `-f, --file PATH`: Dockerfile path (default: Dockerfile)
- `-t, --tag TEXT`: Image tag (default: fix-compile:latest)
- `--no-cache`: Build without cache
- `--no-fixer`: Disable fixer (only execute build)
- `--no-exec`: Disable exec (reuse latest cached log to auto-fix)
- `--retry INTEGER`: Max fix attempts (default: 3)
- `-y, --yes`: Auto-apply fixes without confirmation
- `--dev`: Enable dev mode (.env)
- `-v, --verbose`: Verbose output

Behavior:
- Normal path: Executes `docker build`, caches log, auto-fixes on failure unless `--no-fixer`.
- `--no-exec`: Skips executing build; reuses latest cached log to attempt fixes.
- Each fix shows the proposed Dockerfile and applies changes (auto with `--yes`).

### docker run
Run `docker run` with optional auto-fix for runtime errors.

Usage:
```
fix-compile docker run [OPTIONS] TAG
```

Options:
- `--args TEXT`: Additional `docker run` args (e.g., `-p 8080:80`)
- `--no-fixer`: Disable fixer (only execute run)
- `--no-exec`: Disable exec (reuse latest cached log to auto-fix)
- `--retry INTEGER`: Max fix attempts (default: 3)
- `-y, --yes`: Auto-apply fixes without confirmation
- `--dev`: Enable dev mode (.env)
- `-v, --verbose`: Verbose output

Behavior:
- Normal path: Executes `docker run`, caches log, auto-fixes on failure unless `--no-fixer`.
- `--no-exec`: Skips executing run; reuses latest cached log to attempt fixes.

### fixer
Analyze a log file and produce a single-round suggestion (no execution).

Usage:
```
fix-compile fixer [OPTIONS] LOG_FILE
```

Options:
- `-f, --file PATH`: Path to Dockerfile (default: Dockerfile)
- `-c, --context TEXT`: Docker build context (default: .)
- `-o, --operation TEXT`: `build` or `run` (default: build)
- `--dev`: Enable dev mode (.env)

Behavior:
- Performs one analysis using the provided log.
- Prints suggested Dockerfile and summary.

## Logs
Logs are saved under the user log directory using the pattern defined by `LOG_FILENAME`. The path is constructed as:
```
<USER_LOG_DIR>/<timestamp-based path>
```
The combined stdout+stderr is written to this file after each execution.

## Dev Mode
With `--dev`, the CLI loads environment variables from `.env` located at the project dev root before executing commands.
