'''
Database access layer for v2 task management system.
'''

from datetime import date, datetime, timezone
from typing import Literal, Optional

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from v2.models import (
    CategoryType,
    GoalStatusType,
    Task,
    TaskModel,
    TaskStateType,
    WeeklyGoal,
    WeeklyGoalModel,
)
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

    def _get_task_model(
        self,
        session: Session,
        task_id: int,
    ) -> Optional[TaskModel]:
        '''Get a TaskModel by ID.

        Args:
            session: Active SQLAlchemy session
            task_id: Task ID to retrieve

        Returns:
            TaskModel if found, None otherwise
        '''
        return session.query(TaskModel).filter(
            TaskModel.id == task_id
        ).first()

    def _commit_and_convert_task(
        self,
        session: Session,
        model: TaskModel,
    ) -> Task:
        '''Commit, refresh, and convert a TaskModel to Pydantic.

        Args:
            session: Active SQLAlchemy session
            model: TaskModel instance

        Returns:
            Task Pydantic model
        '''
        session.commit()
        session.refresh(model)
        return Task.model_validate(model)

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

    # Task Operations

    def create_task(
        self,
        title: str,
        category: CategoryType,
        est_minutes: Optional[int] = None,
        repeatable: bool = False,
        goal_id: Optional[int] = None,
        state: TaskStateType = 'ready',
    ) -> Task:
        '''Create a new task.

        Args:
            title: Task title
            category: Task category ('grow', 'maintain', or 'sustain')
            est_minutes: Estimated minutes to complete (optional)
            repeatable: Whether task can be repeated (default: False)
            goal_id: ID of associated weekly goal (optional)
            state: Initial task state (default: 'ready')

        Returns:
            Created Task
        '''
        with self.SessionLocal() as session:
            task_model = TaskModel(
                title=title,
                category=category,
                est_minutes=est_minutes,
                repeatable=repeatable,
                goal_id=goal_id,
                state=state,
            )
            session.add(task_model)
            return self._commit_and_convert_task(session, task_model)

    def get_task(self, task_id: int) -> Optional[Task]:
        '''Get a specific task by ID.

        Args:
            task_id: ID of the task to retrieve

        Returns:
            Task if found, None otherwise
        '''
        with self.SessionLocal() as session:
            task_model = self._get_task_model(session, task_id)
            return Task.model_validate(task_model) if task_model else None

    def get_tasks_by_state(
        self,
        state: TaskStateType,
    ) -> list[Task]:
        '''Get all tasks with a specific state.

        Args:
            state: Task state to filter by

        Returns:
            List of Task objects matching the state
        '''
        return self.get_all_tasks(state=state)

    def get_tasks_by_goal(
        self,
        goal_id: int,
    ) -> list[Task]:
        '''Get all tasks associated with a specific goal.

        Args:
            goal_id: ID of the goal to get tasks for

        Returns:
            List of Task objects associated with the goal
        '''
        return self.get_all_tasks(goal_id=goal_id)

    def get_tasks_by_category(
        self,
        category: CategoryType,
    ) -> list[Task]:
        '''Get all tasks in a specific category.

        Args:
            category: Category to filter by ('grow', 'maintain', or 'sustain')

        Returns:
            List of Task objects in the category
        '''
        return self.get_all_tasks(category=category)

    def get_all_tasks(
        self,
        state: Optional[TaskStateType] = None,
        category: Optional[CategoryType] = None,
        goal_id: Optional[int] = None,
        repeatable: Optional[bool] = None,
    ) -> list[Task]:
        '''Get all tasks with optional filtering.

        Args:
            state: Filter by state (optional)
            category: Filter by category (optional)
            goal_id: Filter by goal ID (optional)
            repeatable: Filter by repeatable flag (optional)

        Returns:
            List of Task objects matching the filters
        '''
        with self.SessionLocal() as session:
            query = session.query(TaskModel)

            if state is not None:
                query = query.filter(TaskModel.state == state)
            if category is not None:
                query = query.filter(TaskModel.category == category)
            if goal_id is not None:
                query = query.filter(TaskModel.goal_id == goal_id)
            if repeatable is not None:
                query = query.filter(TaskModel.repeatable == repeatable)

            task_models = query.order_by(TaskModel.created_at).all()
            return [Task.model_validate(t) for t in task_models]

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        category: Optional[CategoryType] = None,
        est_minutes: Optional[int] = None,
        actual_minutes: Optional[int] = None,
        state: Optional[TaskStateType] = None,
        goal_id: Optional[int] = None,
    ) -> Optional[Task]:
        '''Update a task's fields.

        Handles state change side effects:
        - Sets completed_at when state changes to 'done'
        - Sets last_completed_at for repeatable tasks when state changes to 'done'

        Args:
            task_id: ID of the task to update
            title: New title (optional)
            category: New category (optional)
            est_minutes: New estimated minutes (optional)
            actual_minutes: New actual minutes (optional)
            state: New state (optional)
            goal_id: New goal ID (optional)

        Returns:
            Updated Task if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if task_model := self._get_task_model(session, task_id):
                if title is not None:
                    task_model.title = title
                if category is not None:
                    task_model.category = category
                if est_minutes is not None:
                    task_model.est_minutes = est_minutes
                if actual_minutes is not None:
                    task_model.actual_minutes = actual_minutes
                if goal_id is not None:
                    task_model.goal_id = goal_id

                # Handle state changes and side effects
                if state is not None:
                    task_model.state = state
                    # Auto-set timestamps when marking as done
                    if state == 'done' and task_model.completed_at is None:
                        task_model.completed_at = datetime.now(timezone.utc)
                        # For repeatable tasks, also update last_completed_at
                        if task_model.repeatable:
                            task_model.last_completed_at = datetime.now(timezone.utc)
                    # Clear completed_at when transitioning away from done/archived
                    elif state in ('ready', 'active'):
                        task_model.completed_at = None

                return self._commit_and_convert_task(session, task_model)
            return None

    def update_task_state(
        self,
        task_id: int,
        state: TaskStateType,
    ) -> Optional[Task]:
        '''Update the state of a task.

        Args:
            task_id: ID of the task to update
            state: New state value

        Returns:
            Updated Task if found, None otherwise
        '''
        return self.update_task(task_id, state=state)

    def mark_task_completed(
        self,
        task_id: int,
        actual_minutes: Optional[int] = None,
    ) -> Optional[Task]:
        '''Mark a task as completed.

        Args:
            task_id: ID of the task to mark as completed
            actual_minutes: Actual minutes spent on task (optional)

        Returns:
            Updated Task if found, None otherwise
        '''
        return self.update_task(task_id, state='done', actual_minutes=actual_minutes)

    def archive_task(self, task_id: int) -> Optional[Task]:
        '''Archive a task.

        Args:
            task_id: ID of the task to archive

        Returns:
            Archived Task if found, None otherwise
        '''
        return self.update_task(task_id, state='archived')

    # Learning and Stats Operations

    def increment_task_stat(
        self,
        task_id: int,
        stat: Literal['suggested', 'accepted', 'rejected'],
    ) -> Optional[Task]:
        '''Increment a learning statistic for a task.

        Args:
            task_id: ID of the task to update
            stat: Which statistic to increment ('suggested', 'accepted', or 'rejected')

        Returns:
            Updated Task if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if task_model := self._get_task_model(session, task_id):
                if stat == 'suggested':
                    task_model.times_suggested += 1
                elif stat == 'accepted':
                    task_model.times_accepted += 1
                elif stat == 'rejected':
                    task_model.times_rejected += 1

                return self._commit_and_convert_task(session, task_model)
            return None

    def update_task_learning(
        self,
        task_id: int,
        actual_minutes: Optional[int] = None,
        energy_after: Optional[float] = None,
    ) -> Optional[Task]:
        '''Update learning-related fields for a task.

        Args:
            task_id: ID of the task to update
            actual_minutes: Actual minutes spent (optional)
            energy_after: Energy level after task (1-5 scale, optional)

        Returns:
            Updated Task if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if task_model := self._get_task_model(session, task_id):
                if actual_minutes is not None:
                    task_model.actual_minutes = actual_minutes

                if energy_after is not None:
                    # Update running average of energy_after
                    if task_model.avg_energy_after is None:
                        task_model.avg_energy_after = energy_after
                    else:
                        # Calculate new average based on times_accepted
                        count = task_model.times_accepted or 1
                        current_total = task_model.avg_energy_after * count
                        task_model.avg_energy_after = (current_total + energy_after) / (count + 1)

                return self._commit_and_convert_task(session, task_model)
            return None

    # Repeatable Task Operations

    def get_completed_repeatables(
        self,
        category: Optional[CategoryType] = None,
    ) -> list[Task]:
        '''Get all completed repeatable tasks.

        Args:
            category: Filter by category (optional)

        Returns:
            List of completed repeatable Task objects
        '''
        with self.SessionLocal() as session:
            query = session.query(TaskModel).filter(
                TaskModel.repeatable == True,
                TaskModel.last_completed_at.isnot(None)
            )

            if category is not None:
                query = query.filter(TaskModel.category == category)

            task_models = query.order_by(
                TaskModel.last_completed_at.desc()
            ).all()
            return [Task.model_validate(t) for t in task_models]

    def reset_tasks(self, task_ids: list[int]) -> list[Task]:
        '''Reset tasks to ready state (for repeatables or reuse).

        Clears state to 'ready', clears completed_at, but preserves
        learning data and last_completed_at.

        Args:
            task_ids: List of task IDs to reset

        Returns:
            List of reset Task objects
        '''
        with self.SessionLocal() as session:
            reset_tasks = []

            for task_id in task_ids:
                if task_model := self._get_task_model(session, task_id):
                    task_model.state = 'ready'
                    task_model.completed_at = None
                    # Keep last_completed_at for repeatables
                    # Keep learning stats (times_suggested, etc.)
                    session.add(task_model)
                    reset_tasks.append(task_model)

            if reset_tasks:
                session.commit()
                for task_model in reset_tasks:
                    session.refresh(task_model)

            return [Task.model_validate(t) for t in reset_tasks]

    def clear_repeatable_history(self, task_id: int) -> Optional[Task]:
        '''Clear the last_completed_at for a repeatable task.

        This allows it to be suggested again as if never completed.

        Args:
            task_id: ID of the task to clear history for

        Returns:
            Updated Task if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if task_model := self._get_task_model(session, task_id):
                task_model.last_completed_at = None
                return self._commit_and_convert_task(session, task_model)
            return None
