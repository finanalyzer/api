from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Application configuration loaded from environment variables."""

    title: str = Field(default="FinApp", description="The title of the app.")
    description: str = Field(
        default="FinApp API for OpenBB Workspace",
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
        description="The path to the folder that will store the transaction data."
    )
    data_file: str = Field(
        default="transactions.xlsx", description="Path to transaction data file."
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
