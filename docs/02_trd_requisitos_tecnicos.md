# 02. TRD — Documento de Requisitos Técnicos: TRIFECTA LifeOS

## 1. El stack tecnológico prioriza compatibilidad con Streamlit Cloud, persistencia en Supabase y mantenibilidad en GitHub

Este documento define las decisiones técnicas cerradas para que **Antigravity** construya el código sin realizar suposiciones sobre librerías, versiones, estructura de directorios ni patrones de estado.

| Capa de Arquitectura | Tecnología Seleccionada | Versión Mínima / Recomendada | Justificación Técnica |
| :--- | :--- | :--- | :--- |
| **Lenguaje Base** | Python | `3.11+` | Soporte nativo de tipado moderno (`typing`, `dataclasses`, `pydantic`) y compatibilidad total en Streamlit Cloud |
| **Framework Frontend/App** | Streamlit | `>=1.38.0` | Incluye `st.navigation`, `st.Page`, `@st.dialog` (modales móviles nativos) y `@st.fragment` (recargas parciales sin refrescar toda la pantalla) |
| **Base de Datos y Auth** | Supabase (`supabase-py`) | `>=2.7.0` | Provee PostgreSQL gestionado, autenticación JWT (`gotrue`) y seguridad por fila (`RLS`) sin servidores intermedios |
| **Persistencia de Sesión Móvil** | `extra-streamlit-components` | `>=0.1.71` | Provee `CookieManager` para almacenar el `refresh_token` de Supabase en el navegador móvil y evitar cierres de sesión al recargar |
| **Motor de Gráficas** | Plotly (`plotly`) | `>=5.24.0` | Gráficas interactivas (`go.Bar`, `go.Scatter`, `go.Pie`, `go.Heatmap`) adaptables al ancho móvil (`use_container_width=True`) con tema oscuro transparente |
| **Procesamiento de Datos** | Pandas + NumPy | `>=2.2.0` / `>=1.26.0` | Resampleo de series temporales para los 8 filtros de volumen muscular (`1D` a `1Y`) y cálculos financieros |
| **Validación de Modelos** | Pydantic | `>=2.8.0` | Validación estricta de payloads antes de insertar o actualizar en Supabase |
| **Extracción de PDF (Fase 2)** | `pdfplumber` | `>=0.11.4` | Extracción determinista de tablas y texto en estados de cuenta bancarios PDF sin depender de binarios del sistema |

## 2. La estructura modular del repositorio en GitHub separa interfaz, lógica de negocio y acceso a datos

Antigravity deberá crear exactamente este árbol de directorios. Ningún archivo de vista (`views/`) debe ejecutar consultas directas a Supabase; toda interacción pasa por los servicios (`services/`) y repositorios (`repositories/`).

```text
trifecta-lifeos/
├── .streamlit/
│   ├── config.toml                  # Configuración del tema oscuro y ajustes de servidor móvil
│   └── secrets.toml.example         # Plantilla de variables SUPABASE_URL y SUPABASE_KEY (ignorar secrets.toml en git)
├── docs/
│   ├── 01_PRD_Requisitos_Producto.md
│   ├── 02_TRD_Requisitos_Tecnicos.md
│   ├── 03_Appflow_Flujo_Usuario.md
│   ├── 04_UI_UX_Design_Brief.md
│   ├── 05_Backend_Schema_Supabase.md
│   └── 06_Plan_Implementacion_Antigravity.md
├── sql/
│   ├── 01_schema_ddl.sql            # Script SQL ejecutable con tablas, índices, vistas y RLS
│   └── 02_seed_catalog.sql          # Catálogo base de ejercicios y categorías financieras
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py              # Carga segura de st.secrets y constantes globales
│   │   └── theme.py                 # Paleta hexadecimal por pilar e inyección de CSS global
│   ├── auth/
│   │   ├── supabase_client.py       # Inicialización del cliente Supabase y vinculación del JWT de sesión
│   │   └── session_manager.py       # Login, Sign-up, Logout y persistencia de tokens en CookieManager
│   ├── models/
│   │   ├── workout_models.py        # Esquemas Pydantic para rutinas, sesiones, series y nutrición base
│   │   ├── finance_models.py        # Esquemas Pydantic para cuentas, TDC, transacciones y presupuestos
│   │   └── habit_models.py          # Esquemas Pydantic para hábitos editables, registros y metas/hitos
│   ├── services/
│   │   ├── progression_engine.py    # Algoritmo de recomendación de sobrecarga progresiva y filtros 1D-1Y
│   │   ├── card_advisor_engine.py   # Algoritmo de conveniencia de TDC (corte, pago, cashback, utilización)
│   │   ├── statement_pdf_parser.py  # Módulo Fase 2 para lectura de estados de cuenta en PDF con pdfplumber
│   │   └── habit_streak_engine.py   # Cálculo de rachas, adherencia porcentual y progreso de metas anuales
│   ├── components/
│   │   ├── mobile_nav.py            # Cabecera compacta móvil y selector de pilar activo
│   │   ├── credit_card_widget.py    # Renderizador HTML/CSS de tarjetas bancarias modernas tipo Apple Wallet
│   │   ├── chart_builders.py        # Constructores Plotly con fondo transparente y tipografía móvil
│   │   └── kpi_cards.py             # Tarjetas de métricas con delta y barra de progreso
│   └── views/
│       ├── auth_view.py             # Pantalla de Inicio de Sesión y Registro de Cuenta
│       ├── home_hub_view.py         # Resumen diario unificado de los 3 pilares (Command Center)
│       ├── workout_view.py          # Módulo 1: Entrenamiento Físico (Sesión activa, Rutinas, Analítica 1D-1Y)
│       ├── finance_view.py          # Módulo 2: Finanzas (Flujo, Tarjetas, Calendario, Simulador TDC)
│       └── habits_view.py           # Módulo 3: Hábitos Editables, Dashboard Reordenable y Metas/Planes
├── tests/
│   ├── test_progression_engine.py   # Pruebas unitarias de las 4 reglas de sobrecarga progresiva
│   ├── test_card_advisor.py         # Pruebas unitarias de cálculo de días de financiamiento y score TDC
│   └── test_habit_streaks.py        # Pruebas unitarias de rachas y cumplimiento por tipo de métrica
├── .gitignore
├── requirements.txt
└── app.py                           # Punto de entrada principal (Entrypoint para Streamlit Cloud)
```

