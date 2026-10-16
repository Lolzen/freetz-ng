#!/bin/sh
# Native Freetz package CGI fragment; page and form provided by Freetz.
. /usr/lib/libmodcgi.sh
[ -r /mod/etc/conf/celllock.cfg ] && . /mod/etc/conf/celllock.cfg
MODEM=/dev/ttyUSB2
query_at() {
    local reader
    [ -c "$MODEM" ] || return 1
    { timeout 3 cat "$MODEM" 2>/dev/null & reader=$!; sleep 1; printf '%s\r\n' "$1" > "$MODEM"; wait "$reader" 2>/dev/null; }
}
SERVING=$(query_at 'AT+QENG="servingcell"')
LOCK5G=$(query_at 'AT+QNWLOCK="common/5g"')
# Fixed, user-requested defaults; live serving-cell data is shown above only.
PCI=0
ARFCN=639936
BAND=78
# Parse only modem-reported fields; an LTE NOCONN response is not 5G signal data.
SERVING_LINE=$(printf '%s\n' "$SERVING" | grep '+QENG:.*"servingcell"' | head -n 1)
TECH=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{gsub(/["[:space:]]/,"",$3); print $3}')
STATE=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{gsub(/["[:space:]]/,"",$2); print $2}')
case "$TECH" in LTE|NR5G-SA|NR5G-NSA|WCDMA) ;; *) TECH='Unbekannt' ;; esac
case "$STATE" in NOCONN|CONNECT|SEARCH|LIMSRV) ;; *) STATE='Unbekannt' ;; esac
# NR5G fields vary by firmware and radio mode. Display only when present.
if [ "$TECH" = NR5G-SA ] || [ "$TECH" = NR5G-NSA ]; then
    CELL_ID=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{print $7}')
    LIVE_PCI=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{print $8}')
    LIVE_ARFCN=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{print $10}')
    LIVE_BAND=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{print $11}')
    RSRP=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{print $13}')
    SINR=$(printf '%s\n' "$SERVING_LINE" | awk -F, '{print $15}')
else
    CELL_ID='–'; LIVE_PCI='–'; LIVE_ARFCN='–'; LIVE_BAND='–'; RSRP='–'; SINR='–'
fi
LOCK_LINE=$(printf '%s\n' "$LOCK5G" | grep '+QNWLOCK:.*"common/5g"' | head -n 1)
LOCK_VALUES=$(printf '%s\n' "$LOCK_LINE" | sed 's/.*"common\/5g",[[:space:]]*//')
case "$LOCK_VALUES" in
    ''|'0,0,0,0') LOCK_CLASS=off; LOCK_LABEL='Kein 5G Lock gesetzt' ;;
    *[!0-9,[:space:]]*) LOCK_CLASS=unknown; LOCK_LABEL='Lock-Status unklar' ;;
    *) LOCK_CLASS=on; LOCK_LABEL='5G Lock konfiguriert' ;;
esac
sec_begin 'Aktuelle Funkzelle'
cat <<'CSS'
<style>
.celllock-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px;margin:12px 0 18px}
.celllock-stat{border:1px solid #686868;border-radius:8px;padding:12px;background:rgba(0,0,0,.14)}
.celllock-label{font-size:12px;opacity:.8;margin-bottom:6px}
.celllock-value{font-size:21px;font-weight:700;overflow-wrap:anywhere}
.celllock-status{display:flex;align-items:center;gap:12px;border:1px solid #686868;border-radius:8px;padding:13px;margin:12px 0}
.celllock-dot{height:14px;width:14px;display:inline-block;flex-shrink:0;border-radius:50%;background:#929292}
.celllock-dot.on{background:#36d879;box-shadow:0 0 0 0 rgba(54,216,121,.65);animation:celllock-pulse 1.8s infinite}
.celllock-dot.off{background:#d49b44}
@keyframes celllock-pulse{0%{box-shadow:0 0 0 0 rgba(54,216,121,.65)}65%{box-shadow:0 0 0 11px rgba(54,216,121,0)}100%{box-shadow:0 0 0 0 rgba(54,216,121,0)}}
.celllock-raw{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0}
</style>
CSS
echo '<div class="celllock-grid">'
stat() {
    printf '<div class="celllock-stat"><div class="celllock-label">%s</div><div class="celllock-value">%s</div></div>\n' "$1" "$(html "$2")"
}
stat 'Technologie' "$TECH"
stat 'Verbindungsstatus' "$STATE"
stat 'PCI' "$LIVE_PCI"
stat 'NR-ARFCN' "$LIVE_ARFCN"
stat 'Band' "$LIVE_BAND"
stat 'Cell ID' "$CELL_ID"
stat 'RSRP (dBm)' "$RSRP"
stat 'SINR (dB)' "$SINR"
echo '</div>'
echo '<h4>5G Lock-Status</h4>'
printf '<div class="celllock-status"><span class="celllock-dot %s"></span><strong>%s</strong></div>\n' "$LOCK_CLASS" "$LOCK_LABEL"
[ -n "$LOCK_VALUES" ] && printf '<p>Modemparameter: <code>%s</code></p>\n' "$(html "$LOCK_VALUES")"
echo '<details><summary>AT-Rohdaten anzeigen</summary><h4>Serving Cell</h4><pre class="celllock-raw">'
printf '%s\n' "${SERVING:-Keine Antwort vom Modem}" | html
echo '</pre><h4>5G Lock</h4><pre class="celllock-raw">'
printf '%s\n' "${LOCK5G:-Keine Antwort vom Modem}" | html
echo '</pre></details>'
sec_end
sec_begin '5G Cell Lock'
cat <<EOF
<p>Voreingestellt: PCI 0, NR-ARFCN 639936, SCS 30 kHz und Band 78. Vor dem Setzen pruefen: Ein Lock kann die Verbindung unterbrechen.</p>
<input type="hidden" id="celllock_action" name="action" value="">
<table>
<tr><td>PCI (0-1007)</td><td><input type="number" name="pci" min="0" max="1007" value="$(html "$PCI")"></td></tr>
<tr><td>NR-ARFCN</td><td><input type="number" name="arfcn" min="1" value="$(html "$ARFCN")"></td></tr>
<tr><td>SCS</td><td><select name="scs"><option value="15">15</option><option value="30" selected>30</option><option value="60">60</option><option value="120">120</option></select></td></tr>
<tr><td>Band</td><td><input type="number" name="band" min="1" max="261" value="$(html "$BAND")"></td></tr>
</table>
<p>
<button type="submit" onclick="document.getElementById('celllock_action').value='lock_5g'">5G Lock setzen</button>
<button type="submit" onclick="document.getElementById('celllock_action').value='unlock_5g';return confirm('5G Lock aufheben?')">5G Lock aufheben</button>
</p>
EOF
sec_end
