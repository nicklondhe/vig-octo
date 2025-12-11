'''
Unit tests for v2 TaskDB class.
'''
import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine, event

from v2.db import TaskDB
from v2.models import Base, WeeklyGoal
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
