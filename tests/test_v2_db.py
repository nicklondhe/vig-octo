'''
Unit tests for v2 TaskDB class.
'''
# pylint: disable=redefined-outer-name
from datetime import timedelta
from sqlalchemy import create_engine, event

import pytest

from v2.db import TaskDB
from v2.models import Base, Session, Task, WeeklyGoal, WorkEntry
from v2.util import get_week_start


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
def task_db(db_engine):
    '''Create a TaskDB instance for testing.'''
    return TaskDB(db_engine)


class TestCreateWeeklyGoal:
    '''Tests for create_weekly_goal method.'''

    def test_create_basic_goal(self, task_db):
        '''Test creating a basic weekly goal.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            title='Complete project',
            week_start=week_start
        )

        assert goal.id is not None
        assert goal.title == 'Complete project'
        assert goal.week_start == week_start
        assert goal.status == 'active'
        assert goal.description is None
        assert goal.category is None
        assert goal.created_at is not None

    def test_create_goal_with_all_fields(self, task_db):
        '''Test creating a goal with all optional fields.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            title='Learn Python',
            week_start=week_start,
            description='Focus on advanced topics',
            category='grow',
            status='active'
        )

        assert goal.id is not None
        assert goal.title == 'Learn Python'
        assert goal.description == 'Focus on advanced topics'
        assert goal.category == 'grow'
        assert goal.status == 'active'

    def test_create_goal_with_different_categories(self, task_db):
        '''Test creating goals with different category values.'''
        week_start = get_week_start()

        for category in ['grow', 'maintain', 'sustain']:
            goal = task_db.create_weekly_goal(
                title=f'Test {category}',
                week_start=week_start,
                category=category
            )
            assert goal.category == category

    def test_create_goal_with_different_statuses(self, task_db):
        '''Test creating goals with different status values.'''
        week_start = get_week_start()

        for status in ['active', 'completed', 'archived']:
            goal = task_db.create_weekly_goal(
                title=f'Test {status}',
                week_start=week_start,
                status=status
            )
            assert goal.status == status

    def test_create_multiple_goals_same_week(self, task_db):
        '''Test creating multiple goals for the same week.'''
        week_start = get_week_start()

        goal1 = task_db.create_weekly_goal('Goal 1', week_start)
        goal2 = task_db.create_weekly_goal('Goal 2', week_start)

        assert goal1.id != goal2.id
        assert goal1.week_start == goal2.week_start


class TestGetWeeklyGoal:
    '''Tests for get_weekly_goal method.'''

    def test_get_existing_goal(self, task_db):
        '''Test getting an existing goal by ID.'''
        week_start = get_week_start()
        created_goal = task_db.create_weekly_goal(
            title='Test Goal',
            week_start=week_start
        )

        retrieved_goal = task_db.get_weekly_goal(created_goal.id)

        assert retrieved_goal is not None
        assert retrieved_goal.id == created_goal.id
        assert retrieved_goal.title == created_goal.title
        assert retrieved_goal.week_start == created_goal.week_start

    def test_get_nonexistent_goal(self, task_db):
        '''Test getting a goal with non-existent ID returns None.'''
        goal = task_db.get_weekly_goal(999)
        assert goal is None

    def test_get_goal_with_all_fields(self, task_db):
        '''Test getting a goal preserves all fields.'''
        week_start = get_week_start()
        created_goal = task_db.create_weekly_goal(
            title='Full Goal',
            week_start=week_start,
            description='Detailed description',
            category='maintain',
            status='completed'
        )

        retrieved_goal = task_db.get_weekly_goal(created_goal.id)

        assert retrieved_goal.description == 'Detailed description'
        assert retrieved_goal.category == 'maintain'
        assert retrieved_goal.status == 'completed'


class TestGetGoalsByWeek:
    '''Tests for get_goals_by_week method.'''

    def test_get_goals_for_empty_week(self, task_db):
        '''Test getting goals for a week with no goals.'''
        week_start = get_week_start()
        goals = task_db.get_goals_by_week(week_start)
        assert goals == []

    def test_get_goals_for_week_with_goals(self, task_db):
        '''Test getting goals for a week with multiple goals.'''
        week_start = get_week_start()

        goal1 = task_db.create_weekly_goal('Goal 1', week_start)
        goal2 = task_db.create_weekly_goal('Goal 2', week_start)

        goals = task_db.get_goals_by_week(week_start)

        assert len(goals) == 2
        goal_ids = [g.id for g in goals]
        assert goal1.id in goal_ids
        assert goal2.id in goal_ids

    def test_get_goals_filters_by_week(self, task_db):
        '''Test that get_goals_by_week only returns goals for specific week.'''
        this_week = get_week_start()
        next_week = this_week + timedelta(days=7)

        task_db.create_weekly_goal('This Week Goal', this_week)
        task_db.create_weekly_goal('Next Week Goal', next_week)

        this_week_goals = task_db.get_goals_by_week(this_week)
        next_week_goals = task_db.get_goals_by_week(next_week)

        assert len(this_week_goals) == 1
        assert len(next_week_goals) == 1
        assert this_week_goals[0].title == 'This Week Goal'
        assert next_week_goals[0].title == 'Next Week Goal'

    def test_goals_ordered_by_created_at(self, task_db):
        '''Test that goals are ordered by creation time.'''
        week_start = get_week_start()

        goal1 = task_db.create_weekly_goal('First', week_start)
        goal2 = task_db.create_weekly_goal('Second', week_start)
        goal3 = task_db.create_weekly_goal('Third', week_start)

        goals = task_db.get_goals_by_week(week_start)

        assert goals[0].id == goal1.id
        assert goals[1].id == goal2.id
        assert goals[2].id == goal3.id


class TestGetCurrentWeekGoals:
    '''Tests for get_current_week_goals method.'''

    def test_get_current_week_empty(self, task_db):
        '''Test getting current week goals when none exist.'''
        goals = task_db.get_current_week_goals()
        assert goals == []

    def test_get_current_week_goals(self, task_db):
        '''Test getting goals for current week.'''
        current_week = get_week_start()

        goal1 = task_db.create_weekly_goal('Current 1', current_week)
        goal2 = task_db.create_weekly_goal('Current 2', current_week)

        goals = task_db.get_current_week_goals()

        assert len(goals) == 2
        goal_ids = [g.id for g in goals]
        assert goal1.id in goal_ids
        assert goal2.id in goal_ids

    def test_get_current_week_excludes_other_weeks(self, task_db):
        '''Test that get_current_week_goals excludes other weeks.'''
        current_week = get_week_start()
        last_week = current_week - timedelta(days=7)
        next_week = current_week + timedelta(days=7)

        task_db.create_weekly_goal('Last Week', last_week)
        current_goal = task_db.create_weekly_goal('This Week', current_week)
        task_db.create_weekly_goal('Next Week', next_week)

        goals = task_db.get_current_week_goals()

        assert len(goals) == 1
        assert goals[0].id == current_goal.id


class TestUpdateGoalStatus:
    '''Tests for update_goal_status method.'''

    def test_update_status_to_completed(self, task_db):
        '''Test updating goal status to completed.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Test Goal', week_start)

        updated_goal = task_db.update_goal_status(goal.id, 'completed')

        assert updated_goal is not None
        assert updated_goal.id == goal.id
        assert updated_goal.status == 'completed'

    def test_update_status_to_archived(self, task_db):
        '''Test updating goal status to archived.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Test Goal', week_start)

        updated_goal = task_db.update_goal_status(goal.id, 'archived')

        assert updated_goal is not None
        assert updated_goal.status == 'archived'

    def test_update_status_nonexistent_goal(self, task_db):
        '''Test updating status of non-existent goal returns None.'''
        result = task_db.update_goal_status(999, 'completed')
        assert result is None

    def test_update_status_persists(self, task_db):
        '''Test that status update is persisted in database.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Test Goal', week_start)

        task_db.update_goal_status(goal.id, 'completed')
        retrieved_goal = task_db.get_weekly_goal(goal.id)

        assert retrieved_goal.status == 'completed'

    def test_update_status_preserves_other_fields(self, task_db):
        '''Test that updating status doesn't change other fields.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            title='Test Goal',
            week_start=week_start,
            description='Important goal',
            category='grow'
        )

        updated_goal = task_db.update_goal_status(goal.id, 'completed')

        assert updated_goal.title == 'Test Goal'
        assert updated_goal.description == 'Important goal'
        assert updated_goal.category == 'grow'
        assert updated_goal.week_start == week_start


