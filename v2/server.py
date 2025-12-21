'''MCP server for v2 task management system'''

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine

from v2.config import get_version, get_config
from v2.db import TaskDB
from v2.models import (
    Base,
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    HealthCheckResponse,
    SessionResponse,
    WorkEntryResponse,
    TaskStateType,
    CategoryType,
)

# Get configuration
config = get_config()

# Create an MCP server
mcp = FastMCP("V2 Task Management System", get_version(), dependencies=["pydantic", "sqlalchemy"])

# Create SQLite engine
engine = create_engine(config['db_path'])
Base.metadata.bind = engine

# Initialize TaskDB
task_db = TaskDB(engine)


@mcp.tool()
def health_check() -> HealthCheckResponse:
    '''Check database connection and return basic stats.

    Returns connection status, total task count, and number of active sessions.
    '''
    try:
        # Test database connection using TaskDB count methods (SQL-level)
        total_tasks = task_db.count_tasks()
        active_sessions = task_db.count_active_sessions()

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


@mcp.tool()
def add_task(task_data: TaskCreate) -> TaskResponse:
    '''Add a new task to the system.

    Args:
        task_data: Task creation data including title, category, est_minutes, repeatable, goal_id

    Returns:
        TaskResponse with success status, message, and task_id

    Note:
        - category must be 'grow', 'maintain', or 'sustain' (validated by Pydantic)
        - est_minutes must be > 0 if provided (validated by Pydantic)
        - goal_id will be validated against database if provided
    '''
    try:
        # Only validate goal_id against database (Pydantic handles the rest)
        if task_data.goal_id is not None:
            goal = task_db.get_weekly_goal(task_data.goal_id)
            if goal is None:
                return TaskResponse(
                    success=False,
                    message=f"Goal with ID {task_data.goal_id} not found",
                    task_id=None
                )

        # Create the task
        task = task_db.create_task(
            title=task_data.title,
            category=task_data.category,
            est_minutes=task_data.est_minutes,
            repeatable=task_data.repeatable,
            goal_id=task_data.goal_id
        )

        message = f"Task '{task_data.title}' created successfully"
        if task_data.goal_id is not None:
            message += f" and linked to goal {task_data.goal_id}"

        return TaskResponse(
            success=True,
            message=message,
            task_id=task.id
        )
    except Exception as e:  # pylint: disable=broad-except
        return TaskResponse(
            success=False,
            message=f"Failed to create task: {str(e)}",
            task_id=None
        )


@mcp.tool()
def list_tasks(
    state: TaskStateType | None = None,
    category: CategoryType | None = None,
    goal_id: int | None = None,
    limit: int | None = None
) -> TaskListResponse:
    '''List tasks with optional filtering.

    Args:
        state: Filter by task state ('ready', 'active', 'done', 'archived') - optional
        category: Filter by category ('grow', 'maintain', 'sustain') - optional
        goal_id: Filter by goal ID - optional
        limit: Maximum number of tasks to return (must be > 0) - optional

    Returns:
        TaskListResponse with filtered tasks (ordered by created_at desc)
    '''
    try:
        # Validate limit
        if limit is not None and limit <= 0:
            return TaskListResponse(
                success=False,
                message="limit must be greater than 0",
                tasks=[]
            )

        # Get filtered tasks (with limit applied at SQL level)
        tasks = task_db.get_all_tasks(
            state=state,
            category=category,
            goal_id=goal_id,
            limit=limit
        )

        return TaskListResponse(
            success=True,
            message=f"Found {len(tasks)} tasks",
            tasks=tasks
        )
    except Exception as e:  # pylint: disable=broad-except
        return TaskListResponse(
            success=False,
            message=f"Failed to list tasks: {str(e)}",
            tasks=[]
        )


@mcp.tool()
def start_session(
    available_minutes: int | None = None,
    energy_level: int | None = None,
    focus_area: CategoryType | None = None
) -> SessionResponse:
    '''Start a new work session.

    Args:
        available_minutes: Minutes available for this session (optional)
        energy_level: Current energy level 1-5 (optional)
        focus_area: Focus area ('grow', 'maintain', 'sustain') - optional

    Returns:
        SessionResponse with session_id
    '''
    try:
        # Validate energy_level range
        if energy_level is not None and (energy_level < 1 or energy_level > 5):
            return SessionResponse(
                success=False,
                message="energy_level must be between 1 and 5",
                session_id=None
            )

        # Validate available_minutes
        if available_minutes is not None and available_minutes <= 0:
            return SessionResponse(
                success=False,
                message="available_minutes must be greater than 0",
                session_id=None
            )

        session = task_db.create_session(
            available_minutes=available_minutes,
            energy_level=energy_level,
            focus_area=focus_area
        )

        return SessionResponse(
            success=True,
            message=f"Session {session.id} started",
            session_id=session.id
        )
    except Exception as e:  # pylint: disable=broad-except
        return SessionResponse(
            success=False,
            message=f"Failed to start session: {str(e)}",
            session_id=None
        )


@mcp.tool()
def start_work(session_id: int, task_id: int) -> WorkEntryResponse:
    '''Start work on a task within a session.

    Increments times_accepted and creates a work entry.

    Args:
        session_id: ID of the active session
        task_id: ID of the task to work on

    Returns:
        WorkEntryResponse with work_entry_id
    '''
    try:
        # Validate session exists
        session = task_db.get_session(session_id)
        if session is None:
            return WorkEntryResponse(
                success=False,
                message=f"Session {session_id} not found",
                work_entry_id=None
            )

        # Validate task exists
        task = task_db.get_task(task_id)
        if task is None:
            return WorkEntryResponse(
                success=False,
                message=f"Task {task_id} not found",
                work_entry_id=None
            )

        # Increment accepted stat (suggested happens in rec system)
        task_db.increment_task_stat(task_id, 'accepted')

        # Start work entry
        work_entry = task_db.start_work_entry(session_id, task_id)

        return WorkEntryResponse(
            success=True,
            message=f"Started work on task '{task.title}'",
            work_entry_id=work_entry.id
        )
    except Exception as e:  # pylint: disable=broad-except
        return WorkEntryResponse(
            success=False,
            message=f"Failed to start work: {str(e)}",
            work_entry_id=None
        )
