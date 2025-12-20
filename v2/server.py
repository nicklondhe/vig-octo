'''MCP server for v2 task management system'''

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from sqlalchemy import create_engine

from v2.config import get_version, get_config
from v2.db import TaskDB
from v2.models import Base, SessionModel, TaskModel

# Get configuration
config = get_config()

# Create an MCP server
mcp = FastMCP("V2 Task Management System", get_version(), dependencies=["pydantic", "sqlalchemy"])

# Create SQLite engine
engine = create_engine(config['db_path'])
Base.metadata.bind = engine

# Initialize TaskDB
task_db = TaskDB(engine)


# Response model for health check
class HealthCheckResponse(BaseModel):
    '''Health check response model'''
    success: bool
    message: str
    database_connected: bool
    total_tasks: int
    active_sessions: int
    timestamp: datetime


@mcp.tool()
def health_check() -> HealthCheckResponse:
    '''Check database connection and return basic stats.

    Returns connection status, total task count, and number of active sessions.
    '''
    try:
        # Test database connection by counting tasks
        with task_db.SessionLocal() as session:
            # Count total tasks
            total_tasks = session.query(TaskModel).count()

            # Count active sessions (started but not ended)
            active_sessions = session.query(SessionModel).filter(
                SessionModel.ended_at.is_(None)
            ).count()

        return HealthCheckResponse(
            success=True,
            message="V2 database connection healthy",
            database_connected=True,
            total_tasks=total_tasks,
            active_sessions=active_sessions,
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:  # pylint: disable=broad-except
        return HealthCheckResponse(
            success=False,
            message=f"Database connection failed: {str(e)}",
            database_connected=False,
            total_tasks=0,
            active_sessions=0,
            timestamp=datetime.now(timezone.utc)
        )
