'''
Database access layer for v2 task management system.
'''

from datetime import date, datetime, timezone
from typing import Literal, Optional

from sqlalchemy import Engine
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import sessionmaker

from v2.models import (
    CategoryType,
    GoalStatusType,
    Session,
    SessionModel,
    Task,
    TaskModel,
    TaskStateType,
    WeeklyGoal,
    WeeklyGoalModel,
    WorkEntry,
    WorkEntryModel,
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
        session: DBSession,
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
        session: DBSession,
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
        session: DBSession,
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
        session: DBSession,
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
        limit: Optional[int] = None,
        order_desc: bool = True,
    ) -> list[Task]:
        '''Get all tasks with optional filtering.

        Args:
            state: Filter by state (optional)
            category: Filter by category (optional)
            goal_id: Filter by goal ID (optional)
            repeatable: Filter by repeatable flag (optional)
            limit: Maximum number of tasks to return (optional)
            order_desc: Order by created_at descending (default: True)

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

            # Apply ordering
            if order_desc:
                query = query.order_by(TaskModel.created_at.desc())
            else:
                query = query.order_by(TaskModel.created_at)

            # Apply limit at SQL level
            if limit is not None and limit > 0:
                query = query.limit(limit)

            task_models = query.all()
            return [Task.model_validate(t) for t in task_models]

    def count_tasks(
        self,
        state: Optional[TaskStateType] = None,
        category: Optional[CategoryType] = None,
        goal_id: Optional[int] = None,
        repeatable: Optional[bool] = None,
    ) -> int:
        '''Count tasks with optional filtering (SQL-level count).

        Args:
            state: Filter by state (optional)
            category: Filter by category (optional)
            goal_id: Filter by goal ID (optional)
            repeatable: Filter by repeatable flag (optional)

        Returns:
            Count of tasks matching the filters
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

            return query.count()

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
                    if state == 'done':
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
        energy_after: float = 3.0,
    ) -> Optional[Task]:
        '''Update learning-related fields for a task.

        Args:
            task_id: ID of the task to update
            actual_minutes: Actual minutes spent (optional)
            energy_after: Energy level after task (1-5 scale, defaults to 3.0)
                Business layer should track current energy and provide actual value.

        Returns:
            Updated Task if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if task_model := self._get_task_model(session, task_id):
                if actual_minutes is not None:
                    task_model.actual_minutes = actual_minutes

                # Update running average of energy_after
                # Note: This uses times_accepted as the count.
                # Business layer should ensure update_task_learning is called
                # when incrementing times_accepted to maintain 1:1 relationship.
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
                TaskModel.repeatable.is_(True),
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

    # Session helper methods

    def _get_session_model(
        self,
        session: DBSession,
        session_id: int,
    ) -> Optional[SessionModel]:
        '''Get a SessionModel by ID.

        Args:
            session: Active SQLAlchemy session
            session_id: Session ID to retrieve

        Returns:
            SessionModel if found, None otherwise
        '''
        return session.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()

    def _commit_and_convert_session(
        self,
        session: DBSession,
        model: SessionModel,
    ) -> Session:
        '''Commit, refresh, and convert a SessionModel to Pydantic.

        Args:
            session: Active SQLAlchemy session
            model: SessionModel instance

        Returns:
            Session Pydantic model
        '''
        session.commit()
        session.refresh(model)
        return Session.model_validate(model)

    # Session Operations

    def create_session(
        self,
        available_minutes: Optional[int] = None,
        energy_level: Optional[int] = None,
        focus_area: Optional[str] = None,
    ) -> Session:
        '''Create a new work session.

        Args:
            available_minutes: Minutes available for this session (optional)
            energy_level: Energy level at session start (1-5 scale, optional)
            focus_area: Focus area category ('grow', 'maintain', or 'sustain', optional)

        Returns:
            Created Session
        '''
        with self.SessionLocal() as session:
            session_model = SessionModel(
                available_minutes=available_minutes,
                energy_level=energy_level,
                focus_area=focus_area,
            )
            session.add(session_model)
            return self._commit_and_convert_session(session, session_model)

    def get_session(self, session_id: int) -> Optional[Session]:
        '''Get a specific session by ID.

        Args:
            session_id: ID of the session to retrieve

        Returns:
            Session if found, None otherwise
        '''
        with self.SessionLocal() as session:
            session_model = self._get_session_model(session, session_id)
            return Session.model_validate(session_model) if session_model else None

    def end_session(
        self,
        session_id: int,
        tasks_completed: Optional[int] = None,
        effectiveness: Optional[int] = None,
    ) -> Optional[Session]:
        '''End a work session.

        Sets ended_at to current time and optionally updates tasks_completed
        and effectiveness rating.

        Args:
            session_id: ID of the session to end
            tasks_completed: Number of tasks completed (optional)
            effectiveness: Effectiveness rating (1-5 scale, optional)

        Returns:
            Updated Session if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if session_model := self._get_session_model(session, session_id):
                session_model.ended_at = datetime.now(timezone.utc)
                if tasks_completed is not None:
                    session_model.tasks_completed = tasks_completed
                if effectiveness is not None:
                    session_model.effectiveness = effectiveness
                return self._commit_and_convert_session(session, session_model)
            return None

    def get_recent_sessions(
        self,
        limit: int = 10,
        focus_area: Optional[str] = None,
    ) -> list[Session]:
        '''Get recent sessions ordered by start time (most recent first).

        Args:
            limit: Maximum number of sessions to return (default: 10)
            focus_area: Filter by focus area category (optional)

        Returns:
            List of Session objects
        '''
        with self.SessionLocal() as session:
            query = session.query(SessionModel)

            if focus_area is not None:
                query = query.filter(SessionModel.focus_area == focus_area)

            session_models = query.order_by(
                SessionModel.started_at.desc()
            ).limit(limit).all()
            return [Session.model_validate(s) for s in session_models]

    def update_session(
        self,
        session_id: int,
        available_minutes: Optional[int] = None,
        energy_level: Optional[int] = None,
        focus_area: Optional[str] = None,
        tasks_completed: Optional[int] = None,
        effectiveness: Optional[int] = None,
    ) -> Optional[Session]:
        '''Update a session's fields.

        Args:
            session_id: ID of the session to update
            available_minutes: New available minutes (optional)
            energy_level: New energy level (optional)
            focus_area: New focus area (optional)
            tasks_completed: New tasks completed count (optional)
            effectiveness: New effectiveness rating (optional)

        Returns:
            Updated Session if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if session_model := self._get_session_model(session, session_id):
                if available_minutes is not None:
                    session_model.available_minutes = available_minutes
                if energy_level is not None:
                    session_model.energy_level = energy_level
                if focus_area is not None:
                    session_model.focus_area = focus_area
                if tasks_completed is not None:
                    session_model.tasks_completed = tasks_completed
                if effectiveness is not None:
                    session_model.effectiveness = effectiveness
                return self._commit_and_convert_session(session, session_model)
            return None

    def get_all_sessions(
        self,
        focus_area: Optional[str] = None,
        min_effectiveness: Optional[int] = None,
    ) -> list[Session]:
        '''Get all sessions with optional filtering.

        Args:
            focus_area: Filter by focus area category (optional)
            min_effectiveness: Filter by minimum effectiveness rating (optional)

        Returns:
            List of Session objects ordered by started_at descending
        '''
        with self.SessionLocal() as session:
            query = session.query(SessionModel)

            if focus_area is not None:
                query = query.filter(SessionModel.focus_area == focus_area)
            if min_effectiveness is not None:
                query = query.filter(SessionModel.effectiveness >= min_effectiveness)

            session_models = query.order_by(
                SessionModel.started_at.desc()
            ).all()
            return [Session.model_validate(s) for s in session_models]

    def get_active_sessions(self) -> list[Session]:
        '''Get all active sessions (not ended).

        Returns:
            List of active Session objects ordered by started_at descending
        '''
        with self.SessionLocal() as session:
            session_models = session.query(SessionModel).filter(
                SessionModel.ended_at.is_(None)
            ).order_by(SessionModel.started_at.desc()).all()
            return [Session.model_validate(s) for s in session_models]

    def count_active_sessions(self) -> int:
        '''Count active sessions (not ended) - SQL-level count.

        Returns:
            Count of active sessions
        '''
        with self.SessionLocal() as session:
            return session.query(SessionModel).filter(
                SessionModel.ended_at.is_(None)
            ).count()

    # Work Entry helper methods

    def _get_work_entry_model(
        self,
        session: DBSession,
        work_entry_id: int,
    ) -> Optional[WorkEntryModel]:
        '''Get a WorkEntryModel by ID.

        Args:
            session: Active SQLAlchemy session
            work_entry_id: Work entry ID to retrieve

        Returns:
            WorkEntryModel if found, None otherwise
        '''
        return session.query(WorkEntryModel).filter(
            WorkEntryModel.id == work_entry_id
        ).first()

    def _commit_and_convert_work_entry(
        self,
        session: DBSession,
        model: WorkEntryModel,
    ) -> WorkEntry:
        '''Commit, refresh, and convert a WorkEntryModel to Pydantic.

        Args:
            session: Active SQLAlchemy session
            model: WorkEntryModel instance

        Returns:
            WorkEntry Pydantic model
        '''
        session.commit()
        session.refresh(model)
        return WorkEntry.model_validate(model)

    # Work Entry Operations

    def start_work_entry(
        self,
        session_id: int,
        task_id: int,
    ) -> WorkEntry:
        '''Start a new work entry for a task in a session.

        Args:
            session_id: ID of the session this work entry belongs to
            task_id: ID of the task being worked on

        Returns:
            Created WorkEntry
        '''
        with self.SessionLocal() as session:
            work_entry_model = WorkEntryModel(
                session_id=session_id,
                task_id=task_id,
            )
            session.add(work_entry_model)
            return self._commit_and_convert_work_entry(session, work_entry_model)

    def end_work_entry(
        self,
        work_entry_id: int,
        completed: bool = False,
        energy_after: Optional[int] = None,
        want_more_like_this: Optional[bool] = None,
        abandoned_reason: Optional[str] = None,
    ) -> Optional[WorkEntry]:
        '''End a work entry.

        Sets ended_at to current time and optionally updates outcome fields.

        Args:
            work_entry_id: ID of the work entry to end
            completed: Whether the task was completed (default: False)
            energy_after: Energy level after work (1-5 scale, optional)
            want_more_like_this: Whether user wants more tasks like this (optional)
            abandoned_reason: Reason for abandonment if not completed (optional)

        Returns:
            Updated WorkEntry if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if work_entry_model := self._get_work_entry_model(session, work_entry_id):
                work_entry_model.ended_at = datetime.now(timezone.utc)
                work_entry_model.completed = completed
                if energy_after is not None:
                    work_entry_model.energy_after = energy_after
                if want_more_like_this is not None:
                    work_entry_model.want_more_like_this = want_more_like_this
                if abandoned_reason is not None:
                    work_entry_model.abandoned_reason = abandoned_reason
                return self._commit_and_convert_work_entry(session, work_entry_model)
            return None

    def complete_work_entry(
        self,
        work_entry_id: int,
        completed: bool = False,
        energy_after: Optional[int] = None,
        want_more_like_this: Optional[bool] = None,
        abandoned_reason: Optional[str] = None,
    ) -> Optional[WorkEntry]:
        '''Complete a work entry and update related task data atomically.

        Ends the work entry, calculates actual minutes, updates task state
        (if completed and not repeatable), and updates task learning data.
        All operations are performed in a single transaction.

        Args:
            work_entry_id: ID of the work entry to complete
            completed: Whether the task was completed (default: False)
            energy_after: Energy level after work (1-5 scale, optional)
            want_more_like_this: Whether user wants more tasks like this (optional)
            abandoned_reason: Reason for abandonment if not completed (optional)

        Returns:
            Completed WorkEntry if found, None otherwise
        '''
        with self.SessionLocal() as session:
            # Get work entry
            work_entry_model = self._get_work_entry_model(session, work_entry_id)
            if not work_entry_model:
                return None

            # Get task (fail early if not found)
            task_model = self._get_task_model(session, work_entry_model.task_id)
            if not task_model:
                return None

            # End the work entry
            work_entry_model.ended_at = datetime.now(timezone.utc)
            work_entry_model.completed = completed
            if energy_after is not None:
                work_entry_model.energy_after = energy_after
            if want_more_like_this is not None:
                work_entry_model.want_more_like_this = want_more_like_this
            if abandoned_reason is not None:
                work_entry_model.abandoned_reason = abandoned_reason

            # Calculate actual_minutes
            actual_minutes = None
            if work_entry_model.started_at and work_entry_model.ended_at:
                duration = work_entry_model.ended_at - work_entry_model.started_at
                actual_minutes = int(duration.total_seconds() / 60)

            # Update task state if completed and not repeatable
            if completed and not task_model.repeatable:
                task_model.state = 'done'
                task_model.completed_at = datetime.now(timezone.utc)

            # Update task learning data
            # Note: avg_energy_after uses times_accepted as the count.
            # Business layer should increment times_accepted via increment_task_stat
            # when starting work to maintain 1:1 relationship.
            if actual_minutes is not None:
                task_model.actual_minutes = actual_minutes

            if energy_after is not None:
                if task_model.avg_energy_after is None:
                    task_model.avg_energy_after = float(energy_after)
                else:
                    count = task_model.times_accepted or 1
                    current_total = task_model.avg_energy_after * (count - 1)
                    new_total = current_total + energy_after
                    task_model.avg_energy_after = new_total / count

            # Commit all changes in single transaction
            session.commit()
            session.refresh(work_entry_model)
            return WorkEntry.model_validate(work_entry_model)

    def get_work_entry(self, work_entry_id: int) -> Optional[WorkEntry]:
        '''Get a specific work entry by ID.

        Args:
            work_entry_id: ID of the work entry to retrieve

        Returns:
            WorkEntry if found, None otherwise
        '''
        with self.SessionLocal() as session:
            work_entry_model = self._get_work_entry_model(session, work_entry_id)
            return WorkEntry.model_validate(work_entry_model) if work_entry_model else None

    def get_work_entries_by_session(
        self,
        session_id: int,
    ) -> list[WorkEntry]:
        '''Get all work entries for a specific session.

        Args:
            session_id: ID of the session to get work entries for

        Returns:
            List of WorkEntry objects ordered by started_at
        '''
        with self.SessionLocal() as session:
            work_entry_models = session.query(WorkEntryModel).filter(
                WorkEntryModel.session_id == session_id
            ).order_by(WorkEntryModel.started_at).all()
            return [WorkEntry.model_validate(we) for we in work_entry_models]

    def get_work_entries_by_task(
        self,
        task_id: int,
    ) -> list[WorkEntry]:
        '''Get all work entries for a specific task.

        Args:
            task_id: ID of the task to get work entries for

        Returns:
            List of WorkEntry objects ordered by started_at descending
        '''
        with self.SessionLocal() as session:
            work_entry_models = session.query(WorkEntryModel).filter(
                WorkEntryModel.task_id == task_id
            ).order_by(WorkEntryModel.started_at.desc()).all()
            return [WorkEntry.model_validate(we) for we in work_entry_models]

    def update_work_entry(
        self,
        work_entry_id: int,
        completed: Optional[bool] = None,
        energy_after: Optional[int] = None,
        want_more_like_this: Optional[bool] = None,
        abandoned_reason: Optional[str] = None,
    ) -> Optional[WorkEntry]:
        '''Update a work entry's fields.

        Args:
            work_entry_id: ID of the work entry to update
            completed: New completed status (optional)
            energy_after: New energy after level (optional)
            want_more_like_this: New preference indicator (optional)
            abandoned_reason: New abandoned reason (optional)

        Returns:
            Updated WorkEntry if found, None otherwise
        '''
        with self.SessionLocal() as session:
            if work_entry_model := self._get_work_entry_model(session, work_entry_id):
                if completed is not None:
                    work_entry_model.completed = completed
                if energy_after is not None:
                    work_entry_model.energy_after = energy_after
                if want_more_like_this is not None:
                    work_entry_model.want_more_like_this = want_more_like_this
                if abandoned_reason is not None:
                    work_entry_model.abandoned_reason = abandoned_reason
                return self._commit_and_convert_work_entry(session, work_entry_model)
            return None

    def get_all_work_entries(
        self,
        session_id: Optional[int] = None,
        task_id: Optional[int] = None,
        completed: Optional[bool] = None,
    ) -> list[WorkEntry]:
        '''Get all work entries with optional filtering.

        Args:
            session_id: Filter by session ID (optional)
            task_id: Filter by task ID (optional)
            completed: Filter by completed status (optional)

        Returns:
            List of WorkEntry objects ordered by started_at descending
        '''
        with self.SessionLocal() as session:
            query = session.query(WorkEntryModel)

            if session_id is not None:
                query = query.filter(WorkEntryModel.session_id == session_id)
            if task_id is not None:
                query = query.filter(WorkEntryModel.task_id == task_id)
            if completed is not None:
                query = query.filter(WorkEntryModel.completed == completed)

            work_entry_models = query.order_by(
                WorkEntryModel.started_at.desc()
            ).all()
            return [WorkEntry.model_validate(we) for we in work_entry_models]
