#!/bin/sh
# Native Freetz package CGI fragment; page and form provided by Freetz.
. /usr/lib/libmodcgi.sh
[ -r /mod/etc/conf/celllock.cfg ] && . /mod/etc/conf/celllock.cfg
MODEM=/dev/ttyUSB2
query_at() {
    local reader
    [ -c "$MODEM" ] || return 1
    { timeout 3 cat "$MODEM" 2>/dev/null & reader=$!; sleep 0.2; printf '%s\r\n' "$1" > "$MODEM"; wait "$reader" 2>/dev/null; }
}
SERVING=$(query_at 'AT+QENG="servingcell"')
LOCK5G=$(query_at 'AT+QNWLOCK="common/5g"')
ROW=$(printf '%s\n' "$SERVING" | grep 'QENG:.*servingcell.*NR5G' | head -n 1)
PCI=$(printf '%s\n' "$ROW" | awk -F, '{gsub(/[^0-9]/,"",$8);print $8}')
ARFCN=$(printf '%s\n' "$ROW" | awk -F, '{gsub(/[^0-9]/,"",$10);print $10}')
BAND=$(printf '%s\n' "$ROW" | awk -F, '{gsub(/[^0-9]/,"",$11);print $11}')
[ -n "$CELLLOCK_PCI" ] && PCI=$CELLLOCK_PCI
[ -n "$CELLLOCK_ARFCN" ] && ARFCN=$CELLLOCK_ARFCN
[ -n "$CELLLOCK_BAND" ] && BAND=$CELLLOCK_BAND
sec_begin 'Aktuelle Funkzelle'
echo '<h4>Serving Cell</h4><pre>'
printf '%s\n' "${SERVING:-Keine Antwort vom Modem}" | html
echo '</pre><h4>5G Lock-Status</h4><pre>'
printf '%s\n' "${LOCK5G:-Keine Antwort vom Modem}" | html
echo '</pre>'
sec_end
sec_begin '5G Cell Lock'
cat <<EOF
<p>Die Werte werden nach Moeglichkeit aus der Funkzelle uebernommen. Ein Lock kann die Verbindung unterbrechen.</p>
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
