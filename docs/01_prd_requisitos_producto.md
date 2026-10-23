# 01. PRD — Documento de Requisitos del Producto: TRIFECTA LifeOS

## 1. TRIFECTA LifeOS unifica entrenamiento físico, finanzas estratégicas y hábitos personalizables en una aplicación web móvil multiusuario

**TRIFECTA LifeOS** es una aplicación web progresiva construida en Python sobre **Streamlit** y respaldada por **Supabase (PostgreSQL + Auth)**, diseñada específicamente para operar con ergonomía móvil (*Mobile-First*) y estética oscura de alto contraste. Su propósito es centralizar las tres áreas críticas del desarrollo personal —**Entrenamiento Físico**, **Finanzas Personales** y **Hábitos / Metas de Desarrollo**— bajo una arquitectura multiusuario privada para un grupo estimado de **10 usuarios activos** con aislamiento total de datos.

| Atributo del Producto | Especificación Definida |
| :--- | :--- |
| **Nombre Clave del Proyecto** | `trifecta-lifeos` (TRIFECTA LifeOS) |
| **Plataforma de Despliegue** | GitHub Repository + Streamlit Community Cloud |
| **Dispositivo Principal** | Smartphone (iOS Safari / Android Chrome en vista vertical 360px–430px) |
| **Arquitectura de Usuarios** | Multiusuario (~10 cuentas independientes) con Supabase Auth y Row Level Security (RLS) |
| **Pilar 1: Entrenamiento Físico** | Registro de sesiones, motor algorítmico de sobrecarga progresiva, analítica de volumen muscular en 8 horizontes temporales y base para Nutrición |
| **Pilar 2: Finanzas Personales** | Flujo de caja ágil, billetera visual de tarjetas, calendario financiero, simulador de presupuestos y recomendador inteligente de TDC |
| **Pilar 3: Hábitos y Metas** | Motor de registros personalizables (cualquier tipo de métrica), dashboard reordenable, heatmaps y planes de desarrollo vinculados a metas anuales |

## 2. El módulo de entrenamiento físico optimiza la hipertrofia y la fuerza mediante recomendaciones algorítmicas y ocho horizontes temporales

Inspirado en **Symmetry**, **Hevy** y **Strong**, este pilar se separa de los hábitos cotidianos porque requiere un modelado fisiológico propio basado en tonelaje, esfuerzo percibido (RPE), repeticiones en reserva (RIR) y distribución de volumen por grupo muscular.

### 2.1. El catálogo de ejercicios pondera músculos primarios y secundarios para evitar sesgos de volumen

Cada ejercicio del catálogo (global o creado por el usuario) asigna un impacto biomecánico diferenciado para calcular las series efectivas semanales de forma realista:

| Tipo de Implicación Muscular | Factor de Ponderación de Series | Ejemplo Práctico (Press de Banca con Barra - 4 series efectivas) |
| :--- | :--- | :--- |
| **Músculo Primario (`primary_muscle`)** | `1.0` serie por cada serie efectiva (`working` o `failure`) | Pecho (`chest`): suma **4.0 series efectivas** y el 100% del tonelaje (`peso × reps`) |
| **Músculos Secundarios (`secondary_muscles`)** | `0.5` series por cada serie efectiva | Tríceps (`triceps`) y Deltoides Anterior (`front_delts`): suman **2.0 series efectivas** cada uno |
| **Series de Calentamiento (`warmup`)** | `0.0` series efectivas | Se registran en el historial de la sesión pero se excluyen de las gráficas de hipertrofia y récords |

### 2.2. Las gráficas de volumen muscular operan sobre ocho filtros temporales exactos

El usuario puede auditar su volumen de entrenamiento (medido tanto en **Series Efectivas** como en **Tonelaje Total en kg**) filtrando por grupo muscular y alternando entre **8 ventanas de tiempo preconfiguradas**:

