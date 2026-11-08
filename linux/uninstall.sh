#!/usr/bin/env bash
# Removes EasyNote. Your saved note in ~/.config/easynote is kept unless you pass --all.
"$HOME/.local/bin/easynote" --quit >/dev/null 2>&1 || true
rm -rf "$HOME/.local/share/easynote"
rm -f "$HOME/.local/bin/easynote" \
      "$HOME/.local/share/applications/easynote.desktop" \
      "$HOME/.local/share/icons/hicolor/256x256/apps/easynote.png" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/easynote.desktop"
if [ "$1" = "--all" ]; then
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/easynote"
  echo "EasyNote and your saved note were removed."
else
  echo "EasyNote was removed. Your saved note is still in ~/.config/easynote (use --all to delete it)."
fi
