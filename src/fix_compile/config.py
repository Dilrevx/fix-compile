from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration for DockerfileFixer using Pydantic Settings."""

    # OpenAI API 配置
    OPENAI_API_BASE: str = Field(
        default="https://api.openai.com/v1", description="OpenAI API base URL"
    )
    OPENAI_API_KEY: SecretStr = Field(description="OpenAI API key")

    # 模型配置
    EXECUTOR_MODEL: str = Field(
        default="gpt-4o-mini", description="Executor LLM model name"
    )
    FIXER_MODEL: str = Field(default="gpt-4o-mini", description="Fixer LLM model name")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # 限制配置
    MAX_TOKENS: int = Field(
        default=32768, gt=0, description="Maximum tokens for response"
    )
    TIMEOUT: int = Field(default=300, gt=0, description="Timeout in seconds")

    # Pydantic Settings 的核心配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # 环境变量前缀，一般用 __ 设置 nested 配置
        # env_prefix="FIXER_",
        # env_nested_delimiter="__",
    )


# 实例化
config = Config()
