"""
PostgreSQL Schema for Conversation Memory
Creates tables for persistent conversation history storage
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql
from src.shared.logging.clean_logger import get_clean_logger
from src.core.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_URL
)

logger = get_clean_logger(__name__)


def create_conversation_tables() -> bool:
    """
    Create PostgreSQL tables for conversation memory.
    
    Tables:
    1. conversation_threads - Thread metadata
    2. conversation_messages - Individual messages
    3. conversation_summaries - LLM summaries (optional)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("📦 Creating PostgreSQL tables for conversation memory...")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(POSTGRES_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Table 1: conversation_threads (metadata)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_threads (
                thread_id VARCHAR(255) PRIMARY KEY,
                cooperative VARCHAR(100) NOT NULL,
                user_id VARCHAR(100) NOT NULL,
                session_id VARCHAR(255),
                
                -- Quick stats (updated on each message)
                message_count INT DEFAULT 0,
                last_message_at TIMESTAMP,
                
                -- Topic tracking
                current_topic TEXT,
                topic_history JSONB DEFAULT '[]'::jsonb,
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Indexes for conversation_threads
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_threads_cooperative_user 
            ON conversation_threads(cooperative, user_id);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_threads_session_id 
            ON conversation_threads(session_id);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_threads_updated_at 
            ON conversation_threads(updated_at);
        """)
        
        # Table 2: conversation_messages (messages)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id SERIAL PRIMARY KEY,
                thread_id VARCHAR(255) NOT NULL REFERENCES conversation_threads(thread_id) ON DELETE CASCADE,
                
                -- Message data
                message_role VARCHAR(20) NOT NULL,
                message_content TEXT NOT NULL,
                message_order INT NOT NULL,
                
                -- Tool usage
                tools_used JSONB DEFAULT '[]'::jsonb,
                
                -- Metadata
                metadata JSONB DEFAULT '{}'::jsonb,
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT NOW(),
                
                -- Ensure unique order per thread
                UNIQUE(thread_id, message_order)
            );
        """)
        
        # Indexes for conversation_messages
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread_id 
            ON conversation_messages(thread_id);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread_order 
            ON conversation_messages(thread_id, message_order);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at 
            ON conversation_messages(created_at);
        """)
        
        # Table 3: conversation_summaries (optional, for LLM summaries)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                thread_id VARCHAR(255) PRIMARY KEY REFERENCES conversation_threads(thread_id) ON DELETE CASCADE,
                summary_text TEXT NOT NULL,
                summarized_messages_count INT,
                summarized_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cursor.close()
        conn.close()
        
        logger.info("✅ PostgreSQL conversation memory tables created successfully!")
        return True
        
    except psycopg2.OperationalError as e:
        if "password authentication failed" in str(e).lower():
            logger.error(f"❌ PostgreSQL authentication failed. Check POSTGRES_USER and POSTGRES_PASSWORD")
        elif "could not connect" in str(e).lower():
            logger.error(f"❌ Could not connect to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}. Is PostgreSQL running?")
        else:
            logger.error(f"❌ PostgreSQL connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to create conversation memory tables: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def create_database_if_not_exists() -> bool:
    """
    Create PostgreSQL database if it doesn't exist.
    
    Connects to 'postgres' database first (default PostgreSQL database),
    then creates the target database if needed.
    
    Returns:
        True if database exists or was created successfully, False otherwise
    """
    try:
        # Build default database URL (connect to 'postgres' database)
        # Handle both cases: POSTGRES_URL from env or built from components
        if '/' in POSTGRES_URL:
            # Extract base URL (everything before the last /)
            default_db_url = POSTGRES_URL.rsplit('/', 1)[0] + '/postgres'
        else:
            # Fallback: build from components
            if POSTGRES_PASSWORD:
                default_db_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
            else:
                default_db_url = f"postgresql://{POSTGRES_USER}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
        
        logger.info(f"🔍 Checking if database '{POSTGRES_DB}' exists...")
        conn = psycopg2.connect(default_db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("""
            SELECT 1 FROM pg_database WHERE datname = %s
        """, (POSTGRES_DB,))
        
        exists = cursor.fetchone()
        
        if not exists:
            logger.info(f"📦 Creating database '{POSTGRES_DB}'...")
            # Create database (must be done outside transaction)
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(POSTGRES_DB)
            ))
            logger.info(f"✅ Database '{POSTGRES_DB}' created successfully!")
        else:
            logger.info(f"✅ Database '{POSTGRES_DB}' already exists")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        if "password authentication failed" in str(e).lower():
            logger.error(f"❌ PostgreSQL authentication failed. Check POSTGRES_USER and POSTGRES_PASSWORD")
        elif "could not connect" in str(e).lower():
            logger.error(f"❌ Could not connect to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}. Is PostgreSQL running?")
        else:
            logger.error(f"❌ PostgreSQL connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to create database: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def setup_postgres_memory() -> bool:
    """
    Complete setup: Create database (if needed) and conversation memory tables.
    
    Returns:
        True if setup successful, False otherwise
    """
    try:
        # Step 1: Create database if needed
        if not create_database_if_not_exists():
            logger.error("❌ Failed to create database")
            return False
        
        # Step 2: Create conversation memory tables
        if not create_conversation_tables():
            logger.error("❌ Failed to create conversation memory tables")
            return False
        
        logger.info("✅ PostgreSQL conversation memory setup complete!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to setup PostgreSQL conversation memory: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


if __name__ == "__main__":
    """Run setup directly"""
    import sys
    
    logger.info("🚀 Starting PostgreSQL conversation memory setup...")
    success = setup_postgres_memory()
    
    if success:
        logger.info("✅ Setup completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Setup failed!")
        sys.exit(1)

