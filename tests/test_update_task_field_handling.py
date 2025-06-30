'''Test update_task field handling to ensure proper field modification behavior'''

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from server import update_task, UpdateTaskRequest, TaskResponse
from models import TaskModel


class TestUpdateTaskFieldHandling:
    '''Test cases for update_task field handling behavior'''

    def test_unset_fields_are_not_modified(self):
        '''Test that fields not provided in UpdateTaskRequest are not modified'''
        # Mock task from database
        mock_task = Mock(spec=TaskModel)
        mock_task.id = 1
        mock_task.name = "Original Task"
        mock_task.complexity = "simple"
        mock_task.type = "Direct"
        mock_task.due_date = "2025-01-15"
        mock_task.priority = "low"
        mock_task.repeatable = False
        mock_task.status = "pending"

        # Create update request with only name field set
        update_request = UpdateTaskRequest(name="Updated Task")

        with patch('server.DBSession') as mock_db_session:
            mock_session = Mock()
            mock_db_session.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_task

            # Call update_task
            result = update_task(1, update_request)

            # Verify only name was updated
            assert mock_task.name == "Updated Task"
            # Verify other fields were NOT modified
            assert mock_task.complexity == "simple"
            assert mock_task.type == "Direct"
            assert mock_task.due_date == "2025-01-15"
            assert mock_task.priority == "low"
            assert mock_task.repeatable == False
            assert mock_task.status == "pending"

            assert result.success == True

    def test_explicit_none_due_date_clears_field(self):
        '''Test that explicitly setting due_date=None clears the field'''
        mock_task = Mock(spec=TaskModel)
        mock_task.id = 1
        mock_task.name = "Test Task"
        mock_task.due_date = "2025-01-15"
        mock_task.status = "pending"

        # Create update request with explicit due_date=None
        update_request = UpdateTaskRequest(due_date=None)

        with patch('server.DBSession') as mock_db_session:
            mock_session = Mock()
            mock_db_session.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_task

            # Call update_task
            result = update_task(1, update_request)

            # Verify due_date was cleared
            assert mock_task.due_date is None
            # Verify other fields were NOT modified
            assert mock_task.name == "Test Task"

            assert result.success == True

    def test_partial_update_preserves_other_fields(self):
        '''Test that partial updates only modify specified fields'''
        mock_task = Mock(spec=TaskModel)
        mock_task.id = 1
        mock_task.name = "Original Task"
        mock_task.complexity = "simple"
        mock_task.type = "Direct"
        mock_task.due_date = "2025-01-15"
        mock_task.priority = "low"
        mock_task.repeatable = False
        mock_task.status = "pending"

        # Update only priority and status
        update_request = UpdateTaskRequest(priority="high", status="done")

        with patch('server.DBSession') as mock_db_session, \
             patch('server._get_task_goal') as mock_get_task_goal:
            mock_session = Mock()
            mock_db_session.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_task
            # Mock _get_task_goal to return None (no goal attached)
            mock_get_task_goal.return_value = None

            # Call update_task
            result = update_task(1, update_request)

            # Verify only specified fields were updated
            assert mock_task.priority == "high"
            assert mock_task.status == "done"
            # Verify other fields were NOT modified
            assert mock_task.name == "Original Task"
            assert mock_task.complexity == "simple"
            assert mock_task.type == "Direct"
            assert mock_task.due_date == "2025-01-15"
            assert mock_task.repeatable == False

            assert result.success == True

    def test_empty_update_request_modifies_nothing(self):
        '''Test that an empty UpdateTaskRequest modifies no fields'''
        mock_task = Mock(spec=TaskModel)
        mock_task.id = 1
        mock_task.name = "Original Task"
        mock_task.complexity = "simple"
        mock_task.type = "Direct"
        mock_task.due_date = "2025-01-15"
        mock_task.priority = "low"
        mock_task.repeatable = False
        mock_task.status = "pending"

        # Create empty update request
        update_request = UpdateTaskRequest()

        with patch('server.DBSession') as mock_db_session:
            mock_session = Mock()
            mock_db_session.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_task

            # Call update_task
            result = update_task(1, update_request)

            # Verify NO fields were modified
            assert mock_task.name == "Original Task"
            assert mock_task.complexity == "simple"
            assert mock_task.type == "Direct"
            assert mock_task.due_date == "2025-01-15"
            assert mock_task.priority == "low"
            assert mock_task.repeatable == False
            assert mock_task.status == "pending"

            assert result.success == True

    def test_model_dump_behavior(self):
        '''Test the difference between model_dump() and model_dump(exclude_unset=True)'''
        # Test with only name set
        update_request = UpdateTaskRequest(name="Test Task")
        
        # model_dump() includes all fields with default values
        full_dump = update_request.model_dump()
        expected_keys = {'name', 'complexity', 'type', 'due_date', 'priority', 'repeatable', 'status'}
        assert set(full_dump.keys()) == expected_keys
        assert full_dump['name'] == "Test Task"
        assert full_dump['complexity'] is None  # Default None value included
        assert full_dump['due_date'] is None     # Default None value included
        
        # model_dump(exclude_unset=True) only includes explicitly set fields
        unset_excluded_dump = update_request.model_dump(exclude_unset=True)
        assert set(unset_excluded_dump.keys()) == {'name'}
        assert unset_excluded_dump['name'] == "Test Task"
        assert 'complexity' not in unset_excluded_dump
        assert 'due_date' not in unset_excluded_dump

    def test_explicit_none_vs_unset_field(self):
        '''Test difference between explicitly setting None vs not setting a field'''
        # Explicitly set due_date to None
        explicit_none = UpdateTaskRequest(name="Test", due_date=None)
        explicit_dump = explicit_none.model_dump(exclude_unset=True)
        assert 'due_date' in explicit_dump
        assert explicit_dump['due_date'] is None
        
        # Don't set due_date at all
        unset_field = UpdateTaskRequest(name="Test")
        unset_dump = unset_field.model_dump(exclude_unset=True)
        assert 'due_date' not in unset_dump
        assert unset_dump['name'] == "Test"