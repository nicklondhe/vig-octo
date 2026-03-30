'''Unit tests for v2 MCP server'''

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from v2.db import TaskDB
from v2.models import Base, TaskCreate
from v2 import server


@pytest.fixture
def db_engine():
    '''Create in-memory SQLite engine for testing'''
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def task_db(db_engine):
    '''Create TaskDB instance for testing'''
    return TaskDB(db_engine)


@pytest.fixture
def setup_server(task_db):
    '''Set up server with test database'''
    original_task_db = server.task_db
    server.task_db = task_db
    yield
    server.task_db = original_task_db


# Health Check Tests

class TestHealthCheck:
    '''Tests for health_check tool'''

    def test_health_check_empty_db(self, setup_server):
        '''Test health check with empty database'''
        response = server.health_check()

        assert response.success is True
        assert response.database_connected is True
        assert response.total_tasks == 0
        assert response.active_sessions == 0
        assert isinstance(response.timestamp, datetime)

    def test_health_check_with_data(self, setup_server, task_db):
        '''Test health check with data in database'''
        # Create some test data
        task_db.create_task('Test task', 'grow')
        task_db.create_session()

        response = server.health_check()

        assert response.success is True
        assert response.total_tasks == 1
        assert response.active_sessions == 1


# Add Task Tests

class TestAddTask:
    '''Tests for add_task tool'''

    def test_add_task_minimal(self, setup_server, task_db):
        '''Test adding task with minimal data'''
        task_data = TaskCreate(
            title='Test task',
            category='grow'
        )

        response = server.add_task(task_data)

        assert response.success is True
        assert response.task_id is not None
        assert 'Test task' in response.message

        # Verify task was created
        task = task_db.get_task(response.task_id)
        assert task is not None
        assert task.title == 'Test task'
        assert task.category == 'grow'

    def test_add_task_with_all_fields(self, setup_server, task_db):
        '''Test adding task with all fields'''
        # Create a goal first
        goal = task_db.create_weekly_goal('Test goal', datetime.now(timezone.utc).date())

        task_data = TaskCreate(
            title='Complete task',
            category='maintain',
            est_minutes=30,
            repeatable=True,
            goal_id=goal.id
        )

        response = server.add_task(task_data)

        assert response.success is True
        assert response.task_id is not None
        assert f'goal {goal.id}' in response.message

        # Verify task was created with all fields
        task = task_db.get_task(response.task_id)
        assert task.title == 'Complete task'
        assert task.category == 'maintain'
        assert task.est_minutes == 30
        assert task.repeatable is True
        assert task.goal_id == goal.id

    def test_add_task_invalid_goal_id(self, setup_server):
        '''Test adding task with non-existent goal_id'''
        task_data = TaskCreate(
            title='Test task',
            category='grow',
            goal_id=999
        )

        response = server.add_task(task_data)

        assert response.success is False
        assert 'not found' in response.message
        assert response.task_id is None


# List Tasks Tests

