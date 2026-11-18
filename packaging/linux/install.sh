#!/usr/bin/env sh
# Instala Open Converter para tu usuario (sin permisos de administrador).
# Uso: ./install.sh        instalar        ./install.sh --uninstall   quitar
set -eu

AQUI="$(cd "$(dirname "$0")" && pwd)"
DESTINO="$HOME/.local/share/open-converter"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONOS="$HOME/.local/share/icons/hicolor/256x256/apps"

if [ "${1:-}" = "--uninstall" ]; then
  rm -rf "$DESTINO" "$BIN/open-converter" "$APPS/open-converter.desktop" "$ICONOS/open-converter.png"
  echo "Open Converter se quitó."
  exit 0
fi

mkdir -p "$DESTINO" "$BIN" "$APPS" "$ICONOS"
rm -rf "$DESTINO"/*
cp -R "$AQUI/open-converter/." "$DESTINO/"
ln -sf "$DESTINO/open-converter" "$BIN/open-converter"
cp "$AQUI/open-converter.png" "$ICONOS/open-converter.png"
sed "s|^Exec=.*|Exec=$DESTINO/open-converter %F|" "$AQUI/open-converter.desktop" > "$APPS/open-converter.desktop"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true

echo "Listo. Búscalo como «Open Converter» en tu menú de aplicaciones o ejecuta: open-converter"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Nota: agrega $BIN a tu PATH para usarlo desde la terminal." ;; esac
