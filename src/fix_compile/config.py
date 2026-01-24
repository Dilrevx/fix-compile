"""
Global configuration settings
Priority:
0. cli settings
1. config profile
2. export environment variables
3. .env file (on dev mode)

"""

import logging.config
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from fix_compile.constants import (
    CACHE_FILENAME,
    CONFIG_FILENAME,
    DEFAULT_LOG_LEVEL_INFO,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_GPT_5_MINI,
    DEFAULT_OPENAI_API_BASE,
    DEFAULT_TIMEOUT,
    DEV_ROOT,
    ENV_FILENAME,
    LOG_FILENAME,
    PROJECT_NAME,
    USER_CACHE_DIR,
    USER_CONFIG_DIR,
    USER_DATA_DIR,
    USER_LOG_DIR,
    USER_STATE_DIR,
)
from fix_compile.utils import ui


def _load_dotenv(override: bool = False):
    # Load environment variables from .env file
    env_path = DEV_ROOT / ENV_FILENAME
    load_dotenv(
        dotenv_path=env_path,
        override=override,
    )


# 定义配置字典
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    # 1. 格式器：定义日志长什么样
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(message)s",  # Rich 会自动加时间，这里简单点
        },
    },
    # 2. 处理器：定义日志去哪里
    "handlers": {
        "console": {
            "class": "rich.logging.RichHandler",
            "level": "INFO",
            "formatter": "simple",
            "rich_tracebacks": True,
            "show_path": False,
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "filename": str(
                USER_LOG_DIR / LOG_FILENAME
            ),  # 这里建议用 platformdirs 动态获取路径
            "encoding": "utf-8",
        },
    },
    # 3. 定义 Loggers
    "loggers": {
        # A. 你的项目 Logger (fix-compile)
        PROJECT_NAME: {
            "handlers": ["console", "file"],
            "level": "DEBUG",  # WILL BE OVERRIDED IN setup_logging
            "propagate": False,  # 关键：不向上传递给 root，防止重复打印
        },
        # B. 根 Logger (所有第三方库的兜底配置)
        "root": {
            "handlers": ["console", "file"],
            "level": "WARNING",  # 第三方库只报 Warning 以上的错
        },
        # C. (可选) 如果你想看 docker 的详细日志，可以单独配置它
        "docker": {
            "handlers": ["file"],  # docker 日志只写文件，不打扰屏幕
            "level": "DEBUG",
            "propagate": False,
        },
    },
}


def setup_logging(log_level: str, enabled_console: bool = False):
    """Setup logging configuration. Default log saved as file only. If enabled_console is True, also log to console."""
    if not USER_LOG_DIR.exists():
        ui.error(
            f"Log directory {USER_LOG_DIR} does not exist. Likely config not loaded."
        )
        raise FileNotFoundError(f"Log directory {USER_LOG_DIR} does not exist.")

    if not enabled_console:
        LOGGING_CONFIG["loggers"][PROJECT_NAME]["handlers"].remove("console")

    LOGGING_CONFIG["loggers"][PROJECT_NAME]["level"] = log_level.upper()
    logging.config.dictConfig(LOGGING_CONFIG)
    ui.info(f"Logging initialized with level {log_level}")
    ui.info(f"Log file: {USER_LOG_DIR / LOG_FILENAME}")


class DirConfigs(BaseModel):
    """Directory configurations."""

    config_dir: Path = USER_CONFIG_DIR
    cache_dir: Path = USER_CACHE_DIR
    log_dir: Path = USER_LOG_DIR
    data_dir: Path = USER_DATA_DIR
    state_dir: Path = USER_STATE_DIR

    cache_file: Path = cache_dir / CACHE_FILENAME
    log_file: Path = log_dir / LOG_FILENAME
    config_file: Path = config_dir / CONFIG_FILENAME


