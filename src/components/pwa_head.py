"""
Componente de optimización PWA (Progressive Web App) y meta-tags para instalación
como aplicación nativa a pantalla completa en iOS Safari y Android Chrome (Sprint 5).
"""
from __future__ import annotations

import base64
import json
import streamlit as st
import streamlit.components.v1 as components

SVG_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="42" fill="#0A0D14"/>
  <rect x="8" y="8" width="176" height="176" rx="36" fill="#121722" stroke="#3B82F6" stroke-width="4"/>
  <path d="M106 28L52 104h38l-8 60 58-78H102l4-58z" fill="#3B82F6"/>
</svg>"""


def inject_pwa_metadata() -> None:
    """
    Inyecta de forma silenciosa en el `<head>` del navegador móvil:
    - Web App Manifest (Data URI) con ícono SVG y `display: standalone`
    - Meta-tags para iOS (`apple-mobile-web-app-capable`, `black-translucent`)
    - Color de barra de estado `#0A0D14` (Obsidian Canvas).
    """
    if st.session_state.get("_pwa_head_injected"):
        return

    icon_b64 = base64.b64encode(SVG_ICON.encode("utf-8")).decode("utf-8")
    icon_data_uri = f"data:image/svg+xml;base64,{icon_b64}"

    manifest_dict = {
        "name": "TRIFECTA LifeOS",
        "short_name": "Trifecta",
        "description": "Sistema Operativo Personal: Entrenamiento, Finanzas y Hábitos.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0A0D14",
        "theme_color": "#0A0D14",
        "orientation": "portrait",
        "icons": [
            {
                "src": icon_data_uri,
                "sizes": "192x192",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
    }
    manifest_b64 = base64.b64encode(json.dumps(manifest_dict).encode("utf-8")).decode("utf-8")
    manifest_uri = f"data:application/manifest+json;base64,{manifest_b64}"

    components.html(
        f"""
        <script>
        (function() {{
            try {{
                const doc = window.parent.document;
                if (!doc.getElementById('trifecta-pwa-manifest')) {{
                    const link = doc.createElement('link');
                    link.id = 'trifecta-pwa-manifest';
                    link.rel = 'manifest';
                    link.href = '{manifest_uri}';
                    doc.head.appendChild(link);

                    const metas = [
                        {{ name: 'theme-color', content: '#0A0D14' }},
                        {{ name: 'apple-mobile-web-app-capable', content: 'yes' }},
                        {{ name: 'mobile-web-app-capable', content: 'yes' }},
                        {{ name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' }},
                        {{ name: 'apple-mobile-web-app-title', content: 'Trifecta' }}
                    ];
                    metas.forEach(m => {{
                        const meta = doc.createElement('meta');
                        meta.name = m.name;
                        meta.content = m.content;
                        doc.head.appendChild(meta);
                    }});

                    const appleIcon = doc.createElement('link');
                    appleIcon.rel = 'apple-touch-icon';
                    appleIcon.href = '{icon_data_uri}';
                    doc.head.appendChild(appleIcon);
                }}
            }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )
    st.session_state["_pwa_head_injected"] = True
