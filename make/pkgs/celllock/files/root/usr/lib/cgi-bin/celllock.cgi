#!/bin/sh
# Cell Lock Control CGI für Quectel RM500Q-AE / FritzBox 6850 5G
# Ablegen unter: /var/mod/usr/lib/cgi-bin/celllock.cgi
# chmod +x /var/mod/usr/lib/cgi-bin/celllock.cgi
# Aufruf: http://fritz.box:81/cgi-bin/celllock.cgi

MODEM="/dev/ttyUSB2"
TIMEOUT=1

# AT-Befehl senden und Antwort lesen
send_at() {
    local cmd="$1"
    local wait="${2:-$TIMEOUT}"
    echo -e "${cmd}\r" > "$MODEM"
    # Liest verfügbare Bytes (non-blocking via timeout)
    timeout "$wait" cat "$MODEM" 2>/dev/null || true
}

# URL-Decode
urldecode() {
    echo -e "$(echo "$1" | sed 's/+/ /g; s/%/\\x/g')"
}

# POST-Parameter parsen
parse_post() {
    if [ "$REQUEST_METHOD" = "POST" ]; then
        read -r POST_DATA
        for pair in $(echo "$POST_DATA" | tr '&' '\n'); do
            key=$(echo "$pair" | cut -d= -f1)
            val=$(urldecode "$(echo "$pair" | cut -d= -f2-)")
            eval "PARAM_${key}='${val}'"
        done
    fi
}

# Serving Cell Info holen
get_serving_cell() {
    send_at 'AT+QENG="servingcell"' 1
}

# Nachbarzellen holen
get_neighbour_cells() {
    send_at 'AT+QENG="neighbourcell"' 2
}

# Aktuellen Lock-Status abfragen
get_lock_status_5g() {
    send_at 'AT+QNWLOCK="common/5g"' 1
}

get_lock_status_4g() {
    send_at 'AT+QNWLOCK="common/4g"' 1
}


# Aktuelle Aktion ausführen
ACTION=""
RESULT=""
RESULT2=""

parse_post

ACTION="$PARAM_action"

case "$ACTION" in
    lock_5g)
        PCI="$PARAM_pci"
        ARFCN="$PARAM_arfcn"
        SCS="$PARAM_scs"
        BAND="$PARAM_band"
        RESULT=$(send_at "AT+QNWLOCK=\"common/5g\",${PCI},${ARFCN},${SCS},${BAND}" 1)
        ;;
    lock_4g)
        EARFCN="$PARAM_earfcn"
        PCI="$PARAM_pci"
        RESULT=$(send_at "AT+QNWLOCK=\"common/4g\",1,${EARFCN},${PCI}" 1)
        ;;
    unlock_5g)
        RESULT=$(send_at 'AT+QNWLOCK="common/5g",0,0,0,0' 1)
        ;;
    unlock_4g)
        RESULT=$(send_at 'AT+QNWLOCK="common/4g",0' 1)
        ;;
    save)
        RESULT=$(send_at 'AT+QNWLOCK="save_ctrl",1,1' 1)
        ;;
    query)
        RESULT=$(get_serving_cell)
        RESULT2=$(get_neighbour_cells)
        ;;
esac

# Alle Status-Abfragen in einem Block — 2x sleep statt 3x timeout
ALL=$(
    {
        echo -e 'AT+QENG="servingcell"\r'
        sleep 1
        echo -e 'AT+QNWLOCK="common/5g"\r'
        sleep 1
        echo -e 'AT+QNWLOCK="common/4g"\r'
    } > "$MODEM" & timeout 3 cat "$MODEM"
)
SERVING=$(echo "$ALL" | grep '+QENG:')
LOCK5G=$(echo "$ALL"  | grep '+QNWLOCK:' | head -1)
LOCK4G=$(echo "$ALL"  | grep '+QNWLOCK:' | tail -1)

