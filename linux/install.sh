#!/usr/bin/env bash
# Installs Easy Note for the current user (no root needed except for missing packages).
# Works on Ubuntu, Debian, Linux Mint, Raspberry Pi OS, Fedora, Arch and openSUSE.
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"
ASSETS="$SRC/../assets"
[ -d "$ASSETS" ] || ASSETS="$SRC/assets"
APP_DIR="$HOME/.local/share/easynote"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"
PY="${EASYNOTE_PYTHON:-/usr/bin/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"

echo "Installing Easy Note (EMR Industries)..."

# ---- 1. check the libraries it needs --------------------------------------
need_gtk=0
"$PY" -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; import cairo; from gi.repository import PangoCairo' >/dev/null 2>&1 || need_gtk=1
need_tray=0
"$PY" -c 'import gi
try:
    gi.require_version("AyatanaAppIndicator3","0.1")
except ValueError:
    gi.require_version("AppIndicator3","0.1")' >/dev/null 2>&1 || need_tray=1

if [ $need_gtk = 1 ] || [ $need_tray = 1 ]; then
  if command -v apt-get >/dev/null; then
    pkgs="python3-gi python3-gi-cairo gir1.2-gtk-3.0"
    [ $need_tray = 1 ] && pkgs="$pkgs gir1.2-ayatanaappindicator3-0.1"
    cmd="sudo apt-get install -y $pkgs"
  elif command -v dnf >/dev/null; then
    pkgs="python3-gobject gtk3"
    [ $need_tray = 1 ] && pkgs="$pkgs libayatana-appindicator-gtk3"
    cmd="sudo dnf install -y $pkgs"
  elif command -v pacman >/dev/null; then
    pkgs="python-gobject python-cairo gtk3"
    [ $need_tray = 1 ] && pkgs="$pkgs libayatana-appindicator"
    cmd="sudo pacman -S --needed $pkgs"
  elif command -v zypper >/dev/null; then
    pkgs="python3-gobject python3-gobject-cairo python3-gobject-Gdk typelib-1_0-Gtk-3_0"
    [ $need_tray = 1 ] && pkgs="$pkgs typelib-1_0-AyatanaAppIndicator3-0_1"
    cmd="sudo zypper install -y $pkgs"
  else
    cmd=""
  fi

  if [ -n "$cmd" ]; then
    echo
    [ $need_gtk = 1 ] && echo "Easy Note needs a few system packages (Python GTK)."
    [ $need_gtk = 0 ] && echo "Optional: the tray icon needs one extra package."
    echo "  $cmd"
    read -r -p "Install them now? [Y/n] " ans
    case "$ans" in
      n|N) [ $need_gtk = 1 ] && { echo "Cannot continue without them."; exit 1; } ;;
      *) $cmd || { [ $need_gtk = 1 ] && { echo "Package install failed."; exit 1; }; } ;;
    esac
  elif [ $need_gtk = 1 ]; then
    echo "Please install Python GTK 3 bindings (PyGObject, GTK 3, pycairo) and run this again."
    exit 1
  fi
fi

# ---- 2. copy the app ------------------------------------------------------
pkill -f "easynote/easynote.py" >/dev/null 2>&1 || true
mkdir -p "$APP_DIR/assets" "$BIN_DIR" "$ICON_DIR" "$DESKTOP_DIR"
cp "$SRC/easynote.py" "$APP_DIR/easynote.py"
cp "$ASSETS/logo.png" "$APP_DIR/assets/logo.png"
cp "$ASSETS/logo.png" "$ICON_DIR/easynote.png"

cat > "$BIN_DIR/easynote" <<EOF
#!/bin/sh
exec $PY "$APP_DIR/easynote.py" "\$@"
EOF
chmod +x "$BIN_DIR/easynote" "$APP_DIR/easynote.py"

# ---- 3. app menu entry ----------------------------------------------------
cat > "$DESKTOP_DIR/easynote.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Easy Note
Comment=Quick scratch pad on the edge of your screen
Exec=$BIN_DIR/easynote
Icon=easynote
Terminal=false
Categories=Utility;TextEditor;
StartupWMClass=easynote
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

# ---- 4. start it ----------------------------------------------------------
echo
echo "Installed. Easy Note is in your app menu, and 'easynote' works in a terminal."
if [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
  nohup "$BIN_DIR/easynote" >/dev/null 2>&1 &
  echo "Started - move the mouse to the right edge of the screen."
fi
echo "Tip: set a keyboard shortcut that runs:  $BIN_DIR/easynote --toggle"