class TestUpdateWeeklyGoal:
    '''Tests for update_weekly_goal method.'''

    def test_update_title(self, task_db):
        '''Test updating goal title.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Old Title', week_start)

        updated_goal = task_db.update_weekly_goal(goal.id, title='New Title')

        assert updated_goal is not None
        assert updated_goal.title == 'New Title'

    def test_update_description(self, task_db):
        '''Test updating goal description.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Goal', week_start)

        updated_goal = task_db.update_weekly_goal(
            goal.id,
            description='New description'
        )

        assert updated_goal.description == 'New description'

    def test_update_category(self, task_db):
        '''Test updating goal category.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            'Goal',
            week_start,
            category='grow'
        )

        updated_goal = task_db.update_weekly_goal(goal.id, category='maintain')

        assert updated_goal.category == 'maintain'

    def test_update_status(self, task_db):
        '''Test updating goal status via update_weekly_goal.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Goal', week_start)

        updated_goal = task_db.update_weekly_goal(goal.id, status='completed')

        assert updated_goal.status == 'completed'

    def test_update_multiple_fields(self, task_db):
        '''Test updating multiple fields at once.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Old', week_start)

        updated_goal = task_db.update_weekly_goal(
            goal.id,
            title='New Title',
            description='New description',
            category='sustain',
            status='archived'
        )

        assert updated_goal.title == 'New Title'
        assert updated_goal.description == 'New description'
        assert updated_goal.category == 'sustain'
        assert updated_goal.status == 'archived'

    def test_update_with_none_values_ignores_fields(self, task_db):
        '''Test that None values don't update fields.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            title='Original',
            week_start=week_start,
            description='Original description',
            category='grow'
        )

        updated_goal = task_db.update_weekly_goal(
            goal.id,
            title=None,
            description=None
        )

        assert updated_goal.title == 'Original'
        assert updated_goal.description == 'Original description'

    def test_update_nonexistent_goal(self, task_db):
        '''Test updating non-existent goal returns None.'''
        result = task_db.update_weekly_goal(999, title='New')
        assert result is None

    def test_update_persists(self, task_db):
        '''Test that updates are persisted in database.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Original', week_start)

        task_db.update_weekly_goal(goal.id, title='Updated')
        retrieved_goal = task_db.get_weekly_goal(goal.id)

        assert retrieved_goal.title == 'Updated'


class TestGetAllGoals:
    '''Tests for get_all_goals method.'''

    def test_get_all_goals_empty(self, task_db):
        '''Test getting all goals when none exist.'''
        goals = task_db.get_all_goals()
        assert goals == []

    def test_get_all_goals(self, task_db):
        '''Test getting all goals without filters.'''
        week1 = get_week_start()
        week2 = week1 + timedelta(days=7)

        goal1 = task_db.create_weekly_goal('Goal 1', week1)
        goal2 = task_db.create_weekly_goal('Goal 2', week2)

        goals = task_db.get_all_goals()

        assert len(goals) == 2
        goal_ids = [g.id for g in goals]
        assert goal1.id in goal_ids
        assert goal2.id in goal_ids

    def test_get_all_goals_filter_by_status(self, task_db):
        '''Test filtering goals by status.'''
        week_start = get_week_start()

        active_goal = task_db.create_weekly_goal('Active', week_start)
        task_db.create_weekly_goal(
            'Completed',
            week_start,
            status='completed'
        )

        active_goals = task_db.get_all_goals(status='active')

        assert len(active_goals) == 1
        assert active_goals[0].id == active_goal.id

    def test_get_all_goals_filter_by_category(self, task_db):
        '''Test filtering goals by category.'''
        week_start = get_week_start()

        grow_goal = task_db.create_weekly_goal(
            'Grow',
            week_start,
            category='grow'
        )
        task_db.create_weekly_goal(
            'Maintain',
            week_start,
            category='maintain'
        )

        grow_goals = task_db.get_all_goals(category='grow')

        assert len(grow_goals) == 1
        assert grow_goals[0].id == grow_goal.id

    def test_get_all_goals_filter_by_status_and_category(self, task_db):
        '''Test filtering by both status and category.'''
        week_start = get_week_start()

        target_goal = task_db.create_weekly_goal(
            'Target',
            week_start,
            category='grow',
            status='active'
        )
        task_db.create_weekly_goal(
            'Other',
            week_start,
            category='maintain',
            status='active'
        )
        task_db.create_weekly_goal(
            'Another',
            week_start,
            category='grow',
            status='completed'
        )

        filtered_goals = task_db.get_all_goals(
            status='active',
            category='grow'
        )

        assert len(filtered_goals) == 1
        assert filtered_goals[0].id == target_goal.id

    def test_get_all_goals_ordered_by_week_desc(self, task_db):
        '''Test goals are ordered by week_start descending.'''
        old_week = get_week_start() - timedelta(days=14)
        last_week = get_week_start() - timedelta(days=7)
        this_week = get_week_start()

        task_db.create_weekly_goal('Old', old_week)
        task_db.create_weekly_goal('Last', last_week)
        task_db.create_weekly_goal('This', this_week)

        goals = task_db.get_all_goals()

        assert goals[0].title == 'This'
        assert goals[1].title == 'Last'
        assert goals[2].title == 'Old'

    def test_get_all_goals_ordered_by_created_within_week(self, task_db):
        '''Test goals for same week are ordered by created_at.'''
        week_start = get_week_start()

        goal1 = task_db.create_weekly_goal('First', week_start)
        goal2 = task_db.create_weekly_goal('Second', week_start)

        goals = task_db.get_all_goals()

        # Should be ordered by week desc, then created asc
        same_week_goals = [g for g in goals if g.week_start == week_start]
        assert same_week_goals[0].id == goal1.id
        assert same_week_goals[1].id == goal2.id


class TestEdgeCases:
    '''Tests for edge cases and boundary conditions.'''

    def test_create_goal_with_past_week(self, task_db):
        '''Test creating a goal for a past week.'''
        past_week = get_week_start() - timedelta(days=14)
        goal = task_db.create_weekly_goal('Past Goal', past_week)

        assert goal.week_start == past_week

    def test_create_goal_with_future_week(self, task_db):
        '''Test creating a goal for a future week.'''
        future_week = get_week_start() + timedelta(days=14)
        goal = task_db.create_weekly_goal('Future Goal', future_week)

        assert goal.week_start == future_week

    def test_update_goal_clear_description(self, task_db):
        '''Test updating description to empty string.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal(
            'Goal',
            week_start,
            description='Original'
        )

        updated_goal = task_db.update_weekly_goal(goal.id, description='')

        assert updated_goal.description == ''

    def test_multiple_status_transitions(self, task_db):
        '''Test multiple status transitions on same goal.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Goal', week_start)

        # active -> completed -> archived -> active
        task_db.update_goal_status(goal.id, 'completed')
        task_db.update_goal_status(goal.id, 'archived')
        final_goal = task_db.update_goal_status(goal.id, 'active')

        assert final_goal.status == 'active'

    def test_pydantic_model_returned(self, task_db):
        '''Test that all methods return Pydantic WeeklyGoal instances.'''
        week_start = get_week_start()
        created = task_db.create_weekly_goal('Test', week_start)

        assert isinstance(created, WeeklyGoal)

        retrieved = task_db.get_weekly_goal(created.id)
        assert isinstance(retrieved, WeeklyGoal)

        goals_list = task_db.get_goals_by_week(week_start)
        assert all(isinstance(g, WeeklyGoal) for g in goals_list)

        updated = task_db.update_goal_status(created.id, 'completed')
        assert isinstance(updated, WeeklyGoal)


# Task CRUD Tests


class TestCreateTask:
    '''Tests for create_task method.'''

    def test_create_basic_task(self, task_db):
        '''Test creating a basic task.'''
        task = task_db.create_task(
            title='Write tests',
            category='grow'
        )

        assert task.id is not None
        assert task.title == 'Write tests'
        assert task.category == 'grow'
        assert task.state == 'ready'
        assert task.repeatable is False
        assert task.est_minutes is None
        assert task.goal_id is None
        assert task.created_at is not None

    def test_create_task_with_all_fields(self, task_db):
        '''Test creating a task with all optional fields.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Test Goal', week_start)

        task = task_db.create_task(
            title='Complex task',
            category='maintain',
            est_minutes=60,
            repeatable=True,
            goal_id=goal.id,
            state='active'
        )

        assert task.id is not None
        assert task.title == 'Complex task'
        assert task.category == 'maintain'
        assert task.est_minutes == 60
        assert task.repeatable is True
        assert task.goal_id == goal.id
        assert task.state == 'active'

    def test_create_task_with_different_categories(self, task_db):
        '''Test creating tasks with different categories.'''
        for category in ['grow', 'maintain', 'sustain']:
            task = task_db.create_task(
                title=f'Test {category}',
                category=category
            )
            assert task.category == category

    def test_create_task_with_different_states(self, task_db):
        '''Test creating tasks with different states.'''
        for state in ['ready', 'active', 'done', 'archived']:
            task = task_db.create_task(
                title=f'Test {state}',
                category='grow',
                state=state
            )
            assert task.state == state

    def test_create_repeatable_task(self, task_db):
        '''Test creating a repeatable task.'''
        task = task_db.create_task(
            title='Daily review',
            category='maintain',
            repeatable=True
        )

        assert task.repeatable is True
        assert task.last_completed_at is None


