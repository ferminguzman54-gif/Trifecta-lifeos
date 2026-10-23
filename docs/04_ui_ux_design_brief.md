# 04. UI/UX Design Brief — Sistema de Diseño Móvil de Alto Contraste: TRIFECTA LifeOS

## 1. La identidad visual combina un lienzo oscuro profundo con acentos cromáticos semánticos por cada rama de vida

Inspirado en las interfaces móviles de **Apple Fitness+**, **Whoop**, **Symmetry** y **Google Material You (Dark)**, el diseño elimina los bordes genéricos de Streamlit y aplica superficies oscuras estratificadas con alto contraste (`WCAG AAA > 7:1`), bordes suavizados (`16px–20px`) y efectos de cristal translúcido (*glassmorphism*). Cada rama de vida tiene su propio color de acento para que el usuario identifique al instante en qué módulo se encuentra:

| Token de Color / Superficie | Código Hexadecimal | Uso Específico en la Interfaz |
| :--- | :--- | :--- |
| **Fondo Base (`bg-canvas`)** | `#0A0D14` | Fondo general de la aplicación en móvil (evita el negro puro `#000000` para reducir fatiga visual OLED) |
| **Superficie de Tarjeta (`bg-surface-1`)** | `#121722` | Contenedores de ejercicios, transacciones, hábitos y KPIs |
| **Superficie Elevada (`bg-surface-2`)** | `#1A2232` | Modales, selectores activos, cabeceras de tablas y tarjetas destacadas |
| **Borde Sutil (`border-subtle`)** | `#263044` | Línea divisoria de `1px solid` en tarjetas y contenedores |
| **Texto Primario (`text-primary`)** | `#F8FAFC` | Títulos, montos financieros, pesos de gimnasio y nombres de hábitos |
| **Texto Secundario (`text-muted`)** | `#94A3B8` | Etiquetas de apoyo, fechas de corte, subtítulos y unidades |
| **Acento Pilar 1: Entrenamiento (`accent-workout`)** | `#FF5500` a `#FF2E54` | Naranja/Coral energético (inspirado en *Symmetry* y *Strava*) para series, récords y volumen muscular |
| **Acento Pilar 2: Finanzas (`accent-finance`)** | `#10B981` a `#059669` | Esmeralda financiero para liquidez, ingresos, ahorro y tarjetas óptimas |
| **Acento Pilar 3: Hábitos y Metas (`accent-habits`)** | `#8B5CF6` a `#6366F1` | Violeta/Índigo eléctrico para rachas, heatmaps y planes de desarrollo |
| **Acento Futuro: Nutrición (`accent-nutrition`)** | `#06B6D4` | Cian/Turquesa reservado para el conector futuro de calorías y macronutrientes |
| **Estados Semánticos (`status`)** | `#22C55E` / `#F59E0B` / `#EF4444` | Éxito (Meta cumplida / PR) / Advertencia (Presupuesto >80% o Descarga) / Peligro (Sobregiro o Fecha límite hoy) |

## 2. La jerarquía tipográfica y las zonas táctiles cumplen con los estándares de ergonomía móvil de iOS y Android

Para que la aplicación se sienta como una app nativa al abrirse desde Safari o Chrome en el teléfono, todos los textos y botones siguen estas reglas de escala y tamaño táctil:

| Elemento Tipográfico / Interactivo | Fuente y Peso | Tamaño en Móvil | Regla de Ergonomía Móvil |
| :--- | :--- | :--- | :--- |
| **Título de Módulo / Pantalla (`H1`)** | `Inter` o `SF Pro Display`, Bold (`700`) | `1.50rem` (`24px`) | Una sola línea sin saltos; margen inferior compacto de `8px` |
| **Valor de KPI Principal (`Metric Value`)** | `JetBrains Mono` o `Inter`, ExtraBold (`800`) | `1.75rem` (`28px`) | Números tabulares (`font-variant-numeric: tabular-nums`) para alinear cifras de dinero y kg |
| **Título de Tarjeta / Ejercicio (`H3`)** | `Inter`, SemiBold (`600`) | `1.05rem` (`16.8px`) | Contraste `#F8FAFC` sobre fondo `#121722` |
| **Cuerpo y Etiquetas (`Body`)** | `Inter`, Regular (`400`) | `0.90rem` (`14.4px`) | Altura de línea `1.45` para lectura cómoda |
| **Inputs y Botones Táctiles (`Touch Target`)** | `Inter`, Medium (`600`) | `>= 16px` en inputs | **Altura mínima de `46px`** para evitar zoom automático en iOS Safari y facilitar el toque con una mano |

## 3. Diseño de componentes visuales clave por módulo

### 3.1. Tarjeta Bancaria Moderna tipo Apple Wallet / Revolut (`src/components/credit_card_widget.py`)

Cuando el usuario registra una tarjeta de crédito o débito, el sistema no la muestra como una fila de texto plano, sino como una tarjeta gráfica con proporción bancaria (`aspect-ratio: 1.586 / 1` o versión compacta móvil) con las siguientes capas visuales:

* **Fondo con Degradado Dinámico según Banco o Elección del Usuario:**
  * *Azul Profundo (BBVA / Citibanamex):* `linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%)`
  * *Violeta Neón (Nu / Fintech):* `linear-gradient(135deg, #4A00E0 0%, #8E2DE2 100%)`
  * *Rojo Intenso (Santander / HSBC):* `linear-gradient(135deg, #870000 0%, #190A05 100%)`
  * *Metalizado / Oro / Platino (Amex / Invex):* `linear-gradient(135deg, #232526 0%, #414345 100%)` con borde `#D4AF37`
