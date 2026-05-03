import asyncio
import logging
from pathlib import Path
import aiosqlite
import sys

from src.config import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("clear_db")

async def clear_database():
    """Clear all articles from the database."""
    db_file = Path(DB_PATH)
    
    if not db_file.exists():
        logger.info(f"Database file does not exist at {DB_PATH}.")
        return

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check how many records exist before deleting
            cursor = await db.execute("SELECT COUNT(*) FROM articles")
            count = (await cursor.fetchone())[0]
            
            if count == 0:
                logger.info("Database is already empty.")
                return

            # No confirmation prompt needed for dashboard usage

            # Clear the table
            await db.execute("DELETE FROM articles")
            await db.commit()
            logger.info("Database cleared successfully.")
            
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("============================================================")
    print("  Database Cleanup Utility")
    print("============================================================")
    asyncio.run(clear_database())