class TestGetTask:
    '''Tests for get_task and get_tasks_by_* methods.'''

    def test_get_existing_task(self, task_db):
        '''Test getting an existing task by ID.'''
        created_task = task_db.create_task(
            title='Test Task',
            category='grow'
        )

        retrieved_task = task_db.get_task(created_task.id)

        assert retrieved_task is not None
        assert retrieved_task.id == created_task.id
        assert retrieved_task.title == created_task.title

    def test_get_nonexistent_task(self, task_db):
        '''Test getting a task with non-existent ID returns None.'''
        task = task_db.get_task(999)
        assert task is None

    def test_get_tasks_by_state(self, task_db):
        '''Test getting tasks by state.'''
        task_db.create_task('Ready 1', 'grow', state='ready')
        task_db.create_task('Ready 2', 'maintain', state='ready')
        active_task = task_db.create_task('Active', 'grow', state='active')
        task_db.create_task('Done', 'sustain', state='done')

        ready_tasks = task_db.get_tasks_by_state('ready')
        active_tasks = task_db.get_tasks_by_state('active')

        assert len(ready_tasks) == 2
        assert len(active_tasks) == 1
        assert active_tasks[0].id == active_task.id

    def test_get_tasks_by_goal(self, task_db):
        '''Test getting tasks by goal ID.'''
        week_start = get_week_start()
        goal1 = task_db.create_weekly_goal('Goal 1', week_start)
        goal2 = task_db.create_weekly_goal('Goal 2', week_start)

        task1 = task_db.create_task('Task 1', 'grow', goal_id=goal1.id)
        task2 = task_db.create_task('Task 2', 'maintain', goal_id=goal1.id)
        task_db.create_task('Task 3', 'sustain', goal_id=goal2.id)

        goal1_tasks = task_db.get_tasks_by_goal(goal1.id)

        assert len(goal1_tasks) == 2
        task_ids = [t.id for t in goal1_tasks]
        assert task1.id in task_ids
        assert task2.id in task_ids

    def test_get_tasks_by_category(self, task_db):
        '''Test getting tasks by category.'''
        task_db.create_task('Grow 1', 'grow')
        grow_task2 = task_db.create_task('Grow 2', 'grow')
        task_db.create_task('Maintain', 'maintain')

        grow_tasks = task_db.get_tasks_by_category('grow')

        assert len(grow_tasks) == 2
        assert grow_task2.id in [t.id for t in grow_tasks]

    def test_get_all_tasks_no_filters(self, task_db):
        '''Test getting all tasks without filters.'''
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        tasks = task_db.get_all_tasks()

        assert len(tasks) == 2
        task_ids = [t.id for t in tasks]
        assert task1.id in task_ids
        assert task2.id in task_ids

    def test_get_all_tasks_with_filters(self, task_db):
        '''Test getting all tasks with multiple filters.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Goal', week_start)

        target_task = task_db.create_task(
            'Target',
            'grow',
            goal_id=goal.id,
            state='active',
            repeatable=True
        )
        task_db.create_task('Other 1', 'maintain', goal_id=goal.id, state='active')
        task_db.create_task('Other 2', 'grow', state='ready')

        filtered = task_db.get_all_tasks(
            state='active',
            category='grow',
            goal_id=goal.id,
            repeatable=True
        )

        assert len(filtered) == 1
        assert filtered[0].id == target_task.id


class TestUpdateTask:
    '''Tests for update_task and related methods.'''

    def test_update_task_title(self, task_db):
        '''Test updating task title.'''
        task = task_db.create_task('Old Title', 'grow')

        updated_task = task_db.update_task(task.id, title='New Title')

        assert updated_task is not None
        assert updated_task.title == 'New Title'

    def test_update_task_multiple_fields(self, task_db):
        '''Test updating multiple task fields at once.'''
        task = task_db.create_task('Task', 'grow')

        updated_task = task_db.update_task(
            task.id,
            title='Updated',
            category='maintain',
            est_minutes=45,
            actual_minutes=50
        )

        assert updated_task.title == 'Updated'
        assert updated_task.category == 'maintain'
        assert updated_task.est_minutes == 45
        assert updated_task.actual_minutes == 50

    def test_update_task_state(self, task_db):
        '''Test updating task state.'''
        task = task_db.create_task('Task', 'grow', state='ready')

        updated_task = task_db.update_task_state(task.id, 'active')

        assert updated_task is not None
        assert updated_task.state == 'active'

    def test_update_task_state_to_done_sets_completed_at(self, task_db):
        '''Test that changing state to done sets completed_at.'''
        task = task_db.create_task('Task', 'grow', state='ready')

        updated_task = task_db.update_task(task.id, state='done')

        assert updated_task.state == 'done'
        assert updated_task.completed_at is not None

    def test_update_task_state_to_done_for_repeatable_sets_last_completed(self, task_db):
        '''Test that marking repeatable task as done sets last_completed_at.'''
        task = task_db.create_task('Daily task', 'maintain', repeatable=True)

        updated_task = task_db.update_task(task.id, state='done')

        assert updated_task.state == 'done'
        assert updated_task.completed_at is not None
        assert updated_task.last_completed_at is not None

    def test_mark_task_completed(self, task_db):
        '''Test mark_task_completed convenience method.'''
        task = task_db.create_task('Task', 'grow')

        completed_task = task_db.mark_task_completed(task.id, actual_minutes=30)

        assert completed_task.state == 'done'
        assert completed_task.actual_minutes == 30
        assert completed_task.completed_at is not None

    def test_mark_repeatable_task_completed(self, task_db):
        '''Test marking repeatable task as completed.'''
        task = task_db.create_task('Repeatable', 'maintain', repeatable=True)

        completed_task = task_db.mark_task_completed(task.id)

        assert completed_task.state == 'done'
        assert completed_task.last_completed_at is not None

    def test_archive_task(self, task_db):
        '''Test archiving a task.'''
        task = task_db.create_task('Task', 'grow')

        archived_task = task_db.archive_task(task.id)

        assert archived_task is not None
        assert archived_task.state == 'archived'

    def test_update_nonexistent_task(self, task_db):
        '''Test updating non-existent task returns None.'''
        result = task_db.update_task(999, title='New')
        assert result is None

    def test_update_preserves_other_fields(self, task_db):
        '''Test that updating one field doesn't change others.'''
        task = task_db.create_task(
            'Task',
            'grow',
            est_minutes=60,
            repeatable=True
        )

        updated_task = task_db.update_task(task.id, title='Updated')

        assert updated_task.title == 'Updated'
        assert updated_task.category == 'grow'
        assert updated_task.est_minutes == 60
        assert updated_task.repeatable is True


class TestLearningOperations:
    '''Tests for learning and stats operations.'''

    def test_increment_task_stat_suggested(self, task_db):
        '''Test incrementing times_suggested stat.'''
        task = task_db.create_task('Task', 'grow')

        updated_task = task_db.increment_task_stat(task.id, 'suggested')

        assert updated_task is not None
        assert updated_task.times_suggested == 1
        assert updated_task.times_accepted == 0
        assert updated_task.times_rejected == 0

    def test_increment_task_stat_accepted(self, task_db):
        '''Test incrementing times_accepted stat.'''
        task = task_db.create_task('Task', 'grow')

        task_db.increment_task_stat(task.id, 'accepted')
        updated_task = task_db.increment_task_stat(task.id, 'accepted')

        assert updated_task.times_accepted == 2

    def test_increment_task_stat_rejected(self, task_db):
        '''Test incrementing times_rejected stat.'''
        task = task_db.create_task('Task', 'grow')

        updated_task = task_db.increment_task_stat(task.id, 'rejected')

        assert updated_task.times_rejected == 1

    def test_increment_multiple_stats(self, task_db):
        '''Test incrementing multiple stats on same task.'''
        task = task_db.create_task('Task', 'grow')

        task_db.increment_task_stat(task.id, 'suggested')
        task_db.increment_task_stat(task.id, 'suggested')
        task_db.increment_task_stat(task.id, 'accepted')

        updated_task = task_db.get_task(task.id)

        assert updated_task.times_suggested == 2
        assert updated_task.times_accepted == 1
        assert updated_task.times_rejected == 0

    def test_update_task_learning_actual_minutes(self, task_db):
        '''Test updating actual_minutes via update_task_learning.'''
        task = task_db.create_task('Task', 'grow')

        updated_task = task_db.update_task_learning(task.id, actual_minutes=45)

        assert updated_task is not None
        assert updated_task.actual_minutes == 45

    def test_update_task_learning_energy_after_first_time(self, task_db):
        '''Test updating energy_after for first time sets avg_energy_after.'''
        task = task_db.create_task('Task', 'grow')

        updated_task = task_db.update_task_learning(task.id, energy_after=4.0)

        assert updated_task.avg_energy_after == 4.0

    def test_update_task_learning_energy_after_calculates_average(self, task_db):
        '''Test that energy_after updates calculate running average.'''
        task = task_db.create_task('Task', 'grow')

        task_db.update_task_learning(task.id, energy_after=4.0)
        updated_task = task_db.update_task_learning(task.id, energy_after=2.0)

        # Average of 4.0 and 2.0 should be 3.0
        assert updated_task.avg_energy_after == 3.0

    def test_update_task_learning_both_fields(self, task_db):
        '''Test updating both actual_minutes and energy_after.'''
        task = task_db.create_task('Task', 'grow')

        updated_task = task_db.update_task_learning(
            task.id,
            actual_minutes=60,
            energy_after=5.0
        )

        assert updated_task.actual_minutes == 60
        assert updated_task.avg_energy_after == 5.0


