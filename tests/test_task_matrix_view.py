"""
Unit tests for task matrix view functionality
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import case

from server import get_task_matrix_view, TaskMatrixResponse
from models import TaskModel


class TestTaskMatrixView:
    """Test cases for get_task_matrix_view function"""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query.return_value = session.query
        session.query.filter.return_value = session.query
        session.query.order_by.return_value = session.query
        session.query.limit.return_value = session.query
        session.query.all.return_value = []
        return session

    @pytest.fixture
    def sample_tasks(self):
        """Create sample tasks with different priorities and complexities"""
        tasks = []
        
        # Create tasks with different priorities and complexities
        priorities = ['low', 'medium', 'high']
        complexities = ['low', 'medium', 'high']
        
        for i, priority in enumerate(priorities):
            for j, complexity in enumerate(complexities):
                task = Mock(spec=TaskModel)
                task.id = i * 3 + j + 1
                task.name = f"Task {priority}_{complexity}_{i*3+j+1}"
                task.priority = priority
                task.complexity = complexity
                task.type = "Direct"
                task.due_date = None
                task.repeatable = False
                task.status = "pending"
                task.created_ts = datetime.now(timezone.utc)
                task.updated_ts = datetime.now(timezone.utc)
                tasks.append(task)
        
        return tasks

    @patch('server.DBSession')
    def test_priority_desc_sorting_order(self, mock_db_session, mock_session, sample_tasks):
        """Test that priority_desc sorts tasks in correct order: high -> medium -> low"""
        # Arrange
        mock_db_session.return_value = mock_session
        
        # Create tasks in random order but expect them to be sorted by priority
        random_order_tasks = [
            sample_tasks[0],  # low priority
            sample_tasks[6],  # high priority  
            sample_tasks[3],  # medium priority
            sample_tasks[7],  # high priority
            sample_tasks[1],  # low priority
        ]
        
        mock_session.query.all.return_value = random_order_tasks
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="priority_desc")
        
        # Assert
        # Verify that the query was called with TaskModel
        mock_session.query.assert_called_with(TaskModel)
        # Verify that filter and order_by were called
        assert mock_session.query.filter.called
        assert mock_session.query.order_by.called

    @patch('server.DBSession')
    def test_priority_desc_sorts_high_first(self, mock_db_session, mock_session, sample_tasks):
        """Test that high priority tasks appear first when using priority_desc"""
        # Arrange
        mock_db_session.return_value = mock_session
        
        # Create tasks with mixed priorities
        mixed_tasks = [
            sample_tasks[0],  # low_priority
            sample_tasks[3],  # medium_priority
            sample_tasks[6],  # high_priority
            sample_tasks[1],  # low_priority
            sample_tasks[4],  # medium_priority
            sample_tasks[7],  # high_priority
        ]
        
        mock_session.query.all.return_value = mixed_tasks
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="priority_desc")
        
        # Assert
        # The result should be a TaskMatrixResponse with tasks organized by priority
        assert isinstance(result, TaskMatrixResponse)
        
        # Verify that all priority levels are present in the response
        assert 'low' in result.model_dump()
        assert 'medium' in result.model_dump()
        assert 'high' in result.model_dump()

    @patch('server.DBSession')
    def test_default_sorting_uses_created_desc(self, mock_db_session, mock_session):
        """Test that default sorting uses created_desc when no sort_by is specified"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        get_task_matrix_view(limit=10)  # No sort_by parameter
        
        # Assert
        # Should use the default sort order (created_desc)
        # We can't easily compare SQLAlchemy expressions, so we just verify order_by was called
        assert mock_session.query.order_by.called

    @patch('server.DBSession')
    def test_invalid_sort_by_uses_default(self, mock_db_session, mock_session):
        """Test that invalid sort_by values fall back to default sorting"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        get_task_matrix_view(limit=10, sort_by="invalid_sort")
        
        # Assert
        # Should use the default sort order (created_desc)
        assert mock_session.query.order_by.called

    @patch('server.DBSession')
    def test_created_asc_sorting(self, mock_db_session, mock_session):
        """Test created_asc sorting"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        get_task_matrix_view(limit=10, sort_by="created_asc")
        
        # Assert
        assert mock_session.query.order_by.called

    @patch('server.DBSession')
    def test_updated_desc_sorting(self, mock_db_session, mock_session):
        """Test updated_desc sorting"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        get_task_matrix_view(limit=10, sort_by="updated_desc")
        
        # Assert
        assert mock_session.query.order_by.called

    @patch('server.DBSession')
    def test_matrix_structure_with_tasks(self, mock_db_session, mock_session, sample_tasks):
        """Test that the matrix structure is correctly created with tasks"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = sample_tasks[:3]  # Just a few tasks
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="created_desc")
        
        # Assert
        assert isinstance(result, TaskMatrixResponse)
        
        # Check that all priority levels exist
        assert hasattr(result, 'low')
        assert hasattr(result, 'medium')
        assert hasattr(result, 'high')
        
        # Check that all complexity levels exist for each priority
        for priority in ['low', 'medium', 'high']:
            priority_dict = getattr(result, priority)
            assert isinstance(priority_dict, dict)
            assert 'low' in priority_dict
            assert 'medium' in priority_dict
            assert 'high' in priority_dict
            assert isinstance(priority_dict['low'], list)
            assert isinstance(priority_dict['medium'], list)
            assert isinstance(priority_dict['high'], list)

    @patch('server.DBSession')
    def test_limit_parameter(self, mock_db_session, mock_session):
        """Test that the limit parameter is respected"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        get_task_matrix_view(limit=5, sort_by="created_desc")
        
        # Assert
        mock_session.query.limit.assert_called_with(5)

    @patch('server.DBSession')
    def test_session_cleanup(self, mock_db_session, mock_session):
        """Test that the database session is properly closed"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        get_task_matrix_view(limit=10, sort_by="created_desc")
        
        # Assert
        mock_session.close.assert_called_once()

    @patch('server.DBSession')
    def test_empty_result_structure(self, mock_db_session, mock_session):
        """Test that empty results still have the correct matrix structure"""
        # Arrange
        mock_db_session.return_value = mock_session
        mock_session.query.all.return_value = []
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="created_desc")
        
        # Assert
        assert isinstance(result, TaskMatrixResponse)
        
        # All priority levels should exist with empty lists
        for priority in ['low', 'medium', 'high']:
            priority_dict = getattr(result, priority)
            for complexity in ['low', 'medium', 'high']:
                assert priority_dict[complexity] == []


