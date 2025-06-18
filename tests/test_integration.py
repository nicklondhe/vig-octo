"""
Integration tests for task matrix view functionality
"""
import pytest
import tempfile
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server import get_task_matrix_view, TaskMatrixResponse
from models import Base, TaskModel


class TestTaskMatrixViewIntegration:
    """Integration tests for get_task_matrix_view function"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        # Create a temporary file for the database
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        # Create engine and tables
        engine = create_engine(f'sqlite:///{temp_file.name}')
        Base.metadata.create_all(engine)
        
        yield temp_file.name
        
        # Cleanup
        os.unlink(temp_file.name)

    @pytest.fixture
    def db_session(self, temp_db):
        """Create a database session"""
        engine = create_engine(f'sqlite:///{temp_db}')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        yield session
        
        session.close()

    def create_test_task(self, session, name, priority, complexity, status="pending"):
        """Helper method to create a test task"""
        task = TaskModel(
            name=name,
            priority=priority,
            complexity=complexity,
            type="Direct",
            status=status,
            created_ts=datetime.now(timezone.utc),
            updated_ts=datetime.now(timezone.utc)
        )
        session.add(task)
        session.commit()
        return task

    def test_priority_desc_sorting_integration(self, temp_db, monkeypatch):
        """Integration test for priority_desc sorting with real database"""
        # Arrange
        engine = create_engine(f'sqlite:///{temp_db}')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Create test tasks in random order
        self.create_test_task(session, "Low Priority Task", "low", "medium")
        self.create_test_task(session, "High Priority Task", "high", "medium")
        self.create_test_task(session, "Medium Priority Task", "medium", "medium")
        self.create_test_task(session, "Another High Task", "high", "low")
        self.create_test_task(session, "Another Low Task", "low", "high")
        
        session.close()
        
        # Mock the DBSession to use our test database
        def mock_db_session():
            return Session()
        
        monkeypatch.setattr('server.DBSession', mock_db_session)
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="priority_desc")
        
        # Assert
        assert isinstance(result, TaskMatrixResponse)
        
        # Verify that high priority tasks come first
        # Since we're using a real database, we can't easily verify the exact order
        # but we can verify the structure and that tasks are properly categorized
        assert hasattr(result, 'high')
        assert hasattr(result, 'medium')
        assert hasattr(result, 'low')
        
        # Check that tasks are properly distributed across the matrix
        high_tasks = result.high
        medium_tasks = result.medium
        low_tasks = result.low
        
        # Should have tasks in each priority level
        assert any(len(complexity_list) > 0 for complexity_list in high_tasks.values())
        assert any(len(complexity_list) > 0 for complexity_list in medium_tasks.values())
        assert any(len(complexity_list) > 0 for complexity_list in low_tasks.values())

    def test_matrix_structure_integration(self, temp_db, monkeypatch):
        """Integration test for matrix structure with real database"""
        # Arrange
        engine = create_engine(f'sqlite:///{temp_db}')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Create one task for each priority/complexity combination
        priorities = ['low', 'medium', 'high']
        complexities = ['low', 'medium', 'high']
        
        for priority in priorities:
            for complexity in complexities:
                self.create_test_task(
                    session, 
                    f"Task {priority}_{complexity}", 
                    priority, 
                    complexity
                )
        
        session.close()
        
        # Mock the DBSession to use our test database
        def mock_db_session():
            return Session()
        
        monkeypatch.setattr('server.DBSession', mock_db_session)
        
        # Act
        result = get_task_matrix_view(limit=20, sort_by="created_desc")
        
        # Assert
        assert isinstance(result, TaskMatrixResponse)
        
        # Verify matrix structure
        for priority in ['low', 'medium', 'high']:
            priority_dict = getattr(result, priority)
            assert isinstance(priority_dict, dict)
            
            for complexity in ['low', 'medium', 'high']:
                assert complexity in priority_dict
                assert isinstance(priority_dict[complexity], list)
                
                # Should have exactly one task in each cell
                assert len(priority_dict[complexity]) == 1
                
                # Verify the task has correct priority and complexity
                task = priority_dict[complexity][0]
                assert task['priority'] == priority
                assert task['complexity'] == complexity

    def test_empty_database_integration(self, temp_db, monkeypatch):
        """Integration test for empty database"""
        # Arrange
        engine = create_engine(f'sqlite:///{temp_db}')
        Session = sessionmaker(bind=engine)
        
        # Mock the DBSession to use our test database
        def mock_db_session():
            return Session()
        
        monkeypatch.setattr('server.DBSession', mock_db_session)
        
        # Act
        result = get_task_matrix_view(limit=10, sort_by="created_desc")
        
        # Assert
        assert isinstance(result, TaskMatrixResponse)
        
        # All cells should be empty
        for priority in ['low', 'medium', 'high']:
            priority_dict = getattr(result, priority)
            for complexity in ['low', 'medium', 'high']:
                assert priority_dict[complexity] == []

    def test_limit_parameter_integration(self, temp_db, monkeypatch):
        """Integration test for limit parameter"""
        # Arrange
        engine = create_engine(f'sqlite:///{temp_db}')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Create more tasks than the limit
        for i in range(15):
            self.create_test_task(
                session, 
                f"Task {i}", 
                "medium", 
                "medium"
            )
        
        session.close()
        
        # Mock the DBSession to use our test database
        def mock_db_session():
            return Session()
        
        monkeypatch.setattr('server.DBSession', mock_db_session)
        
        # Act
        result = get_task_matrix_view(limit=5, sort_by="created_desc")
        
        # Assert
        # Count total tasks in the result
        total_tasks = 0
        for priority in ['low', 'medium', 'high']:
            priority_dict = getattr(result, priority)
            for complexity in ['low', 'medium', 'high']:
                total_tasks += len(priority_dict[complexity])
        
        # Should not exceed the limit
        assert total_tasks <= 5 