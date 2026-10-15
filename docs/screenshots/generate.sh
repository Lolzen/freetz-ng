#! /usr/bin/env bash
# generates thumbnails of docs/screenshots/* to docs/README/*_md.*
MYPWD="$(dirname $(realpath $0))"
command -v magick >/dev/null && IM="magick" || IM="convert"

for file in $MYPWD/*.???; do
	src="${file##*/}"
	dst="${src%.*}_md.${src##*.}"
	[ "${dst/_md_md./}" != "$dst" ] && continue
	[ -e "$MYPWD/$dst" ] && continue
	echo "$src -> $dst"
	"$IM" "$MYPWD/$src" -resize x333 "$MYPWD/$dst"
	chmod -x "$MYPWD/$src" "$MYPWD/$dst"
done
exit 0