* **Elementos en la Cara de la Tarjeta:**
  * Esquina superior izquierda: Nombre del banco + Alias de la tarjeta + Chip metálico minimalista.
  * Esquina superior derecha: Insignia con `% Cashback` (ej. `2.0% Cashback`) y red (`VISA` / `MASTERCARD` / `AMEX`).
  * Centro: Máscara de seguridad `•••• •••• •••• 4829` + Monto utilizado actual (`$12,450.00`) sobre límite total (`$50,000.00`).
  * Barra de progreso integrada: Verde si la utilización es `<= 30%`, Ámbar entre `31%–70%`, Roja si es `> 70%`.
  * Pie de tarjeta en dos columnas: `Corte: Día 14 (Faltan 8 días)` | `Pago: Día 04 (48 días de financiamiento hoy)`.

```html
<!-- Plantilla HTML/CSS de referencia que Antigravity implementará en src/components/credit_card_widget.py -->
<div class="trifecta-cc-card" style="background: linear-gradient(135deg, #1E1B4B 0%, #4338CA 100%);">
  <div class="cc-header">
    <div>
      <span class="cc-bank">NU MÉXICO</span>
      <h4 class="cc-alias">TDC Principal</h4>
    </div>
    <span class="cc-badge">1.5% Cashback</span>
  </div>
  <div class="cc-balance-block">
    <span class="cc-label">Saldo Utilizado / Límite</span>
    <div class="cc-amount">$8,400.00 <small>/ $40,000.00</small></div>
    <div class="cc-progress-bg">
      <div class="cc-progress-fill" style="width: 21%; background: #10B981;"></div>
    </div>
  </div>
  <div class="cc-footer">
    <span>•••• 9042</span>
    <span>Corte: <b>Día 15</b></span>
    <span>Pago: <b>Día 05</b></span>
  </div>
</div>
```

### 3.2. Banner de Recomendación de Sobrecarga Progresiva (Módulo Entrenamiento)

Dentro de cada ejercicio de la sesión activa, el diseño muestra una tarjeta compacta con borde izquierdo de `4px solid` que traduce el algoritmo en una instrucción visual inmediata:

* **Subir Peso (`#10B981` Esmeralda):** Fondo `rgba(16, 185, 129, 0.12)`, icono `⚡`, título **"Sugerencia de Progreso: Subir Carga (+2.5 kg)"** y subtítulo con comparativa directa (`Sesión anterior: 80 kg × 10, 10, 10 @ RPE 8.0 → Objetivo hoy: 82.5 kg × 8 reps`).
* **Mantener Peso y Subir Reps (`#3B82F6` Azul):** Fondo `rgba(59, 130, 246, 0.12)`, icono `📈`, título **"Sugerencia de Progreso: +1 Repetición por Serie"**.
* **Bajar Peso y Subir Reps (`#F59E0B` Ámbar):** Fondo `rgba(245, 158, 11, 0.12)`, icono `🛡️`, título **"Ajuste Inteligente: Bajar 7.5% peso y subir a 12–15 reps"**.

### 3.3. Selector de 8 Horizontes Temporales y Gráficas Plotly Móviles

* El selector de tiempo (`1D`, `1W`, `2W`, `1M`, `2M`, `3M`, `6M`, `1Y`) se renderiza mediante `st.segmented_control` (o píldoras horizontales táctiles) ocupando el `100%` del ancho móvil.
* Todas las gráficas Plotly se configuran obligatoriamente con:
  * `paper_bgcolor="rgba(0,0,0,0)"` y `plot_bgcolor="rgba(0,0,0,0)"`.
  * `margin=dict(l=8, r=8, t=28, b=8)` para aprovechar cada píxel de la pantalla del teléfono.
  * Leyenda horizontal en la parte superior (`orientation="h"`, `y=1.12`) y `config={"displayModeBar": False}` para ocultar la barra de herramientas de escritorio que estorba en pantallas táctiles.

## 4. Hoja de estilos CSS global para inyectar en Streamlit (`src/config/theme.py`)

Antigravity debe inyectar este bloque CSS al inicio de `app.py` para transformar la apariencia estándar de Streamlit en una interfaz móvil de alto nivel:

```css
/* Reducción de márgenes muertos en pantallas móviles */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 4.5rem !important;
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
    max-width: 720px !important;
}

/* Ocultar decoración superior y pie de página por defecto de Streamlit */
header[data-testid="stHeader"] {
    background: rgba(10, 13, 20, 0.85) !important;
    backdrop-filter: blur(12px);
}
footer {visibility: hidden;}

/* Tarjetas modernas con efecto Glassmorphism oscuro */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(180deg, rgba(18, 23, 34, 0.95) 0%, rgba(14, 18, 28, 0.98) 100%) !important;
    border: 1px solid #263044 !important;
    border-radius: 16px !important;
    padding: 14px !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35) !important;
}

/* Botones táctiles con altura mínima de 46px y bordes suaves */
.stButton > button {
    min-height: 46px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    transition: all 0.18s ease-in-out !important;
}
.stButton > button:active {
    transform: scale(0.98) !important;
}

/* Estilo de la tarjeta bancaria moderna */
.trifecta-cc-card {
    border-radius: 18px;
    padding: 18px;
    color: #F8FAFC;
    border: 1px solid rgba(255, 255, 255, 0.16);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
    margin-bottom: 12px;
}
.cc-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 14px;
}
.cc-bank {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.8;
}
.cc-alias {
    margin: 2px 0 0 0;
    font-size: 1.05rem;
    font-weight: 700;
}
.cc-badge {
    background: rgba(255, 255, 255, 0.18);
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}
.cc-amount {
    font-size: 1.35rem;
    font-weight: 800;
    margin: 4px 0 8px 0;
}
.cc-progress-bg {
    width: 100%;
    height: 7px;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 12px;
}
.cc-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    opacity: 0.9;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    padding-top: 10px;
}
```
