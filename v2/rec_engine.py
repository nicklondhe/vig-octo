'''
Task recommendation engine using a weighted scoring system.

Scores every ready task across four axes and returns the top-n ranked results:

  time_match          — fits within the available session time
  balance             — avoids category over-sampling within the session
  rejection_penalty   — respects recently / frequently rejected tasks
  momentum_completion — favours tasks that build dopamine and session flow

Data loading: fixed number of queries regardless of task count.
  1. get_session                         (if session_id given)
  2. get_work_entries_by_session         (if session_id given)
  3. get_tasks_by_ids                    (session entry tasks, if any)
  4. get_all_tasks(state='ready')
  5. get_latest_abandoned_entries_batch  (one query for all task ids)

Scoring: fully vectorised via pandas — y = W · x.
'''

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from v2.db import TaskDB
from v2.models import TaskRecItem

# ---------------------------------------------------------------------------
# Default weights — must sum to 1.0
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    'time_match': 0.30,
    'balance': 0.20,
    'rejection_penalty': 0.25,
    'momentum_completion': 0.25,
}

REJECTION_RECENCY_DAYS: int = 7

AXES = list(DEFAULT_WEIGHTS)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RecEngine:
    '''
    Weighted recommendation engine for task prioritisation.

    Example::

        engine = RecEngine(db)
        recs = engine.recommend(available_minutes=60, session_id=3, n=5)
    '''

    def __init__(
        self,
        db: TaskDB,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        self.db = db
        self.weights = weights or DEFAULT_WEIGHTS
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f'Weights must sum to 1.0, got {total:.6f}')

    def recommend(
        self,
        available_minutes: Optional[int] = None,
        session_id: Optional[int] = None,
        focus_area: Optional[str] = None,
        n: int = 5,
        mark_suggested: bool = True,
    ) -> list[TaskRecItem]:
        '''
        Rank all ready tasks and return the top n.

        Args:
            available_minutes: Time budget in minutes. Overrides session value.
            session_id:        Loads context (time, focus, category distribution)
                               from the session. Explicit args take precedence.
            focus_area:        Category to favour ('grow', 'maintain', 'sustain').
            n:                 Number of recommendations to return.
            mark_suggested:    Increment times_suggested for returned tasks.
        '''
        # --- Query 1+2+3: session context (fixed cost) -------------------
        session_category_counts, completed_categories = {}, []
        if session_id is not None:
            available_minutes, focus_area, session_category_counts, completed_categories = (
                self._load_session_context(session_id, available_minutes, focus_area)
            )

        # --- Query 4: all ready tasks → DataFrame ------------------------
        tasks = self.db.get_all_tasks(state='ready')
        if not tasks:
            return []

        df = pd.DataFrame([t.model_dump() for t in tasks])

        # --- Query 5: batch latest abandoned entry per task --------------
        abandoned = self.db.get_latest_abandoned_entries_batch(df['id'].tolist())
        now = datetime.now(timezone.utc)
        if abandoned:
            abandoned_df = pd.DataFrame([
                {
                    'id': e.task_id,
                    'days_ago': (
                        now - (
                            e.started_at if e.started_at.tzinfo
                            else e.started_at.replace(tzinfo=timezone.utc)
                        )
                    ).total_seconds() / 86_400,
                }
                for e in abandoned
            ])
            df = df.merge(abandoned_df, on='id', how='left')
        else:
            df['days_ago'] = float('nan')

        # --- Feature matrix (fully vectorised) ---------------------------
        df['time_match'] = self._feat_time_match(df, available_minutes)
        df['balance'] = self._feat_balance(df, focus_area, session_category_counts)
        df['rejection_penalty'] = self._feat_rejection(df)
        df['momentum_completion'] = self._feat_momentum(df, completed_categories)

        # --- Score: y = W · x --------------------------------------------
        weight_series = pd.Series(self.weights)
        df['score'] = df[AXES].dot(weight_series).round(4)

        top = df.nlargest(n, 'score')

        if mark_suggested:
            for task_id in top['id']:
                self.db.increment_task_stat(int(task_id), 'suggested')

        return [
            TaskRecItem(
                task_id=int(row['id']),
                title=row['title'],
                category=row['category'],
                est_minutes=None if pd.isna(row.get('est_minutes')) else int(row['est_minutes']),
                score=float(row['score']),
                breakdown={a: round(float(row[a]), 4) for a in AXES},
            )
            for _, row in top.iterrows()
        ]

    # ------------------------------------------------------------------
    # Session context loader
    # ------------------------------------------------------------------

    def _load_session_context(
        self,
        session_id: int,
        available_minutes: Optional[int],
        focus_area: Optional[str],
    ) -> tuple[Optional[int], Optional[str], dict[str, int], list[str]]:
        '''Load and return (available_minutes, focus_area, category_counts, completed_categories).'''
        session_category_counts: dict[str, int] = {}
        completed_categories: list[str] = []

        session = self.db.get_session(session_id)
        if session is None:
            return available_minutes, focus_area, session_category_counts, completed_categories

        if available_minutes is None:
            available_minutes = session.available_minutes
        if focus_area is None and session.focus_area:
            focus_area = session.focus_area

        entries = self.db.get_work_entries_by_session(session_id)
        if entries:
            entry_tasks = self.db.get_tasks_by_ids([e.task_id for e in entries])
            cat_by_id = {t.id: t.category for t in entry_tasks}
            for entry in entries:
                cat = cat_by_id.get(entry.task_id)
                if cat:
                    session_category_counts[cat] = session_category_counts.get(cat, 0) + 1
                    if entry.completed:
                        completed_categories.append(cat)

        return available_minutes, focus_area, session_category_counts, completed_categories

    # ------------------------------------------------------------------
    # Vectorised feature computations
    # ------------------------------------------------------------------

    def _feat_time_match(self, df: pd.DataFrame, available_minutes: Optional[int]) -> pd.Series:
        '''
        Score how well each task fits in the available time window.

        no info          → 0.5
        exceeds avail    → 0.0
        <10% of slot     → 0.3
        10–30% of slot   → 0.6
        30–80% of slot   → 1.0  (sweet spot)
        >80% of slot     → 0.9
        '''
        if available_minutes is None:
            return pd.Series(0.5, index=df.index)

        ratio = df['est_minutes'] / available_minutes

        return pd.Series(
            np.select(
                [ratio.isna(), ratio > 1.0, ratio < 0.10, ratio < 0.30, ratio <= 0.80],
                [0.5,          0.0,         0.3,          0.6,          1.0],
                default=0.9,  # >80% — nearly fills the slot
            ),
            index=df.index,
            dtype=float,
        )

    def _feat_balance(
        self,
        df: pd.DataFrame,
        focus_area: Optional[str],
        session_category_counts: dict[str, int],
    ) -> pd.Series:
        '''
        Penalise over-represented categories; boost focus_area matches.

        focus match  → 1.0 (no over-rep penalty applied)
        non-focus    → base 0.35, then reduced if over-represented
        no focus     → base 0.75, then reduced if over-represented
        '''
        total_done = sum(session_category_counts.values())

        if focus_area:
            base = df['category'].map(lambda c: 1.0 if c == focus_area else 0.35)
        else:
            base = pd.Series(0.75, index=df.index)

        if total_done > 0 and focus_area is None:
            cat_ratios = df['category'].map(
                lambda c: session_category_counts.get(c, 0) / total_done
            )
            excess = (cat_ratios - 1 / 3).clip(lower=0)
            base = (base - 3.0 * excess).clip(lower=0.0)

        return base

    def _feat_rejection(self, df: pd.DataFrame) -> pd.Series:
        '''
        Score in [0, 1] — lower means frequently or recently rejected.

        global_rate = times_rejected / times_suggested  (0.8 if never suggested)
        recency     = 0.4 decay over REJECTION_RECENCY_DAYS
        '''
        never_suggested = df['times_suggested'] == 0
        global_rate = (df['times_rejected'] / df['times_suggested'].clip(lower=1)).where(
            ~never_suggested, other=0.2   # novelty: maps to 1 - 0.2 = 0.8
        )
        recency_penalty = (
            0.4 * (1 - df['days_ago'] / REJECTION_RECENCY_DAYS)
        ).clip(lower=0).fillna(0)

        return (1 - global_rate - recency_penalty).clip(lower=0.0)

    def _feat_momentum(
        self,
        df: pd.DataFrame,
        completed_categories: list[str],
    ) -> pd.Series:
        '''
        Momentum and dopamine potential.

        energy       — avg_energy_after normalised 1–5 → 0–1; 0.5 if unknown
        opener_penalty — sustain as session opener: −0.25
        streak_bonus   — last completed category match: +0.15; grow→grow: +0.20
        '''
        energy = ((pd.to_numeric(df['avg_energy_after'], errors='coerce') - 1) / 4.0).clip(0, 1).fillna(0.5)

        opener_penalty = pd.Series(0.0, index=df.index)
        if not completed_categories:
            opener_penalty = (df['category'] == 'sustain').astype(float) * 0.25

        streak_bonus = pd.Series(0.0, index=df.index)
        if completed_categories:
            last = completed_categories[-1]
            streak_bonus = (df['category'] == last).astype(float) * 0.15
            if last == 'grow':
                streak_bonus = (df['category'] == 'grow').astype(float) * 0.20

        return (energy + streak_bonus - opener_penalty).clip(0.0, 1.0)