## 3. La gestión de autenticación y sesión móvil utiliza JWT en Supabase y cookies encriptadas

Para soportar a los ~10 usuarios sin que pierdan su sesión cada vez que abren el navegador en su teléfono o refrescan la pestaña, el módulo `src/auth/session_manager.py` debe implementar el siguiente flujo técnico:

1. **Inicialización del cliente con contexto de usuario:**
   * Se crea una instancia del cliente Supabase usando `SUPABASE_URL` y `SUPABASE_ANON_KEY` almacenados en `st.secrets`.
   * Cuando un usuario inicia sesión con `supabase.auth.sign_in_with_password({"email": email, "password": password})`, Supabase devuelve un `access_token` y un `refresh_token`.
2. **Persistencia en Cookies del Navegador Móvil:**
   * Se almacena el `refresh_token` en una cookie llamada `trifecta_rt` con expiración de 30 días mediante `CookieManager`.
   * Al cargar `app.py`, si `st.session_state.get("authenticated")` no está activo pero existe la cookie `trifecta_rt`, el sistema ejecuta `supabase.auth.refresh_session(refresh_token)` automáticamente, restaura `st.session_state["user"]` y redirige al usuario directo a su dashboard sin pedirle contraseña de nuevo.
3. **Autenticación de Consultas PostgREST (Cumplimiento de RLS):**
   * Antes de cualquier consulta a tablas protegidas, el cliente inyecta el token activo mediante `supabase.postgrest.auth(st.session_state["access_token"])`. Así PostgreSQL evalúa `auth.uid() = user_id` en todas las operaciones `SELECT`, `INSERT`, `UPDATE` y `DELETE`.

## 4. El rendimiento en dispositivos móviles se optimiza con fragmentos parciales y caché con invalidación selectiva

Uno de los problemas comunes de Streamlit en dispositivos móviles es que cada clic recarga toda la página. Para garantizar una respuesta instantánea (<200 ms en interacciones de UI):

| Mecanismo de Streamlit | Aplicación Específica en TRIFECTA LifeOS | Regla de Invalidación |
| :--- | :--- | :--- |
| **`@st.fragment`** | Se aplica al **Registrador de Series en Vivo** (`workout_view.py`), al **Check Rápido de Hábitos** (`habits_view.py`) y al **Simulador de TDC** (`finance_view.py`). Permite marcar una serie o cambiar un filtro temporal (`1D` a `1Y`) recargando únicamente ese bloque visual sin redibujar toda la página. | Se ejecuta localmente dentro del fragmento; solo llama a `st.rerun()` completo si cambia el estado global de navegación. |
| **`@st.dialog`** | Se utiliza para los formularios de creación/edición (Nuevo Gasto/Ingreso, Nueva Tarjeta, Nuevo Hábito, Nueva Meta). Evita saturar la pantalla móvil con formularios largos siempre visibles. | Al pulsar *"Guardar"*, limpia la caché de la tabla afectada y cierra el modal automáticamente. |
| **`@st.cache_data(ttl=300)`** | Se aplica a las funciones de lectura de catálogos, historial de volumen muscular, transacciones del mes y tarjetas, recibiendo siempre `user_id: str` como primer parámetro para aislar el caché entre los 10 usuarios. | Cualquier operación de escritura (`INSERT`, `UPDATE`, `DELETE`) invoca `.clear()` sobre la función cacheada específica antes de refrescar el componente. |

