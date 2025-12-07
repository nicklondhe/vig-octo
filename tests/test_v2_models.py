'''
Unit tests for v2 models (Pydantic and SQLAlchemy).
'''
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from v2.models import (
    Base,
    WeeklyGoalModel,
    TaskModel,
    SessionModel,
    WorkEntryModel,
    WeeklyGoal,
    Task,
    Session,
    WorkEntry,
)


@pytest.fixture
def db_engine():
    '''Create an in-memory SQLite database for testing.'''
    engine = create_engine('sqlite:///:memory:', echo=False)

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    '''Create a database session for testing.'''
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestWeeklyGoalPydantic:
    '''Tests for WeeklyGoal Pydantic model validation.'''

    def test_valid_goal_creation(self):
        '''Test creating a valid weekly goal.'''
        goal = WeeklyGoal(
            title='Complete project',
            category='grow',
            week_start=datetime.now(timezone.utc)
        )
        assert goal.title == 'Complete project'
        assert goal.category == 'grow'
        assert goal.status == 'active'
        assert goal.created_at is not None

    def test_title_min_length(self):
        '''Test title must have minimum length.'''
        with pytest.raises(ValueError):
            WeeklyGoal(
                title='',
                week_start=datetime.now(timezone.utc)
            )

    def test_title_max_length(self):
        '''Test title maximum length constraint.'''
        long_title = 'a' * 501
        with pytest.raises(ValueError):
            WeeklyGoal(
                title=long_title,
                week_start=datetime.now(timezone.utc)
            )

    def test_invalid_category(self):
        '''Test invalid category value is rejected.'''
        with pytest.raises(ValueError):
            WeeklyGoal(
                title='Test',
                category='invalid',
                week_start=datetime.now(timezone.utc)
            )

    def test_invalid_status(self):
        '''Test invalid status value is rejected.'''
        with pytest.raises(ValueError):
            WeeklyGoal(
                title='Test',
                status='invalid',
                week_start=datetime.now(timezone.utc)
            )

    def test_optional_description(self):
        '''Test description is optional.'''
        goal = WeeklyGoal(
            title='Test',
            week_start=datetime.now(timezone.utc)
        )
        assert goal.description is None

    def test_description_max_length(self):
        '''Test description maximum length constraint.'''
        long_desc = 'a' * 2001
        with pytest.raises(ValueError):
            WeeklyGoal(
                title='Test',
                description=long_desc,
                week_start=datetime.now(timezone.utc)
            )


class TestTaskPydantic:
    '''Tests for Task Pydantic model validation.'''

    def test_valid_task_creation(self):
        '''Test creating a valid task.'''
        task = Task(
            title='Write tests',
            category='grow',
            est_minutes=60
        )
        assert task.title == 'Write tests'
        assert task.category == 'grow'
        assert task.state == 'ready'
        assert task.repeatable is False
        assert task.created_at is not None

    def test_est_minutes_positive(self):
        '''Test est_minutes must be positive.'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', est_minutes=0)

    def test_est_minutes_max_value(self):
        '''Test est_minutes cannot exceed 1440 (24 hours).'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', est_minutes=1441)

    def test_actual_minutes_positive(self):
        '''Test actual_minutes must be positive.'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', actual_minutes=0)

    def test_avg_energy_range(self):
        '''Test avg_energy_after must be between 1 and 5.'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', avg_energy_after=0.5)
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', avg_energy_after=5.5)

    def test_completed_at_requires_done_state(self):
        '''Test completed_at can only be set when state is done or archived.'''
        with pytest.raises(ValueError):
            Task(
                title='Test',
                category='grow',
                state='ready',
                completed_at=datetime.now(timezone.utc)
            )

    def test_completed_at_allowed_for_done(self):
        '''Test completed_at is allowed when state is done.'''
        task = Task(
            title='Test',
            category='grow',
            state='done',
            completed_at=datetime.now(timezone.utc)
        )
        assert task.completed_at is not None

    def test_completed_at_allowed_for_archived(self):
        '''Test completed_at is allowed when state is archived.'''
        task = Task(
            title='Test',
            category='grow',
            state='archived',
            completed_at=datetime.now(timezone.utc)
        )
        assert task.completed_at is not None

    def test_invalid_state(self):
        '''Test invalid state value is rejected.'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', state='invalid')

    def test_times_suggested_negative(self):
        '''Test times_suggested must be non-negative.'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', times_suggested=-1)

    def test_times_accepted_negative(self):
        '''Test times_accepted must be non-negative.'''
        with pytest.raises(ValueError):
            Task(title='Test', category='grow', times_accepted=-1)


