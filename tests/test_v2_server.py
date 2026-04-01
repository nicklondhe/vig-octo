'''Unit tests for v2 MCP server'''

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from v2.db import TaskDB
from v2.models import Base, TaskCreate, WorkEntryModel
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

    def test_list_tasks_lightweight_schema(self, setup_server, task_db):
        '''Test that list_tasks returns lightweight TaskSummary, not full Task'''
        task_db.create_task('Task 1', 'grow', est_minutes=30)

        response = server.list_tasks()

        assert response.success is True
        task = response.tasks[0]
        # Fields that should be present
        assert task.id is not None
        assert task.title == 'Task 1'
        assert task.category == 'grow'
        assert task.state == 'ready'
        assert task.est_minutes == 30
        # Learning/stat fields should not exist on the summary
        assert not hasattr(task, 'times_suggested')
        assert not hasattr(task, 'times_accepted')
        assert not hasattr(task, 'avg_energy_after')
        assert not hasattr(task, 'created_at')
        assert not hasattr(task, 'completed_at')


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
        assert response.started_at is not None

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
        assert response.started_at is not None
        assert response.minutes_spent is not None and response.minutes_spent >= 0

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
        # But last_completed_at must be set so daily_triage can track cadence
        assert updated_task.last_completed_at is not None

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
        '''Test that an invalid category returns a failure response'''
        response = server.set_weekly_goal(title='Bad goal', category='invalid')  # type: ignore
        assert response.success is False
        assert response.goal_id is None


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


# Weekly Review Tests

class TestWeeklyReview:
    '''Tests for weekly_review tool'''

    def test_weekly_review_no_goal(self, setup_server):
        '''Test review when no goal exists for current week'''
        response = server.weekly_review()
        assert response.success is True
        assert response.goal_id is None
        assert 'No active goal' in response.message

    def test_weekly_review_with_goal_no_tasks(self, setup_server):
        '''Test review with a goal but no linked tasks'''
        server.set_weekly_goal(title='Ship feature X')
        response = server.weekly_review()
        assert response.success is True
        assert response.goal_title == 'Ship feature X'
        assert response.tasks_total == 0
        assert response.tasks_completed == 0
        assert response.completion_pct == 0.0

    def test_weekly_review_with_tasks(self, setup_server, task_db):
        '''Test review calculates completed tasks and time invested'''
        from v2.util import get_week_start
        goal = task_db.create_weekly_goal(title='Focus week', week_start=get_week_start())

        # Create 3 tasks linked to goal, complete 2
        for i in range(3):
            task_data = TaskCreate(title=f'Task {i}', category='grow', est_minutes=30)
            task_resp = server.add_task(task_data)
            server.link_task_to_goal(task_id=task_resp.task_id, goal_id=goal.id)

        # Complete 2 tasks via session workflow
        session_resp = server.start_session()
        session_id = session_resp.session_id
        tasks = task_db.get_tasks_by_goal(goal.id)
        for task in tasks[:2]:
            work_resp = server.start_work(session_id, task.id)
            server.complete_work(work_id=work_resp.work_entry_id, completed=True)
        server.end_session(session_id)

        response = server.weekly_review()
        assert response.success is True
        assert response.tasks_total == 3
        assert response.tasks_completed == 2
        assert response.completion_pct == pytest.approx(66.7, abs=0.1)

    def test_weekly_review_completion_pct(self, setup_server, task_db):
        '''Test review reports 100% when all tasks completed'''
        from v2.util import get_week_start
        goal = task_db.create_weekly_goal(title='All done', week_start=get_week_start())
        task_data = TaskCreate(title='Only task', category='maintain')
        task_resp = server.add_task(task_data)
        server.link_task_to_goal(task_id=task_resp.task_id, goal_id=goal.id)

        session_resp = server.start_session()
        work_resp = server.start_work(session_resp.session_id, task_resp.task_id)
        server.complete_work(work_id=work_resp.work_entry_id, completed=True)
        server.end_session(session_resp.session_id)

        response = server.weekly_review()
        assert response.success is True
        assert response.tasks_completed == 1
        assert response.completion_pct == 100.0

    def test_weekly_review_single_active_goal_enforced(self, setup_server):
        '''Test that set_weekly_goal blocks a second active goal for the same week'''
        first = server.set_weekly_goal(title='Older goal')
        assert first.success is True

        second = server.set_weekly_goal(title='Newer goal')
        assert second.success is False
        assert second.goal_id == first.goal_id  # returns the conflicting goal's id

        # weekly_review still reports on the one active goal unambiguously
        response = server.weekly_review()
        assert response.success is True
        assert response.goal_title == 'Older goal'


