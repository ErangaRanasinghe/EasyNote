# Easy Note

A tiny scratch pad that hides on the right edge of your screen.
Version 1.0.0 · Publisher: EMR Industries

Move the mouse to the far right edge of the screen and a blue tab appears.
Click it to open the note at the bottom centre of the screen; click it again to hide it.
The note stays on top of other windows and saves as you type.

## Download

Get the latest version from the **Releases** page:

- Windows: `EasyNote-X.Y.Z-windows.zip` - unzip and run `EasyNote.exe`
- Linux: `EasyNote-X.Y.Z-linux.tar.gz` - unpack, then run `bash install.sh` in the `linux` folder

## Build it yourself on Windows

1. Open the `windows` folder and double-click `build.bat`.
2. Run `EasyNote.exe`.

## Linux

Works on Ubuntu, Fedora, Linux Mint, KDE Plasma, Raspberry Pi OS and other GTK-capable desktops.

```
cd linux
bash install.sh
```

The installer asks before installing any missing system packages (it uses sudo for that step only).
Easy Note then appears in your app menu and starts right away.

- Open/close from the keyboard: add a custom shortcut in your desktop settings that runs `easynote --toggle`.
- Quit from a terminal: `easynote --quit`
- Remove: `bash uninstall.sh` (add `--all` to also delete the saved note)

## Menu

The `⋯` button on the note, a right-click on the tab, or the tray icon:
font, transparency, start at login/with Windows, About, Exit.

## Making a release

1. Update the version in `windows/EasyNote.cs` (`AppInfo.Version` and the `AssemblyVersion` lines) and in `linux/easynote.py` (`VERSION`).
2. Add a `## [1.0.1] - date` section to `CHANGELOG.md`; it becomes the release notes.
3. Commit, then tag and push:
   ```
   git tag v1.0.1
   git push origin v1.0.1
   ```
4. GitHub Actions builds the Windows and Linux packages and publishes the release.

## Files

```
assets/    logo.png, logo.ico
windows/   EasyNote.cs, build.bat
linux/     easynote.py, install.sh, uninstall.sh
.github/   release workflow (builds and publishes on a version tag)
CHANGELOG.md
LICENSE
```

## License

MIT License - see [LICENSE](LICENSE). Copyright (c) 2026 EMR Industries.
