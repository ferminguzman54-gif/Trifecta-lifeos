# 06. Plan de Implementación — Secuencia de Construcción para Antigravity: TRIFECTA LifeOS

## 1. El desarrollo se estructura en seis sprints secuenciales para evitar dependencias rotas y validar cada módulo antes de avanzar

Este documento sirve como hoja de ruta ejecutable para **Antigravity**. Cada fase tiene entradas claras, archivos exactos a crear y pruebas de verificación que deben superarse antes de pasar a la siguiente etapa.

| Fase / Sprint | Nombre del Entregable | Archivos Principales Involucrados | Dependencia Previa | Estado Inicial |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | Infraestructura, Base de Datos Supabase y Autenticación Multiusuario | `sql/01_schema_ddl.sql`, `sql/02_seed_catalog.sql`, `src/auth/*`, `src/config/*`, `app.py` | Ninguna (Arranque) | Pendiente de autorización |
| **Sprint 2** | Pilar 3: Motor de Hábitos Editables, Dashboard Reordenable y Metas/Planes | `src/models/habit_models.py`, `src/services/habit_streak_engine.py`, `src/views/habits_view.py` | Sprint 1 completado | Pendiente |
| **Sprint 3** | Pilar 1: Entrenamiento Físico, Motor de Sobrecarga y Analítica `1D`–`1Y` | `src/models/workout_models.py`, `src/services/progression_engine.py`, `src/views/workout_view.py` | Sprint 1 completado | Pendiente |
| **Sprint 4** | Pilar 2: Finanzas, Tarjetas Modernas, Calendario y Simulador de TDC | `src/models/finance_models.py`, `src/services/card_advisor_engine.py`, `src/components/credit_card_widget.py`, `src/views/finance_view.py` | Sprint 1 completado | Pendiente |
| **Sprint 5** | Command Center Unificado, Pulido Móvil y Despliegue en GitHub + Streamlit | `src/views/home_hub_view.py`, `tests/*`, `requirements.txt` | Sprints 2, 3 y 4 | Pendiente |
| **Sprint 6 (Post-MVP)** | Módulo Asistido de Estados de Cuenta en PDF y Activación de Nutrición | `src/services/statement_pdf_parser.py` | Sprint 5 en producción | Opcional Fase 2 |

## 2. Secuencia detallada paso a paso para el agente constructor (Antigravity)

### Sprint 1: Cimientos del Proyecto, Tema Oscuro y Autenticación Persistente en Móvil

1. **Inicialización del repositorio y entorno:**
   * Crear la estructura de carpetas definida en `02_TRD_Requisitos_Tecnicos.md`, `.gitignore` (excluyendo `.venv/`, `__pycache__/`, `.streamlit/secrets.toml`), `requirements.txt` y `.streamlit/config.toml`.
2. **Despliegue del esquema en Supabase:**
   * Ejecutar `sql/01_schema_ddl.sql` (contenido en `05_Backend_Schema_Supabase.md`) en el SQL Editor del proyecto Supabase y cargar `sql/02_seed_catalog.sql` con los 40 ejercicios base ponderados por músculo primario/secundario.
3. **Implementación de `src/auth/supabase_client.py` y `src/auth/session_manager.py`:**
   * Configurar el cliente de Supabase, el formulario de Login/Registro en `src/views/auth_view.py` y la persistencia de sesión mediante `CookieManager` (`extra-streamlit-components`) para que el usuario no tenga que volver a escribir su contraseña al recargar en el celular.
4. **Inyección del sistema de diseño (`src/config/theme.py`):**
   * Cargar el CSS global de alto contraste definido en `04_UI_UX_Design_Brief.md` y construir la barra de navegación superior móvil en `src/components/mobile_nav.py`.
5. **Criterio de validación del Sprint 1:** Registrar 2 cuentas de prueba, iniciar sesión, recargar la página móvil (`F5`) verificando que la sesión se mantiene abierta y comprobar que el cambio entre pestañas principales funciona sin errores.

### Sprint 2: Construcción del Pilar 3 — Hábitos Editables, Heatmaps y Planes de Desarrollo

1. **Modelos y Servicio de Rachas (`src/services/habit_streak_engine.py`):**
   * Programar las funciones CRUD para `habits`, `habit_logs`, `personal_goals` y `goal_milestones`.
   * Implementar el cálculo de `current_streak`, `best_streak`, `% de cumplimiento en 30 días` y la matriz de 90 días para el Heatmap estilo GitHub/HabitKit.
2. **Interfaz Móvil de Hábitos (`src/views/habits_view.py`):**
   * Construir el modal `@st.dialog` para crear registros de cualquier tipo (`BOOLEAN`, `NUMERIC`, `DURATION`, `RATING`) con unidad personalizada.
   * Implementar el fragmento `@st.fragment` de captura rápida diaria y el **Modo Reordenar Dashboard** (`⬆ Subir`, `⬇ Bajar`, `📌 Fijar arriba`) actualizando `display_order`.
   * Construir la pestaña de **Metas Personales y Planes de Desarrollo**, permitiendo crear metas anuales, desglosarlas en hitos (`goal_milestones`) y vincular hábitos diarios (`linked_goal_id`).
3. **Criterio de validación del Sprint 2:** Crear 1 hábito booleano, 1 numérico (ej. litros de agua) y 1 meta anual con 3 hitos; cambiar el orden de aparición en el dashboard y verificar que el orden persiste en Supabase.

### Sprint 3: Construcción del Pilar 1 — Entrenamiento Físico, Sobrecarga Progresiva y Filtros `1D`–`1Y`

