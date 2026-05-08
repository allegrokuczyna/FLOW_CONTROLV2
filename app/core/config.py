from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    D365_TENANT_ID: str
    D365_CLIENT_ID: str
    D365_CLIENT_SECRET: str
    D365_URL: str
    
    DATABASE_URL: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()