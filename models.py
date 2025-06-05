'''
This module contains the SQLAlchemy & Pydantic models for the task
management system.
'''
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Date, Float, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel

Base = declarative_base()

class WorkSessionModel(Base):
   '''WorkSessionModel is a model for the work_session table in the database'''
   __tablename__ = 'work_session'
   
   id = Column(Integer, primary_key=True)
   start_ts = Column(DateTime, default=datetime.now(timezone.utc))
   end_ts = Column(DateTime)
   planned_duration = Column(Integer)  # minutes
   context = Column(String)            # "90 minutes", "big tasks + breaks"
   query = Column(Text)               # original user request
   completion_pct = Column(Float)      # 0.0-1.0
   effectiveness_rating = Column(Integer)  # 1-5
   notes = Column(Text)

class TaskModel(Base):
    '''TaskModel is a model for the task table in the database'''
    __tablename__ = 'task'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    complexity = Column(String(10), nullable=False, default='simple')
    type = Column(String(20))
    due_date = Column(String(10))
    priority = Column(String(10), nullable=False, default='low')
    repeatable = Column(Boolean, default=False)
    status = Column(String(10), nullable=False, default='pending')
    next_scheduled = Column(Date)
    created_ts = Column(DateTime)
    updated_ts = Column(DateTime)


class RecommendationModel(Base):
    '''Model for the recommendation table in the database'''
    __tablename__ = 'recommendation'

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('work_session.id'))
    task_id = Column(Integer, ForeignKey('task.id'))
    rec_type = Column(String)          # "focus_tasks", "break_tasks"
    strategy = Column(String)          # "high_priority_first", "mix_complexity"
    status = Column(String, nullable=False, default='pending')  # "pending", "accepted", "rejected"
    rejected_reason = Column(String)   # Reason if status is "rejected"
    rec_ts = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    task = relationship('TaskModel', backref='recommendations')
    session = relationship('WorkSessionModel', backref='recommendations')


class WorkLogModel(Base):
    '''Model for the work_log table in the database'''
    __tablename__ = 'work_log'

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('work_session.id'))
    task_id = Column(Integer, ForeignKey('task.id'))
    rec_id = Column(Integer, ForeignKey('recommendation.id'))
    start_ts = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    end_ts = Column(DateTime)
    completion_pct = Column(Float)     # per-task completion
    task = relationship('TaskModel', backref='worklogs')
    recommendation = relationship('RecommendationModel', backref='worklogs')
    session = relationship('WorkSessionModel', backref='worklogs')


class TaskSummaryModel(Base):
    '''Model for the task_summary table in the database'''
    __tablename__ = 'task_summary'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'))
    time_worked = Column(Integer, nullable=False, default=0)
    num_restarts = Column(Integer, nullable=False, default=0)
    start_date = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    end_date = Column(DateTime)
    rating = Column(Integer, nullable=False, default=1)
    has_ended = Column(Boolean, default=False)
    task = relationship('TaskModel', backref='summary')


class WeeklyGoalModel(Base):
    '''Model for the weekly_goals table in the database'''
    __tablename__ = 'weekly_goals'

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(String(500))
    category = Column(String(50))
    start_date = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    end_date = Column(DateTime)
    status = Column(String(20), nullable=False, default='active')
    created_ts = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    updated_ts = Column(DateTime)


class GoalTaskModel(Base):
    '''Maps tasks to weekly goals with optional day assignment'''
    __tablename__ = 'goal_tasks'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'), nullable=False)
    goal_id = Column(Integer, ForeignKey('weekly_goals.id'), nullable=False)
    # Optional day number (1-7) if assigned to a specific day
    day_number = Column(Integer)
    # Optional percentage this task contributes to goal completion
    percent_split = Column(Float, nullable=True)
    created_ts = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    updated_ts = Column(DateTime)

    # Define relationships
    task = relationship('TaskModel', backref='goal_tasks')
    goal = relationship('WeeklyGoalModel', backref='goal_tasks')


class GoalProgressHistoryModel(Base):
    '''Tracks progress history for weekly goals'''
    __tablename__ = 'goal_progress_history'

    id = Column(Integer, primary_key=True)
    goal_id = Column(Integer, ForeignKey('weekly_goals.id'), nullable=False)
    timestamp = Column(
        DateTime, nullable=False, default=datetime.now(timezone.utc)
    )
    notes = Column(String(500))
    # Calculated completion percentage
    completion_pct = Column(Float, nullable=False)

    # Define relationship
    goal = relationship('WeeklyGoalModel', backref='progress_history')


# Pydantic Models


class WorkSession(BaseModel):
    '''WorkSession is a model for the work_session table in the database'''
    id: Optional[int] = None
    start_ts: datetime = datetime.now(timezone.utc)
    end_ts: Optional[datetime] = None
    planned_duration: Optional[int] = None  # minutes
    context: Optional[str] = None
    query: Optional[str] = None
    completion_pct: Optional[float] = None
    effectiveness_rating: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class Task(BaseModel):
    '''Task is a model for the task table in the database'''
    id: Optional[int] = None
    name: str
    complexity: str = 'simple'
    type: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = 'low'
    repeatable: bool = False
    status: str = 'pending'
    next_scheduled: Optional[datetime] = None
    created_ts: Optional[datetime] = None
    updated_ts: Optional[datetime] = None

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class Recommendation(BaseModel):
    '''Model for the recommendation table in the database'''
    id: Optional[int] = None
    session_id: int
    task_id: int
    rec_type: Optional[str] = None
    strategy: Optional[str] = None
    status: str = 'pending'  # "pending", "accepted", "rejected"
    rejected_reason: Optional[str] = None
    rec_ts: datetime = datetime.now(timezone.utc)

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class WorkLog(BaseModel):
    '''WorkLog is a log of the work done on a task'''
    id: Optional[int] = None
    session_id: int
    task_id: int
    rec_id: Optional[int] = None
    start_ts: datetime = datetime.now(timezone.utc)
    end_ts: Optional[datetime] = None
    completion_pct: Optional[float] = None

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class TaskSummary(BaseModel):
    '''TaskSummary is a summary of the work done on a task'''
    id: Optional[int] = None
    task_id: int
    time_worked: int = 0
    num_restarts: int = 0
    start_date: datetime = datetime.now(timezone.utc)
    end_date: Optional[datetime] = None
    rating: int = 1
    has_ended: bool = False

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class WeeklyGoal(BaseModel):
    '''WeeklyGoal is a model for weekly goals'''
    id: Optional[int] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    start_date: datetime = datetime.now(timezone.utc)
    end_date: Optional[datetime] = None
    status: str = 'pending'
    created_ts: datetime = datetime.now(timezone.utc)
    updated_ts: Optional[datetime] = None

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class GoalTask(BaseModel):
    '''GoalTask maps tasks to weekly goals with optional day assignment'''
    id: Optional[int] = None
    task_id: int
    goal_id: int
    day_number: Optional[int] = None
    percent_split: Optional[float] = None
    created_ts: datetime = datetime.now(timezone.utc)
    updated_ts: Optional[datetime] = None

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True


class GoalProgressHistory(BaseModel):
    '''Tracks progress history for weekly goals'''
    id: Optional[int] = None
    goal_id: int
    timestamp: datetime = datetime.now(timezone.utc)
    notes: Optional[str] = None
    completion_pct: float

    class Config:
        '''from_attributes allows Pydantic to work with SQLAlchemy models'''
        from_attributes = True