class TestSessionPydantic:
    '''Tests for Session Pydantic model validation.'''

    def test_valid_session_creation(self):
        '''Test creating a valid session.'''
        session = Session()
        assert session.started_at is not None
        assert session.tasks_completed == 0

    def test_available_minutes_positive(self):
        '''Test available_minutes must be positive.'''
        with pytest.raises(ValueError):
            Session(available_minutes=0)

    def test_available_minutes_max(self):
        '''Test available_minutes cannot exceed 1440.'''
        with pytest.raises(ValueError):
            Session(available_minutes=1441)

    def test_energy_level_range(self):
        '''Test energy_level must be between 1 and 5.'''
        with pytest.raises(ValueError):
            Session(energy_level=0)
        with pytest.raises(ValueError):
            Session(energy_level=6)

    def test_effectiveness_range(self):
        '''Test effectiveness must be between 1 and 5.'''
        with pytest.raises(ValueError):
            Session(effectiveness=0)
        with pytest.raises(ValueError):
            Session(effectiveness=6)

    def test_ended_at_after_started_at(self):
        '''Test ended_at must be after started_at.'''
        started = datetime.now(timezone.utc)
        ended = started - timedelta(hours=1)
        with pytest.raises(ValueError):
            Session(started_at=started, ended_at=ended)

    def test_ended_at_valid(self):
        '''Test valid ended_at is accepted.'''
        started = datetime.now(timezone.utc)
        ended = started + timedelta(hours=1)
        session = Session(started_at=started, ended_at=ended)
        assert session.ended_at == ended

    def test_invalid_focus_area(self):
        '''Test invalid focus_area is rejected.'''
        with pytest.raises(ValueError):
            Session(focus_area='invalid')


class TestWorkEntryPydantic:
    '''Tests for WorkEntry Pydantic model validation.'''

    def test_valid_work_entry_creation(self):
        '''Test creating a valid work entry.'''
        entry = WorkEntry(session_id=1, task_id=1)
        assert entry.session_id == 1
        assert entry.task_id == 1
        assert entry.completed is False
        assert entry.started_at is not None

    def test_energy_after_range(self):
        '''Test energy_after must be between 1 and 5.'''
        with pytest.raises(ValueError):
            WorkEntry(session_id=1, task_id=1, energy_after=0)
        with pytest.raises(ValueError):
            WorkEntry(session_id=1, task_id=1, energy_after=6)

    def test_ended_at_after_started_at(self):
        '''Test ended_at must be after started_at.'''
        started = datetime.now(timezone.utc)
        ended = started - timedelta(minutes=30)
        with pytest.raises(ValueError):
            WorkEntry(session_id=1, task_id=1, started_at=started, ended_at=ended)

    def test_abandoned_reason_with_completed(self):
        '''Test abandoned_reason cannot be set when completed is True.'''
        with pytest.raises(ValueError):
            WorkEntry(
                session_id=1,
                task_id=1,
                completed=True,
                abandoned_reason='blocked'
            )

    def test_abandoned_reason_without_completed(self):
        '''Test abandoned_reason can be set when completed is False.'''
        entry = WorkEntry(
            session_id=1,
            task_id=1,
            completed=False,
            abandoned_reason='blocked'
        )
        assert entry.abandoned_reason == 'blocked'

    def test_invalid_abandoned_reason(self):
        '''Test invalid abandoned_reason is rejected.'''
        with pytest.raises(ValueError):
            WorkEntry(session_id=1, task_id=1, abandoned_reason='invalid')


