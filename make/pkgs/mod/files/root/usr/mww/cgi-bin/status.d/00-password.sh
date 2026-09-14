default_password_set() {
	[ "$MOD_HTTPD_PASSWD" == '$1$freetzng$i0SVp/Hgvxd80q6MIUq701' ]
}

if default_password_set; then
	print_warning "$(lang \
	  de:"Standard-Passwort gesetzt. <a href=\"/cgi-bin/passwd.cgi\">Bitte &auml;ndern!</a> " \
	  en:"Default password set. <a href=\"/cgi-bin/passwd.cgi\">Please change!</a>" \
	)"
fi
