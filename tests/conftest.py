"""
Pytest configuration and common fixtures
"""
import pytest
from unittest.mock import Mock
from datetime import datetime, timezone


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        'id': 1,
        'name': 'Test Task',
        'complexity': 'medium',
        'type': 'Direct',
        'due_date': None,
        'priority': 'high',
        'repeatable': False,
        'status': 'pending',
        'created_ts': datetime.now(timezone.utc),
        'updated_ts': datetime.now(timezone.utc)
    }


@pytest.fixture
def mock_task_model():
    """Create a mock TaskModel instance"""
    task = Mock()
    task.id = 1
    task.name = 'Test Task'
    task.complexity = 'medium'
    task.type = 'Direct'
    task.due_date = None
    task.priority = 'high'
    task.repeatable = False
    task.status = 'pending'
    task.created_ts = datetime.now(timezone.utc)
    task.updated_ts = datetime.now(timezone.utc)
    return task 