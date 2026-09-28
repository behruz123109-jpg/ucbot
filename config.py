import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: list[int]
    DATABASE_URL: str
    
    # Midasbuy API yoki Tashqi servislar uchun
    MIDASBUY_API_KEY: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings(
    BOT_TOKEN=os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN"),
    ADMIN_IDS=[int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")],
    DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./uc_store.db") # PostgreSQL uchun: postgresql+asyncpg://user:pass@localhost/dbname
)
