'''
Unit tests for v2 TaskDB class.
'''
# pylint: disable=redefined-outer-name
from datetime import timedelta
from sqlalchemy import create_engine, event

import pytest

from v2.db import TaskDB
from v2.models import Base, Task, WeeklyGoal
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
