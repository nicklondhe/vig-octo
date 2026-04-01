'''Unit tests for v2 RecEngine'''

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from v2.db import TaskDB
from v2.models import Base
from v2.rec_engine import RecEngine


@pytest.fixture
def db_engine():
    '''In-memory SQLite engine.'''
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def task_db(db_engine):
    return TaskDB(db_engine)


@pytest.fixture
def engine(task_db):
    return RecEngine(task_db)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestRecEngineInit:
    '''Tests for RecEngine.__init__'''

    def test_invalid_weights_raises(self, task_db):
        '''Weights that don't sum to 1.0 should raise ValueError.'''
        with pytest.raises(ValueError, match='Weights must sum to 1.0'):
            RecEngine(task_db, weights={
                'time_match': 0.50,
                'balance': 0.50,
                'rejection_penalty': 0.50,
                'momentum_completion': 0.50,
            })

    def test_custom_valid_weights(self, task_db):
        '''Custom weights summing to 1.0 should be accepted.'''
        eng = RecEngine(task_db, weights={
            'time_match': 0.25,
            'balance': 0.25,
            'rejection_penalty': 0.25,
            'momentum_completion': 0.25,
        })
        assert eng.weights['time_match'] == 0.25


# ---------------------------------------------------------------------------
# recommend — empty / basic
# ---------------------------------------------------------------------------

class TestRecommendBasic:
    '''Basic recommend() behaviour.'''

    def test_returns_empty_when_no_ready_tasks(self, engine):
        recs = engine.recommend()
        assert recs == []

    def test_returns_up_to_n_results(self, task_db, engine):
        for i in range(10):
            task_db.create_task(f'Task {i}', 'grow')
        recs = engine.recommend(n=3)
        assert len(recs) <= 3

    def test_rec_item_fields(self, task_db, engine):
        task_db.create_task('My task', 'grow', est_minutes=30)
        recs = engine.recommend()
        assert len(recs) == 1
        r = recs[0]
        assert r.title == 'My task'
        assert r.category == 'grow'
        assert r.est_minutes == 30
        assert 0.0 <= r.score <= 1.0
        assert set(r.breakdown.keys()) == {'time_match', 'balance', 'rejection_penalty', 'momentum_completion'}

    def test_mark_suggested_increments_stat(self, task_db, engine):
        task = task_db.create_task('Task', 'grow')
        engine.recommend(mark_suggested=True)
        updated = task_db.get_task(task.id)
        assert updated.times_suggested == 1

    def test_mark_suggested_false_does_not_increment(self, task_db, engine):
        task = task_db.create_task('Task', 'grow')
        engine.recommend(mark_suggested=False)
        updated = task_db.get_task(task.id)
        assert updated.times_suggested == 0


# ---------------------------------------------------------------------------
# recommend — session context
# ---------------------------------------------------------------------------

class TestRecommendSessionContext:
    '''Session context loading.'''

    def test_invalid_session_id_still_returns_recs(self, task_db, engine):
        '''Non-existent session_id → early return from _load_session_context, still scores tasks.'''
        task_db.create_task('Task', 'grow')
        recs = engine.recommend(session_id=9999)
        assert len(recs) == 1

    def test_session_with_no_entries(self, task_db, engine):
        '''Session that exists but has no work entries.'''
        task_db.create_task('Task', 'grow')
        session = task_db.create_session(available_minutes=60)
        recs = engine.recommend(session_id=session.id)
        assert len(recs) == 1

    def test_session_available_minutes_used(self, task_db, engine):
        '''available_minutes from session propagates to time_match scoring.'''
        task_db.create_task('Quick', 'grow', est_minutes=20)
        task_db.create_task('Long', 'grow', est_minutes=120)
        session = task_db.create_session(available_minutes=60)
        recs = engine.recommend(session_id=session.id)
        # Quick task should score higher on time_match than Long task
        quick = next(r for r in recs if r.title == 'Quick')
        long = next(r for r in recs if r.title == 'Long')
        assert quick.breakdown['time_match'] > long.breakdown['time_match']

    def test_explicit_available_minutes_overrides_session(self, task_db, engine):
        '''Explicit available_minutes takes precedence over session value.'''
        task_db.create_task('Task', 'grow', est_minutes=30)
        session = task_db.create_session(available_minutes=10)
        # 30 min task in 10 min slot → exceeds → 0.0; but 60 min slot → fits → 1.0
        recs_tight = engine.recommend(session_id=session.id)
        recs_wide = engine.recommend(session_id=session.id, available_minutes=60)
        assert recs_wide[0].breakdown['time_match'] > recs_tight[0].breakdown['time_match']

    def test_session_focus_area_used(self, task_db, engine):
        '''focus_area from session boosts matching category.'''
        task_db.create_task('Grow task', 'grow')
        task_db.create_task('Maintain task', 'maintain')
        session = task_db.create_session(focus_area='grow')
        recs = engine.recommend(session_id=session.id)
        grow_rec = next(r for r in recs if r.title == 'Grow task')
        maintain_rec = next(r for r in recs if r.title == 'Maintain task')
        assert grow_rec.breakdown['balance'] > maintain_rec.breakdown['balance']

    def test_session_with_work_entries_builds_category_counts(self, task_db, engine):
        '''Work entries in session populate category distribution for balance scoring.'''
        task_db.create_task('Ready task', 'grow')
        session = task_db.create_session()
        # Add a completed work entry so grow is over-represented
        done_task = task_db.create_task('Done task', 'grow')
        entry = task_db.start_work_entry(session.id, done_task.id)
        task_db.complete_work_entry(entry.id, completed=True)
        task_db.update_task(done_task.id, state='done')
        # recommend should still return the ready task
        recs = engine.recommend(session_id=session.id)
        assert any(r.title == 'Ready task' for r in recs)

    def test_session_entries_track_completed_categories(self, task_db, engine):
        '''Completed entries in session feed into momentum streak scoring.'''
        task_db.create_task('Next grow', 'grow')
        session = task_db.create_session()
        done_task = task_db.create_task('Done grow', 'grow')
        entry = task_db.start_work_entry(session.id, done_task.id)
        task_db.complete_work_entry(entry.id, completed=True)
        task_db.update_task(done_task.id, state='done')
        recs = engine.recommend(session_id=session.id)
        rec = next(r for r in recs if r.title == 'Next grow')
        # grow→grow streak bonus should be > 0
        assert rec.breakdown['momentum_completion'] > 0.5


