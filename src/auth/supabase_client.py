"""
Inicialización del cliente Supabase por sesión de usuario y vinculación del JWT
en PostgREST para cumplimiento estricto de Row Level Security (RLS).
"""
from __future__ import annotations

from typing import Optional
import streamlit as st
from supabase import Client, create_client

from src.config.settings import get_supabase_key, get_supabase_url, is_supabase_configured


def get_supabase_client(access_token: Optional[str] = None) -> Client:
    """
    Retorna la instancia del cliente Supabase aislada en la sesión actual del usuario
    y autentica el cliente PostgREST con el JWT activo para que PostgreSQL evalúe
    `auth.uid() = user_id` en todas las operaciones CRUD.
    """
    if not is_supabase_configured():
        raise RuntimeError(
            "Las credenciales SUPABASE_URL y SUPABASE_ANON_KEY no están configuradas "
            "en .streamlit/secrets.toml."
        )

    url = get_supabase_url()
    key = get_supabase_key()

    if "_supabase_client" not in st.session_state or st.session_state["_supabase_client"] is None:
        st.session_state["_supabase_client"] = create_client(url, key)

    client: Client = st.session_state["_supabase_client"]

    token = access_token or st.session_state.get("access_token")
    if token:
        client.postgrest.auth(token)

    return client