# Werte aus serving cell parsen
# Format: +QENG: "servingcell","NOCONN","NR5G-SA","TDD",232,05,CellID,PCI,TAC,ARFCN,Band,SCS,RSRP,RSRQ,SINR,...
CONN_STATE=$(echo "$SERVING" | awk -F'"' '{print $4}')
RAT=$(echo "$SERVING" | awk -F'"' '{print $6}')
SC_DATA=$(echo "$SERVING" | grep '+QENG:' | sed 's/+QENG: "servingcell",//')
CELL_ID=$(echo "$SERVING" | awk -F',' '{gsub(/"/, "", $7); print $7}')
SC_PCI_VAL=$(echo "$SERVING" | awk -F',' '{print $8}')
TAC=$(echo "$SERVING" | awk -F',' '{print $9}')
SC_ARFCN=$(echo "$SERVING" | awk -F',' '{print $10}')
SC_BAND=$(echo "$SERVING" | awk -F',' '{print $11}')
RSRP=$(echo "$SERVING" | awk -F',' '{print $13}')
SINR=$(echo "$SERVING" | awk -F',' '{print $15}')

# HTTP Header
echo "Content-Type: text/html; charset=utf-8"
echo "Cache-Control: no-cache"
echo ""

cat << 'HTMLEOF'
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cell Lock — RM500Q-AE</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Exo+2:wght@300;400;600;800&display=swap');

  :root {
    --bg:       #0a0e14;
    --surface:  #111720;
    --border:   #1e2d40;
    --accent:   #00d4ff;
    --accent2:  #ff6b35;
    --ok:       #00ff88;
    --err:      #ff3355;
    --warn:     #ffcc00;
    --text:     #c8d8e8;
    --muted:    #4a6080;
    --mono:     'Share Tech Mono', monospace;
    --sans:     'Exo 2', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(0,212,255,0.06) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 100%, rgba(255,107,53,0.04) 0%, transparent 50%);
  }

  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    position: sticky;
    top: 0;
    z-index: 100;
  }

  header .logo {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--accent);
    letter-spacing: 2px;
    text-transform: uppercase;
    opacity: 0.7;
  }

  header h1 {
    font-size: 18px;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.5px;
  }

  header h1 span { color: var(--accent); }


  .container {
    max-width: 960px;
    margin: 0 auto;
    padding: 24px 16px;
    display: grid;
    gap: 16px;
  }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 640px) { .grid-2 { grid-template-columns: 1fr; } }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }

  .card-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
  }

  .card-header .dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 6px var(--accent);
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  .card-body { padding: 16px; }

  /* Status Grid */
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
  }

  .stat {
    background: rgba(0,0,0,0.3);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
  }

  .stat-label {
    font-size: 10px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 6px;
  }

  .stat-value {
    font-family: var(--mono);
    font-size: 18px;
    color: #fff;
    line-height: 1;
  }

  .stat-value.good  { color: var(--ok); }
  .stat-value.warn  { color: var(--warn); }
  .stat-value.bad   { color: var(--err); }
  .stat-value.accent { color: var(--accent); }

  .stat-unit {
    font-size: 10px;
    color: var(--muted);
    margin-top: 3px;
  }

  /* Raw output */
  .raw {
    font-family: var(--mono);
    font-size: 12px;
    background: rgba(0,0,0,0.4);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    white-space: pre-wrap;
    word-break: break-all;
    color: var(--accent);
    max-height: 200px;
    overflow-y: auto;
    line-height: 1.6;
  }

  .raw .ok-line  { color: var(--ok); }
  .raw .err-line { color: var(--err); }

  /* Forms */
  .form-group { margin-bottom: 12px; }

  label {
    display: block;
    font-size: 11px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 6px;
  }

  input[type=text], input[type=number], select {
    width: 100%;
    background: rgba(0,0,0,0.4);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    padding: 8px 12px;
    outline: none;
    transition: border-color 0.2s;
  }

  input:focus, select:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(0,212,255,0.1);
  }

  select option { background: var(--surface); }

  .hint {
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
    font-family: var(--mono);
  }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 18px;
    border-radius: 4px;
    border: none;
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.15s;
    text-decoration: none;
  }

  .btn-primary {
    background: var(--accent);
    color: #000;
  }
  .btn-primary:hover { background: #33dcff; box-shadow: 0 0 16px rgba(0,212,255,0.4); }

  .btn-danger {
    background: transparent;
    color: var(--err);
    border: 1px solid var(--err);
  }
  .btn-danger:hover { background: rgba(255,51,85,0.1); box-shadow: 0 0 12px rgba(255,51,85,0.2); }

  .btn-warn {
    background: transparent;
    color: var(--warn);
    border: 1px solid var(--warn);
  }
  .btn-warn:hover { background: rgba(255,204,0,0.1); }

  .btn-ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .btn-ghost:hover { color: var(--text); border-color: var(--muted); }

  .btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }

  /* Lock status indicator */
  .lock-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 6px;
    font-family: var(--mono);
    font-size: 12px;
    margin-bottom: 16px;
  }

  .lock-status.locked {
    background: rgba(0,255,136,0.05);
    border: 1px solid rgba(0,255,136,0.2);
    color: var(--ok);
  }

  .lock-status.unlocked {
    background: rgba(74,96,128,0.1);
    border: 1px solid var(--border);
    color: var(--muted);
  }

  .lock-icon { font-size: 16px; }

  /* Result flash */
  .result-box {
    margin-top: 12px;
    padding: 10px 14px;
    border-radius: 6px;
    font-family: var(--mono);
    font-size: 12px;
  }

  .result-ok  { background: rgba(0,255,136,0.05); border: 1px solid rgba(0,255,136,0.2); color: var(--ok); }
  .result-err { background: rgba(255,51,85,0.05);  border: 1px solid rgba(255,51,85,0.2);  color: var(--err); }

  /* Divider */
  .divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 16px 0;
  }

  /* Section label */
  .section-label {
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--accent2);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">FritzBox 6850 5G // Quectel RM500Q-AE</div>
    <h1>Cell <span>Lock</span> Control</h1>
  </div>