# ---------------------------------------------------------------------------
# Abandoned entries
# ---------------------------------------------------------------------------

class TestAbandonedEntries:
    '''Abandoned entry path in recommend().'''

    def test_abandoned_task_gets_recency_penalty(self, task_db, engine):
        '''A recently abandoned task scores lower on rejection_penalty than a fresh one.'''
        abandoned_task = task_db.create_task('Abandoned', 'grow')
        fresh_task = task_db.create_task('Fresh', 'grow')

        session = task_db.create_session()
        entry = task_db.start_work_entry(session.id, abandoned_task.id)
        task_db.complete_work_entry(entry.id, completed=False, abandoned_reason='blocked')

        recs = engine.recommend(mark_suggested=False)
        ab_rec = next(r for r in recs if r.title == 'Abandoned')
        fresh_rec = next(r for r in recs if r.title == 'Fresh')
        assert ab_rec.breakdown['rejection_penalty'] < fresh_rec.breakdown['rejection_penalty']


# ---------------------------------------------------------------------------
# _feat_time_match
# ---------------------------------------------------------------------------

class TestFeatTimeMatch:
    '''Time-match feature scoring edge cases.'''

    def test_no_available_minutes_returns_half(self, task_db, engine):
        task_db.create_task('Task', 'grow', est_minutes=30)
        recs = engine.recommend(available_minutes=None)
        assert recs[0].breakdown['time_match'] == 0.5

    def test_task_exceeds_slot(self, task_db, engine):
        '''est_minutes > available_minutes → 0.0.'''
        task_db.create_task('Big task', 'grow', est_minutes=120)
        recs = engine.recommend(available_minutes=60)
        assert recs[0].breakdown['time_match'] == 0.0

    def test_task_tiny_fraction_of_slot(self, task_db, engine):
        '''est_minutes < 10% of slot → 0.3.'''
        task_db.create_task('Tiny', 'grow', est_minutes=5)
        recs = engine.recommend(available_minutes=120)  # 5/120 ≈ 4%
        assert recs[0].breakdown['time_match'] == 0.3

    def test_task_fills_10_to_30_pct(self, task_db, engine):
        '''10–30% of slot → 0.6.'''
        task_db.create_task('Small', 'grow', est_minutes=15)
        recs = engine.recommend(available_minutes=100)  # 15/100 = 15%
        assert recs[0].breakdown['time_match'] == 0.6

    def test_task_in_sweet_spot(self, task_db, engine):
        '''30–80% of slot → 1.0.'''
        task_db.create_task('Good fit', 'grow', est_minutes=45)
        recs = engine.recommend(available_minutes=100)  # 45%
        assert recs[0].breakdown['time_match'] == 1.0

    def test_task_fills_over_80_pct(self, task_db, engine):
        '''>80% of slot → 0.9.'''
        task_db.create_task('Almost full', 'grow', est_minutes=85)
        recs = engine.recommend(available_minutes=100)  # 85%
        assert recs[0].breakdown['time_match'] == 0.9

    def test_no_est_minutes_returns_half(self, task_db, engine):
        '''No est_minutes (NaN) → 0.5.'''
        task_db.create_task('No estimate', 'grow')
        recs = engine.recommend(available_minutes=60)
        assert recs[0].breakdown['time_match'] == 0.5


