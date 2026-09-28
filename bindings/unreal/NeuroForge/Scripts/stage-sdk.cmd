@echo off
rem Copy the NeuroForge C ABI (header, C++ wrapper, import library, DLL) into the plugin's
rem ThirdParty folder so Unreal can build the plugin.
rem   Scripts\stage-sdk.cmd [debug|release]      (default: release)
rem Run from a NeuroForge repository checkout after `cargo build -p neuroforge-c [--release]`.
setlocal enableextensions
set "PROFILE=%~1"
if "%PROFILE%"=="" set "PROFILE=release"
set "PLUGIN=%~dp0.."
for %%I in ("%PLUGIN%") do set "PLUGIN=%%~fI"
for %%I in ("%PLUGIN%\..\..\..") do set "ROOT=%%~fI"
if defined CARGO_TARGET_DIR (set "TARGET=%CARGO_TARGET_DIR%") else (set "TARGET=%ROOT%\target")
set "SRC=%TARGET%\%PROFILE%"
set "TP=%PLUGIN%\ThirdParty\neuroforge"

if not exist "%SRC%\neuroforge.dll" (echo stage-sdk: %SRC%\neuroforge.dll not found; run cargo build -p neuroforge-c first & exit /b 1)
for %%D in ("%TP%\include" "%TP%\lib\Win64" "%TP%\bin\Win64" "%PLUGIN%\Binaries\Win64") do if not exist %%D mkdir %%D
copy /y "%ROOT%\bindings\c\include\neuroforge.h" "%TP%\include\" >nul || exit /b 1
copy /y "%ROOT%\bindings\cpp\include\neuroforge.hpp" "%TP%\include\" >nul || exit /b 1
copy /y "%SRC%\neuroforge.dll.lib" "%TP%\lib\Win64\" >nul || exit /b 1
copy /y "%SRC%\neuroforge.dll" "%TP%\bin\Win64\" >nul || exit /b 1
copy /y "%SRC%\neuroforge.dll" "%PLUGIN%\Binaries\Win64\" >nul || exit /b 1
echo stage-sdk: staged %PROFILE% build into %TP%
endlocal