HTMLEOF


cat << 'HTMLEOF'
</header>

<div class="container">
HTMLEOF

# === STATUS CARD ===
cat << 'HTMLEOF'
  <div class="card">
    <div class="card-header">
      <span class="dot"></span>
      Live Status
    </div>
    <div class="card-body">
      <div class="stat-grid">
HTMLEOF

# RAT
echo "        <div class='stat'>"
echo "          <div class='stat-label'>Technologie</div>"
echo "          <div class='stat-value accent'>$(echo "$SERVING" | grep -oE 'NR5G-SA|NR5G-NSA|LTE|WCDMA' | head -1)</div>"
echo "        </div>"

# Band (Spalte 11)
echo "        <div class='stat'>"
echo "          <div class='stat-label'>Band</div>"
echo "          <div class='stat-value accent'>n$SC_BAND</div>"
echo "        </div>"

# ARFCN (Spalte 10)
echo "        <div class='stat'>"
echo "          <div class='stat-label'>ARFCN</div>"
echo "          <div class='stat-value'>$SC_ARFCN</div>"
echo "        </div>"

# PCI (Spalte 8)
echo "        <div class='stat'>"
echo "          <div class='stat-label'>PCI</div>"
echo "          <div class='stat-value'>$SC_PCI_VAL</div>"
echo "        </div>"

# RSRP mit Farbe (Spalte 13)
RSRP_VAL=$RSRP
if [ -n "$RSRP_VAL" ] && [ "$RSRP_VAL" -gt -90 ] 2>/dev/null; then
    RSRP_CLASS="good"
elif [ -n "$RSRP_VAL" ] && [ "$RSRP_VAL" -gt -105 ] 2>/dev/null; then
    RSRP_CLASS="warn"
else
    RSRP_CLASS="bad"
fi
echo "        <div class='stat'>"
echo "          <div class='stat-label'>RSRP</div>"
echo "          <div class='stat-value $RSRP_CLASS'>$RSRP_VAL</div>"
echo "          <div class='stat-unit'>dBm</div>"
echo "        </div>"

# SINR (Spalte 15)
SINR_VAL=$SINR
if [ -n "$SINR_VAL" ] && [ "$SINR_VAL" -gt 10 ] 2>/dev/null; then
    SINR_CLASS="good"
elif [ -n "$SINR_VAL" ] && [ "$SINR_VAL" -gt 0 ] 2>/dev/null; then
    SINR_CLASS="warn"
else
    SINR_CLASS="bad"
fi
echo "        <div class='stat'>"
echo "          <div class='stat-label'>SINR</div>"
echo "          <div class='stat-value $SINR_CLASS'>$SINR_VAL</div>"
echo "          <div class='stat-unit'>dB</div>"
echo "        </div>"

