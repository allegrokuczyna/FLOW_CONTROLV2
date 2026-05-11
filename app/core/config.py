from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    D365_URL: str
    D365_CLIENT_ID: str
    D365_CLIENT_SECRET: str
    D365_TENANT_ID: str
    
    DATABASE_URL: str
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()