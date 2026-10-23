"""
Temporizador de Descanso Inter-Serie (Client-Side HTML5 / JavaScript + Web Audio API).
Opera en el navegador móvil a 60fps sin recargar el servidor de Streamlit,
sincronizado por timestamp real (Date.now()) con presets 60s, 90s, 120s, 180s,
ajuste +/-15s y alerta visual/sonora al finalizar.
"""
from __future__ import annotations

import streamlit.components.v1 as components


def render_client_rest_timer(
    target_seconds: int = 90,
    start_epoch_ms: int = 0,
    auto_running: bool = False,
    exercise_label: str = "Descanso Inter-Serie",
) -> None:
    """
    Renderiza el cronómetro de descanso inteligente del lado del cliente.
    - Si auto_running=True y start_epoch_ms > 0, calcula el tiempo real transcurrido
      desde que se guardó la última serie sin perder precisión aunque la pantalla se bloquee.
    - Incluye presets táctiles (60s, 90s, 120s, 180s), botones -15s/+15s, pausa/reinicio
      y alarma por Web Audio API + vibración móvil.
    """
    safe_target = max(10, min(900, int(target_seconds or 90)))
    safe_start = int(start_epoch_ms or 0)
    auto_js = "true" if auto_running and safe_start > 0 else "false"
    clean_label = (exercise_label or "Descanso Inter-Serie").replace('"', "&quot;")

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8" />
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&family=JetBrains+Mono:wght@700;800&display=swap');
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }}
        body {{
            background: transparent;
            font-family: 'Inter', -apple-system, sans-serif;
            color: #F8FAFC;
        }}
        .timer-card {{
            background: linear-gradient(180deg, rgba(18, 23, 34, 0.98) 0%, rgba(12, 16, 25, 0.99) 100%);
            border: 1px solid #263044;
            border-radius: 16px;
            padding: 12px 14px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.40);
            transition: border-color 0.25s ease, box-shadow 0.25s ease;
        }}
        .timer-card.completed {{
            border-color: #22C55E;
            box-shadow: 0 0 18px rgba(34, 197, 94, 0.30);
        }}
        .timer-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .timer-title {{
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94A3B8;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #94A3B8;
            display: inline-block;
        }}
        .status-dot.running {{
            background: #FF5500;
            box-shadow: 0 0 8px #FF5500;
        }}
        .status-dot.done {{
            background: #22C55E;
            box-shadow: 0 0 8px #22C55E;
        }}
        .actual-pill {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.74rem;
            font-weight: 700;
            color: #F8FAFC;
            background: #1A2232;
            border: 1px solid #263044;
            padding: 3px 9px;
            border-radius: 999px;
        }}
        .timer-main {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 6px 0 8px 0;
        }}
        .countdown-readout {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 2.15rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: #F8FAFC;
            line-height: 1.05;
        }}
        .countdown-sub {{
            font-size: 0.75rem;
            color: #94A3B8;
            margin-top: 2px;
        }}
        .ctrl-group {{
            display: flex;
            gap: 6px;
        }}
        .btn {{
            background: #1A2232;
            color: #F8FAFC;
            border: 1px solid #263044;
            border-radius: 10px;
            padding: 8px 11px;
            font-size: 0.80rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s ease;
            min-height: 38px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}
        .btn:active {{
            transform: scale(0.96);
        }}
        .btn.primary {{
            background: #FF5500;
            border-color: #FF5500;
            color: #FFFFFF;
        }}
        .btn.preset-active {{
            background: rgba(255, 85, 0, 0.20);
            border-color: #FF5500;
            color: #FF5500;
        }}
        .progress-track {{
            width: 100%;
            height: 7px;
            background: rgba(255, 255, 255, 0.10);
            border-radius: 999px;
            overflow: hidden;
            margin-bottom: 10px;
        }}
        .progress-fill {{
            height: 100%;
            width: 0%;
            background: #FF5500;
            border-radius: 999px;
            transition: width 0.25s linear, background-color 0.25s ease;
        }}
        .presets-row {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 5px;
        }}
        .alert-banner {{
            display: none;
            margin-top: 8px;
            padding: 6px 10px;
            border-radius: 9px;
            background: rgba(34, 197, 94, 0.16);
            border: 1px solid rgba(34, 197, 94, 0.45);
            color: #22C55E;
            font-size: 0.76rem;
            font-weight: 700;
            text-align: center;
        }}
    </style>
    </head>
    <body>
    <div id="card" class="timer-card">
        <div class="timer-header">
            <div class="timer-title">
                <span id="dot" class="status-dot"></span>
                <span>⏱️ {clean_label}</span>
            </div>
            <div class="actual-pill">
                Real: <span id="actualReadout">00:00</span> (<span id="actualSec">0</span>s)
            </div>
        </div>

        <div class="timer-main">
            <div>
                <div id="countdownReadout" class="countdown-readout">01:30</div>
                <div id="targetSub" class="countdown-sub">Objetivo: {safe_target}s</div>
            </div>
            <div class="ctrl-group">
                <button id="btnPlayPause" class="btn primary" onclick="toggleTimer()">▶ Iniciar</button>
                <button class="btn" onclick="resetTimer()" title="Reiniciar">🔄</button>
            </div>
        </div>

        <div class="progress-track">
            <div id="progressFill" class="progress-fill"></div>
        </div>

        <div class="presets-row">
            <button id="p60" class="btn" onclick="setPreset(60)">60s</button>
            <button id="p90" class="btn" onclick="setPreset(90)">90s</button>
            <button id="p120" class="btn" onclick="setPreset(120)">120s</button>
            <button id="p180" class="btn" onclick="setPreset(180)">180s</button>
            <button class="btn" onclick="adjustTarget(-15)">-15s</button>
            <button class="btn" onclick="adjustTarget(15)">+15s</button>
        </div>

        <div id="alertBanner" class="alert-banner">
            🔔 ¡Tiempo de descanso cumplido! Listo para la siguiente serie
        </div>
    </div>

    <script>
        let targetSec = {safe_target};
        let initialStartMs = {safe_start};
        let isRunning = {auto_js};
        let startTimestampMs = isRunning ? initialStartMs : 0;
        let accumulatedPauseSec = 0;
        let alertFired = false;

        function fmtMMSS(sec) {{
            const s = Math.max(0, Math.floor(sec));
            const m = Math.floor(s / 60);
            const r = s % 60;
            return String(m).padStart(2, '0') + ':' + String(r).padStart(2, '0');
        }}

        function playBeep() {{
            try {{
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtx) return;
                const ctx = new AudioCtx();
                const freqs = [880, 1108.73, 1318.51];
                freqs.forEach((f, idx) => {{
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(f, ctx.currentTime + idx * 0.14);
                    gain.gain.setValueAtTime(0.18, ctx.currentTime + idx * 0.14);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.14 + 0.13);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + idx * 0.14);
                    osc.stop(ctx.currentTime + idx * 0.14 + 0.14);
                }});
                if (navigator.vibrate) {{
                    navigator.vibrate([200, 100, 250]);
                }}
            }} catch (e) {{}}
        }}

        function getElapsedSeconds() {{
            if (!isRunning) return accumulatedPauseSec;
            return accumulatedPauseSec + Math.max(0, Math.floor((Date.now() - startTimestampMs) / 1000));
        }}

        function highlightPresets() {{
            [60, 90, 120, 180].forEach(p => {{
                const el = document.getElementById('p' + p);
                if (el) {{
                    el.className = (targetSec === p) ? 'btn preset-active' : 'btn';
                }}
            }});
            document.getElementById('targetSub').textContent = 'Objetivo: ' + targetSec + 's';
        }}

        function updateUI() {{
            const elapsed = getElapsedSeconds();
            const remaining = Math.max(0, targetSec - elapsed);
            const pct = targetSec > 0 ? Math.min(100, (elapsed / targetSec) * 100) : 0;

            document.getElementById('countdownReadout').textContent = fmtMMSS(remaining);
            document.getElementById('actualReadout').textContent = fmtMMSS(elapsed);
            document.getElementById('actualSec').textContent = elapsed;

            const fill = document.getElementById('progressFill');
            const card = document.getElementById('card');
            const dot = document.getElementById('dot');
            const banner = document.getElementById('alertBanner');
            const btnPP = document.getElementById('btnPlayPause');

            fill.style.width = pct.toFixed(1) + '%';
            btnPP.textContent = isRunning ? '⏸ Pausar' : '▶ Iniciar';

            if (elapsed >= targetSec && isRunning) {{
                fill.style.backgroundColor = '#22C55E';
                card.className = 'timer-card completed';
                dot.className = 'status-dot done';
                banner.style.display = 'block';
                document.getElementById('countdownReadout').style.color = '#22C55E';
                if (!alertFired) {{
                    alertFired = true;
                    playBeep();
                }}
            }} else if (remaining <= 15 && isRunning) {{
                fill.style.backgroundColor = '#F59E0B';
                card.className = 'timer-card';
                dot.className = 'status-dot running';
                banner.style.display = 'none';
                document.getElementById('countdownReadout').style.color = '#F59E0B';
            }} else {{
                fill.style.backgroundColor = '#FF5500';
                card.className = 'timer-card';
                dot.className = isRunning ? 'status-dot running' : 'status-dot';
                banner.style.display = 'none';
                document.getElementById('countdownReadout').style.color = '#F8FAFC';
            }}
        }}

        function toggleTimer() {{
            if (isRunning) {{
                accumulatedPauseSec = getElapsedSeconds();
                isRunning = false;
            }} else {{
                startTimestampMs = Date.now();
                isRunning = true;
            }}
            updateUI();
        }}

        function resetTimer() {{
            isRunning = false;
            accumulatedPauseSec = 0;
            startTimestampMs = 0;
            alertFired = false;
            updateUI();
        }}

        function setPreset(sec) {{
            targetSec = sec;
            alertFired = false;
            highlightPresets();
            if (!isRunning && accumulatedPauseSec === 0) {{
                startTimestampMs = Date.now();
                isRunning = true;
            }}
            updateUI();
        }}

        function adjustTarget(delta) {{
            targetSec = Math.max(15, Math.min(900, targetSec + delta));
            alertFired = false;
            highlightPresets();
            updateUI();
        }}

        highlightPresets();
        updateUI();
        setInterval(updateUI, 250);
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=198, scrolling=False)
