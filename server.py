'''MCP server for task management system'''
#pylint: disable=too-many-lines
# Standard library imports
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from functools import wraps

# Third-party imports
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from sqlalchemy import create_engine, case
from sqlalchemy.orm import sessionmaker

# Local application imports
from config import get_version, get_config
from models import (
    TaskModel, WeeklyGoalModel, GoalTaskModel,
    GoalProgressHistoryModel, WorkSessionModel,
    RecommendationModel, WorkLogModel, Base,
    TaskSummaryModel
)

# Get configuration
config = get_config()

# Create an MCP server
mcp = FastMCP("Task Management System", get_version(), dependencies=["pydantic", "sqlalchemy"])

# Create SQLite engine and session
engine = create_engine(config['db_path'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)


# Response model for task listing
class TaskList(BaseModel):
    '''TaskList is a model for the task list response'''
    tasks: List[dict[str, object]]

# Response model for weekly goals listing
class WeeklyGoalList(BaseModel):
    '''WeeklyGoalList is a model for the weekly goals list response'''
    goals: List[dict[str, object]]

# Request model for adding a task
class AddTaskRequest(BaseModel):
    """Model for task creation request"""
    name: str
    complexity: str = 'simple'
    type: str = 'Direct'
    due_date: Optional[str] = None
    priority: str = 'low'
    repeatable: bool = False
    # Goal-related attributes
    goal_id: Optional[int] = None
    day_number: Optional[int] = None
    percent_split: Optional[float] = None

# Request model for updating a task
class UpdateTaskRequest(BaseModel):
    """Model for task update request with all fields optional"""
    name: Optional[str] = None
    complexity: Optional[str] = None
    type: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    repeatable: Optional[bool] = None
    status: Optional[str] = None

# Response model for task operations
class TaskResponse(BaseModel):
    """Model for task operation response"""
    success: bool
    message: str
    task_id: int = None

# Request model for adding a weekly goal
class AddWeeklyGoalRequest(BaseModel):
    """Model for weekly goal creation request"""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = 'pending'

# Response model for weekly goal operations
class WeeklyGoalResponse(BaseModel):
    """Model for weekly goal operation response"""
    success: bool
    message: str
    goal_id: Optional[int] = None

# Request model for updating goal progress
class UpdateGoalProgressRequest(BaseModel):
    """Model for updating a goal's progress"""
    task_id: int
    goal_id: int
    completion_pct: float = 100.0
    notes: Optional[str] = None

# Response model for goal progress operations
class GoalProgressResponse(BaseModel):
    """Model for goal progress operation response"""
    success: bool
    message: str
    goal_id: Optional[int] = None
    current_completion_pct: Optional[float] = None

# Request model for saving recommendations
class SaveRecommendationsRequest(BaseModel):
    """Model for saving task recommendations for a session"""
    session_id: int
    task_ids: List[int]
    rec_type: str = "focus_tasks"  # "focus_tasks", "break_tasks", etc.
    strategy: Optional[str] = None  # "high_priority_first", "mix_complexity", etc.

# Request model for updating recommendation status
class UpdateRecommendationStatusRequest(BaseModel):
    """Model for updating the status of a recommendation"""
    recommendation_id: int
    status: str  # "pending", "accepted", "rejected"
    rejected_reason: Optional[str] = None  # Required if status is "rejected"

# Request model for starting a work log
class StartWorkLogRequest(BaseModel):
    """Model for starting a work log entry"""
    session_id: int
    task_id: int
    recommendation_id: Optional[int] = None

# Request model for ending a work log
class EndWorkLogRequest(BaseModel):
    """Model for ending a work log entry with completion percentage"""
    work_log_id: int
    completion_pct: float = 0.0  # 0.0 to 100.0

# Request model for ending a session
class EndSessionRequest(BaseModel):
    """Model for ending a work session with effectiveness rating"""
    session_id: int
    completion_pct: float = 0.0  # 0.0 to 100.0
    effectiveness_rating: Optional[int] = None  # 1-5 rating
    notes: Optional[str] = None

# Request model for getting velocity stats
class VelocityStatsRequest(BaseModel):
    """Model for getting velocity stats for a given time frame"""
    days: int = 7  # Default to last 7 days
    task_type: Optional[str] = None  # Filter by task type

# Response model for recommendation operations
class RecommendationResponse(BaseModel):
    """Model for recommendation operation response"""
    success: bool
    message: str
    session_id: int
    recommendations: List[dict[str, object]] = []

# Response model for work log operations
class WorkLogResponse(BaseModel):
    """Model for work log operation response"""
    success: bool
    message: str
    session_id: int
    work_log: Optional[dict[str, object]] = None

# Response model for velocity stats
class VelocityStatsResponse(BaseModel):
    """Model for velocity stats response"""
    success: bool
    message: str
    time_frame_days: int
    stats: dict[str, object]

# Response model for getting goal progress
class GoalProgressInfoResponse(BaseModel):
    """Model for goal progress information response"""
    success: bool
    goal_id: int
    title: Optional[str] = None
    current_completion_pct: float
    history: List[dict[str, object]] = []

# Request model for starting a work session
class StartSessionRequest(BaseModel):
    """Model for starting a new work session"""
    query: str
    context: Optional[str] = None
    planned_duration: Optional[int] = None  # minutes

# Response model for session operations
class SessionResponse(BaseModel):
    """Model for session operation response"""
    success: bool
    message: str
    session_id: Optional[int] = None

# Response model for session listing
class SessionListResponse(BaseModel):
    """Model for session list response"""
    sessions: List[dict[str, object]]

# Response model for session details
class SessionDetailsResponse(BaseModel):
    """Model for detailed session information including tasks and recommendations"""
    success: bool
    session: Optional[dict[str, object]] = None
    tasks: List[dict[str, object]] = []
    recommendations: List[dict[str, object]] = []
    work_logs: List[dict[str, object]] = []

# Request model for task matrix view
class TaskMatrixResponse(BaseModel):
    """Model for task matrix view response with tasks organized by priority and complexity"""
    low: dict[str, List[dict[str, object]]]
    medium: dict[str, List[dict[str, object]]]
    high: dict[str, List[dict[str, object]]]

# Helper functions for goal-related operations

def _ensure_timezone_aware(dt: datetime) -> datetime:
    """Helper function to ensure a datetime is timezone-aware (UTC if None).
    
    Args:
        dt: datetime object that may or may not be timezone-aware
        
    Returns:
        datetime: timezone-aware datetime object
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _calculate_time_diff_minutes(start_dt: datetime, end_dt: datetime) -> float:
    """Helper function to calculate time difference in minutes between two datetimes.
    
    Handles timezone normalization automatically.
    
    Args:
        start_dt: Start datetime
        end_dt: End datetime
        
    Returns:
        float: Time difference in minutes
    """
    start_aware = _ensure_timezone_aware(start_dt)
    end_aware = _ensure_timezone_aware(end_dt)
    return (end_aware - start_aware).total_seconds() / 60


def _get_entity_or_error(session, model_class, entity_id, entity_name):
    """Helper function to get an entity by ID or return error info.
    
    Args:
        session: SQLAlchemy session
        model_class: The model class to query
        entity_id: ID of the entity to find
        entity_name: Human-readable name for error messages
        
    Returns:
        tuple: (entity, error_message) - entity is None if not found, error_message is None if found
    """
    entity = session.query(model_class).filter(model_class.id == entity_id).first()
    if not entity:
        return None, f"{entity_name} with ID {entity_id} not found"
    return entity, None


def with_db_session(func):
    """Decorator to handle database session management with proper error handling.
    
    The decorated function should accept 'db_session' as its first parameter.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        db_session = DBSession()
        try:
            return func(db_session, *args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            db_session.rollback()
            # Re-raise the exception to be handled by the calling function
            raise e
        finally:
            db_session.close()
    return wrapper


def _get_task_goal(session, task_id):
    """Helper method to get the goal associated with a task.

    Args:
        session: SQLAlchemy session
        task_id: ID of the task

    Returns:
        GoalTaskModel: The goal task relationship if found, else None
    """
    return session.query(GoalTaskModel).filter(
        GoalTaskModel.task_id == task_id
    ).first()


def _update_goal_progress(session, task_id, goal_id,
                          task_completion_pct=100.0, notes=None):
    """Helper method to update goal progress when a task is completed.

    Args:
        session: SQLAlchemy session
        task_id: ID of the task that was completed
        goal_id: ID of the goal to update
        task_completion_pct: Percentage completion of this specific task (0.0-100.0)
        notes: Optional custom notes for the progress history entry

    Returns:
        float: Updated completion percentage of the goal
    """
    try:
        # Get the task
        task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return None

        # Get the goal task relationship
        goal_task = session.query(GoalTaskModel).filter(
            GoalTaskModel.task_id == task_id,
            GoalTaskModel.goal_id == goal_id
        ).first()

        # Determine how much this task contributes to the goal
        task_contribution = 0.0
        if goal_task and goal_task.percent_split is not None:
            # Use the defined percent split
            task_contribution = goal_task.percent_split
        else:
            # Calculate based on equal distribution
            total_tasks = session.query(GoalTaskModel).filter(
                GoalTaskModel.goal_id == goal_id
            ).count()

            if total_tasks > 0:
                task_contribution = 100.0 / total_tasks

        # Get the most recent progress entry for this goal
        latest_progress = session.query(GoalProgressHistoryModel).filter(
            GoalProgressHistoryModel.goal_id == goal_id
        ).order_by(
            GoalProgressHistoryModel.timestamp.desc()
        ).first()

        # Start with current completion percentage or 0 if no previous entries
        current_completion = latest_progress.completion_pct if latest_progress else 0.0

        # Calculate the actual contribution based on task completion percentage
        # If task is 50% complete and represents 20% of the goal, it contributes 10%
        actual_contribution = task_contribution * (task_completion_pct / 100.0)

        # Add this task's actual contribution to the current completion
        new_completion = current_completion + actual_contribution

        # Cap at 100%
        new_completion = min(100.0, new_completion)

        # Record progress history
        if notes is None:
            notes = (f"Task '{task.name}' at {task_completion_pct:.1f}% completion "
                    f"added {actual_contribution:.1f}% to goal "
                    f"(task weight: {task_contribution:.1f}%)")

        progress_entry = GoalProgressHistoryModel(
            goal_id=goal_id,
            timestamp=datetime.now(timezone.utc),
            notes=notes,
            completion_pct=new_completion
        )
        session.add(progress_entry)

        # Update goal's status if complete (>= 99.9% for float precision)
        if new_completion >= 99.9:
            goal = session.query(WeeklyGoalModel).filter(
                WeeklyGoalModel.id == goal_id
            ).first()
            if goal:
                goal.status = "completed"
                goal.updated_ts = datetime.now(timezone.utc)

        return new_completion

    except Exception as e: #pylint: disable=broad-except
        print(f"Error updating goal progress: {str(e)}")
        return None


def _serialize_task(task: TaskModel):
    """Helper method to serialize a TaskModel into a dictionary.

    Args:
        task (TaskModel): The TaskModel instance to serialize

    Returns:
        dict: A dictionary representation of the task
    """
    return {
        'id': task.id,
        'name': task.name,
        'complexity': task.complexity,
        'type': task.type,
        'due_date': task.due_date,
        'priority': task.priority,
        'repeatable': task.repeatable,
        'status': task.status,
        'created': task.created_ts,
        'updated': task.updated_ts,
        'context': config['env_type']
    }


def _serialize_session(session: WorkSessionModel):
    """Helper method to serialize a WorkSessionModel into a dictionary.

    Args:
        session (WorkSessionModel): The WorkSessionModel instance to serialize

    Returns:
        dict: A dictionary representation of the session
    """
    return {
        'id': session.id,
        'start_ts': session.start_ts,
        'end_ts': session.end_ts,
        'planned_duration': session.planned_duration,
        'context': session.context,
        'query': session.query,
        'completion_pct': session.completion_pct,
        'effectiveness_rating': session.effectiveness_rating,
        'notes': session.notes
    }


def _serialize_recommendation(recommendation):
    """Helper method to serialize a RecommendationModel into a dictionary.

    Args:
        recommendation: The RecommendationModel instance to serialize

    Returns:
        dict: A dictionary representation of the recommendation
    """
    return {
        'id': recommendation.id,
        'session_id': recommendation.session_id,
        'task_id': recommendation.task_id,
        'rec_type': recommendation.rec_type,
        'strategy': recommendation.strategy,
        'status': recommendation.status,
        'rejected_reason': recommendation.rejected_reason,
        'rec_ts': recommendation.rec_ts,
        'task_name': recommendation.task.name if recommendation.task else None
    }


def _serialize_work_log(work_log):
    """Helper method to serialize a WorkLogModel into a dictionary.

    Args:
        work_log: The WorkLogModel instance to serialize

    Returns:
        dict: A dictionary representation of the work log
    """
    return {
        'id': work_log.id,
        'session_id': work_log.session_id,
        'task_id': work_log.task_id,
        'rec_id': work_log.rec_id,
        'start_ts': work_log.start_ts,
        'end_ts': work_log.end_ts,
        'completion_pct': work_log.completion_pct,
        'task_name': work_log.task.name if work_log.task else None
    }


# Add a tool to list tasks with 'to-do' status
@mcp.tool()
def list_pending_tasks() -> TaskList:
    """List all tasks with 'pending' status"""
    session = DBSession()
    try:
        # Query tasks with status 'to-do' (stored as 'pending' in database)
        tasks = (session.query(TaskModel)
                 .filter(TaskModel.status == 'pending')
                 .all())

        # Convert to dictionary format for response
        task_list = [
            _serialize_task(task)
            for task in tasks
        ]

        return TaskList(tasks=task_list)
    finally:
        session.close()

@mcp.tool()
def add_task(task_data: AddTaskRequest) -> TaskResponse:
    """Add a new task to the system with optional goal association"""
    session = DBSession()
    try:
        # Create new task
        new_task = TaskModel(
            name=task_data.name,
            complexity=task_data.complexity,
            type=task_data.type,
            due_date=task_data.due_date,
            priority=task_data.priority,
            repeatable=task_data.repeatable,
            status="pending",  # Default status for new tasks
            created_ts=datetime.now(timezone.utc),
            updated_ts=datetime.now(timezone.utc)
        )
        session.add(new_task)
        session.flush()  # Flush to get the new task ID

        # Check if goal-related attributes are provided
        if task_data.goal_id is not None:
            # Verify that the goal exists
            goal = session.query(WeeklyGoalModel).filter(
                WeeklyGoalModel.id == task_data.goal_id
            ).first()

            if not goal:
                session.rollback()
                return TaskResponse(
                    success=False,
                    message=f"Goal with ID {task_data.goal_id} not found",
                    task_id=None
                )

            # Create goal task relationship
            goal_task = GoalTaskModel(
                task_id=new_task.id,
                goal_id=task_data.goal_id,
                day_number=task_data.day_number,
                percent_split=task_data.percent_split,
                created_ts=datetime.now(timezone.utc),
                updated_ts=datetime.now(timezone.utc)
            )
            session.add(goal_task)

        # Commit the transaction
        session.commit()

        # Success message varies based on goal attachment
        success_message = f"Task '{task_data.name}' added successfully"
        if task_data.goal_id is not None:
            success_message += f" and attached to goal ID {task_data.goal_id}"

        return TaskResponse(
            success=True,
            message=success_message,
            task_id=new_task.id
        )
    except Exception as e:  # pylint: disable=broad-except
        session.rollback()
        return TaskResponse(success=False, message=f"Failed to add task: {str(e)}")
    finally:
        session.close()

@mcp.tool()
def mark_task_status(task_id: int, status: str = "done") -> TaskResponse:
    """Mark a task with a specific status by its ID

    Status can be 'done' or 'pending' or any other valid status.
    """
    # Create update request with only status field
    task_data = UpdateTaskRequest(status=status)

    # Use the update_task functionality internally
    return update_task(task_id, task_data)


@mcp.tool()
def list_completed_repeatable_tasks() -> TaskList:
    """List all completed tasks that are marked as repeatable"""
    session = DBSession()
    try:
        # Query tasks with status 'done' and repeatable=True
        tasks = (
            session.query(TaskModel)
            .filter(TaskModel.status == 'done')
            .filter(TaskModel.repeatable.is_(True))
            .all()
        )

        # Convert to dictionary format for response
        task_list = [
            _serialize_task(task)
            for task in tasks
        ]

        return TaskList(tasks=task_list)
    finally:
        session.close()


@mcp.tool()
def update_task(task_id: int, task_data: UpdateTaskRequest) -> TaskResponse:
    """Update an existing task with provided fields

    If task is marked as 'done' and is attached to a goal, updates goal progress.
    """
    session = DBSession()
    try:
        task, error_msg = _get_entity_or_error(session, TaskModel, task_id, "Task")
        if error_msg:
            return TaskResponse(
                success=False,
                message=error_msg
            )

        # Store original status to detect changes
        original_status = task.status

        # Convert the request data to a dictionary, excluding unset fields
        # This ensures we only modify fields that were explicitly provided
        updates = task_data.model_dump(exclude_unset=True)
        
        # For due_date specifically, we need to check if it was explicitly set to None
        # since exclude_unset=True excludes None values, but we want to allow explicit clearing
        if hasattr(task_data, '__pydantic_fields_set__') and 'due_date' in task_data.__pydantic_fields_set__:
            # due_date was explicitly set (either to a value or explicitly to None)
            # Get the actual value including None
            updates['due_date'] = getattr(task_data, 'due_date')

        # Apply the updates to the task
        for key, value in updates.items():
            setattr(task, key, value)

        # Always update the updated_ts timestamp when a task is modified
        task.updated_ts = datetime.now(timezone.utc)

        # Check if task was marked as done (status changed to "done")
        is_newly_completed = original_status != "done" and task.status == "done"

        # If task is newly marked as done, check if it's attached to a goal
        completion_message = ""
        if is_newly_completed:
            goal_task = _get_task_goal(session, task_id)
            if goal_task:
                # Update goal progress - task is newly completed so it's 100%
                new_completion = _update_goal_progress(
                    session, task_id, goal_task.goal_id, task_completion_pct=100.0
                )
                if new_completion is not None:
                    completion_message = (
                        f" Goal {goal_task.goal_id} progress "
                        f"updated to {new_completion:.1f}%"
                    )

        session.commit()
        msg = f"Task with ID {task_id} updated successfully.{completion_message}"
        return TaskResponse(
            success=True,
            message=msg,
            task_id=task.id
        )
    except Exception as e:  # pylint: disable=broad-except
        session.rollback()
        return TaskResponse(success=False, message=f"Failed to update task: {str(e)}")
    finally:
        session.close()

@mcp.tool()
def get_task_matrix_view(limit: int = 10, sort_by: str = "created_desc") -> TaskMatrixResponse:
    """Get tasks organized in a 3x3 matrix by priority and complexity.
    This function retrieves tasks with 'pending' status and organizes them into a matrix
    based on their priority and complexity. The matrix has three priority levels (low, medium, high)
    and three complexity levels (low, medium, high).

    Args:
        limit: Maximum number of tasks to return
        sort_by: How to sort tasks
            - 'created_desc': Newest first (default)
            - 'created_asc': Oldest first
            - 'priority_desc': High priority first
            - 'updated_desc': Recently touched first

    Returns:
        A dictionary with tasks organized by priority and complexity
    """
    session = DBSession()
    try:
        # Define valid sort orders
        sort_orders = {
            "created_desc": TaskModel.created_ts.desc(),
            "created_asc": TaskModel.created_ts.asc(),
            "priority_desc": TaskModel.priority.desc(),
            "updated_desc": TaskModel.updated_ts.desc()
        }

        # Use default sort if invalid sort_by is provided
        sort_order = sort_orders.get(sort_by, sort_orders["created_desc"])

        # Query pending tasks with the specified sort order
        tasks_query = session.query(TaskModel).filter(TaskModel.status == 'pending')
        
        # Handle priority sorting with custom order
        if sort_by == "priority_desc":
            # Use CASE statement to sort by priority level (high=3, medium=2, low=1)
            priority_order = case(
                (TaskModel.priority == 'high', 3),
                (TaskModel.priority == 'medium', 2),
                (TaskModel.priority == 'low', 1),
                else_=1
            ).desc()
            tasks = tasks_query.order_by(priority_order).limit(limit).all()
        else:
            tasks = tasks_query.order_by(sort_order).limit(limit).all()

        # Use nested defaultdict to automatically create bins
        matrix = defaultdict(lambda: defaultdict(list))

        # Group tasks by priority and complexity
        for task in tasks:
            matrix[task.priority][task.complexity].append(_serialize_task(task))

        # Ensure all nine cells exist by initializing empty lists for missing cells
        for priority in ["low", "medium", "high"]:
            for complexity in ["low", "medium", "high"]:
                if complexity not in matrix[priority]:
                    matrix[priority][complexity] = []

        # Convert defaultdict to regular dict for serialization
        return TaskMatrixResponse(
            low=dict(matrix["low"]),
            medium=dict(matrix["medium"]),
            high=dict(matrix["high"])
        )
    finally:
        session.close()


@mcp.tool()
def get_goal_progress(goal_id: int) -> GoalProgressInfoResponse:
    """Get current progress and history for a goal."""
    session = DBSession()
    try:
        # Verify the goal exists
        goal = session.query(WeeklyGoalModel).filter(
            WeeklyGoalModel.id == goal_id
        ).first()

        if not goal:
            return GoalProgressInfoResponse(
                success=False,
                goal_id=goal_id,
                current_completion_pct=0.0,
                title=None,
                history=[]
            )

        # Get progress history entries
        history_entries = session.query(GoalProgressHistoryModel).filter(
            GoalProgressHistoryModel.goal_id == goal_id
        ).order_by(
            GoalProgressHistoryModel.timestamp.desc()
        ).all()

        # Format history entries as a list of dictionaries
        history = [
            {
                'timestamp': entry.timestamp,
                'notes': entry.notes,
                'completion_pct': entry.completion_pct
            }
            for entry in history_entries
        ]

        # Get current completion percentage from the most recent entry
        current_completion = history_entries[0].completion_pct if history_entries else 0.0

        return GoalProgressInfoResponse(
            success=True,
            goal_id=goal_id,
            title=goal.title,
            current_completion_pct=current_completion,
            history=history
        )
    except Exception: # pylint: disable=broad-except
        return GoalProgressInfoResponse(
            success=False,
            goal_id=goal_id,
            current_completion_pct=0.0,
            title=None,
            history=[]
        )
    finally:
        session.close()


@mcp.tool()
def update_goal_progress(progress_data: UpdateGoalProgressRequest) -> GoalProgressResponse:
    """Update a goal's progress based on task completion."""
    session = DBSession()
    try:
        # Verify task and goal exist
        task = session.query(TaskModel).filter(
            TaskModel.id == progress_data.task_id
        ).first()
        if not task:
            return GoalProgressResponse(
                success=False,
                message=f"Task with ID {progress_data.task_id} not found",
                goal_id=progress_data.goal_id
            )

        goal = session.query(WeeklyGoalModel).filter(
            WeeklyGoalModel.id == progress_data.goal_id
        ).first()
        if not goal:
            return GoalProgressResponse(
                success=False,
                message=f"Goal with ID {progress_data.goal_id} not found",
                goal_id=progress_data.goal_id
            )

        # Use the helper method with notes
        new_completion = _update_goal_progress(
            session,
            progress_data.task_id,
            progress_data.goal_id,
            progress_data.completion_pct,
            progress_data.notes
        )

        session.commit()

        return GoalProgressResponse(
            success=new_completion is not None,
            message=f"Goal progress updated to {new_completion:.1f}%" if new_completion is not None
                   else "Failed to update goal progress",
            goal_id=progress_data.goal_id,
            current_completion_pct=new_completion
        )
    except Exception as e: # pylint: disable=broad-except
        session.rollback()
        return GoalProgressResponse(
            success=False,
            message=f"Error updating goal progress: {str(e)}",
            goal_id=progress_data.goal_id
        )
    finally:
        session.close()


@mcp.tool()
def create_weekly_goal(goal_data: AddWeeklyGoalRequest) -> WeeklyGoalResponse:
    """Add a new weekly goal to the system"""
    session = DBSession()
    try:
        # Set default dates if not provided
        now = datetime.now(timezone.utc)
        start_date = goal_data.start_date or now

        new_goal = WeeklyGoalModel(
            title=goal_data.title,
            description=goal_data.description,
            category=goal_data.category,
            start_date=start_date,
            end_date=goal_data.end_date,
            status=goal_data.status,
            created_ts=now,
            updated_ts=now
        )

        session.add(new_goal)
        session.commit()

        return WeeklyGoalResponse(
            success=True,
            message=f"Weekly goal '{goal_data.title}' added successfully",
            goal_id=new_goal.id
        )
    except Exception as e:  # pylint: disable=broad-except
        session.rollback()
        return WeeklyGoalResponse(success=False, message=f"Failed to add weekly goal: {str(e)}")
    finally:
        session.close()


@mcp.tool()
def get_session_details(session_id: int) -> SessionDetailsResponse:
    """Get detailed information about a specific work session including tasks and recommendations

    Args:
        session_id: The ID of the session to retrieve

    Returns:
        Detailed session information including associated tasks and recommendations
    """
    db_session = DBSession()
    try:
        # Get the session
        session = db_session.query(WorkSessionModel).filter(
            WorkSessionModel.id == session_id
        ).first()

        if not session:
            return SessionDetailsResponse(
                success=False,
                session=None,
                tasks=[],
                recommendations=[],
                work_logs=[]
            )

        # Get recommendations for this session
        recommendations = db_session.query(RecommendationModel).filter(
            RecommendationModel.session_id == session_id
        ).all()

        # Get work logs for this session
        work_logs = db_session.query(WorkLogModel).filter(
            WorkLogModel.session_id == session_id
        ).all()

        # Get the unique task IDs from both recommendations and work logs
        task_ids = set()
        for rec in recommendations:
            task_ids.add(rec.task_id)
        for log in work_logs:
            task_ids.add(log.task_id)

        # Get the tasks
        tasks = db_session.query(TaskModel).filter(
            TaskModel.id.in_(list(task_ids))
        ).all() if task_ids else []

        # Serialize the data
        return SessionDetailsResponse(
            success=True,
            session=_serialize_session(session),
            tasks=[_serialize_task(task) for task in tasks],
            recommendations=[_serialize_recommendation(rec) for rec in recommendations],
            work_logs=[_serialize_work_log(log) for log in work_logs]
        )
    except Exception as e:  # pylint: disable=broad-except
        # Log the error
        print(f"Error getting session details: {str(e)}")
        return SessionDetailsResponse(
            success=False,
            session=None,
            tasks=[],
            recommendations=[],
            work_logs=[]
        )
    finally:
        db_session.close()


@mcp.tool()
def get_sessions(limit: int = 10, days: Optional[int] = None) -> SessionListResponse:
    """Get a list of work sessions with optional time frame filter

    Args:
        limit: Maximum number of sessions to return (default: 10)
        days: Number of days to look back (optional, default: all sessions)

    Returns:
        A list of session objects
    """
    db_session = DBSession()
    try:
        # Start with base query
        query = db_session.query(WorkSessionModel)

        # Apply time frame filter if days parameter is provided
        if days is not None:
            # Calculate the date N days ago
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(WorkSessionModel.start_ts >= cutoff_date)

        # Get most recent sessions first
        sessions = query.order_by(WorkSessionModel.start_ts.desc()).limit(limit).all()

        # Convert to dictionary format for response
        session_list = [_serialize_session(session) for session in sessions]

        return SessionListResponse(sessions=session_list)
    except Exception as e:  # pylint: disable=broad-except
        # Log the error but return an empty list rather than failing
        print(f"Error fetching sessions: {str(e)}")
        return SessionListResponse(sessions=[])
    finally:
        db_session.close()


@mcp.tool()
def get_velocity_stats(stats_data: VelocityStatsRequest) -> VelocityStatsResponse:
    """Get productivity and velocity stats for a given time frame

    Args:
        stats_data: Data containing days (time frame) and optional task_type filter

    Returns:
        A response with velocity statistics for the specified time frame
    """
    db_session = DBSession()
    try:
        # Calculate the date for the start of the time frame
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=stats_data.days)

        # Build base query for completed work logs
        work_logs_query = db_session.query(WorkLogModel).filter(
            WorkLogModel.start_ts >= cutoff_date,
            WorkLogModel.end_ts.isnot(None)
        )

        # Build base query for sessions
        sessions_query = db_session.query(WorkSessionModel).filter(
            WorkSessionModel.start_ts >= cutoff_date,
            WorkSessionModel.end_ts.isnot(None)
        )

        # Apply task type filter if specified
        if stats_data.task_type:
            # Get task IDs with the specified type
            task_ids = [
                task.id for task in
                db_session.query(TaskModel.id).filter(
                    TaskModel.type == stats_data.task_type
                ).all()
            ]

            # Filter work logs by these task IDs
            work_logs_query = work_logs_query.filter(
                WorkLogModel.task_id.in_(task_ids)
            )

        # Execute the queries
        work_logs = work_logs_query.all()
        sessions = sessions_query.all()

        # Calculate stats

        # 1. Total time spent on tasks in minutes
        total_time_minutes = 0
        for log in work_logs:
            if log.end_ts and log.start_ts:
                time_diff = _calculate_time_diff_minutes(log.start_ts, log.end_ts)
                total_time_minutes += time_diff

        # 2. Average completion percentage of tasks
        avg_completion = 0
        if work_logs:
            completion_sum = sum(log.completion_pct or 0 for log in work_logs)
            avg_completion = completion_sum / len(work_logs)

        # 3. Number of completed tasks
        completed_tasks = len(set(log.task_id for log in work_logs
                               if log.completion_pct and log.completion_pct >= 90))

        # 4. Average task completion time in minutes
        avg_task_time = 0
        if completed_tasks > 0:
            avg_task_time = total_time_minutes / completed_tasks

        # 5. Average session effectiveness rating
        avg_effectiveness = 0
        rated_sessions = [s for s in sessions if s.effectiveness_rating is not None]
        if rated_sessions:
            avg_effectiveness = sum(s.effectiveness_rating
                                    for s in rated_sessions) / len(rated_sessions)

        # 6. Productivity by day of week
        weekday_productivity = {i: 0 for i in range(7)}  # 0 = Monday, 6 = Sunday
        for log in work_logs:
            if log.end_ts and log.start_ts:
                start_ts_aware = _ensure_timezone_aware(log.start_ts)
                weekday = start_ts_aware.weekday()
                time_diff = _calculate_time_diff_minutes(log.start_ts, log.end_ts)
                weekday_productivity[weekday] += time_diff

        # 7. Total number of sessions
        total_sessions = len(sessions)

        # Compile stats
        stats = {
            "total_time_minutes": int(total_time_minutes),
            "avg_completion_pct": round(avg_completion, 2),
            "completed_tasks": completed_tasks,
            "avg_task_time_minutes": round(avg_task_time, 2),
            "avg_effectiveness_rating": round(avg_effectiveness, 2),
            "weekday_productivity": weekday_productivity,
            "total_sessions": total_sessions,
            "tasks_per_day": round(completed_tasks /
                                    stats_data.days, 2) if stats_data.days > 0 else 0,
            "minutes_per_day": round(total_time_minutes /
                                     stats_data.days, 2) if stats_data.days > 0 else 0
        }

        return VelocityStatsResponse(
            success=True,
            message=f"Velocity stats for the last {stats_data.days} days",
            time_frame_days=stats_data.days,
            stats=stats
        )
    except Exception as e:  # pylint: disable=broad-except
        return VelocityStatsResponse(
            success=False,
            message=f"Failed to get velocity stats: {str(e)}",
            time_frame_days=stats_data.days,
            stats={}
        )
    finally:
        db_session.close()


@mcp.tool()
def end_session(end_data: EndSessionRequest) -> SessionResponse:
    """End a work session with completion percentage and effectiveness rating

    Args:
        end_data: Data containing session_id, completion_pct, effectiveness_rating, and notes

    Returns:
        A response indicating success or failure with the updated session
    """
    db_session = DBSession()
    try:
        # Verify the session exists and is not already ended
        session = db_session.query(WorkSessionModel).filter(
            WorkSessionModel.id == end_data.session_id
        ).first()

        if not session:
            return SessionResponse(
                success=False,
                message=f"Session with ID {end_data.session_id} not found",
                session_id=end_data.session_id
            )

        # Check if the session is already ended
        if session.end_ts is not None:
            return SessionResponse(
                success=False,
                message=f"Session with ID {end_data.session_id} is already ended",
                session_id=end_data.session_id
            )

        # Update the session with end time, completion percentage, rating, and notes
        now = datetime.now(timezone.utc)
        session.end_ts = now
        session.completion_pct = end_data.completion_pct

        if end_data.effectiveness_rating is not None:
            session.effectiveness_rating = end_data.effectiveness_rating

        if end_data.notes is not None:
            session.notes = end_data.notes

        # Close any open work logs for this session
        open_logs = db_session.query(WorkLogModel).filter(
            WorkLogModel.session_id == end_data.session_id,
            WorkLogModel.end_ts.is_(None)
        ).all()

        for log in open_logs:
            log.end_ts = now
            # If no completion percentage is set, default to the session's completion
            if log.completion_pct is None:
                log.completion_pct = end_data.completion_pct

        # Commit the transaction
        db_session.commit()

        return SessionResponse(
            success=True,
            message=f"Session ended with {end_data.completion_pct}% completion",
            session_id=end_data.session_id
        )
    except Exception as e:  # pylint: disable=broad-except
        db_session.rollback()
        return SessionResponse(
            success=False,
            message=f"Failed to end session: {str(e)}",
            session_id=end_data.session_id
        )
    finally:
        db_session.close()


@mcp.tool()
def end_work_log(end_data: EndWorkLogRequest) -> WorkLogResponse:
    """End a work log entry with completion percentage

    Args:
        end_data: Data containing work_log_id and completion_pct

    Returns:
        A response indicating success or failure with the updated work log
    """
    db_session = DBSession()
    try:
        # Verify the work log exists
        work_log, error_msg = _get_entity_or_error(
            db_session, WorkLogModel, end_data.work_log_id, "Work log"
        )
        if error_msg:
            return WorkLogResponse(
                success=False,
                message=error_msg,
                session_id=0
            )

        # Check if the work log is already ended
        if work_log.end_ts is not None:
            return WorkLogResponse(
                success=False,
                message=f"Work log with ID {end_data.work_log_id} is already ended",
                session_id=work_log.session_id
            )

        # Get the task for this work log
        task, error_msg = _get_entity_or_error(
            db_session, TaskModel, work_log.task_id, "Task"
        )
        if error_msg:
            return WorkLogResponse(
                success=False,
                message=error_msg,
                session_id=work_log.session_id
            )

        # Update the work log with end time and completion percentage
        now = datetime.now(timezone.utc)
        work_log.end_ts = now
        work_log.completion_pct = end_data.completion_pct

        # If completion percentage is high (e.g., >= 90%), update task status to "done"
        if end_data.completion_pct >= 90 and task.status != "done":
            task.status = "done"
            task.updated_ts = now

        # Update task summary if it exists
        summary = db_session.query(TaskSummaryModel).filter(
            TaskSummaryModel.task_id == work_log.task_id
        ).first()

        # Calculate time worked in minutes using helper function
        time_diff = _calculate_time_diff_minutes(work_log.start_ts, now)
        
        if summary:
            summary.time_worked += int(time_diff)
            summary.updated_ts = now
        else:
            # Create a new task summary
            summary = TaskSummaryModel(
                task_id=work_log.task_id,
                time_worked=int(time_diff),
                start_date=work_log.start_ts,
                has_ended=False
            )
            db_session.add(summary)

        # Commit the transaction
        db_session.commit()

        return WorkLogResponse(
            success=True,
            message=f"Work log ended for task '{task.name}' with {end_data.completion_pct}% completion",
            session_id=work_log.session_id,
            work_log=_serialize_work_log(work_log)
        )
    except Exception as e:  # pylint: disable=broad-except
        db_session.rollback()
        return WorkLogResponse(
            success=False,
            message=f"Failed to end work log: {str(e)}",
            session_id=0
        )
    finally:
        db_session.close()


@mcp.tool()
def start_work_log(log_data: StartWorkLogRequest) -> WorkLogResponse:
    """Start a work log entry for a task within a session

    Args:
        log_data: Data containing session_id, task_id, and optional recommendation_id

    Returns:
        A response indicating success or failure with the created work log
    """
    db_session = DBSession()
    try:
        # Verify the session exists
        session, error_msg = _get_entity_or_error(
            db_session, WorkSessionModel, log_data.session_id, "Session"
        )
        if error_msg:
            return WorkLogResponse(
                success=False,
                message=error_msg,
                session_id=log_data.session_id
            )

        # Verify the task exists
        task, error_msg = _get_entity_or_error(
            db_session, TaskModel, log_data.task_id, "Task"
        )
        if error_msg:
            return WorkLogResponse(
                success=False,
                message=error_msg,
                session_id=log_data.session_id
            )

        # If recommendation_id is provided, verify it exists
        if log_data.recommendation_id is not None:
            recommendation, error_msg = _get_entity_or_error(
                db_session, RecommendationModel, log_data.recommendation_id, "Recommendation"
            )
            if error_msg:
                return WorkLogResponse(
                    success=False,
                    message=error_msg,
                    session_id=log_data.session_id
                )

        # Create a new work log entry
        now = datetime.now(timezone.utc)
        new_log = WorkLogModel(
            session_id=log_data.session_id,
            task_id=log_data.task_id,
            rec_id=log_data.recommendation_id,
            start_ts=now
        )

        db_session.add(new_log)
        db_session.commit()

        return WorkLogResponse(
            success=True,
            message=f"Work log started for task '{task.name}'",
            session_id=log_data.session_id,
            work_log=_serialize_work_log(new_log)
        )
    except Exception as e:  # pylint: disable=broad-except
        db_session.rollback()
        return WorkLogResponse(
            success=False,
            message=f"Failed to start work log: {str(e)}",
            session_id=log_data.session_id
        )
    finally:
        db_session.close()


@mcp.tool()
def update_recommendation_status(status_data:
                                 UpdateRecommendationStatusRequest) -> RecommendationResponse:
    """Update the status of a recommendation (accept or reject with reason)

    Args:
        status_data: Data containing recommendation_id, status, and optional rejected_reason

    Returns:
        A response indicating success or failure with the updated recommendation
    """
    db_session = DBSession()
    try:
        # Verify the recommendation exists
        recommendation, error_msg = _get_entity_or_error(
            db_session, RecommendationModel, status_data.recommendation_id, "Recommendation"
        )
        if error_msg:
            return RecommendationResponse(
                success=False,
                message=error_msg,
                session_id=0
            )

        # Update the status
        recommendation.status = status_data.status

        # If status is rejected, ensure a reason is provided
        if status_data.status == 'rejected':
            if not status_data.rejected_reason:
                return RecommendationResponse(
                    success=False,
                    message="A rejection reason is required when status is 'rejected'",
                    session_id=recommendation.session_id
                )
            recommendation.rejected_reason = status_data.rejected_reason

        # Commit the transaction
        db_session.commit()

        return RecommendationResponse(
            success=True,
            message=f"Recommendation status updated to '{status_data.status}'",
            session_id=recommendation.session_id,
            recommendations=[_serialize_recommendation(recommendation)]
        )
    except Exception as e:  # pylint: disable=broad-except
        db_session.rollback()
        return RecommendationResponse(
            success=False,
            message=f"Failed to update recommendation status: {str(e)}",
            session_id=0
        )
    finally:
        db_session.close()


@mcp.tool()
def save_recommendations(recommendation_data: SaveRecommendationsRequest) -> RecommendationResponse:
    """Save task recommendations for a work session

    Args:
        recommendation_data: Data containing session_id, task_ids, rec_type, and strategy

    Returns:
        A response indicating success or failure with the created recommendations
    """
    db_session = DBSession()
    try:
        # Verify the session exists
        session = db_session.query(WorkSessionModel).filter(
            WorkSessionModel.id == recommendation_data.session_id
        ).first()

        if not session:
            return RecommendationResponse(
                success=False,
                message=f"Session with ID {recommendation_data.session_id} not found",
                session_id=recommendation_data.session_id
            )

        # Verify all tasks exist
        tasks = db_session.query(TaskModel).filter(
            TaskModel.id.in_(recommendation_data.task_ids)
        ).all()

        found_task_ids = [task.id for task in tasks]
        missing_task_ids = [
            task_id for task_id in recommendation_data.task_ids
            if task_id not in found_task_ids
        ]

        if missing_task_ids:
            return RecommendationResponse(
                success=False,
                message=f"Tasks with IDs {missing_task_ids} not found",
                session_id=recommendation_data.session_id
            )

        # Create recommendation entries for each task
        recommendations = []
        now = datetime.now(timezone.utc)

        for task_id in recommendation_data.task_ids:
            recommendation = RecommendationModel(
                session_id=recommendation_data.session_id,
                task_id=task_id,
                rec_type=recommendation_data.rec_type,
                strategy=recommendation_data.strategy,
                rec_ts=now
            )
            db_session.add(recommendation)
            recommendations.append(recommendation)

        db_session.flush()  # Flush to get the recommendation IDs

        # Commit the transaction
        db_session.commit()

        # Serialize the recommendations
        serialized_recommendations = [
            _serialize_recommendation(rec) for rec in recommendations
        ]

        return RecommendationResponse(
            success=True,
            message=f"Successfully saved {len(recommendations)} task recommendations",
            session_id=recommendation_data.session_id,
            recommendations=serialized_recommendations
        )
    except Exception as e:  # pylint: disable=broad-except
        db_session.rollback()
        return RecommendationResponse(
            success=False,
            message=f"Failed to save recommendations: {str(e)}",
            session_id=recommendation_data.session_id
        )
    finally:
        db_session.close()


@mcp.tool()
def start_session(session_data: StartSessionRequest) -> SessionResponse:
    """Start a new work session with the given query, context, and planned duration

    Args:
        session_data: The session data containing query, context, and planned duration

    Returns:
        A response indicating success or failure with the session ID
    """
    db_session = DBSession()
    try:
        # Create new work session
        new_session = WorkSessionModel(
            query=session_data.query,
            context=session_data.context,
            planned_duration=session_data.planned_duration,
            start_ts=datetime.now(timezone.utc)
        )
        db_session.add(new_session)
        db_session.commit()

        return SessionResponse(
            success=True,
            message="Work session started successfully",
            session_id=new_session.id
        )
    except Exception as e:  # pylint: disable=broad-except
        db_session.rollback()
        return SessionResponse(
            success=False,
            message=f"Failed to start work session: {str(e)}"
        )
    finally:
        db_session.close()


@mcp.tool()
def list_weekly_goals(date: Optional[datetime] = None) -> WeeklyGoalList:
    """List weekly goals for a specific week

    If date is not provided, defaults to the current week.
    The week is considered from Monday to Sunday.
    """
    session = DBSession()
    try:
        # If date is not provided, use the current date
        target_date = date or datetime.now(timezone.utc)

        # Calculate the start of the week (Monday)
        # weekday() returns 0 for Monday, 6 for Sunday
        days_since_monday = target_date.weekday()
        start_of_week = target_date.replace(hour=0, minute=0, second=0, microsecond=0) - \
                        timedelta(days=days_since_monday)

        # Calculate the end of the week (Sunday)
        end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

        # Query goals that overlap with the target week
        # A goal overlaps with the week if:
        # 1. It starts before or during the week AND
        # 2. It ends during or after the week OR it has no end date
        goals = (session.query(WeeklyGoalModel)
                .filter(
                    (WeeklyGoalModel.start_date <= end_of_week) &
                    (
                        (WeeklyGoalModel.end_date >= start_of_week) |
                        (WeeklyGoalModel.end_date.is_(None))
                    )
                )
                .order_by(WeeklyGoalModel.start_date)
                .all())

        # Convert to dictionary format for response
        goal_list = [
            {
                'id': goal.id,
                'title': goal.title,
                'description': goal.description,
                'category': goal.category,
                'start_date': goal.start_date,
                'end_date': goal.end_date,
                'status': goal.status,
                'created_ts': goal.created_ts,
                'updated_ts': goal.updated_ts
            }
            for goal in goals
        ]

        return WeeklyGoalList(goals=goal_list)
    except Exception as e:  # pylint: disable=broad-except
        # Log the error but return an empty list rather than failing
        print(f"Error fetching weekly goals: {str(e)}")
        return WeeklyGoalList(goals=[])
    finally:
        session.close()