class TestWeeklyGoalModel:
    '''Tests for WeeklyGoalModel SQLAlchemy model.'''

    def test_create_goal(self, db_session):
        '''Test creating a goal in the database.'''
        goal = WeeklyGoalModel(
            title='Test Goal',
            week_start=datetime.now(timezone.utc)
        )
        db_session.add(goal)
        db_session.commit()

        assert goal.id is not None
        assert goal.created_at is not None
        assert goal.status == 'active'

    def test_goal_category_constraint(self, db_session):
        '''Test category check constraint.'''
        goal = WeeklyGoalModel(
            title='Test',
            category='invalid',
            week_start=datetime.now(timezone.utc)
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_goal_status_constraint(self, db_session):
        '''Test status check constraint.'''
        goal = WeeklyGoalModel(
            title='Test',
            status='invalid',
            week_start=datetime.now(timezone.utc)
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_goal_cascade_delete(self, db_session):
        '''Test that deleting a goal cascades to tasks.'''
        goal = WeeklyGoalModel(
            title='Test Goal',
            week_start=datetime.now(timezone.utc)
        )
        db_session.add(goal)
        db_session.commit()

        task = TaskModel(
            title='Test Task',
            category='grow',
            goal_id=goal.id
        )
        db_session.add(task)
        db_session.commit()

        task_id = task.id
        db_session.delete(goal)
        db_session.commit()

        # Task should be deleted due to cascade
        deleted_task = db_session.get(TaskModel, task_id)
        assert deleted_task is None


class TestTaskModel:
    '''Tests for TaskModel SQLAlchemy model.'''

    def test_create_task(self, db_session):
        '''Test creating a task in the database.'''
        task = TaskModel(
            title='Test Task',
            category='grow'
        )
        db_session.add(task)
        db_session.commit()

        assert task.id is not None
        assert task.created_at is not None
        assert task.state == 'ready'
        assert task.repeatable is False
        assert task.times_suggested == 0

    def test_task_category_constraint(self, db_session):
        '''Test category check constraint.'''
        task = TaskModel(title='Test', category='invalid')
        db_session.add(task)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_task_state_constraint(self, db_session):
        '''Test state check constraint.'''
        task = TaskModel(title='Test', category='grow', state='invalid')
        db_session.add(task)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_task_foreign_key_constraint(self, db_session):
        '''Test foreign key constraint for goal_id.'''
        task = TaskModel(
            title='Test',
            category='grow',
            goal_id=999  # Non-existent goal
        )
        db_session.add(task)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_task_with_goal(self, db_session):
        '''Test task with valid goal relationship.'''
        goal = WeeklyGoalModel(
            title='Test Goal',
            week_start=datetime.now(timezone.utc)
        )
        db_session.add(goal)
        db_session.commit()

        task = TaskModel(
            title='Test Task',
            category='grow',
            goal_id=goal.id
        )
        db_session.add(task)
        db_session.commit()

        assert task.goal == goal
        assert task in goal.tasks

    def test_task_cascade_delete_work_entries(self, db_session):
        '''Test that deleting a task cascades to work entries.'''
        task = TaskModel(title='Test', category='grow')
        session_model = SessionModel()
        db_session.add(task)
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=task.id
        )
        db_session.add(entry)
        db_session.commit()

        entry_id = entry.id
        db_session.delete(task)
        db_session.commit()

        # Work entry should be deleted due to cascade
        deleted_entry = db_session.get(WorkEntryModel, entry_id)
        assert deleted_entry is None


class TestSessionModel:
    '''Tests for SessionModel SQLAlchemy model.'''

    def test_create_session(self, db_session):
        '''Test creating a session in the database.'''
        session_model = SessionModel()
        db_session.add(session_model)
        db_session.commit()

        assert session_model.id is not None
        assert session_model.started_at is not None
        assert session_model.tasks_completed == 0

    def test_session_energy_level_constraint(self, db_session):
        '''Test energy_level check constraint.'''
        session_model = SessionModel(energy_level=6)
        db_session.add(session_model)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_session_effectiveness_constraint(self, db_session):
        '''Test effectiveness check constraint.'''
        session_model = SessionModel(effectiveness=0)
        db_session.add(session_model)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_session_focus_area_constraint(self, db_session):
        '''Test focus_area check constraint.'''
        session_model = SessionModel(focus_area='invalid')
        db_session.add(session_model)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_session_cascade_delete_work_entries(self, db_session):
        '''Test that deleting a session cascades to work entries.'''
        task = TaskModel(title='Test', category='grow')
        session_model = SessionModel()
        db_session.add(task)
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=task.id
        )
        db_session.add(entry)
        db_session.commit()

        entry_id = entry.id
        db_session.delete(session_model)
        db_session.commit()

        # Work entry should be deleted due to cascade
        deleted_entry = db_session.get(WorkEntryModel, entry_id)
        assert deleted_entry is None