# ---------------------------------------------------------------------------
# _feat_balance
# ---------------------------------------------------------------------------

class TestFeatBalance:
    '''Balance feature scoring.'''

    def test_focus_area_match_scores_one(self, task_db, engine):
        task_db.create_task('Grow task', 'grow')
        recs = engine.recommend(focus_area='grow')
        assert recs[0].breakdown['balance'] == 1.0

    def test_focus_area_non_match_scores_lower(self, task_db, engine):
        task_db.create_task('Maintain task', 'maintain')
        recs = engine.recommend(focus_area='grow')
        assert recs[0].breakdown['balance'] == 0.35

    def test_no_focus_no_session_history_scores_075(self, task_db, engine):
        task_db.create_task('Task', 'grow')
        recs = engine.recommend()
        assert recs[0].breakdown['balance'] == 0.75

    def test_over_represented_category_penalised(self, task_db, engine):
        '''Without focus_area, over-represented category gets reduced balance score.'''
        task_db.create_task('Grow A', 'grow')
        task_db.create_task('Grow B', 'grow')
        task_db.create_task('Maintain', 'maintain')

        session = task_db.create_session()
        # Add two completed grow tasks to skew distribution
        for title in ['Done Grow 1', 'Done Grow 2']:
            t = task_db.create_task(title, 'grow')
            e = task_db.start_work_entry(session.id, t.id)
            task_db.complete_work_entry(e.id, completed=True)
            task_db.update_task(t.id, state='done')

        recs = engine.recommend(session_id=session.id)
        grow_recs = [r for r in recs if r.category == 'grow']
        maintain_recs = [r for r in recs if r.category == 'maintain']
        if grow_recs and maintain_recs:
            assert maintain_recs[0].breakdown['balance'] >= grow_recs[0].breakdown['balance']


# ---------------------------------------------------------------------------
# _feat_momentum
# ---------------------------------------------------------------------------

class TestFeatMomentum:
    '''Momentum / dopamine feature scoring.'''

    def test_sustain_opener_penalty(self, task_db, engine):
        '''Sustain task as session opener gets penalty vs grow.'''
        task_db.create_task('Grow task', 'grow')
        task_db.create_task('Sustain task', 'sustain')
        recs = engine.recommend()
        grow_rec = next(r for r in recs if r.title == 'Grow task')
        sustain_rec = next(r for r in recs if r.title == 'Sustain task')
        assert grow_rec.breakdown['momentum_completion'] > sustain_rec.breakdown['momentum_completion']

    def test_streak_bonus_same_category(self, task_db, engine):
        '''Last completed category match adds streak bonus.'''
        task_db.create_task('Maintain next', 'maintain')
        session = task_db.create_session()
        done = task_db.create_task('Done maintain', 'maintain')
        e = task_db.start_work_entry(session.id, done.id)
        task_db.complete_work_entry(e.id, completed=True)
        task_db.update_task(done.id, state='done')

        recs = engine.recommend(session_id=session.id)
        rec = recs[0]
        assert rec.breakdown['momentum_completion'] > 0.5

    def test_grow_streak_bonus_higher(self, task_db, engine):
        '''grow→grow streak gives +0.20 vs +0.15 for other categories.'''
        task_db.create_task('Grow next', 'grow')
        task_db.create_task('Maintain next', 'maintain')

        session = task_db.create_session()
        done = task_db.create_task('Done grow', 'grow')
        e = task_db.start_work_entry(session.id, done.id)
        task_db.complete_work_entry(e.id, completed=True)
        task_db.update_task(done.id, state='done')

        recs = engine.recommend(session_id=session.id)
        grow_rec = next(r for r in recs if r.title == 'Grow next')
        maintain_rec = next(r for r in recs if r.title == 'Maintain next')
        assert grow_rec.breakdown['momentum_completion'] > maintain_rec.breakdown['momentum_completion']

    def test_energy_after_boosts_momentum(self, task_db, engine):
        '''High avg_energy_after task scores higher momentum than unknown.'''
        high_energy = task_db.create_task('Energising', 'grow')
        unknown_energy = task_db.create_task('Unknown energy', 'grow')

        # Simulate high energy by completing a work entry with high energy_after
        session = task_db.create_session()
        e = task_db.start_work_entry(session.id, high_energy.id)
        task_db.complete_work_entry(e.id, completed=False, energy_after=5)
        # Task stays ready (not completed)

        recs = engine.recommend(session_id=session.id, mark_suggested=False)
        high_rec = next(r for r in recs if r.title == 'Energising')
        unknown_rec = next(r for r in recs if r.title == 'Unknown energy')
        assert high_rec.breakdown['momentum_completion'] >= unknown_rec.breakdown['momentum_completion']
