"""MongoDB database connection and utilities"""
from motor.motor_asyncio import AsyncIOMotorClient
import os
from typing import Optional

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "agentdog")

class Database:
    client: Optional[AsyncIOMotorClient] = None
    
    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        if cls.client is None:
            cls.client = AsyncIOMotorClient(MONGO_URL)
        return cls.client
    
    @classmethod
    def get_db(cls):
        return cls.get_client()[DB_NAME]

def get_db():
    return Database.get_db()