| Código del Filtro | Etiqueta en Interfaz | Ventana de Cálculo (`NOW() - Intervalo`) | Agrupación en Eje X de la Gráfica | Comparativa Automática (Delta `%`) |
| :--- | :--- | :--- | :--- | :--- |
| `1D` | **Diario** | Últimas 24 horas (día actual) | Por ejercicio y grupo muscular de la sesión | Vs. sesión homóloga anterior |
| `1W` | **Semanal** | Últimos 7 días naturales | Día por día (`Lun` a `Dom`) | Vs. los 7 días previos |
| `2W` | **Quincenal** | Últimos 15 días naturales | Bloques de 3 días | Vs. los 15 días previos |
| `1M` | **Mensual** | Últimos 30 días naturales | Semana por semana (4 barras/puntos) | Vs. los 30 días previos |
| `2M` | **Bimestral** | Últimos 60 días naturales | Quincena por quincena (4 bloques) | Vs. los 60 días previos |
| `3M` | **Trimestral** | Últimos 90 días naturales | Semana por semana (12 puntos) | Vs. los 90 días previos |
| `6M` | **Semestral** | Últimos 180 días naturales | Mes por mes (6 barras/puntos) | Vs. los 180 días previos |
| `1Y` | **Anual** | Últimos 365 días naturales | Mes por mes (12 barras/puntos) | Vs. el año previo |

### 2.3. El motor de recomendación de sobrecarga progresiva prescribe ajustes de peso y repeticiones antes de cada serie

Cada ejercicio dentro de una rutina tiene un rango objetivo de repeticiones (`target_rep_min` a `target_rep_max`, por ejemplo `8–12`) y un RPE objetivo (`target_rpe`, por ejemplo `8.0`). Al abrir un ejercicio, el sistema analiza las últimas 2 sesiones del usuario y emite una de las **4 prescripciones algorítmicas**:

| Estado Detectado en Sesiones Previas | Regla de Decisión Algorítmica | Recomendación Mostrada al Usuario | Acción Sugerida (1 Toque) |
| :--- | :--- | :--- | :--- |
| **1. Dominio del Rango (`UP_WEIGHT_DOWN_REPS`)** | El usuario completó `>= target_rep_max` en todas las series de trabajo con `RPE <= 8.5` | **Subir peso y bajar repeticiones al piso del rango:** Has dominado el tope del rango con margen de esfuerzo. | Incrementar peso `+2.5 kg` (o `+5%`) y apuntar a `target_rep_min` reps |
| **2. Progreso en Rango (`KEEP_WEIGHT_UP_REPS`)** | El usuario logró entre `target_rep_min` y `target_rep_max - 1` reps con `RPE <= 9.0` | **Mantener peso y subir repeticiones:** Conserva la carga actual y busca ganar 1–2 repeticiones por serie. | Mantener `peso anterior` y apuntar a `reps_previas + 1` |
| **3. Fatiga o Caída de Rendimiento (`DOWN_WEIGHT_UP_REPS`)** | El usuario quedó por debajo de `target_rep_min` o registró `RPE >= 9.5` con caída `> 20%` de reps entre la 1ª y última serie | **Bajar peso y subir repeticiones (Descarga de Hipertrofia):** Fatiga neural detectada; prioriza volumen limpio y control técnico. | Reducir peso `-7.5%` a `-10%` y subir objetivo a `target_rep_max + 2` reps |
| **4. Estancamiento en Meseta (`UP_WEIGHT_STRENGTH_SHIFT`)** | El usuario repitió exactamente el mismo peso y repeticiones durante `3 sesiones consecutivas` sin lograr avanzar | **Subir peso y bajar repeticiones (Ruptura de Meseta):** Rompe la adaptación con un estímulo de fuerza submáxima. | Incrementar peso `+5%` a `+7.5%` y reducir objetivo a `target_rep_min - 2` reps |

### 2.4. La arquitectura reserva conectores nativos para el futuro módulo de Nutrición

Sin recargar la primera versión (MVP), la base de datos y la capa de servicios incluyen desde el inicio las entidades de **Metas Nutricionales (`nutrition_targets`)** y **Registro Diario de Nutrición (`nutrition_daily_logs`)**. Esto permitirá que en una fase posterior el usuario conecte su ingesta calórica (`kcal`), macronutrientes (`proteína`, `carbohidratos`, `grasas`) y peso corporal directamente con las gráficas de volumen muscular para evaluar fases de volumen (*bulking*) o definición (*cutting*).

## 3. El módulo de finanzas personales combina control de flujo de caja, billetera moderna, calendario y simulador de tarjetas de crédito

Inspirado en **Wallet by BudgetBakers**, **YNAB** y **Apple Wallet**, este pilar va más allá de anotar gastos: actúa como un asesor financiero diario que optimiza la liquidez, el uso del crédito y las recompensas bancarias.

### 3.1. La billetera digital presenta las tarjetas con estética moderna y métricas de corte y pago en tiempo real

Cada cuenta o tarjeta registrada (`débito`, `efectivo`, `ahorro/inversión`, `tarjeta de crédito`) se visualiza como una tarjeta interactiva de diseño moderno (*glassmorphism*, degradado personalizable, red `Visa/Mastercard/Amex` y últimos 4 dígitos). Para las **Tarjetas de Crédito (TDC)**, el sistema almacena y calcula automáticamente:

* **Límite de crédito, saldo actual utilizado y crédito disponible:** Muestra una barra visual de utilización crediticia con alertas preventivas al superar el `30%` (óptimo de buró) y el `70%` (riesgo de sobreendeudamiento).
* **Día de corte (`cutoff_day`, 1–31) y día límite de pago (`payment_due_day`, 1–31) o días de gracia (`grace_days`):** Calcula dinámicamente la próxima fecha de corte exacta y la fecha límite para pagar sin intereses.
* **Porcentaje de Cashback (`cashback_pct`) y anualidad/beneficios:** Permite comparar el retorno financiero real de cada plástico.

### 3.2. El recomendador inteligente de TDC determina qué tarjeta conviene usar hoy antes de pagar

Cuando el usuario va a realizar una compra, ingresa el **Monto ($)**, la **Categoría** y la **Fecha (por defecto hoy)** en el *Simulador de Pago y Presupuesto*. El algoritmo evalúa todas sus tarjetas de crédito activas y las ordena mediante un **Score de Conveniencia (0 a 100 puntos)** basado en cuatro variables:

| Variable del Algoritmo | Peso en el Score | Lógica de Cálculo Financiero |
| :--- | :--- | :--- |
| **1. Días de Financiamiento Gratuito (`float_days`)** | `45%` | Calcula los días naturales entre la fecha de compra y la fecha límite de pago correspondiente. Comprar el día posterior al corte otorga el máximo puntaje (~45–50 días para pagar); comprar 1–2 días antes del corte otorga el puntaje mínimo (~15–20 días). |
| **2. Retorno por Cashback (`cashback_reward`)** | `25%` | Calcula `monto_compra × (cashback_pct / 100)` y normaliza frente a la tarjeta con mayor tasa de reembolso del usuario. |
| **3. Salud de Utilización de Línea (`utilization_health`)** | `20%` | Evalúa `(saldo_actual + monto_compra) / limite_credito`. Otorga el máximo puntaje si la utilización resultante es `<= 30%`, penaliza gradualmente entre `31%–70%` y descarta la tarjeta si supera el `90%` o excede el disponible. |
| **4. Impacto en Presupuesto de Categoría (`budget_fit`)** | `10%` | Verifica el saldo disponible en el presupuesto mensual asignado a esa categoría (`presupuesto_mensual - gasto_acumulado_mes - monto_compra`) y alerta si la compra provocará un sobregiro presupuestal. |

### 3.3. El calendario financiero y el gestor de suscripciones previenen cargos sorpresa e intereses moratorios

* **Vista de Calendario Mensual Interactivo:** Muestra en una cuadrícula mensual todos los eventos financieros críticos con códigos de color:
  * **Fechas de corte de TDC** (indicando qué tarjetas inician nuevo periodo al día siguiente).
  * **Fechas límite de pago de TDC** (con el monto acumulado a pagar para no generar intereses).
  * **Cobros de suscripciones y pagos fijos recurrentes** (streaming, gimnasio, servicios, renta).
  * **Fechas programadas de ingresos** (quincenas, honorarios, dividendos).
* **Dashboard de Flujo de Caja:** Presenta ingresos vs. gastos del periodo, tasa de ahorro (`%`), distribución por categoría y gráfica de evolución del patrimonio neto.

### 3.4. La importación de estados de cuenta bancarios en PDF se estructura como módulo asistido de Fase 2

Dado que cada institución bancaria (BBVA, Banorte, Santander, Citibanamex, Nu, Amex) utiliza plantillas PDF distintas y sujetas a cambios frecuentes, **no se bloquea la primera versión (MVP Fase 1)** con un parser automático rígido. En su lugar, se establece una estrategia en dos etapas:

* **Fase 1 (MVP):** Registro manual ultrarrápido en 3 toques + generación automática de cargos por suscripciones recurrentes + **estructura de base de datos lista (`statement_imports`)**.
* **Fase 2 (Módulo Asistido de PDF):** Carga de archivo PDF mediante `pdfplumber` que extrae las líneas con fecha y monto hacia una **tabla de previsualización editable (`st.data_editor`)** en pantalla. El usuario revisa, ajusta cualquier categoría en segundos y pulsa *"Confirmar e Importar Movimientos"*, evitando que errores de lectura del PDF contaminen la contabilidad.