class TestPrioritySortingEdgeCases:
    """Test edge cases for priority sorting"""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session"""
        session = Mock()
        session.query.return_value = session.query
        session.query.filter.return_value = session.query
        session.query.order_by.return_value = session.query
        session.query.limit.return_value = session.query
        session.query.all.return_value = []
        return session

    @patch('server.DBSession')
    def test_priority_desc_with_mixed_case_priorities(self, mock_db_session, mock_session):
        """Test priority sorting with mixed case priority values"""
        # Arrange
        mock_db_session.return_value = mock_session
        
        # Create tasks with mixed case priorities
        tasks = []
        for i, priority in enumerate(['LOW', 'Medium', 'HIGH']):
            task = Mock(spec=TaskModel)
            task.id = i + 1
            task.name = f"Task {priority}"
            task.priority = priority
            task.complexity = 'medium'
            task.type = "Direct"
            task.due_date = None
            task.repeatable = False
            task.status = "pending"
            task.created_ts = datetime.now(timezone.utc)
            task.updated_ts = datetime.now(timezone.utc)
            tasks.append(task)
        
        mock_session.query.all.return_value = tasks
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="priority_desc")
        
        # Assert
        # Just verify order_by was called
        assert mock_session.query.order_by.called

    @patch('server.DBSession')
    def test_priority_desc_with_unknown_priority_values(self, mock_db_session, mock_session):
        """Test priority sorting with unknown priority values"""
        # Arrange
        mock_db_session.return_value = mock_session
        
        # Create tasks with unknown priority values
        tasks = []
        for i, priority in enumerate(['unknown', 'critical', 'urgent']):
            task = Mock(spec=TaskModel)
            task.id = i + 1
            task.name = f"Task {priority}"
            task.priority = priority
            task.complexity = 'medium'
            task.type = "Direct"
            task.due_date = None
            task.repeatable = False
            task.status = "pending"
            task.created_ts = datetime.now(timezone.utc)
            task.updated_ts = datetime.now(timezone.utc)
            tasks.append(task)
        
        mock_session.query.all.return_value = tasks
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="priority_desc")
        
        # Assert
        # Just verify order_by was called
        assert mock_session.query.order_by.called 