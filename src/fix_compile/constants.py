"""
Global constants for fix-compile.
This module should NOT import any other internal modules to avoid circular dependencies.
"""

from enum import IntEnum, StrEnum  # Python 3.11+ use StrEnum
from pathlib import Path
from typing import Final

from platformdirs import PlatformDirs

# ---------------------------------------------------------
# 1. 基础元数据 (Basic Metadata)
# 使用 Final 标记，IDE 和 MyPy 会检查是否有代码试图修改它
# ---------------------------------------------------------
PROJECT_NAME: Final[str] = "fix-compile"
__version__: Final[str] = "0.2.0"

# ---------------------------------------------------------
# 2. 默认值与硬编码配置 (Defaults)
# 这些是代码逻辑的默认值，用户无法通过 .env 修改
# ---------------------------------------------------------
DEFAULT_ENCODING: Final[str] = "utf-8"
DEFAULT_TIMEOUT: Final[int] = 300  # seconds
DEFAULT_RETRY_COUNT: Final[int] = 3
DEFAULT_OPENAI_API_BASE: Final[str] = "https://api.openai.com/v1"
DEFAULT_MODEL_GPT_5_MINI: Final[str] = "gpt-5-mini"
DEFAULT_LOG_LEVEL_INFO: Final[str] = "INFO"
DEFAULT_MAX_TOKENS: Final[int] = 32768

# ---------------------------------------------------------
# 3. 文件系统与路径 (Files & Paths)
# ---------------------------------------------------------
# 获取项目源码根目录 (防御性写法)
PKG_ROOT = Path(__file__).resolve().parent
DEV_ROOT: Final[Path] = PKG_ROOT.parent.parent

PLATFORM_DIRS: Final[PlatformDirs] = PlatformDirs(
    appname=PROJECT_NAME, appauthor=PROJECT_NAME, version=__version__
)

USER_DATA_DIR: Final[Path] = Path(PLATFORM_DIRS.user_data_dir)
USER_CONFIG_DIR: Final[Path] = Path(PLATFORM_DIRS.user_config_dir)
USER_CACHE_DIR: Final[Path] = Path(PLATFORM_DIRS.user_cache_dir)
USER_LOG_DIR: Final[Path] = Path(PLATFORM_DIRS.user_log_dir)
USER_STATE_DIR: Final[Path] = Path(PLATFORM_DIRS.user_state_dir)


# 固定的文件名
ENV_FILENAME: Final[str] = ".env"
CONFIG_FILENAME: Final[str] = "config.yaml"
CACHE_FILENAME: Final[str] = "cache.json"
LOG_FILENAME: Final[str] = "%Y/%m/%d/%H-%M-%S.log"


# ---------------------------------------------------------
# 4. 枚举值 (Enums) - 强烈推荐用于 CLI 状态码
# ---------------------------------------------------------
class ExitCode(IntEnum):
    """标准的 CLI 退出码"""

    SUCCESS = 0
    ERROR_GENERAL = 1
    ERROR_DOCKER_BUILD = 2
    ERROR_LLM_API = 3
    ERROR_USER_CANCEL = 130  # Ctrl+C


class FixStatus(StrEnum):
    """修复流程的状态"""

    PENDING = "pending"
    ANALYZING = "analyzing"
    APPLYING = "applying"
    SUCCESS = "success"
    FAILED = "failed"
