@echo off
rem Run the com.neuroforge.sdk EditMode tests in the Unity editor (batch mode, no window).
rem   bindings\unity\Samples~\SdkTestProject\run-tests.cmd
rem 1. builds neuroforge-c (debug, -j 2) unless NF_SKIP_CARGO is set,
rem 2. writes the shared fixture to <target>\unity-tests\fixture,
rem 3. copies neuroforge.dll into the package's Plugins\x86_64,
rem 4. runs Unity's command-line test runner; results in <target>\unity-tests\editmode-results.xml.
rem Set UNITY_EXE to pick an editor; otherwise the newest Unity 6 under the Hub's default folder is used.
setlocal enableextensions

set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"
for %%I in ("%PROJ%\..\..") do set "PKG=%%~fI"
for %%I in ("%PKG%\..\..") do set "ROOT=%%~fI"
if defined CARGO_TARGET_DIR (set "TARGET=%CARGO_TARGET_DIR%") else (set "TARGET=%ROOT%\target")
set "LIBDIR=%TARGET%\debug"
set "OUT=%TARGET%\unity-tests"

if defined UNITY_EXE goto have_unity
for /d %%V in ("%ProgramFiles%\Unity\Hub\Editor\6000.*") do if exist "%%V\Editor\Unity.exe" set "UNITY_EXE=%%V\Editor\Unity.exe"
if not defined UNITY_EXE (echo run-tests: Unity 6 editor not found; set UNITY_EXE & exit /b 1)
:have_unity
echo == Unity: %UNITY_EXE%

if defined NF_SKIP_CARGO goto skip_cargo
echo == cargo build (neuroforge + fixture writer)
cargo build -p neuroforge-c --lib --examples -j 2 --manifest-path "%ROOT%\Cargo.toml" || exit /b 1
:skip_cargo
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%" || exit /b 1
"%LIBDIR%\examples\make_fixture.exe" "%OUT%\fixture" >nul || exit /b 1
if not exist "%PKG%\Plugins\x86_64" mkdir "%PKG%\Plugins\x86_64"
copy /y "%LIBDIR%\neuroforge.dll" "%PKG%\Plugins\x86_64\" >nul || exit /b 1

set "NF_FIXTURE_DIR=%OUT%\fixture"
if "%NF_TLS_SPIKE%"=="1" goto tls_spike
echo == Unity EditMode tests (batch mode)
"%UNITY_EXE%" -batchmode -nographics -projectPath "%PROJ%" -runTests -testPlatform EditMode ^
  -assemblyNames NeuroForge.Tests.Editor ^
  -testResults "%OUT%\editmode-results.xml" -logFile "%OUT%\editmode.log"
set "RC=%ERRORLEVEL%"
goto report

:tls_spike
rem CABI-M1 E1 owner spike: the local TLS test server (127.0.0.1:47000-47099, temp certs, stopped and
rem cleaned up by run_conformance.py) around one Unity run of the NeuroForge.TlsSpike assembly only.
if not defined NF_PYTHON if exist "%ROOT%\.venv\Scripts\python.exe" set "NF_PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined NF_PYTHON if exist "%USERPROFILE%\neuro-company\.venv\Scripts\python.exe" set "NF_PYTHON=%USERPROFILE%\neuro-company\.venv\Scripts\python.exe"
if not defined NF_PYTHON (echo run-tests: Python venv not found; set NF_PYTHON & exit /b 1)
set "NF_TLS_SPIKE_OUT=%OUT%"
echo == Unity TLS spike (batch mode, local TLS server)
"%NF_PYTHON%" "%ROOT%\bindings\transport-conformance\run_conformance.py" -- ^
  "%UNITY_EXE%" -batchmode -nographics -projectPath "%PROJ%" -runTests -testPlatform EditMode ^
  -assemblyNames NeuroForge.TlsSpike ^
  -testResults "%OUT%\tls-spike-results.xml" -logFile "%OUT%\tls-spike.log"
set "RC=%ERRORLEVEL%"
if exist "%OUT%\tls-spike.txt" type "%OUT%\tls-spike.txt"

:report
if "%RC%"=="0" (echo run-tests: all EditMode tests passed) else (echo run-tests: Unity exited with %RC%; see %OUT%\editmode-results.xml and editmode.log)
endlocal & exit /b %RC%
