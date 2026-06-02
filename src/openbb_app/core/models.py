from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Application configuration loaded from environment variables."""

    title: str = Field(default="openbb-app", description="The title of the app.")
    description: str = Field(
        default="openbb-app API for OpenBB Workspace",
        description="The description of the app.",
    )
    agent_host_url: str = Field(
        description="The host URL and port number where the app is running."
    )
    app_api_key: str = Field(description="The API key to access the bot.")
    openrouter_api_key: str = Field(
        description="OpenRouter API key for AI functionality."
    )
    data_folder_path: str | None = Field(
        description=("The path to the folder that will store the " "transaction data."),
    )
    data_file: str = Field(
        default="transactions.xlsx",
        description="Path to transaction data file.",
    )
    cors_origins: list[str] = Field(
        default=[
            "https://pro.openbb.co",
            "https://finanalyzer.github.io",
            "http://localhost:1420",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
        ],
        description="List of allowed CORS origins.",
    )
    default_provider: str = Field(
        default="akshare",
        description="Default data provider.",
    )

    @field_validator(
        "agent_host_url", "app_api_key", "openrouter_api_key", mode="before"
    )
    def validate_required_env_vars(cls, value: str | None, info) -> str | None:
        """Validate required environment variables.

        Raises ValueError if any required variable is not set.
        """
        if not value:
            raise ValueError(f"{info.field_name} environment variable is required.")
        return value

    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, value: str | list[str] | None) -> list[str]:
        """Parse CORS origins from environment variable.

        Accepts either a comma-separated string or a list.
        Empty strings are treated as None to use defaults.
        """
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Treat empty string as None to use defaults
            if not value.strip():
                return None
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return [
            "https://pro.openbb.co",
            "http://localhost:1420",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
        ]
