"""
PostgreSQL Connection Pool Manager

Manages a connection pool for PostgreSQL to prevent connection exhaustion.
Uses psycopg2.pool.SimpleConnectionPool for thread-safe connection management.
"""
from typing import Optional
import psycopg2
from psycopg2 import pool
from src.shared.logging.clean_logger import get_clean_logger
from src.core.config import POSTGRES_URL, POSTGRES_POOL_MIN, POSTGRES_POOL_MAX

logger = get_clean_logger(__name__)

# Global connection pool (initialized on first use)
_postgres_pool: Optional[pool.SimpleConnectionPool] = None


def get_postgres_pool() -> Optional[pool.SimpleConnectionPool]:
    """
    Get or create PostgreSQL connection pool.
    
    Uses singleton pattern - pool is created once and reused.
    Thread-safe for concurrent requests.
    
    Returns:
        SimpleConnectionPool instance or None if initialization failed
    """
    global _postgres_pool
    
    # Return existing pool if already initialized
    if _postgres_pool is not None:
        return _postgres_pool
    
    # Initialize pool if not exists
    if not POSTGRES_URL:
        logger.warning("⚠️ POSTGRES_URL not configured, connection pool not initialized")
        return None
    
    try:
        logger.info(f"🔌 Initializing PostgreSQL connection pool (min={POSTGRES_POOL_MIN}, max={POSTGRES_POOL_MAX})...")
        
        _postgres_pool = pool.SimpleConnectionPool(
            minconn=POSTGRES_POOL_MIN,
            maxconn=POSTGRES_POOL_MAX,
            dsn=POSTGRES_URL
        )
        
        if _postgres_pool:
            logger.info(f"✅ PostgreSQL connection pool initialized successfully")
            return _postgres_pool
        else:
            logger.error("❌ Failed to create PostgreSQL connection pool")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize PostgreSQL connection pool: {e}")
        return None


def get_postgres_connection():
    """
    Get a connection from the pool.
    
    Returns:
        psycopg2 connection object or None if pool unavailable
        
    Usage:
        conn = get_postgres_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # ... use connection ...
                conn.commit()
            finally:
                return_connection(conn)
    """
    pool_instance = get_postgres_pool()
    if not pool_instance:
        return None
    
    try:
        return pool_instance.getconn()
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        return None


def return_connection(conn):
    """
    Return a connection to the pool.
    
    Args:
        conn: psycopg2 connection object to return to pool
        
    Always call this after using a connection to prevent pool exhaustion.
    """
    pool_instance = get_postgres_pool()
    if not pool_instance or not conn:
        return
    
    try:
        pool_instance.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to return connection to pool: {e}")


def close_pool():
    """
    Close all connections in the pool.
    
    Call this on application shutdown to properly close all connections.
    """
    global _postgres_pool
    
    if _postgres_pool:
        try:
            _postgres_pool.closeall()
            logger.info("✅ PostgreSQL connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            _postgres_pool = None

