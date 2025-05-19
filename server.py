'''MCP server example with a tool and a dynamic resource'''
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import (
    TaskModel, WeeklyGoalModel, GoalTaskModel,
    GoalProgressHistoryModel, Base
)
from config import get_version, get_config

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

# Response model for getting goal progress
class GoalProgressInfoResponse(BaseModel):
    """Model for goal progress information response"""
    success: bool
    goal_id: int
    title: Optional[str] = None
    current_completion_pct: float
    history: List[dict[str, object]] = []

# Helper functions for goal-related operations

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


def _update_goal_progress(session, task_id, goal_id, task_completion_pct=100.0, notes=None):
    """Helper method to update goal progress when a task is completed.

    Args:
        session: SQLAlchemy session
        task_id: ID of the task that was completed
        goal_id: ID of the goal to update
        task_completion_pct: Percentage contribution of this task (default 100%)
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

        # Add this task's contribution to the current completion
        new_completion = current_completion + task_contribution

        # Cap at 100%
        new_completion = min(100.0, new_completion)

        # Record progress history
        if notes is None:
            notes = f"Task '{task.name}' added {task_contribution:.1f}% to goal completion"
        
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

    except Exception as e:
        print(f"Error updating goal progress: {str(e)}")
        return None


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
            {
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
                'context': config['env_type']  # Add environment type as context
            }
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
            {
                'id': task.id,
                'name': task.name,
                'complexity': task.complexity,
                'type': task.type,
                'due_date': task.due_date,
                'priority': task.priority,
                'repeatable': task.repeatable,
                'status': task.status,
                'context': config['env_type']
            }
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
        task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return TaskResponse(
                success=False,
                message=f"Task with ID {task_id} not found"
            )

        # Store original status to detect changes
        original_status = task.status

        # Convert the request data to a dictionary and filter out None values
        updates = {k: v for k, v in task_data.dict().items() if v is not None}

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
                # Update goal progress
                new_completion = _update_goal_progress(
                    session, task_id, goal_task.goal_id
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
    except Exception as e:
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
    except Exception as e:
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
                    ((WeeklyGoalModel.end_date >= start_of_week) | (WeeklyGoalModel.end_date.is_(None)))
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
