'''
SQLAlchemy and Pydantic models for the v2 task management system.
'''

from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# SQLAlchemy Models

class Base(DeclarativeBase):
    '''Base class for all SQLAlchemy models.'''

class WeeklyGoalModel(Base):
    '''Weekly goal model for tracking weekly objectives.'''

    __tablename__ = 'weekly_goals'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(
        Text,
        CheckConstraint("category IN ('grow', 'maintain', 'sustain')"),
        nullable=True
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("status IN ('active', 'completed', 'archived')"),
        default='active',
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    tasks: Mapped[list['TaskModel']] = relationship(
        'TaskModel',
        back_populates='goal',
        cascade='all, delete-orphan'
    )


class TaskModel(Base):
    '''Task model for managing individual tasks.'''

    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("category IN ('grow', 'maintain', 'sustain')"),
        nullable=False
    )

    # Time tracking
    est_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # State management
    state: Mapped[str] = mapped_column(
        Text,
        CheckConstraint("state IN ('ready', 'active', 'done', 'archived')"),
        default='ready',
        nullable=False
    )

    # Repeatable handling
    repeatable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Learning data
    times_suggested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_accepted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_energy_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Goal linking
    goal_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('weekly_goals.id'),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    goal: Mapped[Optional['WeeklyGoalModel']] = relationship(
        'WeeklyGoalModel',
        back_populates='tasks'
    )
    work_entries: Mapped[list['WorkEntryModel']] = relationship(
        'WorkEntryModel',
        back_populates='task',
        cascade='all, delete-orphan'
    )


class SessionModel(Base):
    '''Session model for tracking work sessions.'''

    __tablename__ = 'sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # User state at start
    available_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    energy_level: Mapped[Optional[int]] = mapped_column(
        Integer,
        CheckConstraint('energy_level BETWEEN 1 AND 5'),
        nullable=True
    )
    focus_area: Mapped[Optional[str]] = mapped_column(
        Text,
        CheckConstraint("focus_area IN ('grow', 'maintain', 'sustain')"),
        nullable=True
    )

    # Outcomes
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effectiveness: Mapped[Optional[int]] = mapped_column(
        Integer,
        CheckConstraint('effectiveness BETWEEN 1 AND 5'),
        nullable=True
    )

    # Relationships
    work_entries: Mapped[list['WorkEntryModel']] = relationship(
        'WorkEntryModel',
        back_populates='session',
        cascade='all, delete-orphan'
    )


class WorkEntryModel(Base):
    '''Work entry model for tracking work on specific tasks during sessions.'''

    __tablename__ = 'work_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('sessions.id'),
        nullable=False
    )
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('tasks.id'),
        nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Outcomes
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    energy_after: Mapped[Optional[int]] = mapped_column(
        Integer,
        CheckConstraint('energy_after BETWEEN 1 AND 5'),
        nullable=True
    )
    want_more_like_this: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # If not completed, why?
    abandoned_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        CheckConstraint(
            "abandoned_reason IN ('blocked', 'too_hard', 'wrong_time', "
            "'not_important', 'distracted') OR abandoned_reason IS NULL"
        ),
        nullable=True
    )

    # Relationships
    session: Mapped['SessionModel'] = relationship(
        'SessionModel',
        back_populates='work_entries'
    )
    task: Mapped['TaskModel'] = relationship(
        'TaskModel',
        back_populates='work_entries'
    )


# Pydantic Models

CategoryType = Literal['grow', 'maintain', 'sustain']
GoalStatusType = Literal['active', 'completed', 'archived']
TaskStateType = Literal['ready', 'active', 'done', 'archived']
AbandonedReasonType = Literal['blocked', 'too_hard', 'wrong_time', 'not_important', 'distracted']


class WeeklyGoal(BaseModel):
    '''Pydantic model for weekly goals.'''

    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[CategoryType] = None
    week_start: date
    status: GoalStatusType = 'active'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# Base model for shared task fields
class TaskBase(BaseModel):
    '''Base model with shared task fields for creation/updates'''
    title: str = Field(..., min_length=1, max_length=500)
    category: CategoryType
    est_minutes: Optional[int] = Field(None, gt=0, le=1440)
    repeatable: bool = False
    goal_id: Optional[int] = None


class TaskCreate(TaskBase):
    '''Request model for creating tasks (used by MCP server)'''
    pass  # Inherits all validation from TaskBase



class TaskUpdate(BaseModel):
    '''Request model for updating tasks (all fields optional, used by MCP server)'''
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    category: Optional[CategoryType] = None
    est_minutes: Optional[int] = Field(None, gt=0, le=1440)
    actual_minutes: Optional[int] = Field(None, gt=0)
    state: Optional[TaskStateType] = None
    repeatable: Optional[bool] = None
    goal_id: Optional[int] = None


class Task(BaseModel):
    '''Full Pydantic model for tasks (includes DB-generated fields)'''

    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    category: CategoryType
    est_minutes: Optional[int] = Field(None, gt=0, le=1440)
    actual_minutes: Optional[int] = Field(None, gt=0)
    state: TaskStateType = 'ready'
    repeatable: bool = False
    last_completed_at: Optional[datetime] = None
    times_suggested: int = Field(default=0, ge=0)
    times_accepted: int = Field(default=0, ge=0)
    times_rejected: int = Field(default=0, ge=0)
    avg_energy_after: Optional[float] = Field(None, ge=1.0, le=5.0)
    goal_id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    @field_validator('completed_at')
    @classmethod
    def validate_completed_at(cls, v: Optional[datetime], info) -> Optional[datetime]:
        '''Ensure completed_at is set only when state is done or archived.'''
        state = info.data.get('state')
        if v is not None and state not in ('done', 'archived'):
            raise ValueError('completed_at can only be set when state is done or archived')
        return v

    model_config = ConfigDict(from_attributes=True)