class TestRepeatableOperations:
    '''Tests for repeatable task operations.'''

    def test_get_completed_repeatables_empty(self, task_db):
        '''Test getting completed repeatables when none exist.'''
        repeatables = task_db.get_completed_repeatables()
        assert repeatables == []

    def test_get_completed_repeatables(self, task_db):
        '''Test getting completed repeatable tasks.'''
        task1 = task_db.create_task('Daily 1', 'maintain', repeatable=True)
        task2 = task_db.create_task('Daily 2', 'sustain', repeatable=True)
        task_db.create_task('Not Repeatable', 'grow', repeatable=False)

        # Complete the repeatable tasks
        task_db.mark_task_completed(task1.id)
        task_db.mark_task_completed(task2.id)

        repeatables = task_db.get_completed_repeatables()

        assert len(repeatables) == 2
        task_ids = [t.id for t in repeatables]
        assert task1.id in task_ids
        assert task2.id in task_ids

    def test_get_completed_repeatables_excludes_uncompleted(self, task_db):
        '''Test that get_completed_repeatables excludes uncompleted ones.'''
        completed = task_db.create_task('Completed', 'maintain', repeatable=True)
        task_db.create_task('Not Completed', 'maintain', repeatable=True)

        task_db.mark_task_completed(completed.id)

        repeatables = task_db.get_completed_repeatables()

        assert len(repeatables) == 1
        assert repeatables[0].id == completed.id

    def test_get_completed_repeatables_filter_by_category(self, task_db):
        '''Test filtering completed repeatables by category.'''
        grow_task = task_db.create_task('Grow', 'grow', repeatable=True)
        maintain_task = task_db.create_task('Maintain', 'maintain', repeatable=True)

        task_db.mark_task_completed(grow_task.id)
        task_db.mark_task_completed(maintain_task.id)

        grow_repeatables = task_db.get_completed_repeatables(category='grow')

        assert len(grow_repeatables) == 1
        assert grow_repeatables[0].id == grow_task.id

    def test_reset_tasks(self, task_db):
        '''Test resetting tasks to ready state.'''
        task1 = task_db.create_task('Task 1', 'grow', state='done')
        task2 = task_db.create_task('Task 2', 'maintain', state='done')

        reset_tasks = task_db.reset_tasks([task1.id, task2.id])

        assert len(reset_tasks) == 2
        for task in reset_tasks:
            assert task.state == 'ready'
            assert task.completed_at is None

    def test_reset_tasks_preserves_learning_data(self, task_db):
        '''Test that resetting tasks preserves learning stats.'''
        task = task_db.create_task('Task', 'grow')
        task_db.increment_task_stat(task.id, 'suggested')
        task_db.increment_task_stat(task.id, 'accepted')
        task_db.mark_task_completed(task.id)

        reset_tasks = task_db.reset_tasks([task.id])

        reset_task = reset_tasks[0]
        assert reset_task.state == 'ready'
        assert reset_task.completed_at is None
        assert reset_task.times_suggested == 1
        assert reset_task.times_accepted == 1

    def test_reset_repeatable_task_preserves_last_completed(self, task_db):
        '''Test that resetting repeatable task preserves last_completed_at.'''
        task = task_db.create_task('Repeatable', 'maintain', repeatable=True)
        task_db.mark_task_completed(task.id)

        completed_task = task_db.get_task(task.id)
        original_last_completed = completed_task.last_completed_at

        reset_tasks = task_db.reset_tasks([task.id])

        assert reset_tasks[0].state == 'ready'
        assert reset_tasks[0].last_completed_at == original_last_completed

    def test_reset_tasks_with_nonexistent_ids(self, task_db):
        '''Test resetting with some non-existent IDs.'''
        task = task_db.create_task('Task', 'grow', state='done')

        reset_tasks = task_db.reset_tasks([task.id, 999])

        # Should only reset the existing task
        assert len(reset_tasks) == 1
        assert reset_tasks[0].id == task.id

    def test_clear_repeatable_history(self, task_db):
        '''Test clearing last_completed_at for repeatable task.'''
        task = task_db.create_task('Repeatable', 'maintain', repeatable=True)
        task_db.mark_task_completed(task.id)

        # Verify it was set
        completed_task = task_db.get_task(task.id)
        assert completed_task.last_completed_at is not None

        # Clear the history
        cleared_task = task_db.clear_repeatable_history(task.id)

        assert cleared_task is not None
        assert cleared_task.last_completed_at is None

    def test_clear_repeatable_history_nonexistent_task(self, task_db):
        '''Test clearing history for non-existent task returns None.'''
        result = task_db.clear_repeatable_history(999)
        assert result is None


class TestTaskEdgeCases:
    '''Tests for edge cases and boundary conditions.'''

    def test_pydantic_model_returned(self, task_db):
        '''Test that all methods return Pydantic Task instances.'''
        created = task_db.create_task('Task', 'grow')
        assert isinstance(created, Task)

        retrieved = task_db.get_task(created.id)
        assert isinstance(retrieved, Task)

        tasks_list = task_db.get_all_tasks()
        assert all(isinstance(t, Task) for t in tasks_list)

        updated = task_db.update_task(created.id, title='Updated')
        assert isinstance(updated, Task)

    def test_create_task_linked_to_goal(self, task_db):
        '''Test creating task linked to a goal.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Goal', week_start)

        task = task_db.create_task('Task', 'grow', goal_id=goal.id)

        assert task.goal_id == goal.id

        # Verify we can retrieve tasks by goal
        goal_tasks = task_db.get_tasks_by_goal(goal.id)
        assert len(goal_tasks) == 1
        assert goal_tasks[0].id == task.id

    def test_multiple_state_transitions(self, task_db):
        '''Test multiple state transitions on same task.'''
        task = task_db.create_task('Task', 'grow')

        task_db.update_task_state(task.id, 'active')
        task_db.update_task_state(task.id, 'done')
        task_db.update_task_state(task.id, 'archived')
        final_task = task_db.update_task_state(task.id, 'ready')

        assert final_task.state == 'ready'

    def test_update_with_none_values_ignores_fields(self, task_db):
        '''Test that None values don't update fields.'''
        task = task_db.create_task(
            'Original',
            'grow',
            est_minutes=60
        )

        updated_task = task_db.update_task(
            task.id,
            title=None,
            est_minutes=None
        )

        assert updated_task.title == 'Original'
        assert updated_task.est_minutes == 60


class TestCountTasks:
    '''Tests for count_tasks method.'''

    def test_count_all_tasks(self, task_db):
        '''Test counting all tasks without filters.'''
        task_db.create_task('Task 1', 'grow')
        task_db.create_task('Task 2', 'maintain')
        task_db.create_task('Task 3', 'sustain')

        count = task_db.count_tasks()
        assert count == 3

    def test_count_empty_database(self, task_db):
        '''Test count returns 0 for empty database.'''
        count = task_db.count_tasks()
        assert count == 0

    def test_count_by_state(self, task_db):
        '''Test counting tasks filtered by state.'''
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'grow')
        task_db.create_task('Task 3', 'grow')

        # Change some states
        task_db.update_task_state(task1.id, 'done')
        task_db.update_task_state(task2.id, 'done')

        assert task_db.count_tasks(state='done') == 2
        assert task_db.count_tasks(state='ready') == 1
        assert task_db.count_tasks(state='active') == 0

    def test_count_by_category(self, task_db):
        '''Test counting tasks filtered by category.'''
        task_db.create_task('Task 1', 'grow')
        task_db.create_task('Task 2', 'grow')
        task_db.create_task('Task 3', 'maintain')
        task_db.create_task('Task 4', 'sustain')

        assert task_db.count_tasks(category='grow') == 2
        assert task_db.count_tasks(category='maintain') == 1
        assert task_db.count_tasks(category='sustain') == 1

    def test_count_by_goal_id(self, task_db):
        '''Test counting tasks filtered by goal_id.'''
        week_start = get_week_start()
        goal1 = task_db.create_weekly_goal('Goal 1', week_start)
        goal2 = task_db.create_weekly_goal('Goal 2', week_start)

        task_db.create_task('Task 1', 'grow', goal_id=goal1.id)
        task_db.create_task('Task 2', 'grow', goal_id=goal1.id)
        task_db.create_task('Task 3', 'grow', goal_id=goal2.id)
        task_db.create_task('Task 4', 'grow')  # No goal

        assert task_db.count_tasks(goal_id=goal1.id) == 2
        assert task_db.count_tasks(goal_id=goal2.id) == 1
        assert task_db.count_tasks(goal_id=None) == 4  # All tasks

    def test_count_by_repeatable(self, task_db):
        '''Test counting tasks filtered by repeatable flag.'''
        task_db.create_task('Task 1', 'grow', repeatable=True)
        task_db.create_task('Task 2', 'grow', repeatable=True)
        task_db.create_task('Task 3', 'grow', repeatable=False)
        task_db.create_task('Task 4', 'grow')  # Defaults to False

        assert task_db.count_tasks(repeatable=True) == 2
        assert task_db.count_tasks(repeatable=False) == 2

    def test_count_with_multiple_filters(self, task_db):
        '''Test counting tasks with multiple filters combined.'''
        week_start = get_week_start()
        goal = task_db.create_weekly_goal('Goal', week_start)

        task1 = task_db.create_task('Task 1', 'grow', goal_id=goal.id, repeatable=True)
        task_db.create_task('Task 2', 'grow', goal_id=goal.id, repeatable=False)
        task_db.create_task('Task 3', 'maintain', goal_id=goal.id, repeatable=True)

        task_db.update_task_state(task1.id, 'done')

        # Multiple filters
        assert task_db.count_tasks(category='grow', goal_id=goal.id) == 2
        assert task_db.count_tasks(category='grow', repeatable=True, goal_id=goal.id) == 1
        assert task_db.count_tasks(state='done', category='grow') == 1
        assert task_db.count_tasks(state='ready', category='maintain', repeatable=True) == 1

    def test_count_sql_level_performance(self, task_db):
        '''Test that count uses SQL-level COUNT, not fetch-all.'''
        # Create many tasks
        for i in range(100):
            task_db.create_task(f'Task {i}', 'grow')

        # Count should be efficient (SQL-level)
        count = task_db.count_tasks()
        assert count == 100

        # Count with filter should also be efficient
        count_grow = task_db.count_tasks(category='grow')
        assert count_grow == 100