## 5. Especificación algorítmica de los motores de negocio (`services/`)

### 5.1. Algoritmo de los 8 filtros temporales y volumen ponderado (`src/services/progression_engine.py`)

* **Entrada:** `df_sets` (historial de series del usuario unido con `exercises`), `timeframe_code` (`1D`, `1W`, `2W`, `1M`, `2M`, `3M`, `6M`, `1Y`), `metric_mode` (`effective_sets` o `tonnage_kg`).
* **Mapeo exacto de días (`TIMEFRAME_DAYS_MAP`):**
  ```python
  TIMEFRAME_CONFIG = {
      "1D": {"days": 1,   "freq": "H",     "label": "Diario (Hoy)"},
      "1W": {"days": 7,   "freq": "D",     "label": "Semanal (7d)"},
      "2W": {"days": 15,  "freq": "3D",    "label": "Quincenal (15d)"},
      "1M": {"days": 30,  "freq": "W-MON", "label": "Mensual (30d)"},
      "2M": {"days": 60,  "freq": "2W",    "label": "Bimestral (60d)"},
      "3M": {"days": 90,  "freq": "W-MON", "label": "Trimestral (90d)"},
      "6M": {"days": 180, "freq": "MS",    "label": "Semestral (6m)"},
      "1Y": {"days": 365, "freq": "MS",    "label": "Anual (12m)"},
  }
  ```
* **Cálculo de series efectivas y tonelaje por músculo:**
  1. Filtrar `set_type IN ('working', 'dropset', 'failure')` (excluir `'warmup'`).
  2. Para cada fila, generar el aporte al `primary_muscle` con factor `1.0` y desglosar cada elemento del arreglo `secondary_muscles` con factor `0.5`.
  3. Calcular `delta_pct` comparando la ventana `[NOW() - days, NOW()]` contra la ventana previa `[NOW() - 2*days, NOW() - days]`.

### 5.2. Algoritmo recomendador de tarjetas de crédito (`src/services/card_advisor_engine.py`)

* **Cálculo exacto de fechas de corte y pago (`calculate_float_days`):**
  Dado `purchase_date` (fecha de la compra), `cutoff_day` (día de corte, 1–31) y `payment_due_day` (día límite de pago, 1–31):
  1. Si `purchase_date.day <= cutoff_day`, la compra entra en el **corte del mes en curso** (`statement_cutoff_date = date(year, month, cutoff_day)`).
  2. Si `purchase_date.day > cutoff_day`, la compra entra en el **corte del mes siguiente** (`statement_cutoff_date = date(next_month_year, next_month, cutoff_day)`).
  3. La fecha límite de pago (`due_date`) es el próximo `payment_due_day` posterior a `statement_cutoff_date` (típicamente ~20 días después del corte).
  4. `float_days = (due_date - purchase_date).days`.
* **Fórmula del Score de Conveniencia (`0–100`):**
  ```python
  score_float = min(float_days / 50.0, 1.0) * 45.0
  score_cashback = (card.cashback_pct / max_cashback_pct_among_cards) * 25.0 if max_cashback_pct_among_cards > 0 else 12.5
  new_utilization = (card.current_balance + amount) / card.credit_limit
  if new_utilization > 1.0:
      return -1  # Tarjeta descartada por saldo insuficiente
  score_utilization = 20.0 if new_utilization <= 0.30 else max(0.0, 20.0 * (1.0 - (new_utilization - 0.30) / 0.70))
  score_budget = 10.0 if category_remaining_budget >= amount else max(0.0, 10.0 * (category_remaining_budget / amount))
  total_score = round(score_float + score_cashback + score_utilization + score_budget, 1)
  ```

## 6. Archivos de configuración base requeridos para despliegue en GitHub y Streamlit Cloud

### 6.1. Dependencias exactas (`requirements.txt`)

```text
streamlit>=1.38.0
supabase>=2.7.0
extra-streamlit-components>=0.1.71
pandas>=2.2.0
numpy>=1.26.0
plotly>=5.24.0
pydantic>=2.8.0
pdfplumber>=0.11.4
python-dateutil>=2.9.0
```

### 6.2. Configuración de tema oscuro nativo (`.streamlit/config.toml`)

```toml
[theme]
base = "dark"
primaryColor = "#3B82F6"
backgroundColor = "#0A0D14"
secondaryBackgroundColor = "#121722"
textColor = "#F8FAFC"
font = "sans serif"

[server]
headless = true
enableCORS = false
maxUploadSize = 15

[browser]
gatherUsageStats = false
```