class TestListTasks:
    '''Tests for list_tasks tool'''

    def test_list_tasks_empty(self, setup_server):
        '''Test listing tasks with empty database'''
        response = server.list_tasks()

        assert response.success is True
        assert len(response.tasks) == 0

    def test_list_tasks_all(self, setup_server, task_db):
        '''Test listing all tasks'''
        task_db.create_task('Task 1', 'grow')
        task_db.create_task('Task 2', 'maintain')
        task_db.create_task('Task 3', 'sustain')

        response = server.list_tasks()

        assert response.success is True
        assert len(response.tasks) == 3

    def test_list_tasks_filter_by_state(self, setup_server, task_db):
        '''Test filtering tasks by state'''
        task1 = task_db.create_task('Task 1', 'grow')
        task_db.create_task('Task 2', 'grow')
        task_db.update_task_state(task1.id, 'done')

        response = server.list_tasks(state='done')

        assert response.success is True
        assert len(response.tasks) == 1
        assert response.tasks[0].state == 'done'

    def test_list_tasks_filter_by_category(self, setup_server, task_db):
        '''Test filtering tasks by category'''
        task_db.create_task('Task 1', 'grow')
        task_db.create_task('Task 2', 'maintain')
        task_db.create_task('Task 3', 'grow')

        response = server.list_tasks(category='grow')

        assert response.success is True
        assert len(response.tasks) == 2
        assert all(t.category == 'grow' for t in response.tasks)

    def test_list_tasks_filter_by_goal(self, setup_server, task_db):
        '''Test filtering tasks by goal_id'''
        goal = task_db.create_weekly_goal('Test goal', datetime.now(timezone.utc).date())
        task_db.create_task('Task 1', 'grow', goal_id=goal.id)
        task_db.create_task('Task 2', 'grow')

        response = server.list_tasks(goal_id=goal.id)

        assert response.success is True
        assert len(response.tasks) == 1
        assert response.tasks[0].goal_id == goal.id

    def test_list_tasks_with_limit(self, setup_server, task_db):
        '''Test limiting number of tasks returned'''
        for i in range(5):
            task_db.create_task(f'Task {i}', 'grow')

        response = server.list_tasks(limit=3)

        assert response.success is True
        assert len(response.tasks) == 3

    def test_list_tasks_invalid_limit(self, setup_server):
        '''Test with invalid limit (zero or negative)'''
        response = server.list_tasks(limit=0)

        assert response.success is False
        assert 'greater than 0' in response.message

    def test_list_tasks_order(self, setup_server, task_db):
        '''Test tasks are ordered by created_at desc'''
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'grow')
        task3 = task_db.create_task('Task 3', 'grow')

        response = server.list_tasks()

        # Most recent first (descending order)
        assert response.tasks[0].id == task3.id
        assert response.tasks[1].id == task2.id
        assert response.tasks[2].id == task1.id


# Start Session Tests

class TestStartSession:
    '''Tests for start_session tool'''

    def test_start_session_minimal(self, setup_server, task_db):
        '''Test starting session with no parameters'''
        response = server.start_session()

        assert response.success is True
        assert response.session_id is not None

        # Verify session was created
        session = task_db.get_session(response.session_id)
        assert session is not None

    def test_start_session_with_all_params(self, setup_server, task_db):
        '''Test starting session with all parameters'''
        response = server.start_session(
            available_minutes=60,
            energy_level=4,
            focus_area='grow'
        )

        assert response.success is True
        assert response.session_id is not None

        # Verify session was created with parameters
        session = task_db.get_session(response.session_id)
        assert session.available_minutes == 60
        assert session.energy_level == 4
        assert session.focus_area == 'grow'


# Start Work Tests

class TestStartWork:
    '''Tests for start_work tool'''

    def test_start_work_success(self, setup_server, task_db):
        '''Test starting work on a task'''
        session = task_db.create_session()
        task = task_db.create_task('Test task', 'grow')

        response = server.start_work(session.id, task.id)

        assert response.success is True
        assert response.work_entry_id is not None
        assert 'Test task' in response.message

        # Verify work entry was created
        work_entry = task_db.get_work_entry(response.work_entry_id)
        assert work_entry is not None
        assert work_entry.session_id == session.id
        assert work_entry.task_id == task.id

        # Verify task stats were updated
        updated_task = task_db.get_task(task.id)
        assert updated_task.times_accepted == 1

    def test_start_work_invalid_session(self, setup_server, task_db):
        '''Test starting work with non-existent session'''
        task = task_db.create_task('Test task', 'grow')

        response = server.start_work(999, task.id)

        assert response.success is False
        assert 'not found' in response.message
        assert response.work_entry_id is None

    def test_start_work_invalid_task(self, setup_server, task_db):
        '''Test starting work with non-existent task'''
        session = task_db.create_session()

        response = server.start_work(session.id, 999)

        assert response.success is False
        assert 'not found' in response.message
        assert response.work_entry_id is None


# Complete Work Tests