# Session CRUD Tests


class TestCreateSession:
    '''Tests for create_session method.'''

    def test_create_basic_session(self, task_db):
        '''Test creating a basic session.'''
        session = task_db.create_session()

        assert session.id is not None
        assert session.started_at is not None
        assert session.ended_at is None
        assert session.available_minutes is None
        assert session.energy_level is None
        assert session.focus_area is None
        assert session.tasks_completed == 0
        assert session.effectiveness is None

    def test_create_session_with_all_fields(self, task_db):
        '''Test creating a session with all optional fields.'''
        session = task_db.create_session(
            available_minutes=120,
            energy_level=4,
            focus_area='grow'
        )

        assert session.id is not None
        assert session.available_minutes == 120
        assert session.energy_level == 4
        assert session.focus_area == 'grow'
        assert session.tasks_completed == 0

    def test_create_session_with_different_focus_areas(self, task_db):
        '''Test creating sessions with different focus areas.'''
        for focus_area in ['grow', 'maintain', 'sustain']:
            session = task_db.create_session(focus_area=focus_area)
            assert session.focus_area == focus_area

    def test_create_session_with_different_energy_levels(self, task_db):
        '''Test creating sessions with different energy levels.'''
        for energy_level in [1, 2, 3, 4, 5]:
            session = task_db.create_session(energy_level=energy_level)
            assert session.energy_level == energy_level


class TestGetSession:
    '''Tests for get_session method.'''

    def test_get_existing_session(self, task_db):
        '''Test getting an existing session by ID.'''
        created_session = task_db.create_session(
            available_minutes=60,
            energy_level=3
        )

        retrieved_session = task_db.get_session(created_session.id)

        assert retrieved_session is not None
        assert retrieved_session.id == created_session.id
        assert retrieved_session.available_minutes == 60
        assert retrieved_session.energy_level == 3

    def test_get_nonexistent_session(self, task_db):
        '''Test getting a session with non-existent ID returns None.'''
        session = task_db.get_session(999)
        assert session is None

    def test_get_session_with_all_fields(self, task_db):
        '''Test getting a session preserves all fields.'''
        created_session = task_db.create_session(
            available_minutes=90,
            energy_level=5,
            focus_area='maintain'
        )

        retrieved_session = task_db.get_session(created_session.id)

        assert retrieved_session.available_minutes == 90
        assert retrieved_session.energy_level == 5
        assert retrieved_session.focus_area == 'maintain'


class TestEndSession:
    '''Tests for end_session method.'''

    def test_end_session_basic(self, task_db):
        '''Test ending a session sets ended_at.'''
        session = task_db.create_session()

        ended_session = task_db.end_session(session.id)

        assert ended_session is not None
        assert ended_session.ended_at is not None
        assert ended_session.ended_at > session.started_at

    def test_end_session_with_tasks_completed(self, task_db):
        '''Test ending a session with tasks_completed.'''
        session = task_db.create_session()

        ended_session = task_db.end_session(session.id, tasks_completed=3)

        assert ended_session.ended_at is not None
        assert ended_session.tasks_completed == 3

    def test_end_session_with_effectiveness(self, task_db):
        '''Test ending a session with effectiveness rating.'''
        session = task_db.create_session()

        ended_session = task_db.end_session(session.id, effectiveness=4)

        assert ended_session.effectiveness == 4

    def test_end_session_with_all_fields(self, task_db):
        '''Test ending a session with all optional fields.'''
        session = task_db.create_session()

        ended_session = task_db.end_session(
            session.id,
            tasks_completed=5,
            effectiveness=5
        )

        assert ended_session.ended_at is not None
        assert ended_session.tasks_completed == 5
        assert ended_session.effectiveness == 5

    def test_end_session_nonexistent(self, task_db):
        '''Test ending a non-existent session returns None.'''
        result = task_db.end_session(999)
        assert result is None

    def test_end_session_preserves_other_fields(self, task_db):
        '''Test that ending a session doesn't change other fields.'''
        session = task_db.create_session(
            available_minutes=120,
            energy_level=4,
            focus_area='grow'
        )

        ended_session = task_db.end_session(session.id, tasks_completed=2)

        assert ended_session.available_minutes == 120
        assert ended_session.energy_level == 4
        assert ended_session.focus_area == 'grow'


class TestGetRecentSessions:
    '''Tests for get_recent_sessions method.'''

    def test_get_recent_sessions_empty(self, task_db):
        '''Test getting recent sessions when none exist.'''
        sessions = task_db.get_recent_sessions()
        assert sessions == []

    def test_get_recent_sessions(self, task_db):
        '''Test getting recent sessions.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        session3 = task_db.create_session()

        sessions = task_db.get_recent_sessions()

        assert len(sessions) == 3
        # Should be ordered by started_at descending (most recent first)
        assert sessions[0].id == session3.id
        assert sessions[1].id == session2.id
        assert sessions[2].id == session1.id

    def test_get_recent_sessions_with_limit(self, task_db):
        '''Test getting recent sessions with limit.'''
        task_db.create_session()
        task_db.create_session()
        session3 = task_db.create_session()

        sessions = task_db.get_recent_sessions(limit=2)

        assert len(sessions) == 2
        assert sessions[0].id == session3.id

    def test_get_recent_sessions_filter_by_focus_area(self, task_db):
        '''Test filtering recent sessions by focus area.'''
        grow_session = task_db.create_session(focus_area='grow')
        task_db.create_session(focus_area='maintain')
        task_db.create_session(focus_area='sustain')

        grow_sessions = task_db.get_recent_sessions(focus_area='grow')

        assert len(grow_sessions) == 1
        assert grow_sessions[0].id == grow_session.id

    def test_get_recent_sessions_default_limit(self, task_db):
        '''Test that default limit is 10.'''
        # Create 12 sessions
        for _ in range(12):
            task_db.create_session()

        sessions = task_db.get_recent_sessions()

        assert len(sessions) == 10


class TestUpdateSession:
    '''Tests for update_session method.'''

    def test_update_session_available_minutes(self, task_db):
        '''Test updating session available_minutes.'''
        session = task_db.create_session(available_minutes=60)

        updated_session = task_db.update_session(
            session.id,
            available_minutes=90
        )

        assert updated_session is not None
        assert updated_session.available_minutes == 90

    def test_update_session_energy_level(self, task_db):
        '''Test updating session energy_level.'''
        session = task_db.create_session(energy_level=3)

        updated_session = task_db.update_session(session.id, energy_level=5)

        assert updated_session.energy_level == 5

    def test_update_session_focus_area(self, task_db):
        '''Test updating session focus_area.'''
        session = task_db.create_session(focus_area='grow')

        updated_session = task_db.update_session(session.id, focus_area='maintain')

        assert updated_session.focus_area == 'maintain'

    def test_update_session_tasks_completed(self, task_db):
        '''Test updating session tasks_completed.'''
        session = task_db.create_session()

        updated_session = task_db.update_session(session.id, tasks_completed=3)

        assert updated_session.tasks_completed == 3

    def test_update_session_effectiveness(self, task_db):
        '''Test updating session effectiveness.'''
        session = task_db.create_session()

        updated_session = task_db.update_session(session.id, effectiveness=4)

        assert updated_session.effectiveness == 4

    def test_update_session_multiple_fields(self, task_db):
        '''Test updating multiple session fields at once.'''
        session = task_db.create_session()

        updated_session = task_db.update_session(
            session.id,
            available_minutes=120,
            energy_level=5,
            focus_area='grow',
            tasks_completed=4,
            effectiveness=5
        )

        assert updated_session.available_minutes == 120
        assert updated_session.energy_level == 5
        assert updated_session.focus_area == 'grow'
        assert updated_session.tasks_completed == 4
        assert updated_session.effectiveness == 5

    def test_update_session_with_none_values_ignores_fields(self, task_db):
        '''Test that None values don't update fields.'''
        session = task_db.create_session(
            available_minutes=60,
            energy_level=3
        )

        updated_session = task_db.update_session(
            session.id,
            available_minutes=None,
            energy_level=None
        )

        assert updated_session.available_minutes == 60
        assert updated_session.energy_level == 3

    def test_update_session_nonexistent(self, task_db):
        '''Test updating non-existent session returns None.'''
        result = task_db.update_session(999, available_minutes=60)
        assert result is None

    def test_update_session_persists(self, task_db):
        '''Test that updates are persisted in database.'''
        session = task_db.create_session()

        task_db.update_session(session.id, available_minutes=90)
        retrieved_session = task_db.get_session(session.id)

        assert retrieved_session.available_minutes == 90


