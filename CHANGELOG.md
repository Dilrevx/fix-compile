# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- 核心功能：重构 `docker` 子命令，支持自动捕获构建错误并调用 LLM 分析修复。
- 新增 `fix-compile docker build` 和 `fix-compile docker run` 命令。
- 基础环境模板：新增通用的 `Dockerfile.template`，支持按需注入 JDK、Maven、Gradle 和 CodeQL，并内置 Conda 环境容错加载逻辑。
- 引入 `importlib.resources` 用于安全读取包内静态资产（如 prompt 模板）。

- 提供 `fix-compile java` 命令作为 Java 项目的专用入口，自动识别构建工具并应用最佳实践的 Dockerfile 配置。

### Changed
- 架构调整：采用依赖注入模式传递 Config 对象，废弃全局变量，提升可测试性。
- 优化 LLM 提示词：强制 `DOCKER_BUILDKIT=0` 以获取更干净的线性构建日志，提高模型分析准确率。

## [1.0.0] - 2026-02-28
### Added
- 初始化 `fix-compile` 项目框架，cli 和 fix_compile 解耦。
- 基于 Typer 实现基础 CLI 命令，包括 config, docker。
- 用户数据存储于 `~/.config/fix-compile/`, `~/.cache/fix-compile/`, `~/.local/share/fix-compile/`，通过 `platformdirs` 统一管理。支持持久化日志、缓存和 Java 状态数据。
- 接入 LLM 基础分析模块（Analyzer），支持解析常规的编译报错日志。
- 实现 `subprocess` 命令执行器（Executor）的流式输出拦截。

[Unreleased]: https://github.com/yourusername/fix-compile/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/fix-compile/releases/tag/v0.1.0