# Cell ID (Spalte 7)
echo "        <div class='stat'>"
echo "          <div class='stat-label'>Cell ID</div>"
echo "          <div class='stat-value' style='font-size:13px'>$CELL_ID</div>"
echo "        </div>"

# MCC/MNC (Spalten 5+6)
MCC=$(echo "$SERVING" | awk -F',' '{print $5}')
MNC=$(echo "$SERVING" | awk -F',' '{print $6}')
echo "        <div class='stat'>"
echo "          <div class='stat-label'>Operator</div>"
echo "          <div class='stat-value' style='font-size:13px'>$MCC-$MNC</div>"
echo "        </div>"

cat << 'HTMLEOF'
      </div>

      <hr class="divider">
      <div class="section-label">Raw Output</div>
      <div class="raw">
HTMLEOF
echo "$SERVING" | sed 's/OK/<span class="ok-line">OK<\/span>/g; s/ERROR/<span class="err-line">ERROR<\/span>/g'
cat << 'HTMLEOF'
      </div>
    </div>
  </div>
HTMLEOF

# === LOCK STATUS ===
cat << 'HTMLEOF'
  <div class="grid-2">
    <div class="card">
      <div class="card-header">
        <span class="dot" style="background:var(--accent2);box-shadow:0 0 6px var(--accent2)"></span>
        5G Lock Status
      </div>
      <div class="card-body">
HTMLEOF

# Lock aktiv wenn QNWLOCK Zeile einen Wert enthält der nicht ",0" endet
LOCK5G_VAL=$(echo "$LOCK5G" | grep '+QNWLOCK:' | grep -v '"common/5g",0$')
if [ -n "$LOCK5G_VAL" ]; then
    echo "        <div class='lock-status locked'>🔒 Cell Lock aktiv</div>"
else
    echo "        <div class='lock-status unlocked'>🔓 Kein Lock gesetzt</div>"
fi

echo "        <div class='raw'>"
echo "$LOCK5G"
echo "        </div>"

cat << 'HTMLEOF'
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="dot" style="background:var(--warn);box-shadow:0 0 6px var(--warn)"></span>
        4G Lock Status
      </div>
      <div class="card-body">
HTMLEOF

LOCK4G_VAL=$(echo "$LOCK4G" | grep '+QNWLOCK:' | grep -v '"common/4g",0$')
if [ -n "$LOCK4G_VAL" ]; then
    echo "        <div class='lock-status locked'>🔒 Cell Lock aktiv</div>"
else
    echo "        <div class='lock-status unlocked'>🔓 Kein Lock gesetzt</div>"
fi

echo "        <div class='raw'>"
echo "$LOCK4G"
echo "        </div>"

cat << 'HTMLEOF'
      </div>
    </div>
  </div>
HTMLEOF

# === RESULT BOX (wenn Aktion ausgeführt wurde) ===
if [ -n "$ACTION" ] && [ -n "$RESULT" ]; then
    if echo "$RESULT" | grep -q "^OK"; then
        echo "<div class='result-ok'>✓ Befehl erfolgreich: $RESULT</div>"
    else
        echo "<div class='result-err'>✕ Fehler: $RESULT</div>"
    fi
fi

# === 5G LOCK FORM ===
# Prefill aus bereits geparsten Variablen

