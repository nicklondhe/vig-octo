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
    EndSessionResponse,
    SessionSummary,
    TaskStateType,
    CategoryType,
    WeeklyGoalResponse,
)
from v2.rec_engine import RecEngine
from v2.util import get_week_start

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
        session = task_db.create_session(
            available_minutes=available_minutes,
            energy_level=energy_level,
            focus_area=focus_area
        )

        recs = RecEngine(task_db).recommend(session_id=session.id)

        return SessionResponse(
            success=True,
            message=f"Session {session.id} started",
            session_id=session.id,
            recommendations=recs,
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


@mcp.tool()
def complete_work(
    work_id: int,
    completed: bool = False,
    energy_after: int | None = None,
    want_more_like_this: bool | None = None,
    abandoned_reason: str | None = None
) -> WorkEntryResponse:
    '''Complete work on a task.

    Atomically ends the work entry, updates task state (if completed and not repeatable),
    calculates actual minutes, and updates learning data.

    Args:
        work_id: ID of the work entry to complete
        completed: Whether the task was completed (default: False)
        energy_after: Energy level after work 1-5 (optional)
        want_more_like_this: Whether user wants more tasks like this (optional)
        abandoned_reason: Reason if not completed (optional)

    Returns:
        WorkEntryResponse with success status
    '''
    try:
        completed_entry = task_db.complete_work_entry(
            work_entry_id=work_id,
            completed=completed,
            energy_after=energy_after,
            want_more_like_this=want_more_like_this,
            abandoned_reason=abandoned_reason
        )

        if completed_entry is None:
            return WorkEntryResponse(
                success=False,
                message=f"Work entry {work_id} not found",
                work_entry_id=None
            )

        # Get task for success message
        task = task_db.get_task(completed_entry.task_id)
        task_title = task.title if task else "unknown"

        return WorkEntryResponse(
            success=True,
            message=f"Work completed on task '{task_title}'",
            work_entry_id=work_id
        )
    except Exception as e:  # pylint: disable=broad-except
        return WorkEntryResponse(
            success=False,
            message=f"Failed to complete work: {str(e)}",
            work_entry_id=None
        )


@mcp.tool()
def end_session(
    session_id: int,
    effectiveness: int | None = None,
) -> EndSessionResponse:
    '''End a work session and return a summary of what was accomplished.

    Calculates tasks_completed and category breakdown from work entries
    automatically — no need to pass them manually.

    Args:
        session_id:    ID of the session to end
        effectiveness: Self-rated effectiveness 1-5 (optional)

    Returns:
        EndSessionResponse with session summary (duration, tasks completed,
        category breakdown, effectiveness)
    '''
    try:
        # Compute stats from work entries before closing
        entries = task_db.get_work_entries_by_session(session_id)
        completed_entries = [e for e in entries if e.completed]
        tasks_completed = len(completed_entries)

        categories_completed: dict[str, int] = {}
        if completed_entries:
            entry_tasks = task_db.get_tasks_by_ids([e.task_id for e in completed_entries])
            cat_by_id = {t.id: t.category for t in entry_tasks}
            for entry in completed_entries:
                cat = cat_by_id.get(entry.task_id, 'unknown')
                categories_completed[cat] = categories_completed.get(cat, 0) + 1

        session = task_db.end_session(
            session_id=session_id,
            tasks_completed=tasks_completed,
            effectiveness=effectiveness,
        )

        if session is None:
            return EndSessionResponse(
                success=False,
                message=f"Session {session_id} not found",
            )

        duration = int(
            (session.ended_at - session.started_at).total_seconds() / 60
        ) if session.ended_at else 0

        return EndSessionResponse(
            success=True,
            message=f"Session {session_id} ended — {tasks_completed} task(s) completed",
            summary=SessionSummary(
                session_id=session_id,
                duration_minutes=duration,
                tasks_completed=tasks_completed,
                effectiveness=effectiveness,
                categories_completed=categories_completed,
            ),
        )
    except Exception as e:  # pylint: disable=broad-except
        return EndSessionResponse(
            success=False,
            message=f"Failed to end session: {str(e)}",
        )


@mcp.tool()
def set_weekly_goal(
    title: str,
    description: str | None = None,
    category: CategoryType | None = None,
) -> WeeklyGoalResponse:
    '''Create a goal for the current week.

    Automatically sets week_start to Monday of the current week.

    Args:
        title: Goal title (required)
        description: Optional description of the goal
        category: Optional category ('grow', 'maintain', 'sustain')

    Returns:
        WeeklyGoalResponse with goal_id
    '''
    try:
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            title=title,
            week_start=week_start,
            description=description,
            category=category,
        )
        return WeeklyGoalResponse(
            success=True,
            message=f"Goal '{title}' created for week of {week_start}",
            goal_id=goal.id,
        )
    except Exception as e:  # pylint: disable=broad-except
        return WeeklyGoalResponse(
            success=False,
            message=f"Failed to create weekly goal: {str(e)}",
            goal_id=None,
        )


@mcp.tool()
def link_task_to_goal(task_id: int, goal_id: int) -> TaskResponse:
    '''Link an existing task to a weekly goal.

    Updates the task's goal_id field.

    Args:
        task_id: ID of the task to link
        goal_id: ID of the weekly goal to link to

    Returns:
        TaskResponse with success status
    '''
    try:
        task = task_db.get_task(task_id)
        if task is None:
            return TaskResponse(
                success=False,
                message=f"Task {task_id} not found",
                task_id=None,
            )

        goal = task_db.get_weekly_goal(goal_id)
        if goal is None:
            return TaskResponse(
                success=False,
                message=f"Goal {goal_id} not found",
                task_id=None,
            )

        task_db.update_task(task_id, goal_id=goal_id)

        return TaskResponse(
            success=True,
            message=f"Task '{task.title}' linked to goal '{goal.title}'",
            task_id=task_id,
        )
    except Exception as e:  # pylint: disable=broad-except
        return TaskResponse(
            success=False,
            message=f"Failed to link task to goal: {str(e)}",
            task_id=None,
        )
