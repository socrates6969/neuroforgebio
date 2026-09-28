@echo off
rem Build and run the Unreal plugin's engine-free core tests with MSVC /W4 /WX.
rem   bindings\unreal\tests\run-msvc.cmd
rem Builds neuroforge (debug, -j 2), writes the shared fixture, compiles tests\test_core.cpp against
rem the import library (DLL) and against the static library, and runs both. Unreal is NOT needed and
rem NOT used: the UE module sources are not compiled here. Output goes to <target>\unreal-core-tests.
setlocal enableextensions

set "HERE=%~dp0"
for %%I in ("%HERE%..\..\..") do set "ROOT=%%~fI"
set "PLUGIN=%ROOT%\bindings\unreal\NeuroForge"
if defined CARGO_TARGET_DIR (set "TARGET=%CARGO_TARGET_DIR%") else (set "TARGET=%ROOT%\target")
set "LIBDIR=%TARGET%\debug"
set "OUT=%TARGET%\unreal-core-tests"

where cl >nul 2>nul
if not errorlevel 1 goto have_cl
set "PF86=%ProgramFiles(x86)%"
set "VS=Microsoft Visual Studio\2022"
set "VCVARS="
for %%E in (Community Professional Enterprise BuildTools) do (
  if exist "%ProgramFiles%\%VS%\%%E\VC\Auxiliary\Build\vcvars64.bat" set "VCVARS=%ProgramFiles%\%VS%\%%E\VC\Auxiliary\Build\vcvars64.bat"
  if exist "%PF86%\%VS%\%%E\VC\Auxiliary\Build\vcvars64.bat" set "VCVARS=%PF86%\%VS%\%%E\VC\Auxiliary\Build\vcvars64.bat"
)
if not defined VCVARS (echo run-msvc: vcvars64.bat not found & exit /b 1)
call "%VCVARS%" >nul || exit /b 1
:have_cl

if defined NF_SKIP_CARGO goto skip_cargo
echo == cargo build (neuroforge + fixture writer)
cargo build -p neuroforge-c --lib --examples -j 2 --manifest-path "%ROOT%\Cargo.toml" || exit /b 1
:skip_cargo
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%" || exit /b 1
"%LIBDIR%\examples\make_fixture.exe" "%OUT%\fixture" >nul || exit /b 1
copy /y "%LIBDIR%\neuroforge.dll" "%OUT%\" >nul || exit /b 1

set CXXFLAGS=/nologo /W4 /WX /std:c++17 /EHsc /permissive- /I "%PLUGIN%\Source\NeuroForge\Public" /I "%ROOT%\bindings\c\include" /I "%ROOT%\bindings\cpp\include" /I "%ROOT%\bindings\c\tests\c"
set SYSLIBS=crypt32.lib kernel32.lib bcrypt.lib advapi32.lib ntdll.lib userenv.lib ws2_32.lib dbghelp.lib

echo == engine core test (DLL)
cl %CXXFLAGS% "%HERE%test_core.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_core.exe" /link "%LIBDIR%\neuroforge.dll.lib" psapi.lib || exit /b 1
"%OUT%\test_core.exe" "%OUT%\fixture" || exit /b 1

echo == engine core test (static library, /MD as Unreal uses)
cl %CXXFLAGS% /MD "%HERE%test_core.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_core_static.exe" /link "%LIBDIR%\neuroforge.lib" %SYSLIBS% psapi.lib || exit /b 1
"%OUT%\test_core_static.exe" "%OUT%\fixture" || exit /b 1

echo run-msvc: all Unreal engine-core tests passed
endlocal
