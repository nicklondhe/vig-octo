'''MCP server example with a tool and a dynamic resource'''
from typing import List
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
    type: str
    due_date: str = None
    priority: str = 'low'
    repeatable: bool = False

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
            status="pending"  # Default status for new tasks
        )
        session.add(new_task)
        session.commit()
        return TaskResponse(
            success=True,
            message=f"Task '{task_data.name}' added successfully",
            task_id=new_task.id
        )
    except Exception as e:
        session.rollback()
        return TaskResponse(success=False, message=f"Failed to add task: {str(e)}")
    finally:
        session.close()

@mcp.tool()
def mark_task_done(task_name: str) -> TaskResponse:
    """Mark a task as done by its name"""
    session = DBSession()
    try:
        task = session.query(TaskModel).filter(TaskModel.name == task_name).first()
        if not task:
            return TaskResponse(success=False, message=f"Task with ID {task_id} not found")
        
        task.status = "done"
        session.commit()
        return TaskResponse(
            success=True,
            message=f"Task '{task.name}' marked as done",
            task_id=task.id
        )
    except Exception as e:
        session.rollback()
        return TaskResponse(success=False, message=f"Failed to update task: {str(e)}")
    finally:
        session.close()