## 4. El módulo de hábitos generales y desarrollo personal ofrece una base 100% editable vinculada a metas de largo plazo

Inspirado en **HabitKit**, **Streaks** y los sistemas de **OKRs de Notion**, este pilar evita encasillar al usuario en plantillas fijas y le permite construir su propio sistema de seguimiento y desarrollo personal.

### 4.1. El motor de registros soporta cuatro tipos de métricas definidas por el usuario

El usuario puede crear, editar o archivar cualquier hábito o registro personalizado eligiendo su nombre, icono, color, frecuencia y **tipo de captura**:

| Tipo de Registro (`metric_type`) | Control en Interfaz Móvil | Ejemplo de Uso Personalizado | Regla de Cumplimiento Diario |
| :--- | :--- | :--- | :--- |
| **Booleano (`BOOLEAN`)** | Botón de 1 toque (*Check / Uncheck*) | "Leer antes de dormir", "Tomar creatina", "Cero azúcar" | Se marca como completado (`100%`) al activarse |
| **Numérico (`NUMERIC`)** | Botones rápidos `+` / `-` o campo numérico con unidad libre | "Agua (`3.0 Litros`)", "Páginas leídas (`20 págs`)", "Pasos (`10,000`)" | Se cumple cuando `valor_registrado >= meta_diaria` |
| **Duración (`DURATION`)** | Selector de minutos/horas | "Estudio de inglés (`45 min`)", "Meditación (`15 min`)", "Sueño (`7.5 hrs`)" | Se cumple cuando `minutos_registrados >= meta_minutos` |
| **Escala / Valoración (`RATING`)** | Control deslizante (*slider* `1 a 5` o `1 a 10`) | "Nivel de energía diaria (`1–10`)", "Enfoque mental (`1–5`)" | Se registra como completado al capturar la valoración del día |

### 4.2. El dashboard interactivo permite reordenar widgets y visualizar mapas de calor por hábito

* **Orden Editable por el Usuario (`display_order`):** Cada tarjeta de hábito y meta posee un índice de prioridad editable desde la interfaz (subir/bajar posición o fijar en la parte superior con `is_pinned`), garantizando que la pantalla se adapte a las prioridades cambiantes del usuario.
* **Heatmaps y Rachas (`Streaks`):** Cada hábito muestra su racha actual (`current_streak`), mejor racha histórica (`best_streak`), porcentaje de adherencia de los últimos 30 días y una cuadrícula visual de consistencia estilo GitHub/HabitKit.

### 4.3. Las metas personales y planes de desarrollo conectan los propósitos anuales con la acción diaria

Para que los propósitos (como metas de Año Nuevo, desarrollo profesional o proyectos personales) no queden en intenciones aisladas, el módulo implementa una jerarquía de tres niveles:

1. **Meta Personal / Propósito (`personal_goals`):** Define el objetivo macro (ej. *"Dominar Inglés Conversacional B2 en 2026"* o *"Crear Fondo de Emergencia de $60,000"*), con fecha límite, categoría de vida y barra de progreso global (`0%–100%`).
2. **Plan de Desarrollo / Hitos (`goal_milestones`):** Divide la meta en pasos concretos y verificables con fechas objetivo (ej. *"Terminar curso nivel intermedio"*, *"Aprobar simulacro de examen"*).
3. **Hábitos Vinculados (`linked_goal_id`):** Permite enlazar uno o más hábitos diarios a una meta personal (ej. vincular el hábito *"Estudiar inglés 30 min"* a la meta *"Dominar Inglés B2"*), mostrando en el plan de desarrollo la tasa de consistencia real que respalda esa meta.

## 5. Criterios de aceptación del MVP para pasar a la primera prueba de código

Para considerar exitosa la primera versión funcional desplegada en GitHub y Streamlit, el sistema deberá cumplir los siguientes criterios verificables:

* **Aislamiento Multiusuario:** Dos usuarios distintos pueden registrarse, iniciar sesión desde su móvil y operar los tres módulos viendo únicamente sus propios registros gracias a Supabase RLS.
* **Operación Móvil Fluida:** Cero tablas cortadas horizontalmente en pantallas de `390px` de ancho; captura de una serie de gimnasio o un gasto financiero en menos de 10 segundos.
* **Exactitud Algorítmica:** El motor de sobrecarga progresiva muestra la recomendación correcta según el historial del ejercicio, los 8 filtros temporales recalculan el volumen muscular al instante y el simulador de TDC ordena correctamente las tarjetas según fecha de corte, pago, cashback y presupuesto.
