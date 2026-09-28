@echo off
rem Build and run the C and C++ ABI tests with MSVC (ADR 0013).
rem   bindings\c\tests\run-msvc.cmd
rem Builds neuroforge (debug, -j 2), writes the fixture, compiles tests\c\test_abi.c against the
rem import library (DLL) and the static library, compiles bindings\cpp\tests\test_wrapper.cpp and
rem the caller-misuse test tests\c\test_misuse.c, and runs all four. Output goes to <target>\c-tests.
setlocal enableextensions

set "CRATE=%~dp0.."
for %%I in ("%CRATE%\..\..") do set "ROOT=%%~fI"
for %%I in ("%CRATE%") do set "CRATE=%%~fI"
if defined CARGO_TARGET_DIR (set "TARGET=%CARGO_TARGET_DIR%") else (set "TARGET=%ROOT%\target")
set "LIBDIR=%TARGET%\debug"
set "OUT=%TARGET%\c-tests"

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

echo == cargo build (neuroforge + fixture writer)
cargo build -p neuroforge-c --lib --examples -j 2 --manifest-path "%ROOT%\Cargo.toml" || exit /b 1
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%" || exit /b 1
cargo run -q -p neuroforge-c --example make_fixture -j 2 --manifest-path "%ROOT%\Cargo.toml" -- "%OUT%\fixture" || exit /b 1
copy /y "%LIBDIR%\neuroforge.dll" "%OUT%\" >nul || exit /b 1

set CFLAGS=/nologo /W4 /WX /I "%CRATE%\include" /I "%CRATE%\tests\c"
set SYSLIBS=crypt32.lib kernel32.lib bcrypt.lib advapi32.lib ntdll.lib userenv.lib ws2_32.lib dbghelp.lib

echo == C test (DLL)
cl %CFLAGS% /std:c11 "%CRATE%\tests\c\test_abi.c" /Fo"%OUT%\\" /Fe"%OUT%\test_abi.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1
"%OUT%\test_abi.exe" "%OUT%\fixture" || exit /b 1

echo == C test (static library)
cl %CFLAGS% /std:c11 /MD "%CRATE%\tests\c\test_abi.c" /Fo"%OUT%\\" /Fe"%OUT%\test_abi_static.exe" /link "%LIBDIR%\neuroforge.lib" %SYSLIBS% || exit /b 1
"%OUT%\test_abi_static.exe" "%OUT%\fixture" || exit /b 1

echo == C++ wrapper test
cl %CFLAGS% /std:c++17 /EHsc /I "%ROOT%\bindings\cpp\include" "%ROOT%\bindings\cpp\tests\test_wrapper.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_wrapper.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1
"%OUT%\test_wrapper.exe" "%OUT%\fixture" || exit /b 1

echo == C caller-misuse test
cl %CFLAGS% /std:c11 "%CRATE%\tests\c\test_misuse.c" /Fo"%OUT%\\" /Fe"%OUT%\test_misuse.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1
"%OUT%\test_misuse.exe" "%OUT%\fixture" || exit /b 1

echo run-msvc: all C/C++ tests passed
endlocal