class TestGetAllSessions:
    '''Tests for get_all_sessions method.'''

    def test_get_all_sessions_empty(self, task_db):
        '''Test getting all sessions when none exist.'''
        sessions = task_db.get_all_sessions()
        assert sessions == []

    def test_get_all_sessions(self, task_db):
        '''Test getting all sessions without filters.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()

        sessions = task_db.get_all_sessions()

        assert len(sessions) == 2
        session_ids = [s.id for s in sessions]
        assert session1.id in session_ids
        assert session2.id in session_ids

    def test_get_all_sessions_filter_by_focus_area(self, task_db):
        '''Test filtering sessions by focus_area.'''
        grow_session = task_db.create_session(focus_area='grow')
        task_db.create_session(focus_area='maintain')

        grow_sessions = task_db.get_all_sessions(focus_area='grow')

        assert len(grow_sessions) == 1
        assert grow_sessions[0].id == grow_session.id

    def test_get_all_sessions_filter_by_min_effectiveness(self, task_db):
        '''Test filtering sessions by minimum effectiveness.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        task_db.end_session(session1.id, effectiveness=3)
        task_db.end_session(session2.id, effectiveness=5)

        effective_sessions = task_db.get_all_sessions(min_effectiveness=4)

        assert len(effective_sessions) == 1
        assert effective_sessions[0].id == session2.id

    def test_get_all_sessions_filter_by_focus_and_effectiveness(self, task_db):
        '''Test filtering by both focus_area and min_effectiveness.'''
        session1 = task_db.create_session(focus_area='grow')
        session2 = task_db.create_session(focus_area='grow')
        task_db.create_session(focus_area='maintain')

        task_db.end_session(session1.id, effectiveness=3)
        task_db.end_session(session2.id, effectiveness=5)

        filtered_sessions = task_db.get_all_sessions(
            focus_area='grow',
            min_effectiveness=4
        )

        assert len(filtered_sessions) == 1
        assert filtered_sessions[0].id == session2.id

    def test_get_all_sessions_ordered_by_started_desc(self, task_db):
        '''Test sessions are ordered by started_at descending.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        session3 = task_db.create_session()

        sessions = task_db.get_all_sessions()

        assert sessions[0].id == session3.id
        assert sessions[1].id == session2.id
        assert sessions[2].id == session1.id


class TestSessionEdgeCases:
    '''Tests for edge cases and boundary conditions.'''

    def test_pydantic_model_returned(self, task_db):
        '''Test that all methods return Pydantic Session instances.'''
        created = task_db.create_session()
        assert isinstance(created, Session)

        retrieved = task_db.get_session(created.id)
        assert isinstance(retrieved, Session)

        sessions_list = task_db.get_all_sessions()
        assert all(isinstance(s, Session) for s in sessions_list)

        updated = task_db.update_session(created.id, available_minutes=60)
        assert isinstance(updated, Session)

        ended = task_db.end_session(created.id)
        assert isinstance(ended, Session)

    def test_session_ended_at_after_started_at(self, task_db):
        '''Test that ended_at is after started_at.'''
        session = task_db.create_session()
        ended_session = task_db.end_session(session.id)

        assert ended_session.ended_at > ended_session.started_at

    def test_multiple_sessions_different_timestamps(self, task_db):
        '''Test multiple sessions have different timestamps.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()

        # IDs should be different
        assert session1.id != session2.id
        # Timestamps should be close but session2 should be >= session1
        assert session2.started_at >= session1.started_at


# Work Entry CRUD Tests


class TestStartWorkEntry:
    '''Tests for start_work_entry method.'''

    def test_start_basic_work_entry(self, task_db):
        '''Test starting a basic work entry.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')

        work_entry = task_db.start_work_entry(session.id, task.id)

        assert work_entry.id is not None
        assert work_entry.session_id == session.id
        assert work_entry.task_id == task.id
        assert work_entry.started_at is not None
        assert work_entry.ended_at is None
        assert work_entry.completed is False
        assert work_entry.energy_after is None
        assert work_entry.want_more_like_this is None
        assert work_entry.abandoned_reason is None

    def test_start_multiple_work_entries_same_session(self, task_db):
        '''Test starting multiple work entries in the same session.'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        work_entry1 = task_db.start_work_entry(session.id, task1.id)
        work_entry2 = task_db.start_work_entry(session.id, task2.id)

        assert work_entry1.id != work_entry2.id
        assert work_entry1.session_id == session.id
        assert work_entry2.session_id == session.id

    def test_start_work_entry_different_sessions_same_task(self, task_db):
        '''Test starting work entries for same task in different sessions.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        task = task_db.create_task('Repeatable Task', 'grow', repeatable=True)

        work_entry1 = task_db.start_work_entry(session1.id, task.id)
        work_entry2 = task_db.start_work_entry(session2.id, task.id)

        assert work_entry1.id != work_entry2.id
        assert work_entry1.task_id == task.id
        assert work_entry2.task_id == task.id
        assert work_entry1.session_id == session1.id
        assert work_entry2.session_id == session2.id


class TestGetWorkEntry:
    '''Tests for get_work_entry method.'''

    def test_get_existing_work_entry(self, task_db):
        '''Test getting an existing work entry by ID.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        created_entry = task_db.start_work_entry(session.id, task.id)

        retrieved_entry = task_db.get_work_entry(created_entry.id)

        assert retrieved_entry is not None
        assert retrieved_entry.id == created_entry.id
        assert retrieved_entry.session_id == session.id
        assert retrieved_entry.task_id == task.id

    def test_get_nonexistent_work_entry(self, task_db):
        '''Test getting a work entry with non-existent ID returns None.'''
        entry = task_db.get_work_entry(999)
        assert entry is None

    def test_get_work_entry_preserves_all_fields(self, task_db):
        '''Test getting a work entry preserves all fields.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        created_entry = task_db.start_work_entry(session.id, task.id)
        task_db.end_work_entry(
            created_entry.id,
            completed=True,
            energy_after=4,
            want_more_like_this=True
        )

        retrieved_entry = task_db.get_work_entry(created_entry.id)

        assert retrieved_entry.completed is True
        assert retrieved_entry.energy_after == 4
        assert retrieved_entry.want_more_like_this is True


class TestEndWorkEntry:
    '''Tests for end_work_entry method.'''

    def test_end_work_entry_basic(self, task_db):
        '''Test ending a work entry sets ended_at.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        ended_entry = task_db.end_work_entry(work_entry.id)

        assert ended_entry is not None
        assert ended_entry.ended_at is not None
        assert ended_entry.ended_at > work_entry.started_at
        assert ended_entry.completed is False

    def test_end_work_entry_completed(self, task_db):
        '''Test ending a work entry as completed.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        ended_entry = task_db.end_work_entry(work_entry.id, completed=True)

        assert ended_entry.completed is True

    def test_end_work_entry_with_energy_after(self, task_db):
        '''Test ending a work entry with energy_after rating.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        ended_entry = task_db.end_work_entry(work_entry.id, energy_after=5)

        assert ended_entry.energy_after == 5

    def test_end_work_entry_with_want_more_like_this(self, task_db):
        '''Test ending a work entry with want_more_like_this flag.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        ended_entry = task_db.end_work_entry(
            work_entry.id,
            completed=True,
            want_more_like_this=True
        )

        assert ended_entry.want_more_like_this is True

    def test_end_work_entry_with_abandoned_reason(self, task_db):
        '''Test ending a work entry with abandoned_reason.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        ended_entry = task_db.end_work_entry(
            work_entry.id,
            completed=False,
            abandoned_reason='blocked'
        )

        assert ended_entry.completed is False
        assert ended_entry.abandoned_reason == 'blocked'

    def test_end_work_entry_with_all_fields(self, task_db):
        '''Test ending a work entry with all optional fields.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        ended_entry = task_db.end_work_entry(
            work_entry.id,
            completed=True,
            energy_after=4,
            want_more_like_this=True
        )

        assert ended_entry.ended_at is not None
        assert ended_entry.completed is True
        assert ended_entry.energy_after == 4
        assert ended_entry.want_more_like_this is True

    def test_end_work_entry_nonexistent(self, task_db):
        '''Test ending a non-existent work entry returns None.'''
        result = task_db.end_work_entry(999)
        assert result is None

    def test_end_work_entry_different_abandoned_reasons(self, task_db):
        '''Test ending work entries with different abandoned reasons.'''
        session = task_db.create_session()
        reasons = ['blocked', 'too_hard', 'wrong_time', 'not_important', 'distracted']

        for reason in reasons:
            task = task_db.create_task(f'Task {reason}', 'grow')
            work_entry = task_db.start_work_entry(session.id, task.id)
            ended_entry = task_db.end_work_entry(
                work_entry.id,
                abandoned_reason=reason
            )
            assert ended_entry.abandoned_reason == reason


class TestGetWorkEntriesBySession:
    '''Tests for get_work_entries_by_session method.'''

    def test_get_work_entries_by_session_empty(self, task_db):
        '''Test getting work entries for a session with none.'''
        session = task_db.create_session()
        entries = task_db.get_work_entries_by_session(session.id)
        assert entries == []

    def test_get_work_entries_by_session(self, task_db):
        '''Test getting work entries for a session.'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        entry1 = task_db.start_work_entry(session.id, task1.id)
        entry2 = task_db.start_work_entry(session.id, task2.id)

        entries = task_db.get_work_entries_by_session(session.id)

        assert len(entries) == 2
        entry_ids = [e.id for e in entries]
        assert entry1.id in entry_ids
        assert entry2.id in entry_ids

    def test_get_work_entries_filters_by_session(self, task_db):
        '''Test that get_work_entries_by_session only returns entries for specific session.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        task = task_db.create_task('Task', 'grow')

        entry1 = task_db.start_work_entry(session1.id, task.id)
        task_db.start_work_entry(session2.id, task.id)

        session1_entries = task_db.get_work_entries_by_session(session1.id)

        assert len(session1_entries) == 1
        assert session1_entries[0].id == entry1.id

    def test_get_work_entries_ordered_by_started_at(self, task_db):
        '''Test that work entries are ordered by started_at.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')

        entry1 = task_db.start_work_entry(session.id, task.id)
        entry2 = task_db.start_work_entry(session.id, task.id)
        entry3 = task_db.start_work_entry(session.id, task.id)

        entries = task_db.get_work_entries_by_session(session.id)

        assert entries[0].id == entry1.id
        assert entries[1].id == entry2.id
        assert entries[2].id == entry3.id


