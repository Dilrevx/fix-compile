"""Java isolated docker workflow with LLM auto-fix and optional CodeQL."""

import shlex
from pathlib import Path
from typing import Optional

from fix_compile.config import Configs
from fix_compile.constants import JAVA_TEMPLATE_FILE
from fix_compile.executor import ExecutionError, Executor
from fix_compile.schema import JavaBuildTool, JavaFixConfig, JavaFixResult
from fix_compile.utils import ui
from fix_compile.utils.io import cmd2hash, save_exec_output
from fix_compile.workflows.general_fixer import GeneralFixer


class JavaCompileAgent:
    """Compile Java projects in an isolated docker env and auto-fix failures with LLM."""

    def __init__(self, config: Configs):
        self.config = config
        self.executor = Executor()
        self.fixer: Optional[GeneralFixer] = None

    def run_pipeline(self, java_config: JavaFixConfig) -> JavaFixResult:
        """Run the Java compile pipeline in docker with optional CodeQL scan."""
        project_dir = Path(java_config.project_dir).resolve()
        if not project_dir.exists() or not project_dir.is_dir():
            raise FileNotFoundError(f"Java project dir not found: {project_dir}")

        if not java_config.use_docker:
            raise ValueError("Current java workflow only supports --docker mode")

        self._ensure_docker_available()

        run_hash = cmd2hash(
            [
                project_dir.as_posix(),
                str(java_config.with_codeql),
                *java_config.passthrough_args,
            ],
            project_dir,
        )
        run_dir = self.config.dir_configs.java_state_dir / run_hash
        run_dir.mkdir(parents=True, exist_ok=True)

        dockerfile_path = run_dir / "Dockerfile"
        dockerfile_path.write_text(
            JAVA_TEMPLATE_FILE.read_text(encoding="utf-8"), encoding="utf-8"
        )

        build_tool = self._detect_build_tool(project_dir)
        compile_cmd = self._default_compile_command(build_tool, project_dir)
        if java_config.compile_command:
            compile_cmd = shlex.split(java_config.compile_command)
        m2_settings = self._resolve_m2_settings(java_config.m2_settings_file)

        image_tag = f"{self.config.JAVA_DOCKER_IMAGE_PREFIX}:{run_hash}"
        need_rebuild_image = True

        codeql_command: Optional[str] = None
        success = False
        attempt_used = 0

        for attempt in range(1, java_config.max_attempts + 1):
            attempt_used = attempt
            ui.step(f"Java compile attempt {attempt}/{java_config.max_attempts}")

            attempt_dir = run_dir / f"attempt-{attempt}"

            if need_rebuild_image or java_config.force_rebuild:
                image_result = self._build_java_image(
                    dockerfile_path=dockerfile_path,
                    run_dir=run_dir,
                    image_tag=image_tag,
                    log_dir=attempt_dir / "docker-build",
                )
                save_exec_output(image_result, attempt_dir / "docker-build")
                if not image_result.success:
                    raise ExecutionError("Failed to build Java docker image")
                need_rebuild_image = False

            compile_result = self._run_compile_in_container(
                image_tag=image_tag,
                project_dir=project_dir,
                run_dir=run_dir,
                compile_cmd=compile_cmd,
                passthrough_args=java_config.passthrough_args,
                m2_settings=m2_settings,
                docker_run_args=java_config.docker_run_args,
                log_dir=attempt_dir / "compile",
            )
            save_exec_output(compile_result, attempt_dir / "compile")

            if compile_result.success:
                ui.success(
                    "Java project compile succeeded in isolated docker environment"
                )
                success = True
                break

            ui.warning("Compile failed in docker container")
            if java_config.no_fix:
                break

            suggestion = self._get_fixer().quick_analyze(
                error_log=self._build_error_log(compile_result, compile_cmd),
                cwd=project_dir.as_posix(),
            )
            compile_cmd, image_changed = self._apply_llm_suggestion(
                suggestion=suggestion,
                project_dir=project_dir,
                run_dir=run_dir,
                current_compile_cmd=compile_cmd,
            )
            need_rebuild_image = image_changed

        if not success:
            return JavaFixResult(
                success=False,
                attempts=attempt_used,
                build_tool=build_tool,
                build_command=shlex.join(compile_cmd),
                codeql_command=None,
                image_tag=image_tag,
                logs_dir=run_dir.as_posix(),
            )

        if java_config.with_codeql:
            codeql_command = self._build_codeql_command(compile_cmd)
            codeql_log_dir = run_dir / f"attempt-{attempt_used}" / "codeql"
            codeql_result = self._run_shell_in_container(
                image_tag=image_tag,
                project_dir=project_dir,
                run_dir=run_dir,
                shell_cmd=codeql_command,
                m2_settings=m2_settings,
                docker_run_args=java_config.docker_run_args,
                log_dir=codeql_log_dir,
            )
            save_exec_output(codeql_result, codeql_log_dir)
            if not codeql_result.success:
                return JavaFixResult(
                    success=False,
                    attempts=attempt_used,
                    build_tool=build_tool,
                    build_command=shlex.join(compile_cmd),
                    codeql_command=codeql_command,
                    image_tag=image_tag,
                    logs_dir=run_dir.as_posix(),
                )
            ui.success("CodeQL analysis completed")

        return JavaFixResult(
            success=True,
            attempts=attempt_used,
            build_tool=build_tool,
            build_command=shlex.join(compile_cmd),
            codeql_command=codeql_command,
            image_tag=image_tag,
            logs_dir=run_dir.as_posix(),
        )

    def _ensure_docker_available(self) -> None:
        result = self.executor.execute(["docker", "--version"], stream=False)
        if not result.success:
            raise ExecutionError("Docker is required for java --docker workflow")

    def _get_fixer(self) -> GeneralFixer:
        if self.fixer is None:
            self.fixer = GeneralFixer(
                model=self.config.FIXER_MODEL,
                api_key=self.config.OPENAI_API_KEY.get_secret_value(),
                custom_prompt=self.config.CUSTOM_PROMPT,
            )
        return self.fixer

    def _detect_build_tool(self, project_dir: Path) -> JavaBuildTool:
        if (project_dir / "pom.xml").exists() or (project_dir / "mvnw").exists():
            return JavaBuildTool.MAVEN
        if (project_dir / "build.gradle").exists() or (
            project_dir / "gradlew"
        ).exists():
            return JavaBuildTool.GRADLE
        return JavaBuildTool.UNKNOWN

    def _default_compile_command(
        self, tool: JavaBuildTool, project_dir: Path
    ) -> list[str]:
        if tool == JavaBuildTool.MAVEN:
            if (project_dir / "mvnw").exists():
                return ["./mvnw", "-B", "-DskipTests", "compile"]
            return ["mvn", "-B", "-DskipTests", "compile"]

        if tool == JavaBuildTool.GRADLE:
            if (project_dir / "gradlew").exists():
                return ["./gradlew", "classes", "--no-daemon"]
            return ["gradle", "classes", "--no-daemon"]

        return ["mvn", "-B", "-DskipTests", "compile"]

    def _build_java_image(
        self,
        dockerfile_path: Path,
        run_dir: Path,
        image_tag: str,
        log_dir: Optional[Path] = None,
    ):
        build_args: list[str] = []
        for env_key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
            env_val = self._safe_env(env_key)
            if env_val:
                build_args.extend(["--build-arg", f"{env_key}={env_val}"])

        use_cn_mirror = getattr(self.config, "JAVA_USE_CN_MIRROR", False)
        build_args.extend(
            ["--build-arg", f"USE_CN_MIRROR={'true' if use_cn_mirror else 'false'}"]
        )

        cmd = [
            "docker",
            "build",
            # Use host networking so loopback-bound services on the host
            # (e.g. a proxy on 127.0.0.1:port) are directly reachable
            # inside the build container as 127.0.0.1.
            "--network=host",
            "-f",
            dockerfile_path.as_posix(),
            "-t",
            image_tag,
            *build_args,
            run_dir.as_posix(),
        ]
        return self.executor.execute(cmd, stream=True, log_dir=log_dir)

    def _resolve_m2_settings(self, m2_settings_file: Optional[str]) -> Optional[Path]:
        if m2_settings_file:
            resolved = Path(m2_settings_file).expanduser().resolve()
            if not resolved.exists() or not resolved.is_file():
                raise FileNotFoundError(f"Maven settings file not found: {resolved}")
            return resolved

        mirror_url = self.config.JAVA_M2_MIRROR_URL.strip()
        proxy = self._parse_proxy()
        # Generate settings.xml whenever mirror OR proxy is configured.
        if not mirror_url and proxy is None:
            return None

        settings_dir = self.config.dir_configs.java_data_dir / "m2"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "settings.xml"
        settings_path.write_text(self._render_m2_settings(proxy), encoding="utf-8")
        return settings_path

    def _parse_proxy(self) -> Optional[tuple[str, str]]:
        """Parse HTTP_PROXY / HTTPS_PROXY into (host, port) suitable for use inside Docker.

        Returns None when no proxy is configured.
        """
        import re

        for key in ("HTTP_PROXY", "HTTPS_PROXY"):
            raw = self._safe_env(key)
            if raw:
                m = re.match(r"https?://([^:/]+):(\d+)", raw)
                if m:
                    return m.group(1), m.group(2)
        return None

    def _render_m2_settings(self, proxy: Optional[tuple[str, str]] = None) -> str:
        mirror_url = self.config.JAVA_M2_MIRROR_URL.strip()

        mirrors_block = ""
        if mirror_url:
            mirrors_block = f"""  <mirrors>
    <mirror>
      <id>{self.config.JAVA_M2_MIRROR_ID}</id>
      <name>fix-compile-generated-mirror</name>
      <url>{mirror_url}</url>
      <mirrorOf>{self.config.JAVA_M2_MIRROR_OF}</mirrorOf>
    </mirror>
  </mirrors>"""

        # Maven does NOT read HTTP_PROXY environment variables — proxy must be
        # configured explicitly in settings.xml <proxies>.
        proxies_block = ""
        if proxy:
            host, port = proxy
            proxies_block = f"""  <proxies>
    <proxy>
      <id>fix-compile-http-proxy</id>
      <active>true</active>
      <protocol>http</protocol>
      <host>{host}</host>
      <port>{port}</port>
      <nonProxyHosts>localhost|127.0.0.1|::1</nonProxyHosts>
    </proxy>
    <proxy>
      <id>fix-compile-https-proxy</id>
      <active>true</active>
      <protocol>https</protocol>
      <host>{host}</host>
      <port>{port}</port>
      <nonProxyHosts>localhost|127.0.0.1|::1</nonProxyHosts>
    </proxy>
  </proxies>"""

        body = "\n".join(part for part in [mirrors_block, proxies_block] if part)
        return f"""<settings xmlns=\"http://maven.apache.org/SETTINGS/1.0.0\"
          xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"
          xsi:schemaLocation=\"http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd\">
{body}
</settings>
"""

    def _docker_run_base_cmd(
        self,
        image_tag: str,
        project_dir: Path,
        run_dir: Path,
        m2_settings: Optional[Path],
        docker_run_args: list[str],
    ) -> list[str]:
        host_m2_repo = self.config.dir_configs.java_data_dir / "m2" / "repository"
        host_m2_repo.mkdir(parents=True, exist_ok=True)

        cmd = [
            "docker",
            "run",
            "--rm",
            "--network=host",
            "-v",
            f"{project_dir.as_posix()}:{self.config.JAVA_DOCKER_WORKDIR}",
            "-v",
            f"{run_dir.as_posix()}:/workspace/runstate",
            "-v",
            f"{host_m2_repo.as_posix()}:{self.config.JAVA_M2_LOCAL_REPO}",
        ]

        if m2_settings:
            cmd.extend(["-v", f"{m2_settings.as_posix()}:/root/.m2/settings.xml:ro"])

        for env_key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
            env_val = self._safe_env(env_key)
            if env_val:
                cmd.extend(["-e", f"{env_key}={env_val}"])

        if docker_run_args:
            cmd.extend(docker_run_args)

        cmd.append(image_tag)
        return cmd

    def _safe_env(self, key: str) -> str:
        import os

        return (os.environ.get(key) or "").strip()

    def _docker_proxy_url(self, url: str) -> str:
        """Kept for backwards-compatibility / tests.  No longer called.

        Both ``docker build`` and ``docker run`` now use ``--network=host``
        which means the container shares the host's network namespace and
        127.0.0.1 / localhost refer directly to the host.  No URL
        translation is necessary.
        """
        import re

        return re.sub(r"(localhost|127\.0\.0\.1)", "host.docker.internal", url)

    def _run_compile_in_container(
        self,
        image_tag: str,
        project_dir: Path,
        run_dir: Path,
        compile_cmd: list[str],
        passthrough_args: list[str],
        m2_settings: Optional[Path],
        docker_run_args: list[str],
        log_dir: Optional[Path] = None,
    ):
        shell_cmd = shlex.join([*compile_cmd, *passthrough_args])
        return self._run_shell_in_container(
            image_tag=image_tag,
            project_dir=project_dir,
            run_dir=run_dir,
            shell_cmd=shell_cmd,
            m2_settings=m2_settings,
            docker_run_args=docker_run_args,
            log_dir=log_dir,
        )

    def _run_shell_in_container(
        self,
        image_tag: str,
        project_dir: Path,
        run_dir: Path,
        shell_cmd: str,
        m2_settings: Optional[Path],
        docker_run_args: list[str],
        log_dir: Optional[Path] = None,
    ):
        cmd = self._docker_run_base_cmd(
            image_tag=image_tag,
            project_dir=project_dir,
            run_dir=run_dir,
            m2_settings=m2_settings,
            docker_run_args=docker_run_args,
        )
        cmd.extend(["bash", "-lc", shell_cmd])
        return self.executor.execute(cmd, stream=True, log_dir=log_dir)

    def _build_error_log(self, result, compile_cmd: list[str]) -> str:
        return (
            f"compile command: {shlex.join(compile_cmd)}\n"
            f"cwd: {result.cwd}\n\n"
            f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )

    def _apply_llm_suggestion(
        self,
        suggestion,
        project_dir: Path,
        run_dir: Path,
        current_compile_cmd: list[str],
    ) -> tuple[list[str], bool]:
        image_changed = False

        if suggestion.fix_type.value == "command" and suggestion.command:
            try:
                new_cmd = shlex.split(suggestion.command)
                if new_cmd:
                    ui.info(f"Using LLM-suggested command: {suggestion.command}")
                    return new_cmd, image_changed
            except ValueError:
                ui.warning("LLM command suggestion is invalid shell syntax, ignored")
            return current_compile_cmd, image_changed

        if (
            suggestion.fix_type.value == "file"
            and suggestion.file_path
            and suggestion.new_content is not None
        ):
            target = (project_dir / suggestion.file_path).resolve()
            backup = Path(f"{target}.bak")
            if target.exists() and target.is_file():
                backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(suggestion.new_content, encoding="utf-8")
            ui.info(f"Applied LLM file suggestion: {target}")
            return current_compile_cmd, image_changed

        if suggestion.fix_type.value == "docker" and suggestion.dockerfile_content:
            dockerfile_path = run_dir / "Dockerfile"
            backup = Path(f"{dockerfile_path}.bak")
            backup.write_text(
                dockerfile_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
            dockerfile_path.write_text(suggestion.dockerfile_content, encoding="utf-8")
            ui.info("Applied LLM docker suggestion to java runtime Dockerfile")
            return current_compile_cmd, True

        ui.warning(
            "No actionable LLM suggestion received, keeping current compile command"
        )
        return current_compile_cmd, image_changed

    def _build_codeql_command(self, compile_cmd: list[str]) -> str:
        codeql_db = "/workspace/runstate/codeql-db"
        codeql_out = "/workspace/runstate/codeql-result.sarif"
        compile_shell = shlex.join(compile_cmd)
        compile_part = shlex.quote(compile_shell)

        return (
            f"codeql database create {codeql_db} "
            f"--language={self.config.JAVA_CODEQL_LANGUAGE} "
            f"--source-root={self.config.JAVA_DOCKER_WORKDIR} "
            f"--command {compile_part} "
            "&& "
            f"codeql database analyze {codeql_db} "
            f"{self.config.JAVA_CODEQL_QUERY_SUITE} "
            f"--format=sarif-latest --output={codeql_out}"
        )