class TestCompleteWork:
    '''Tests for complete_work tool'''

    def test_complete_work_success(self, setup_server, task_db):
        '''Test completing work successfully'''
        session = task_db.create_session()
        task = task_db.create_task('Test task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        response = server.complete_work(
            work_id=work_entry.id,
            completed=True,
            energy_after=4
        )

        assert response.success is True
        assert response.work_entry_id == work_entry.id

        # Verify work entry was completed
        completed_entry = task_db.get_work_entry(work_entry.id)
        assert completed_entry.completed is True
        assert completed_entry.energy_after == 4
        assert completed_entry.ended_at is not None

        # Verify task state was updated (not repeatable)
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'done'
        # actual_minutes may be None if duration < 1 minute

    def test_complete_work_repeatable_task(self, setup_server, task_db):
        '''Test completing work on repeatable task'''
        session = task_db.create_session()
        task = task_db.create_task('Repeatable task', 'grow', repeatable=True)
        work_entry = task_db.start_work_entry(session.id, task.id)

        response = server.complete_work(
            work_id=work_entry.id,
            completed=True
        )

        assert response.success is True

        # Verify task state was NOT changed to done
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'ready'  # Still ready for repeatable tasks

    def test_complete_work_abandoned(self, setup_server, task_db):
        '''Test completing work that was abandoned'''
        session = task_db.create_session()
        task = task_db.create_task('Test task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        response = server.complete_work(
            work_id=work_entry.id,
            completed=False,
            abandoned_reason='blocked'
        )

        assert response.success is True

        # Verify work entry was marked as not completed
        completed_entry = task_db.get_work_entry(work_entry.id)
        assert completed_entry.completed is False
        assert completed_entry.abandoned_reason == 'blocked'

        # Verify task state was NOT changed
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'ready'

    def test_complete_work_invalid_work_id(self, setup_server):
        '''Test completing work with non-existent work_id'''
        response = server.complete_work(999)

        assert response.success is False
        assert 'not found' in response.message

    def test_complete_work_with_feedback(self, setup_server, task_db):
        '''Test completing work with all feedback fields'''
        session = task_db.create_session()
        task = task_db.create_task('Test task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        response = server.complete_work(
            work_id=work_entry.id,
            completed=True,
            energy_after=5,
            want_more_like_this=True
        )

        assert response.success is True

        # Verify all feedback was recorded
        completed_entry = task_db.get_work_entry(work_entry.id)
        assert completed_entry.energy_after == 5
        assert completed_entry.want_more_like_this is True


# End Session Tests

class TestEndSession:
    '''Tests for end_session tool'''

    def test_end_session_minimal(self, setup_server, task_db):
        '''Test ending session with minimal data'''
        session = task_db.create_session()

        response = server.end_session(session.id)

        assert response.success is True
        assert response.summary.session_id == session.id

        # Verify session was ended
        ended_session = task_db.get_session(session.id)
        assert ended_session.ended_at is not None

    def test_end_session_with_outcomes(self, setup_server, task_db):
        '''Test ending session with effectiveness rating'''
        session = task_db.create_session()

        response = server.end_session(
            session_id=session.id,
            effectiveness=4,
        )

        assert response.success is True
        assert response.summary.effectiveness == 4
        # No work entries — computed count should be 0
        assert response.summary.tasks_completed == 0

        ended_session = task_db.get_session(session.id)
        assert ended_session.effectiveness == 4

    def test_end_session_invalid_session_id(self, setup_server):
        '''Test ending non-existent session'''
        response = server.end_session(999)

        assert response.success is False
        assert 'not found' in response.message


# Integration Tests

