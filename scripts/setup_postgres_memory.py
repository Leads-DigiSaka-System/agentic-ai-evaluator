"""
PostgreSQL Memory Setup Script
Run this to set up the PostgreSQL database and tables for conversation memory.

Usage:
    python setup_postgres_memory.py
"""
import sys
from src.infrastructure.postgres.postgres_memory_schema import setup_postgres_memory
from src.shared.logging.clean_logger import get_clean_logger

logger = get_clean_logger(__name__)


def main():
    """Main setup function"""
    logger.info("🚀 Starting PostgreSQL conversation memory setup...")
    logger.info("=" * 60)
    
    success = setup_postgres_memory()
    
    logger.info("=" * 60)
    if success:
        logger.info("✅ Setup completed successfully!")
        logger.info("💡 You can now use PostgresConversationMemory in your chat agent")
        sys.exit(0)
    else:
        logger.error("❌ Setup failed!")
        logger.error("💡 Please check:")
        logger.error("   1. PostgreSQL is running")
        logger.error("   2. POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD are set correctly in .env")
        logger.error("   3. User has permission to create databases and tables")
        sys.exit(1)



