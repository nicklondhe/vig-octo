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


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


# Response model for task listing
class TaskList(BaseModel):
    '''TaskList is a model for the task list response'''
    tasks: List[dict[str, object]]


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