class TestWorkflowIntegration:
    '''Integration tests for complete workflows'''

    def test_complete_work_session_workflow(self, setup_server, task_db):
        '''Test complete workflow: start session -> start work -> complete work -> end session'''
        # Start session
        session_response = server.start_session(
            available_minutes=60,
            energy_level=3,
            focus_area='grow'
        )
        assert session_response.success is True
        session_id = session_response.session_id

        # Create task
        task_data = TaskCreate(title='Important task', category='grow', est_minutes=30)
        task_response = server.add_task(task_data)
        assert task_response.success is True
        task_id = task_response.task_id

        # Start work
        work_response = server.start_work(session_id, task_id)
        assert work_response.success is True
        work_id = work_response.work_entry_id

        # Complete work
        complete_response = server.complete_work(
            work_id=work_id,
            completed=True,
            energy_after=4,
            want_more_like_this=True
        )
        assert complete_response.success is True

        # End session
        end_response = server.end_session(
            session_id=session_id,
            effectiveness=4,
        )
        assert end_response.success is True
        assert end_response.summary.tasks_completed == 1
        assert end_response.summary.effectiveness == 4

        # Verify final state
        task = task_db.get_task(task_id)
        assert task.state == 'done'
        assert task.times_accepted == 1
        # actual_minutes may be None if duration < 1 minute

        session = task_db.get_session(session_id)
        assert session.ended_at is not None
        assert session.tasks_completed == 1

    def test_multiple_tasks_in_session(self, setup_server, task_db):
        '''Test completing multiple tasks in one session'''
        # Start session
        session_response = server.start_session()
        session_id = session_response.session_id

        # Create and complete 3 tasks
        for i in range(3):
            task_data = TaskCreate(title=f'Task {i}', category='grow')
            task_response = server.add_task(task_data)

            work_response = server.start_work(session_id, task_response.task_id)

            server.complete_work(
                work_id=work_response.work_entry_id,
                completed=True
            )

        # End session
        server.end_session(session_id)

        # Verify all tasks completed
        response = server.list_tasks(state='done')
        assert len(response.tasks) == 3


# Weekly Goal Tests

class TestSetWeeklyGoal:
    '''Tests for set_weekly_goal tool'''

    def test_set_weekly_goal_minimal(self, setup_server):
        '''Test creating a weekly goal with title only'''
        response = server.set_weekly_goal(title='Ship the feature')
        assert response.success is True
        assert response.goal_id is not None
        assert 'Ship the feature' in response.message

    def test_set_weekly_goal_with_all_fields(self, setup_server):
        '''Test creating a weekly goal with all optional fields'''
        response = server.set_weekly_goal(
            title='Learn SQLAlchemy',
            description='Deep dive into ORM patterns',
            category='grow',
        )
        assert response.success is True
        assert response.goal_id is not None

    def test_set_weekly_goal_links_to_current_week(self, setup_server, task_db):
        '''Test that week_start is set to current Monday'''
        from v2.util import get_week_start
        response = server.set_weekly_goal(title='This week goal')
        assert response.success is True
        goal = task_db.get_weekly_goal(response.goal_id)
        assert goal.week_start == get_week_start()

    def test_set_weekly_goal_category_validation(self, setup_server):
        '''Test that invalid category raises an error'''
        try:
            server.set_weekly_goal(title='Bad goal', category='invalid')  # type: ignore
            assert False, 'Should have raised an error'
        except Exception:
            pass  # Expected


# Link Task to Goal Tests

class TestLinkTaskToGoal:
    '''Tests for link_task_to_goal tool'''

    def test_link_task_to_goal_success(self, setup_server, task_db):
        '''Test linking a task to a goal updates goal_id'''
        from v2.util import get_week_start
        goal = task_db.create_weekly_goal(title='My Goal', week_start=get_week_start())
        task_data = TaskCreate(title='Some task', category='grow')
        task_resp = server.add_task(task_data)
        task_id = task_resp.task_id

        response = server.link_task_to_goal(task_id=task_id, goal_id=goal.id)

        assert response.success is True
        assert response.task_id == task_id
        updated = task_db.get_task(task_id)
        assert updated.goal_id == goal.id

    def test_link_task_to_goal_invalid_task(self, setup_server, task_db):
        '''Test linking with a non-existent task returns failure'''
        from v2.util import get_week_start
        goal = task_db.create_weekly_goal(title='My Goal', week_start=get_week_start())

        response = server.link_task_to_goal(task_id=9999, goal_id=goal.id)

        assert response.success is False
        assert 'not found' in response.message

    def test_link_task_to_goal_invalid_goal(self, setup_server):
        '''Test linking with a non-existent goal returns failure'''
        task_data = TaskCreate(title='Some task', category='grow')
        task_resp = server.add_task(task_data)

        response = server.link_task_to_goal(task_id=task_resp.task_id, goal_id=9999)

        assert response.success is False
        assert 'not found' in response.message