class Session(BaseModel):
    '''Pydantic model for work sessions.'''

    id: Optional[int] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    available_minutes: Optional[int] = Field(None, gt=0, le=1440)
    energy_level: Optional[int] = Field(None, ge=1, le=5)
    focus_area: Optional[CategoryType] = None
    tasks_completed: int = Field(default=0, ge=0)
    effectiveness: Optional[int] = Field(None, ge=1, le=5)

    @field_validator('ended_at')
    @classmethod
    def validate_ended_at(cls, v: Optional[datetime], info) -> Optional[datetime]:
        '''Ensure ended_at is after started_at.'''
        started_at = info.data.get('started_at')
        if v is not None and started_at is not None and v <= started_at:
            raise ValueError('ended_at must be after started_at')
        return v

    model_config = ConfigDict(from_attributes=True)


class WorkEntry(BaseModel):
    '''Pydantic model for work entries.'''

    id: Optional[int] = None
    session_id: int
    task_id: int
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    completed: bool = False
    energy_after: Optional[int] = Field(None, ge=1, le=5)
    want_more_like_this: Optional[bool] = None
    abandoned_reason: Optional[AbandonedReasonType] = None

    @field_validator('ended_at')
    @classmethod
    def validate_ended_at(cls, v: Optional[datetime], info) -> Optional[datetime]:
        '''Ensure ended_at is after started_at.'''
        started_at = info.data.get('started_at')
        if v is not None and started_at is not None and v <= started_at:
            raise ValueError('ended_at must be after started_at')
        return v

    @field_validator('abandoned_reason')
    @classmethod
    def validate_abandoned_reason(cls, v: Optional[str], info) -> Optional[str]:
        '''Ensure abandoned_reason is only set when not completed.'''
        completed = info.data.get('completed')
        if v is not None and completed:
            raise ValueError('abandoned_reason should not be set when completed is True')
        return v

    model_config = ConfigDict(from_attributes=True)


# Database utilities

# API Response Models (generic, reusable across different interfaces)

class HealthCheckResponse(BaseModel):
    '''Response for health check operations'''
    success: bool
    message: str
    database_connected: bool
    total_tasks: int
    active_sessions: int
    timestamp: datetime


class TaskResponse(BaseModel):
    '''Generic response for task operations'''
    success: bool
    message: str
    task_id: Optional[int] = None


class TaskListResponse(BaseModel):
    '''Response for listing tasks'''
    success: bool
    message: str
    tasks: list[Task]


class TaskRecItem(BaseModel):
    '''Single recommendation item returned by the rec engine.'''
    task_id: int
    title: str
    category: CategoryType
    est_minutes: Optional[int] = None
    score: float = Field(..., ge=0.0, le=1.0)
    breakdown: dict[str, float]


class SessionResponse(BaseModel):
    '''Generic response for session operations'''
    success: bool
    message: str
    session_id: Optional[int] = None
    recommendations: list[TaskRecItem] = Field(default_factory=list)


class WorkEntryResponse(BaseModel):
    '''Generic response for work entry operations'''
    success: bool
    message: str
    work_entry_id: Optional[int] = None


class WeeklyGoalResponse(BaseModel):
    '''Generic response for weekly goal operations'''
    success: bool
    message: str
    goal_id: Optional[int] = None


class SessionSummary(BaseModel):
    '''Stats computed at session close.'''
    session_id: int
    duration_minutes: int
    tasks_completed: int
    effectiveness: Optional[int] = None
    categories_completed: dict[str, int]


class EndSessionResponse(BaseModel):
    '''Response for end_session.'''
    success: bool
    message: str
    summary: Optional[SessionSummary] = None


class WeeklyReviewResponse(BaseModel):
    '''Response for the weekly_review tool.'''
    success: bool
    message: str
    goal_id: Optional[int] = None
    goal_title: Optional[str] = None
    tasks_total: int = 0
    tasks_completed: int = 0
    time_invested_minutes: int = 0
    completion_pct: float = 0.0


class ResetTasksResponse(BaseModel):
    '''Response for the reset_tasks tool.'''
    success: bool
    message: str
    reset_count: int = 0
    task_ids: list[int] = Field(default_factory=list)


class DailyTriageItem(BaseModel):
    '''Single item in daily triage — a completed repeatable task.'''
    task_id: int
    title: str
    category: CategoryType
    last_completed_at: Optional[datetime] = None
    days_since_completion: int


class DailyTriageResponse(BaseModel):
    '''Response for the daily_triage tool.'''
    success: bool
    message: str
    tasks: list[DailyTriageItem] = Field(default_factory=list)


# Database helper functions

def create_tables(engine) -> None:
    '''Create all tables in the database.

    Args:
        engine: SQLAlchemy engine instance
    '''
    Base.metadata.create_all(engine)


def get_engine(database_url: str = 'sqlite:///v2_tasks.db'):
    '''Get SQLAlchemy engine for database connection.

    Args:
        database_url: Database connection URL

    Returns:
        SQLAlchemy engine instance
    '''
    return create_engine(database_url, echo=False)
