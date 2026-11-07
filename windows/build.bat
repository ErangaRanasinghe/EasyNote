@echo off
rem Builds EasyNote.exe with the C# compiler that ships with Windows. No install needed.
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
  echo Could not find the .NET Framework 4 compiler on this PC.
  if not defined CI pause
  exit /b 1
)
"%CSC%" /nologo /target:winexe /optimize+ /out:EasyNote.exe /win32icon:..\assets\logo.ico /resource:..\assets\logo.png,logo.png /resource:..\assets\logo.ico,logo.ico /r:System.Windows.Forms.dll /r:System.Drawing.dll EasyNote.cs
if errorlevel 1 (
  echo.
  echo Build failed - see the errors above.
  if not defined CI pause
  exit /b 1
)
echo.
echo Built EasyNote.exe - double-click it to run.
if not defined CI pause
