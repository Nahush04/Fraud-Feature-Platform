"""Point-in-time join: attach feature values to a labeled training event using
only the feature history that existed strictly before that event.

This is the reason a feature store's offline side keeps full history rather
than only "current" values: training on the online store's *current* value
for a past event would leak anything the entity did between that event and
now. `pandas.merge_asof(..., allow_exact_matches=False)` does the as-of
match — for each event, the most recent feature row strictly before it.
"""

from __future__ import annotations

import pandas as pd

from fstore.offline import ENTITY_COL, TIME_COL


def point_in_time_join(
    events: pd.DataFrame,
    feature_history: pd.DataFrame,
    event_time_col: str = "event_time",
    entity_col: str = ENTITY_COL,
    feature_time_col: str = TIME_COL,
) -> pd.DataFrame:
    events_sorted = events.sort_values(event_time_col).reset_index(drop=True)
    history_sorted = feature_history.sort_values(feature_time_col).reset_index(drop=True)

    merged = pd.merge_asof(
        events_sorted,
        history_sorted,
        left_on=event_time_col,
        right_on=feature_time_col,
        by=entity_col,
        direction="backward",
        allow_exact_matches=False,  # strictly before, never at, the event's own timestamp
        suffixes=("", "_feature"),
    )
    return merged