# Reset Tasks Tests

class TestResetTasks:
    '''Tests for reset_tasks tool'''

    def test_reset_tasks_success(self, setup_server, task_db):
        '''Test resetting done tasks back to ready'''
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')
        task_db.update_task_state(task1.id, 'done')
        task_db.update_task_state(task2.id, 'done')

        response = server.reset_tasks([task1.id, task2.id])

        assert response.success is True
        assert response.reset_count == 2
        assert task1.id in response.task_ids
        assert task2.id in response.task_ids

        # Verify state was reset
        t1 = task_db.get_task(task1.id)
        assert t1.state == 'ready'
        assert t1.completed_at is None

    def test_reset_tasks_partial(self, setup_server, task_db):
        '''Test resetting with a mix of valid and invalid task IDs'''
        task = task_db.create_task('Task 1', 'grow')
        task_db.update_task_state(task.id, 'done')

        response = server.reset_tasks([task.id, 9999])

        assert response.success is True
        assert response.reset_count == 1
        assert task.id in response.task_ids

    def test_reset_tasks_empty_list(self, setup_server):
        '''Test resetting with empty list returns failure'''
        response = server.reset_tasks([])

        assert response.success is False
        assert response.reset_count == 0

    def test_reset_tasks_preserves_learning_data(self, setup_server, task_db):
        '''Test that reset preserves learning stats and last_completed_at'''
        task = task_db.create_task('Repeatable', 'grow', repeatable=True)
        task_db.increment_task_stat(task.id, 'accepted')
        task_db.update_task_state(task.id, 'done')

        before = task_db.get_task(task.id)
        assert before.last_completed_at is not None  # set when marked done

        server.reset_tasks([task.id])

        updated = task_db.get_task(task.id)
        assert updated.state == 'ready'
        assert updated.times_accepted == 1  # learning data preserved
        assert updated.last_completed_at == before.last_completed_at  # last_completed_at preserved


# Daily Triage Tests

class TestDailyTriage:
    '''Tests for daily_triage tool'''

    def test_daily_triage_empty(self, setup_server):
        '''Test daily triage with no completed repeatables'''
        response = server.daily_triage()

        assert response.success is True
        assert len(response.tasks) == 0

    def test_daily_triage_shows_completed_repeatables(self, setup_server, task_db):
        '''Test daily triage returns completed repeatable tasks'''
        task = task_db.create_task('Morning workout', 'maintain', repeatable=True)
        task_db.update_task_state(task.id, 'done')  # sets last_completed_at

        response = server.daily_triage()

        assert response.success is True
        assert len(response.tasks) == 1
        assert response.tasks[0].task_id == task.id
        assert response.tasks[0].title == 'Morning workout'
        assert response.tasks[0].days_since_completion >= 0

    def test_daily_triage_excludes_non_repeatables(self, setup_server, task_db):
        '''Test daily triage does not include non-repeatable tasks'''
        repeatable = task_db.create_task('Repeatable', 'grow', repeatable=True)
        non_repeatable = task_db.create_task('One-off', 'grow', repeatable=False)
        task_db.update_task_state(repeatable.id, 'done')
        task_db.update_task_state(non_repeatable.id, 'done')

        response = server.daily_triage()

        assert response.success is True
        assert len(response.tasks) == 1
        assert response.tasks[0].task_id == repeatable.id

    def test_daily_triage_excludes_never_completed_repeatables(self, setup_server, task_db):
        '''Test daily triage excludes repeatables that were never completed'''
        task_db.create_task('Not done yet', 'grow', repeatable=True)

        response = server.daily_triage()

        assert response.success is True
        assert len(response.tasks) == 0


# Get Stats Tests