class TestWorkEntryModel:
    '''Tests for WorkEntryModel SQLAlchemy model.'''

    def test_create_work_entry(self, db_session):
        '''Test creating a work entry in the database.'''
        task = TaskModel(title='Test', category='grow')
        session_model = SessionModel()
        db_session.add(task)
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=task.id
        )
        db_session.add(entry)
        db_session.commit()

        assert entry.id is not None
        assert entry.started_at is not None
        assert entry.completed is False

    def test_work_entry_energy_after_constraint(self, db_session):
        '''Test energy_after check constraint.'''
        task = TaskModel(title='Test', category='grow')
        session_model = SessionModel()
        db_session.add(task)
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=task.id,
            energy_after=6
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_work_entry_abandoned_reason_constraint(self, db_session):
        '''Test abandoned_reason check constraint.'''
        task = TaskModel(title='Test', category='grow')
        session_model = SessionModel()
        db_session.add(task)
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=task.id,
            abandoned_reason='invalid'
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_work_entry_foreign_key_session(self, db_session):
        '''Test foreign key constraint for session_id.'''
        task = TaskModel(title='Test', category='grow')
        db_session.add(task)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=999,  # Non-existent session
            task_id=task.id
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_work_entry_foreign_key_task(self, db_session):
        '''Test foreign key constraint for task_id.'''
        session_model = SessionModel()
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=999  # Non-existent task
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_work_entry_relationships(self, db_session):
        '''Test work entry relationships with session and task.'''
        task = TaskModel(title='Test', category='grow')
        session_model = SessionModel()
        db_session.add(task)
        db_session.add(session_model)
        db_session.commit()

        entry = WorkEntryModel(
            session_id=session_model.id,
            task_id=task.id
        )
        db_session.add(entry)
        db_session.commit()

        assert entry.session == session_model
        assert entry.task == task
        assert entry in session_model.work_entries
        assert entry in task.work_entries


class TestEdgeCases:
    '''Tests for edge cases and boundary conditions.'''

    def test_task_with_zero_energy_learning_data(self, db_session):
        '''Test task with zero learning data is valid.'''
        task = TaskModel(
            title='Test',
            category='grow',
            times_suggested=0,
            times_accepted=0,
            times_rejected=0
        )
        db_session.add(task)
        db_session.commit()
        assert task.id is not None

    def test_repeatable_task_with_last_completed(self, db_session):
        '''Test repeatable task can have last_completed_at.'''
        task = TaskModel(
            title='Test',
            category='maintain',
            repeatable=True,
            last_completed_at=datetime.now(timezone.utc)
        )
        db_session.add(task)
        db_session.commit()
        assert task.last_completed_at is not None

    def test_session_with_no_work_entries(self, db_session):
        '''Test session with no work entries is valid.'''
        session_model = SessionModel()
        db_session.add(session_model)
        db_session.commit()
        assert len(session_model.work_entries) == 0

    def test_goal_with_no_tasks(self, db_session):
        '''Test goal with no tasks is valid.'''
        goal = WeeklyGoalModel(
            title='Empty Goal',
            week_start=datetime.now(timezone.utc)
        )
        db_session.add(goal)
        db_session.commit()
        assert len(goal.tasks) == 0

    def test_task_without_goal(self, db_session):
        '''Test task without a goal is valid.'''
        task = TaskModel(
            title='Standalone Task',
            category='grow',
            goal_id=None
        )
        db_session.add(task)
        db_session.commit()
        assert task.goal is None

    def test_pydantic_model_from_orm(self, db_session):
        '''Test creating Pydantic models from ORM instances.'''
        task_model = TaskModel(
            title='Test',
            category='grow',
            est_minutes=30
        )
        db_session.add(task_model)
        db_session.commit()

        # Refresh to get auto-generated values
        db_session.refresh(task_model)

        # Create Pydantic model from ORM
        task_pydantic = Task.model_validate(task_model)
        assert task_pydantic.title == 'Test'
        assert task_pydantic.category == 'grow'
        assert task_pydantic.est_minutes == 30

    def test_multiple_work_entries_same_task(self, db_session):
        '''Test multiple work entries can reference the same task.'''
        task = TaskModel(title='Test', category='grow')
        session1 = SessionModel()
        session2 = SessionModel()
        db_session.add_all([task, session1, session2])
        db_session.commit()

        entry1 = WorkEntryModel(session_id=session1.id, task_id=task.id)
        entry2 = WorkEntryModel(session_id=session2.id, task_id=task.id)
        db_session.add_all([entry1, entry2])
        db_session.commit()

        assert len(task.work_entries) == 2

    def test_max_est_minutes_boundary(self):
        '''Test est_minutes at boundary value (1440 minutes = 24 hours).'''
        task = Task(title='Test', category='grow', est_minutes=1440)
        assert task.est_minutes == 1440

    def test_energy_level_boundaries(self):
        '''Test energy level at boundary values.'''
        session1 = Session(energy_level=1)
        session5 = Session(energy_level=5)
        assert session1.energy_level == 1
        assert session5.energy_level == 5