class Configs(BaseSettings):
    """Configuration for DockerfileFixer using Pydantic Settings."""

    # OpenAI API 配置
    OPENAI_API_BASE: str = Field(
        default=DEFAULT_OPENAI_API_BASE, description="OpenAI API base URL"
    )
    OPENAI_API_KEY: SecretStr = Field(description="OpenAI API key")

    # 模型配置
    EXECUTOR_MODEL: str = Field(
        default=DEFAULT_MODEL_GPT_5_MINI,
        description="Executor model that provides execution command",
    )
    FIXER_MODEL: str = Field(
        default=DEFAULT_MODEL_GPT_5_MINI,
        description="Fixer model that fix error log",
    )

    # 日志配置
    LOG_LEVEL: str = Field(default=DEFAULT_LOG_LEVEL_INFO, description="Logging level")

    # 限制配置
    MAX_TOKENS: int = Field(
        default=DEFAULT_MAX_TOKENS, gt=0, description="Maximum tokens for response"
    )
    TIMEOUT: int = Field(
        default=DEFAULT_TIMEOUT, gt=0, description="Timeout in seconds"
    )

    dir_configs: DirConfigs = Field(default_factory=DirConfigs)

    # 关闭 Pydantic Settings 的 dotenv 功能，已由 dotenv 加载到 os.environ
    # （默认不区分大小写）
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
        # 环境变量前缀，一般用 __ 设置 nested 配置
        # env_prefix="FIXER_",
        # env_nested_delimiter="__",
    )


# ---------------------------------------------------------
# 2. 配置管理器 (The Config Manager)
# ---------------------------------------------------------
class ConfigService:
    def __init__(self):
        # 懒加载：实例化时才去读取环境变量
        self._settings: Configs = None
        self._dir_settings: DirConfigs = None

    def _ensure_dirs(self):
        """确保所有运行时需要的目录都存在"""
        for attr in self._dir_settings.model_dump():
            if attr.endswith("_file"):
                continue

            path = getattr(self._dir_settings, attr)
            if isinstance(path, Path) and not path.exists():
                path.mkdir(parents=True, exist_ok=True)

        # only log file's file name contains path components
        self._dir_settings.log_file.parent.mkdir(parents=True, exist_ok=True)

    def load_config(self, *, dev_mode: bool = False, **kwargs):
        """加载配置"""
        if dev_mode:
            _load_dotenv(override=False)

        # 读取配置
        self._settings = Configs()
        self._dir_settings = self._settings.dir_configs
        self._ensure_dirs()

        config_file = self._dir_settings.config_file
        if config_file.exists():
            ui.info(f"Loading config file from {config_file}")
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    _profile_settings = Configs.model_validate(data)
                    kv_pairs = _profile_settings.model_dump(
                        exclude={"dir_configs"}
                    ).items()
                    ui.debug(f"Config file key-values: {kv_pairs}")

                    for key, value in kv_pairs:
                        setattr(self._settings, key, value)
                        ui.debug(f"Loaded config {key} from file")

            except Exception as e:
                ui.error(f"Failed to load config file {config_file}: {e}")
                raise

        # 覆盖配置
        try:
            for key, value in kwargs.items():
                key = key.upper()
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
                    ui.debug(f"Overridden config {key} from kwargs")
        except Exception as e:
            ui.error(f"Failed to override config with kwargs: {e}")
            raise

        setup_logging(self._settings.LOG_LEVEL)

    @property
    def config(self) -> Configs:
        """对外暴露静态配置"""
        if self._settings is None:
            ui.warning(
                "Configuration accessed before initialization. May cause issues."
            )
        return self._settings

    def save_config(self):
        """保存当前配置到文件 (YAML 格式)"""

        dump_settings = self._settings.model_dump(exclude={"dir_configs"})
        dump_settings["OPENAI_API_KEY"] = dump_settings[
            "OPENAI_API_KEY"
        ].get_secret_value()  # decrypt for saving

        config_path = self._dir_settings.config_file
        with config_path.open("w", encoding="utf-8") as f:
            yaml.dump(dump_settings, f)


# ---------------------------------------------------------
# 4. 单例导出 (Singleton Export)
# ---------------------------------------------------------
config_service = ConfigService()
