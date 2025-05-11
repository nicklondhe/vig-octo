''' This module contains the SQLAlchemy & Pydantic models for the task management system. '''
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel

Base = declarative_base()

# SQLAlchemy Models
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

class RecommendationModel(Base):
    '''RecommendationModel is a model for the recommendation table in the database'''
    __tablename__ = 'recommendation'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'))
    rec_ts = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    task = relationship('TaskModel', backref='recommendations')

class WorkLogModel(Base):
    '''WorkLogModel is a model for the work_log table in the database'''
    __tablename__ = 'work_log'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'))
    rec_id = Column(Integer, ForeignKey('recommendation.id'))
    start_ts = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    end_ts = Column(DateTime)
    task = relationship('TaskModel', backref='worklogs')
    recommendation = relationship('RecommendationModel', backref='worklogs')

class TaskSummaryModel(Base):
    '''TaskSummaryModel is a model for the task_summary table in the database'''
    __tablename__ = 'task_summary'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('task.id'))
    time_worked = Column(Integer, nullable=False, default=0)
    num_restarts = Column(Integer, nullable=False, default=0)
    start_date = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    end_date = Column(DateTime)
    rating = Column(Integer, nullable=False, default=1)
    has_ended = Column(Boolean, default=False)
    task = relationship('TaskModel', backref='summary')

# Pydantic Models
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

    class Config:
        '''orm mode allows Pydantic to work with SQLAlchemy models'''
        orm_mode = True

class Recommendation(BaseModel):
    '''Recommendation is a model for the recommendation table in the database'''
    id: Optional[int] = None
    task_id: int
    rec_ts: datetime = datetime.now(timezone.utc)

    class Config:
        '''orm mode allows Pydantic to work with SQLAlchemy models'''
        orm_mode = True

class WorkLog(BaseModel):
    '''WorkLog is a log of the work done on a task'''
    id: Optional[int] = None
    task_id: int
    rec_id: Optional[int] = None
    start_ts: datetime = datetime.now(timezone.utc)
    end_ts: Optional[datetime] = None

    class Config:
        '''orm mode allows Pydantic to work with SQLAlchemy models'''
        orm_mode = True

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
        '''orm mode allows Pydantic to work with SQLAlchemy models'''
        orm_mode = True
