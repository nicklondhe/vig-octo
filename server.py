'''MCP server example with a tool and a dynamic resource'''
from typing import List, Optional
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import TaskModel, Base
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

# Request model for adding a task
class AddTaskRequest(BaseModel):
    """Model for task creation request"""
    name: str
    complexity: str = 'simple'
    type: str = 'Direct'
    due_date: Optional[str] = None
    priority: str = 'low'
    repeatable: bool = False

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
    """Add a new task to the system"""
    session = DBSession()
    try:
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
        session.commit()
        return TaskResponse(
            success=True,
            message=f"Task '{task_data.name}' added successfully",
            task_id=new_task.id
        )
    except Exception as e: #pylint: disable=broad-except
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
    """Update an existing task with provided fields"""
    session = DBSession()
    try:
        task = session.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return TaskResponse(success=False, message=f"Task with ID {task_id} not found")

        # Convert the request data to a dictionary and filter out None values
        updates = {k: v for k, v in task_data.dict().items() if v is not None}
        
        # Apply the updates to the task
        for key, value in updates.items():
            setattr(task, key, value)
            
        # Always update the updated_ts timestamp when a task is modified
        task.updated_ts = datetime.now(timezone.utc)
        
        session.commit()
        return TaskResponse(
            success=True,
            message=f"Task with ID {task_id} updated successfully",
            task_id=task.id
        )
    except Exception as e:  # pylint: disable=broad-except
        session.rollback()
        return TaskResponse(success=False, message=f"Failed to update task: {str(e)}")
    finally:
        session.close()