class TestGetStats:
    '''Tests for get_stats tool'''

    def test_get_stats_empty_db(self, setup_server):
        '''Test get_stats with no completed work'''
        response = server.get_stats(days=7)

        assert response.success is True
        assert response.tasks_completed == 0
        assert response.total_minutes == 0
        assert response.category_distribution == {}
        assert response.current_streak == 0
        assert response.days == 7

    def test_get_stats_invalid_days(self, setup_server):
        '''Test get_stats with invalid days parameter'''
        response = server.get_stats(days=0)

        assert response.success is False
        assert 'greater than 0' in response.message

    def test_get_stats_counts_completed_tasks(self, setup_server, task_db):
        '''Test get_stats counts completed tasks correctly'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')
        task3 = task_db.create_task('Task 3', 'grow')

        # Complete task1 and task2, leave task3 incomplete
        we1 = task_db.start_work_entry(session.id, task1.id)
        task_db.complete_work_entry(we1.id, completed=True)

        we2 = task_db.start_work_entry(session.id, task2.id)
        task_db.complete_work_entry(we2.id, completed=True)

        we3 = task_db.start_work_entry(session.id, task3.id)
        task_db.complete_work_entry(we3.id, completed=False)

        response = server.get_stats(days=7)

        assert response.success is True
        assert response.tasks_completed == 2

    def test_get_stats_category_distribution(self, setup_server, task_db):
        '''Test get_stats returns correct category distribution'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'grow')
        task3 = task_db.create_task('Task 3', 'maintain')

        for task in [task1, task2, task3]:
            we = task_db.start_work_entry(session.id, task.id)
            task_db.complete_work_entry(we.id, completed=True)

        response = server.get_stats(days=7)

        assert response.success is True
        assert response.category_distribution.get('grow') == 2
        assert response.category_distribution.get('maintain') == 1

    def test_get_stats_default_days(self, setup_server):
        '''Test get_stats uses 7 days as default'''
        response = server.get_stats()

        assert response.success is True
        assert response.days == 7

    def test_get_stats_streak_today(self, setup_server, task_db):
        '''Test streak is 1 when there is a completed task today'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        we = task_db.start_work_entry(session.id, task.id)
        task_db.complete_work_entry(we.id, completed=True)

        response = server.get_stats(days=7)

        assert response.success is True
        assert response.current_streak == 1

    def test_get_stats_total_minutes(self, setup_server, task_db):
        '''Test total_minutes sums actual work entry durations'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        we = task_db.start_work_entry(session.id, task.id)

        # Backdate started_at so the duration is measurable
        thirty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
        with task_db.SessionLocal() as db_session:
            model = db_session.query(WorkEntryModel).filter_by(id=we.id).first()
            model.started_at = thirty_min_ago
            db_session.commit()

        task_db.complete_work_entry(we.id, completed=True)

        response = server.get_stats(days=7)

        assert response.success is True
        assert response.total_minutes >= 30

    def test_get_stats_streak_multi_day(self, setup_server, task_db):
        '''Test streak counts consecutive days correctly'''
        session = task_db.create_session()

        for days_ago in [0, 1, 2]:
            task = task_db.create_task(f'Task {days_ago}', 'grow')
            we = task_db.start_work_entry(session.id, task.id)
            task_db.complete_work_entry(we.id, completed=True)
            # Backdate both timestamps — streak uses ended_at for the activity date
            entry_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=1)
            with task_db.SessionLocal() as db_session:
                model = db_session.query(WorkEntryModel).filter_by(id=we.id).first()
                model.started_at = entry_time
                model.ended_at = entry_time + timedelta(minutes=30)
                db_session.commit()

        response = server.get_stats(days=7)

        assert response.success is True
        assert response.current_streak == 3

    def test_get_stats_streak_with_gap(self, setup_server, task_db):
        '''Test streak resets at a gap — only today counts when yesterday is missing'''
        session = task_db.create_session()

        # Entry today and two days ago, nothing yesterday
        for days_ago in [0, 2]:
            task = task_db.create_task(f'Task {days_ago}', 'grow')
            we = task_db.start_work_entry(session.id, task.id)
            task_db.complete_work_entry(we.id, completed=True)
            entry_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=1)
            with task_db.SessionLocal() as db_session:
                model = db_session.query(WorkEntryModel).filter_by(id=we.id).first()
                model.started_at = entry_time
                model.ended_at = entry_time + timedelta(minutes=30)
                db_session.commit()

        response = server.get_stats(days=7)

        assert response.success is True
        assert response.current_streak == 1  # yesterday breaks the chain