class TestGetWorkEntriesByTask:
    '''Tests for get_work_entries_by_task method.'''

    def test_get_work_entries_by_task_empty(self, task_db):
        '''Test getting work entries for a task with none.'''
        task = task_db.create_task('Task', 'grow')
        entries = task_db.get_work_entries_by_task(task.id)
        assert entries == []

    def test_get_work_entries_by_task(self, task_db):
        '''Test getting work entries for a task.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        task = task_db.create_task('Repeatable Task', 'grow', repeatable=True)

        entry1 = task_db.start_work_entry(session1.id, task.id)
        entry2 = task_db.start_work_entry(session2.id, task.id)

        entries = task_db.get_work_entries_by_task(task.id)

        assert len(entries) == 2
        entry_ids = [e.id for e in entries]
        assert entry1.id in entry_ids
        assert entry2.id in entry_ids

    def test_get_work_entries_filters_by_task(self, task_db):
        '''Test that get_work_entries_by_task only returns entries for specific task.'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        entry1 = task_db.start_work_entry(session.id, task1.id)
        task_db.start_work_entry(session.id, task2.id)

        task1_entries = task_db.get_work_entries_by_task(task1.id)

        assert len(task1_entries) == 1
        assert task1_entries[0].id == entry1.id

    def test_get_work_entries_ordered_by_started_desc(self, task_db):
        '''Test that work entries are ordered by started_at descending.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow', repeatable=True)

        entry1 = task_db.start_work_entry(session.id, task.id)
        entry2 = task_db.start_work_entry(session.id, task.id)
        entry3 = task_db.start_work_entry(session.id, task.id)

        entries = task_db.get_work_entries_by_task(task.id)

        # Should be in descending order (most recent first)
        assert entries[0].id == entry3.id
        assert entries[1].id == entry2.id
        assert entries[2].id == entry1.id


class TestUpdateWorkEntry:
    '''Tests for update_work_entry method.'''

    def test_update_work_entry_completed(self, task_db):
        '''Test updating work entry completed status.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        updated_entry = task_db.update_work_entry(work_entry.id, completed=True)

        assert updated_entry is not None
        assert updated_entry.completed is True

    def test_update_work_entry_energy_after(self, task_db):
        '''Test updating work entry energy_after.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        updated_entry = task_db.update_work_entry(work_entry.id, energy_after=3)

        assert updated_entry.energy_after == 3

    def test_update_work_entry_want_more_like_this(self, task_db):
        '''Test updating work entry want_more_like_this.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        updated_entry = task_db.update_work_entry(
            work_entry.id,
            want_more_like_this=False
        )

        assert updated_entry.want_more_like_this is False

    def test_update_work_entry_abandoned_reason(self, task_db):
        '''Test updating work entry abandoned_reason.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        updated_entry = task_db.update_work_entry(
            work_entry.id,
            abandoned_reason='too_hard'
        )

        assert updated_entry.abandoned_reason == 'too_hard'

    def test_update_work_entry_multiple_fields(self, task_db):
        '''Test updating multiple work entry fields at once.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        updated_entry = task_db.update_work_entry(
            work_entry.id,
            completed=True,
            energy_after=5,
            want_more_like_this=True
        )

        assert updated_entry.completed is True
        assert updated_entry.energy_after == 5
        assert updated_entry.want_more_like_this is True

    def test_update_work_entry_with_none_values_ignores_fields(self, task_db):
        '''Test that None values don't update fields.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)
        task_db.update_work_entry(work_entry.id, energy_after=4)

        updated_entry = task_db.update_work_entry(
            work_entry.id,
            energy_after=None
        )

        assert updated_entry.energy_after == 4

    def test_update_work_entry_nonexistent(self, task_db):
        '''Test updating non-existent work entry returns None.'''
        result = task_db.update_work_entry(999, completed=True)
        assert result is None

    def test_update_work_entry_persists(self, task_db):
        '''Test that updates are persisted in database.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        task_db.update_work_entry(work_entry.id, completed=True)
        retrieved_entry = task_db.get_work_entry(work_entry.id)

        assert retrieved_entry.completed is True


class TestGetAllWorkEntries:
    '''Tests for get_all_work_entries method.'''

    def test_get_all_work_entries_empty(self, task_db):
        '''Test getting all work entries when none exist.'''
        entries = task_db.get_all_work_entries()
        assert entries == []

    def test_get_all_work_entries(self, task_db):
        '''Test getting all work entries without filters.'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        entry1 = task_db.start_work_entry(session.id, task1.id)
        entry2 = task_db.start_work_entry(session.id, task2.id)

        entries = task_db.get_all_work_entries()

        assert len(entries) == 2
        entry_ids = [e.id for e in entries]
        assert entry1.id in entry_ids
        assert entry2.id in entry_ids

    def test_get_all_work_entries_filter_by_session(self, task_db):
        '''Test filtering work entries by session_id.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        task = task_db.create_task('Task', 'grow')

        entry1 = task_db.start_work_entry(session1.id, task.id)
        task_db.start_work_entry(session2.id, task.id)

        session1_entries = task_db.get_all_work_entries(session_id=session1.id)

        assert len(session1_entries) == 1
        assert session1_entries[0].id == entry1.id

    def test_get_all_work_entries_filter_by_task(self, task_db):
        '''Test filtering work entries by task_id.'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        entry1 = task_db.start_work_entry(session.id, task1.id)
        task_db.start_work_entry(session.id, task2.id)

        task1_entries = task_db.get_all_work_entries(task_id=task1.id)

        assert len(task1_entries) == 1
        assert task1_entries[0].id == entry1.id

    def test_get_all_work_entries_filter_by_completed(self, task_db):
        '''Test filtering work entries by completed status.'''
        session = task_db.create_session()
        task1 = task_db.create_task('Task 1', 'grow')
        task2 = task_db.create_task('Task 2', 'maintain')

        entry1 = task_db.start_work_entry(session.id, task1.id)
        entry2 = task_db.start_work_entry(session.id, task2.id)
        task_db.end_work_entry(entry1.id, completed=True)
        task_db.end_work_entry(entry2.id, completed=False)

        completed_entries = task_db.get_all_work_entries(completed=True)

        assert len(completed_entries) == 1
        assert completed_entries[0].id == entry1.id

    def test_get_all_work_entries_multiple_filters(self, task_db):
        '''Test filtering work entries by multiple criteria.'''
        session1 = task_db.create_session()
        session2 = task_db.create_session()
        task = task_db.create_task('Task', 'grow')

        entry1 = task_db.start_work_entry(session1.id, task.id)
        task_db.start_work_entry(session2.id, task.id)

        task_db.end_work_entry(entry1.id, completed=True)

        filtered_entries = task_db.get_all_work_entries(
            session_id=session1.id,
            task_id=task.id,
            completed=True
        )

        assert len(filtered_entries) == 1
        assert filtered_entries[0].id == entry1.id

    def test_get_all_work_entries_ordered_by_started_desc(self, task_db):
        '''Test work entries are ordered by started_at descending.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')

        entry1 = task_db.start_work_entry(session.id, task.id)
        entry2 = task_db.start_work_entry(session.id, task.id)
        entry3 = task_db.start_work_entry(session.id, task.id)

        entries = task_db.get_all_work_entries()

        assert entries[0].id == entry3.id
        assert entries[1].id == entry2.id
        assert entries[2].id == entry1.id


