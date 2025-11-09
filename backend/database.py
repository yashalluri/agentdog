"""
MongoDB Database Configuration and Collections Setup for AgentDog
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'agentdog')

# Global client and database
client: Optional[AsyncIOMotorClient] = None
db = None

async def connect_to_mongo():
    """Connect to MongoDB and initialize collections with indexes"""
    global client, db
    
    try:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Test connection
        await client.admin.command('ping')
        logger.info(f"Successfully connected to MongoDB at {MONGO_URL}")
        
        # Initialize collections and indexes
        await init_collections()
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

async def init_collections():
    """Initialize collections with proper indexes"""
    
    # Workflows collection indexes
    workflows_collection = db['workflows']
    
    # Create indexes for workflows
    await workflows_collection.create_index(
        [("run_id", ASCENDING)], 
        unique=True,
        name="run_id_unique"
    )
    await workflows_collection.create_index(
        [("created_at", DESCENDING)],
        name="created_at_desc"
    )
    await workflows_collection.create_index(
        [("final_status", ASCENDING)],
        name="final_status_asc"
    )
    
    logger.info("Workflows collection indexes created")
    
    # Agent runs collection indexes
    agent_runs_collection = db['agent_runs']
    
    # Create indexes for agent_runs
    await agent_runs_collection.create_index(
        [("run_id", ASCENDING)],
        name="run_id_asc"
    )
    await agent_runs_collection.create_index(
        [("parent_step_id", ASCENDING)],
        name="parent_step_id_asc"
    )
    await agent_runs_collection.create_index(
        [("coordination_status", ASCENDING)],
        name="coordination_status_asc"
    )
    await agent_runs_collection.create_index(
        [("created_at", DESCENDING)],
        name="created_at_desc"
    )
    
    logger.info("Agent runs collection indexes created")

async def close_mongo_connection():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")

def get_database():
    """Get database instance"""
    return db

def get_workflows_collection():
    """Get workflows collection"""
    return db['workflows']

def get_agent_runs_collection():
    """Get agent_runs collection"""
    return db['agent_runs']