cat << HTMLEOF
  <div class="card">
    <div class="card-header">
      <span class="dot" style="background:var(--accent2);box-shadow:0 0 6px var(--accent2)"></span>
      5G Cell Lock (NR5G-SA/NSA)
    </div>
    <div class="card-body">
      <p style="font-size:12px;color:var(--muted);margin-bottom:16px;">
        Felder sind mit der aktuellen Serving Cell vorausgefüllt.
        Werte aus <code style="color:var(--accent)">AT+QENG="neighbourcell"</code> für andere Zellen.
      </p>

      <form method="post">
        <input type="hidden" name="action" value="lock_5g">
        <div class="grid-2">
          <div class="form-group">
            <label>PCI (Physical Cell ID)</label>
            <input type="number" name="pci" value="$SC_PCI_VAL" min="0" max="1007" required>
            <div class="hint">0 – 1007</div>
          </div>
          <div class="form-group">
            <label>ARFCN (NR-ARFCN)</label>
            <input type="number" name="arfcn" value="$SC_ARFCN" required>
            <div class="hint">z.B. 639936 für n78</div>
          </div>
          <div class="form-group">
            <label>SCS (Subcarrier Spacing)</label>
            <select name="scs">
              <option value="15">15 kHz</option>
              <option value="30" selected>30 kHz (n78 Standard)</option>
              <option value="60">60 kHz</option>
              <option value="120">120 kHz</option>
            </select>
          </div>
          <div class="form-group">
            <label>Band</label>
            <input type="number" name="band" value="$SC_BAND" min="1" max="261" required>
            <div class="hint">z.B. 78 für n78 (3.5 GHz)</div>
          </div>
        </div>
        <div class="btn-row">
          <button type="submit" class="btn btn-primary">🔒 5G Lock setzen</button>
        </div>
      </form>

      <hr class="divider">

      <form method="post">
        <input type="hidden" name="action" value="unlock_5g">
        <button type="submit" class="btn btn-danger">🔓 5G Lock aufheben</button>
      </form>
    </div>
  </div>
HTMLEOF

# === 4G LOCK FORM ===
cat << 'HTMLEOF'
  <div class="card">
    <div class="card-header">
      <span class="dot" style="background:var(--warn);box-shadow:0 0 6px var(--warn)"></span>
      4G Cell Lock (LTE)
    </div>
    <div class="card-body">
      <form method="post">
        <input type="hidden" name="action" value="lock_4g">
        <div class="grid-2">
          <div class="form-group">
            <label>EARFCN</label>
            <input type="number" name="earfcn" placeholder="z.B. 1300" required>
            <div class="hint">aus AT+QENG="servingcell"</div>
          </div>
          <div class="form-group">
            <label>PCI</label>
            <input type="number" name="pci" placeholder="z.B. 123" min="0" max="503" required>
            <div class="hint">0 – 503</div>
          </div>
        </div>
        <div class="btn-row">
          <button type="submit" class="btn btn-primary">🔒 4G Lock setzen</button>
        </div>
      </form>

      <hr class="divider">

      <form method="post">
        <input type="hidden" name="action" value="unlock_4g">
        <button type="submit" class="btn btn-danger">🔓 4G Lock aufheben</button>
      </form>
    </div>
  </div>
HTMLEOF

# === QUERY + SAVE ===
cat << 'HTMLEOF'
  <div class="grid-2">
    <div class="card">
      <div class="card-header">
        <span class="dot"></span>
        Nachbarzellen
      </div>
      <div class="card-body">
        <form method="post">
          <input type="hidden" name="action" value="query">
          <button type="submit" class="btn btn-ghost">📡 Nachbarzellen abfragen</button>
        </form>
HTMLEOF

if [ "$ACTION" = "query" ] && [ -n "$RESULT2" ]; then
    echo "        <div class='raw' style='margin-top:12px'>$RESULT2</div>"
fi

cat << 'HTMLEOF'
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="dot" style="background:var(--warn);box-shadow:0 0 6px var(--warn)"></span>
        Lock persistent speichern
      </div>
      <div class="card-body">
        <p style="font-size:12px;color:var(--muted);margin-bottom:12px;">
          Speichert den aktuellen Lock ins NV-Speicher des Modems (überlebt Reboot).
          Nicht alle Firmware-Versionen unterstützen das.
        </p>
        <form method="post">
          <input type="hidden" name="action" value="save">
          <button type="submit" class="btn btn-warn">💾 Lock speichern</button>
        </form>
HTMLEOF

if [ "$ACTION" = "save" ] && [ -n "$RESULT" ]; then
    if echo "$RESULT" | grep -q "OK"; then
        echo "        <div class='result-ok' style='margin-top:12px'>✓ Gespeichert</div>"
    else
        echo "        <div class='result-err' style='margin-top:12px'>✕ Nicht unterstützt: $RESULT</div>"
    fi
fi

cat << 'HTMLEOF'
      </div>
    </div>
  </div>

  <div style="text-align:center;padding:16px;font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;">
    FRITZ!BOX 6850 5G // QUECTEL RM500Q-AE // FREETZ-NG
  </div>

</div>
</body>
</html>
HTMLEOF