class TestCompleteWorkEntry:
    '''Tests for complete_work_entry atomic operation.'''

    def test_complete_work_entry_basic(self, task_db):
        '''Test basic work completion updates all fields atomically.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        completed_entry = task_db.complete_work_entry(
            work_entry.id,
            completed=True,
            energy_after=4
        )

        assert completed_entry is not None
        assert completed_entry.ended_at is not None
        assert completed_entry.completed is True
        assert completed_entry.energy_after == 4

    def test_complete_work_updates_task_state_non_repeatable(self, task_db):
        '''Test completing work updates task state for non-repeatable tasks.'''
        session = task_db.create_session()
        task = task_db.create_task('One-time task', 'grow', repeatable=False)
        work_entry = task_db.start_work_entry(session.id, task.id)

        task_db.complete_work_entry(work_entry.id, completed=True)

        # Verify task state was updated to 'done'
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'done'
        assert updated_task.completed_at is not None

    def test_complete_work_preserves_repeatable_task_state(self, task_db):
        '''Test completing work doesn't change state for repeatable tasks.'''
        session = task_db.create_session()
        task = task_db.create_task('Repeatable task', 'grow', repeatable=True)
        work_entry = task_db.start_work_entry(session.id, task.id)

        task_db.complete_work_entry(work_entry.id, completed=True)

        # Verify task state stays 'ready' for repeatable tasks
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'ready'
        assert updated_task.completed_at is None

    def test_complete_work_updates_avg_energy(self, task_db):
        '''Test that avg_energy_after is updated from energy_after.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        task_db.complete_work_entry(work_entry.id, completed=True, energy_after=5)

        # Verify avg_energy_after was updated
        updated_task = task_db.get_task(task.id)
        assert updated_task.avg_energy_after == 5.0

    def test_complete_work_abandoned(self, task_db):
        '''Test completing abandoned work doesn't update task state.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        task_db.complete_work_entry(
            work_entry.id,
            completed=False,
            abandoned_reason='blocked'
        )

        # Verify work entry was marked as abandoned
        completed_entry = task_db.get_work_entry(work_entry.id)
        assert completed_entry.completed is False
        assert completed_entry.abandoned_reason == 'blocked'

        # Verify task state was not changed
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'ready'

    def test_complete_work_atomicity(self, task_db):
        '''Test that all updates happen atomically (all or nothing).'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        # Complete work with all parameters
        completed_entry = task_db.complete_work_entry(
            work_entry.id,
            completed=True,
            energy_after=4,
            want_more_like_this=True
        )

        # Verify all fields were updated together
        assert completed_entry.completed is True
        assert completed_entry.energy_after == 4
        assert completed_entry.want_more_like_this is True

        # Verify task was also updated
        updated_task = task_db.get_task(task.id)
        assert updated_task.state == 'done'
        assert updated_task.avg_energy_after == 4.0

    def test_complete_work_invalid_work_id(self, task_db):
        '''Test completing non-existent work entry returns None.'''
        result = task_db.complete_work_entry(999, completed=True)
        assert result is None

    def test_complete_work_with_all_feedback(self, task_db):
        '''Test completing work with all feedback parameters.'''
        session = task_db.create_session()
        task = task_db.create_task('Test Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)

        completed_entry = task_db.complete_work_entry(
            work_entry.id,
            completed=True,
            energy_after=5,
            want_more_like_this=True
        )

        assert completed_entry.completed is True
        assert completed_entry.energy_after == 5
        assert completed_entry.want_more_like_this is True
        assert completed_entry.abandoned_reason is None


class TestWorkEntryEdgeCases:
    '''Tests for edge cases and boundary conditions.'''

    def test_pydantic_model_returned(self, task_db):
        '''Test that all methods return Pydantic WorkEntry instances.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')

        created = task_db.start_work_entry(session.id, task.id)
        assert isinstance(created, WorkEntry)

        retrieved = task_db.get_work_entry(created.id)
        assert isinstance(retrieved, WorkEntry)

        entries_list = task_db.get_all_work_entries()
        assert all(isinstance(e, WorkEntry) for e in entries_list)

        updated = task_db.update_work_entry(created.id, completed=True)
        assert isinstance(updated, WorkEntry)

        ended = task_db.end_work_entry(created.id, completed=True)
        assert isinstance(ended, WorkEntry)

    def test_work_entry_ended_at_after_started_at(self, task_db):
        '''Test that ended_at is after started_at.'''
        session = task_db.create_session()
        task = task_db.create_task('Task', 'grow')
        work_entry = task_db.start_work_entry(session.id, task.id)
        ended_entry = task_db.end_work_entry(work_entry.id)

        assert ended_entry.ended_at > ended_entry.started_at

    def test_multiple_work_entries_for_repeatable_task(self, task_db):
        '''Test creating multiple work entries for a repeatable task.'''
        session = task_db.create_session()
        task = task_db.create_task('Daily Task', 'maintain', repeatable=True)

        entry1 = task_db.start_work_entry(session.id, task.id)
        task_db.end_work_entry(entry1.id, completed=True)

        entry2 = task_db.start_work_entry(session.id, task.id)
        task_db.end_work_entry(entry2.id, completed=True)

        entries = task_db.get_work_entries_by_task(task.id)

        assert len(entries) == 2


class TestGetTasksByIds:
    '''Tests for get_tasks_by_ids method.'''

    def test_empty_list_returns_empty(self, task_db):
        '''Empty input returns empty list without hitting the DB.'''
        assert task_db.get_tasks_by_ids([]) == []

    def test_returns_matching_tasks(self, task_db):
        '''Returns exactly the tasks for the given IDs.'''
        t1 = task_db.create_task('Task A', 'grow')
        t2 = task_db.create_task('Task B', 'maintain')
        task_db.create_task('Task C', 'sustain')  # not requested

        result = task_db.get_tasks_by_ids([t1.id, t2.id])

        assert len(result) == 2
        assert {r.id for r in result} == {t1.id, t2.id}

    def test_missing_ids_are_silently_omitted(self, task_db):
        '''IDs that don't exist in the DB are silently skipped.'''
        t1 = task_db.create_task('Task A', 'grow')

        result = task_db.get_tasks_by_ids([t1.id, 99999])

        assert len(result) == 1
        assert result[0].id == t1.id

    def test_all_missing_ids_returns_empty(self, task_db):
        '''All non-existent IDs returns empty list.'''
        assert task_db.get_tasks_by_ids([99998, 99999]) == []


class TestGetLatestAbandonedEntriesBatch:
    '''Tests for get_latest_abandoned_entries_batch method.'''

    def test_empty_list_returns_empty(self, task_db):
        '''Empty input returns empty list.'''
        assert task_db.get_latest_abandoned_entries_batch([]) == []

    def test_no_abandoned_entries_returns_empty(self, task_db):
        '''Tasks with no abandonments are omitted from results.'''
        task = task_db.create_task('Task', 'grow')
        session = task_db.create_session()
        entry = task_db.start_work_entry(session.id, task.id)
        task_db.complete_work_entry(entry.id, completed=True)

        result = task_db.get_latest_abandoned_entries_batch([task.id])

        assert result == []

    def test_returns_one_row_per_task(self, task_db):
        '''Returns exactly one entry per task, even with multiple abandonments.'''
        t1 = task_db.create_task('Task 1', 'grow', repeatable=True)
        t2 = task_db.create_task('Task 2', 'maintain', repeatable=True)
        session = task_db.create_session()

        e1 = task_db.start_work_entry(session.id, t1.id)
        task_db.end_work_entry(e1.id, abandoned_reason='wrong_time')
        e2 = task_db.start_work_entry(session.id, t1.id)
        task_db.end_work_entry(e2.id, abandoned_reason='too_hard')

        e3 = task_db.start_work_entry(session.id, t2.id)
        task_db.end_work_entry(e3.id, abandoned_reason='not_important')

        result = task_db.get_latest_abandoned_entries_batch([t1.id, t2.id])

        assert len(result) == 2
        by_task = {r.task_id: r for r in result}
        assert by_task[t1.id].id == e2.id
        assert by_task[t2.id].id == e3.id

    def test_returns_latest_not_first(self, task_db):
        '''Returns the most recent abandonment, not the earliest.'''
        task = task_db.create_task('Task', 'grow', repeatable=True)
        session = task_db.create_session()

        old = task_db.start_work_entry(session.id, task.id)
        task_db.end_work_entry(old.id, abandoned_reason='wrong_time')
        recent = task_db.start_work_entry(session.id, task.id)
        task_db.end_work_entry(recent.id, abandoned_reason='too_hard')

        result = task_db.get_latest_abandoned_entries_batch([task.id])

        assert len(result) == 1
        assert result[0].id == recent.id

    def test_missing_task_ids_are_omitted(self, task_db):
        '''Non-existent task IDs produce no rows (no error).'''
        assert task_db.get_latest_abandoned_entries_batch([99999]) == []

    def test_tie_on_started_at_returns_highest_id(self, task_db):
        '''When two entries share the same started_at, the higher id wins.'''
        task = task_db.create_task('Task', 'grow', repeatable=True)
        session = task_db.create_session()

        e1 = task_db.start_work_entry(session.id, task.id)
        e2 = task_db.start_work_entry(session.id, task.id)

        # Force identical started_at to create a tie
        from v2.models import WorkEntryModel
        from sqlalchemy.orm import sessionmaker
        LocalSession = sessionmaker(bind=task_db.engine)
        with LocalSession() as s:
            we1 = s.query(WorkEntryModel).filter_by(id=e1.id).first()
            we2 = s.query(WorkEntryModel).filter_by(id=e2.id).first()
            we2.started_at = we1.started_at
            we1.abandoned_reason = 'wrong_time'
            we2.abandoned_reason = 'too_hard'
            s.commit()

        result = task_db.get_latest_abandoned_entries_batch([task.id])

        assert len(result) == 1
        assert result[0].id == e2.id  # higher id wins the tie
