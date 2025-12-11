'''
Database access layer for v2 task management system.
'''

from datetime import date
from typing import Optional

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from v2.models import GoalStatusType, WeeklyGoal, WeeklyGoalModel
from v2.util import get_week_start


class TaskDB:
    '''Database access layer for task management operations.'''

    def __init__(self, engine: Engine) -> None:
        '''Initialize TaskDB with a SQLAlchemy engine.

        Args:
            engine: SQLAlchemy engine instance
        '''
        self.engine = engine
        self.SessionLocal = sessionmaker(bind=engine)

    # Helper methods

    def _commit_and_convert(
        self,
        session: Session,
        model: WeeklyGoalModel,
    ) -> WeeklyGoal:
        '''Commit, refresh, and convert a model to Pydantic.

        Args:
            session: Active SQLAlchemy session
            model: WeeklyGoalModel instance

        Returns:
            WeeklyGoal Pydantic model
        '''
        session.commit()
        session.refresh(model)
        return WeeklyGoal.model_validate(model)

    def _get_goal_model(
        self,
        session: Session,
        goal_id: int,
    ) -> Optional[WeeklyGoalModel]:
        '''Get a WeeklyGoalModel by ID.

        Args:
            session: Active SQLAlchemy session
            goal_id: Goal ID to retrieve

        Returns:
            WeeklyGoalModel if found, None otherwise
        '''
        return session.query(WeeklyGoalModel).filter(
            WeeklyGoalModel.id == goal_id
        ).first()

    # Weekly Goals Operations

    def create_weekly_goal(
        self,
        title: str,
        week_start: date,
        description: Optional[str] = None,
        category: Optional[str] = None,
        status: GoalStatusType = 'active',
    ) -> WeeklyGoal:
        '''Create a new weekly goal.

        Args:
            title: Goal title
            week_start: Start date of the week for this goal (should be a Monday)
            description: Optional goal description
            category: Optional category ('grow', 'maintain', or 'sustain')
            status: Goal status (default: 'active')

        Returns:
            Created WeeklyGoal
        '''
        with self.SessionLocal() as session:
            goal_model = WeeklyGoalModel(
                title=title,
                description=description,
                category=category,
                week_start=week_start,
                status=status,
            )
            session.add(goal_model)
            return self._commit_and_convert(session, goal_model)

    def get_weekly_goal(self, goal_id: int) -> Optional[WeeklyGoal]:
        '''Get a specific weekly goal by ID.

        Args:
            goal_id: ID of the goal to retrieve

        Returns:
            WeeklyGoal if found, None otherwise
        '''
        with self.SessionLocal() as session:
            goal_model = session.query(WeeklyGoalModel).filter(
                WeeklyGoalModel.id == goal_id
            ).first()
            return WeeklyGoal.model_validate(goal_model) if goal_model else None

    def get_goals_by_week(self, week_start: date) -> list[WeeklyGoal]:
        '''Get all goals for a specific week.

        Args:
            week_start: Start date of the week to query goals for (should be a Monday)

        Returns:
            List of WeeklyGoal objects for the specified week
        '''
        with self.SessionLocal() as session:
            goal_models = session.query(WeeklyGoalModel).filter(
                WeeklyGoalModel.week_start == week_start
            ).order_by(WeeklyGoalModel.created_at).all()
            return [WeeklyGoal.model_validate(g) for g in goal_models]

    def get_current_week_goals(self) -> list[WeeklyGoal]:
        '''Get all goals for the current week.

        Returns:
            List of WeeklyGoal objects for the current week
        '''
        return self.get_goals_by_week(get_week_start())

    def update_goal_status(
        self,
        goal_id: int,
        status: GoalStatusType,
    ) -> Optional[WeeklyGoal]:
        '''Update the status of a weekly goal.

        Args:
            goal_id: ID of the goal to update
            status: New status value

        Returns:
            Updated WeeklyGoal if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if goal_model := self._get_goal_model(session, goal_id):
                goal_model.status = status
                return self._commit_and_convert(session, goal_model)
            return None

    def update_weekly_goal(
        self,
        goal_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[GoalStatusType] = None,
    ) -> Optional[WeeklyGoal]:
        '''Update a weekly goal's fields.

        Args:
            goal_id: ID of the goal to update
            title: New title (optional)
            description: New description (optional)
            category: New category (optional)
            status: New status (optional)

        Returns:
            Updated WeeklyGoal if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if goal_model := self._get_goal_model(session, goal_id):
                if title is not None:
                    goal_model.title = title
                if description is not None:
                    goal_model.description = description
                if category is not None:
                    goal_model.category = category
                if status is not None:
                    goal_model.status = status
                return self._commit_and_convert(session, goal_model)
            return None

    def get_all_goals(
        self,
        status: Optional[GoalStatusType] = None,
        category: Optional[str] = None,
    ) -> list[WeeklyGoal]:
        '''Get all weekly goals with optional filtering.

        Args:
            status: Filter by status (optional)
            category: Filter by category (optional)

        Returns:
            List of WeeklyGoal objects matching the filters
        '''
        with self.SessionLocal() as session:
            query = session.query(WeeklyGoalModel)

            if status is not None:
                query = query.filter(WeeklyGoalModel.status == status)
            if category is not None:
                query = query.filter(WeeklyGoalModel.category == category)

            goal_models = query.order_by(
                WeeklyGoalModel.week_start.desc(),
                WeeklyGoalModel.created_at
            ).all()
            return [WeeklyGoal.model_validate(g) for g in goal_models]
