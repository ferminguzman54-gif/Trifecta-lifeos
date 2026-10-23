"""
Puente de compatibilidad hacia `src/views/hub_view.py` (Sprint 5 Command Center Hub).
Conserva `_fetch_hub_summary_counts` para invalidaciones de caché de módulos existentes.
"""
from __future__ import annotations

from typing import Dict
import streamlit as st

from src.auth.supabase_client import get_supabase_client
from src.views.hub_view import render_hub_view


@st.cache_data(ttl=300)
def _fetch_hub_summary_counts(user_id: str, access_token: str) -> Dict[str, int]:
    """Consulta conteos básicos aislados por user_id para el Command Center."""
    counts = {
        "exercises_catalog": 0,
        "workout_sessions": 0,
        "finance_accounts": 0,
        "finance_categories": 0,
        "habits_active": 0,
        "personal_goals": 0,
    }
    try:
        client = get_supabase_client(access_token=access_token)
        ex_res = client.table("exercises").select("id", count="exact").execute()
        counts["exercises_catalog"] = ex_res.count or len(ex_res.data or [])

        ws_res = client.table("workout_sessions").select("id", count="exact").eq("user_id", user_id).execute()
        counts["workout_sessions"] = ws_res.count or len(ws_res.data or [])

        fa_res = client.table("finance_accounts").select("id", count="exact").eq("user_id", user_id).execute()
        counts["finance_accounts"] = fa_res.count or len(fa_res.data or [])

        fc_res = client.table("finance_categories").select("id", count="exact").eq("user_id", user_id).execute()
        counts["finance_categories"] = fc_res.count or len(fc_res.data or [])

        hb_res = (
            client.table("habits")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_archived", False)
            .execute()
        )
        counts["habits_active"] = hb_res.count or len(hb_res.data or [])

        pg_res = client.table("personal_goals").select("id", count="exact").eq("user_id", user_id).execute()
        counts["personal_goals"] = pg_res.count or len(pg_res.data or [])
    except Exception:
        pass
    return counts


def render_home_hub_view() -> None:
    """Delega al nuevo Command Center Central del Sprint 5 (`render_hub_view`)."""
    render_hub_view()
