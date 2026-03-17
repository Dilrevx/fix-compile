from pathlib import Path


from fix_compile.config import Configs, DirConfigs
from fix_compile.schema import JavaBuildTool
from fix_compile.workflows.java_fixer import JavaCompileAgent


def _build_test_config(tmp_path: Path, **overrides) -> Configs:
    dirs = DirConfigs(
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
        log_dir=tmp_path / "log",
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
    )
    return Configs(
        OPENAI_API_KEY="test-key",
        CUSTOM_PROMPT="",
        dir_configs=dirs,
        **overrides,
    )


def test_detect_build_tool_maven(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    project = tmp_path / "project-maven"
    project.mkdir(parents=True)
    (project / "pom.xml").write_text("<project></project>", encoding="utf-8")

    tool = agent._detect_build_tool(project)
    assert tool == JavaBuildTool.MAVEN


def test_detect_build_tool_gradle(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    project = tmp_path / "project-gradle"
    project.mkdir(parents=True)
    (project / "build.gradle").write_text("plugins {}", encoding="utf-8")

    tool = agent._detect_build_tool(project)
    assert tool == JavaBuildTool.GRADLE


def test_resolve_m2_settings_generates_file(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    settings_file = agent._resolve_m2_settings(None)
    assert settings_file is not None
    assert settings_file.exists()

    content = settings_file.read_text(encoding="utf-8")
    assert cfg.JAVA_M2_MIRROR_URL in content
    assert cfg.JAVA_M2_MIRROR_ID in content


def test_render_m2_settings_includes_proxy_section(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    content = agent._render_m2_settings(proxy=("127.0.0.1", "7890"))
    assert "<proxies>" in content
    assert "<host>127.0.0.1</host>" in content
    assert "<port>7890</port>" in content
    # Two entries: http + https
    assert content.count("<proxy>") == 2


def test_render_m2_settings_no_proxy_section_when_none(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    content = agent._render_m2_settings(proxy=None)
    assert "<proxies>" not in content
    assert "<mirrors>" in content  # mirror is still present


def test_parse_proxy_returns_raw_loopback(tmp_path: Path, monkeypatch):
    """With --network=host, 127.0.0.1 is reachable as-is; no translation needed."""
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    result = agent._parse_proxy()
    assert result == ("127.0.0.1", "7890")


def test_parse_proxy_returns_none_when_unset(tmp_path: Path, monkeypatch):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    result = agent._parse_proxy()
    assert result is None


def test_resolve_m2_settings_proxy_only(tmp_path: Path, monkeypatch):
    """Settings file should still be generated when only proxy is set (no mirror)."""
    cfg = _build_test_config(tmp_path, JAVA_M2_MIRROR_URL="")
    agent = JavaCompileAgent(cfg)

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    settings_file = agent._resolve_m2_settings(None)
    assert settings_file is not None
    content = settings_file.read_text(encoding="utf-8")
    assert "<proxies>" in content
    assert "<mirrors>" not in content


def test_resolve_m2_settings_returns_none_when_nothing_configured(
    tmp_path: Path, monkeypatch
):
    cfg = _build_test_config(tmp_path, JAVA_M2_MIRROR_URL="")
    agent = JavaCompileAgent(cfg)

    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    result = agent._resolve_m2_settings(None)
    assert result is None


def test_detect_build_tool_maven(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    project = tmp_path / "project-maven"
    project.mkdir(parents=True)
    (project / "pom.xml").write_text("<project></project>", encoding="utf-8")

    tool = agent._detect_build_tool(project)
    assert tool == JavaBuildTool.MAVEN


def test_detect_build_tool_gradle(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    project = tmp_path / "project-gradle"
    project.mkdir(parents=True)
    (project / "build.gradle").write_text("plugins {}", encoding="utf-8")

    tool = agent._detect_build_tool(project)
    assert tool == JavaBuildTool.GRADLE


def test_resolve_m2_settings_generates_file(tmp_path: Path):
    cfg = _build_test_config(tmp_path)
    agent = JavaCompileAgent(cfg)

    settings_file = agent._resolve_m2_settings(None)
    assert settings_file is not None
    assert settings_file.exists()

    content = settings_file.read_text(encoding="utf-8")
    assert cfg.JAVA_M2_MIRROR_URL in content
    assert cfg.JAVA_M2_MIRROR_ID in content
