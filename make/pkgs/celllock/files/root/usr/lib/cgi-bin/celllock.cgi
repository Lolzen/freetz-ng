#!/bin/sh
# Native Freetz package configuration fragment.
# /usr/mww/cgi-bin/conf/celllock is wrapped by Freetz's page handler.
# Do not emit HTTP headers, <html>, <body>, or nested forms here.

MODEM=/dev/ttyUSB2
sec_begin "Celllock – Quectel RM500Q-AE"

if [ ! -c "$MODEM" ]; then
    echo "<p>Modem-Schnittstelle /dev/ttyUSB2 nicht verfügbar.</p>"
else
    echo "<p>Celllock ist in Freetz integriert. Die Modem-Statusanzeige ist verfügbar.</p>"
    echo "<h3>Aktuelle Funkzelle</h3><pre>"
    # Read-only status query; avoid indefinite blocking.
    ( printf 'AT+QENG="servingcell"\\r\n' > "$MODEM" ) 2>/dev/null &
    timeout 3 cat "$MODEM" 2>/dev/null | html
    echo "</pre>"
    echo "<h3>Lock-Status</h3><pre>"
    ( printf 'AT+QNWLOCK="common/5g"\\r\n' > "$MODEM" ) 2>/dev/null &
    timeout 3 cat "$MODEM" 2>/dev/null | html
    echo "</pre>"
fi

echo "<p>Die bisherigen Lock-/Unlock-Schaltflächen werden erst nach Anbindung an die abgesicherte Freetz-Formularverarbeitung wieder aktiviert.</p>"
sec_end