1. **Motor de Sobrecarga Progresiva y Analítica (`src/services/progression_engine.py`):**
   * Implementar la función `get_exercise_recommendation(user_id, exercise_id, target_rep_min, target_rep_max, target_rpe)` con los 4 estados de recomendación (`UP_WEIGHT_DOWN_REPS`, `KEEP_WEIGHT_UP_REPS`, `DOWN_WEIGHT_UP_REPS`, `UP_WEIGHT_STRENGTH_SHIFT`).
   * Implementar el agregador de volumen muscular ponderado (`1.0` músculo primario, `0.5` músculos secundarios) con soporte exacto para los **8 filtros temporales** (`1D`, `1W`, `2W`, `1M`, `2M`, `3M`, `6M`, `1Y`) y cálculo de delta porcentual contra el periodo previo.
2. **Interfaz Móvil de Entrenamiento (`src/views/workout_view.py`):**
   * **Tab 1 (Sesión en Vivo):** Selector de rutina, banner visual de recomendación algorítmica con botón `Aplicar sugerencia`, captura reactiva de series con `@st.fragment` y detector de récords (`is_pr`).
   * **Tab 2 (Analítica de Volumen):** Selector segmentado de los 8 filtros temporales (`1D` a `1Y`), conmutador `Series Efectivas / Tonelaje (kg)` y gráficas Plotly horizontales y de evolución temporal.
   * **Tab 3 (Rutinas y Catálogo):** Gestor para crear/editar rutinas y añadir ejercicios personalizados.
3. **Criterio de validación del Sprint 3:** Ejecutar 2 sesiones de prueba, comprobar que en la 3ª sesión aparece la recomendación de subida de peso o repeticiones, y alternar entre los 8 botones (`1D` a `1Y`) verificando las gráficas.

### Sprint 4: Construcción del Pilar 2 — Finanzas, Billetera Moderna, Calendario y Simulador de TDC

1. **Componente de Tarjeta Moderna y Motor Recomendador (`src/services/card_advisor_engine.py`):**
   * Crear `src/components/credit_card_widget.py` para renderizar las tarjetas bancarias con gradientes CSS, barra de utilización de crédito, día de corte, día de pago y porcentaje de Cashback.
   * Programar `evaluate_best_payment_card(user_id, amount, category_id, purchase_date)` que calcula los **días exactos de financiamiento sin intereses (`float_days`)** según la fecha de corte (`cutoff_day`) y fecha límite de pago (`payment_due_day`), el retorno en Cashback, el impacto en la utilización de línea y el ajuste al presupuesto mensual.
2. **Interfaz Móvil de Finanzas (`src/views/finance_view.py`):**
   * **Tab 1 (Flujo de Caja y Dashboard):** Modal rápido de 3 toques para registrar gastos/ingresos/transferencias, KPIs de liquidez y gráficas de distribución por categoría vs. presupuesto.
   * **Tab 2 (Mis Tarjetas y Simulador de Decisión):** Vista de tarjetas modernas y panel interactivo *"¿Con qué tarjeta pago hoy?"* con ranking explicativo de conveniencia.
   * **Tab 3 (Calendario y Suscripciones):** Cuadrícula mensual con fechas de corte, fechas límite de pago y cobros de suscripciones recurrentes.
3. **Criterio de validación del Sprint 4:** Registrar 2 tarjetas de crédito con distintas fechas de corte (ej. día 5 y día 20) y comprobar que el simulador recomienda la tarjeta recién cortada explicando los ~45 días de financiamiento y el Cashback ganado.

### Sprint 5: Command Center, Pruebas Automatizadas y Despliegue en Streamlit Cloud

1. **Construcción de `src/views/home_hub_view.py`:**
   * Integrar en la pantalla de inicio el resumen del entrenamiento del día, la alerta financiera más próxima (corte/pago/presupuesto) y los hábitos pendientes de hoy.
2. **Ejecución de suite de pruebas (`pytest`):**
   * Ejecutar `tests/test_progression_engine.py`, `tests/test_card_advisor.py` y `tests/test_habit_streaks.py`.
3. **Despliegue en GitHub y Streamlit Community Cloud:**
   * Subir el repositorio a GitHub, conectar la rama `main` con `app.py` en Streamlit Cloud y pegar `SUPABASE_URL` y `SUPABASE_ANON_KEY` en el panel **Settings -> Secrets** de Streamlit Cloud.

### Sprint 6 (Opcional Fase 2): Importador Asistido de Estados de Cuenta en PDF

1. **Construcción de `src/services/statement_pdf_parser.py`:**
   * Utilizar `pdfplumber` para detectar líneas con fecha, concepto y cargo/abono en estados de cuenta PDF y presentarlas en un `st.data_editor` dentro de la pestaña de Finanzas antes de insertarlas en `finance_transactions`.

## 3. Instrucción maestra de arranque para pegar en Antigravity

Cuando autorices estos 6 documentos y abras tu proyecto en **Antigravity**, pega el siguiente bloque para iniciar la construcción de la primera prueba sin ambigüedades:

```text
Lee los 6 documentos de especificación ubicados en la carpeta /docs:
1. 01_PRD_Requisitos_Producto.md
2. 02_TRD_Requisitos_Tecnicos.md
3. 03_Appflow_Flujo_Usuario.md
4. 04_UI_UX_Design_Brief.md
5. 05_Backend_Schema_Supabase.md
6. 06_Plan_Implementacion_Antigravity.md

Sigue estrictamente las decisiones técnicas del TRD, el esquema SQL del Backend Schema y la estética oscura de alto contraste del UI/UX Design Brief. Vamos a comenzar ejecutando el SPRINT 1 del Plan de Implementación: genera la estructura completa de carpetas, los scripts SQL en /sql, la configuración de tema oscuro, la autenticación multiusuario con Supabase + cookies y el esqueleto navegable móvil en app.py.
```
