from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    SECRET_KEY =  os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

settings = Settings()
