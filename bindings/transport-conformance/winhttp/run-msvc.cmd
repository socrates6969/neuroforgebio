@echo off
rem Build the WinHTTP transport conformance tests with MSVC /W4 /WX and run them against the local
rem TLS server (bindings\transport-conformance\run_conformance.py; 127.0.0.1:47000-47099 only).
rem   bindings\transport-conformance\winhttp\run-msvc.cmd
rem Needs an existing debug build of neuroforge-c (cargo build -p neuroforge-c) and the project venv
rem Python (set NF_PYTHON to override). Output: <target>\winhttp-conformance.
setlocal enableextensions

set "HERE=%~dp0"
for %%I in ("%HERE%..\..\..") do set "ROOT=%%~fI"
if defined CARGO_TARGET_DIR (set "TARGET=%CARGO_TARGET_DIR%") else (set "TARGET=%ROOT%\target")
set "LIBDIR=%TARGET%\debug"
set "OUT=%TARGET%\winhttp-conformance"

if not defined NF_PYTHON if exist "%ROOT%\.venv\Scripts\python.exe" set "NF_PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not defined NF_PYTHON if exist "%USERPROFILE%\neuro-company\.venv\Scripts\python.exe" set "NF_PYTHON=%USERPROFILE%\neuro-company\.venv\Scripts\python.exe"
if not defined NF_PYTHON (echo run-msvc: Python venv not found; set NF_PYTHON & exit /b 1)

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

if not exist "%LIBDIR%\neuroforge.dll" (echo run-msvc: %LIBDIR%\neuroforge.dll missing; cargo build -p neuroforge-c first & exit /b 1)
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%" || exit /b 1
copy /y "%LIBDIR%\neuroforge.dll" "%OUT%\" >nul || exit /b 1

rem _CRT_SECURE_NO_WARNINGS: the TEST code reads NF_CONFORMANCE with getenv; the transport header itself compiles clean without it.
set CXXFLAGS=/nologo /W4 /WX /std:c++17 /EHsc /permissive- /D_CRT_SECURE_NO_WARNINGS /I "%HERE%include" /I "%HERE%tests" /I "%ROOT%\bindings\c\include" /I "%ROOT%\bindings\cpp\include"
echo == negative compile: NF_TRANSPORT_TESTING against the shipped header must FAIL
cl %CXXFLAGS% /c "%HERE%tests\test_macro_rejected.cpp" /Fo"%OUT%\\" >"%OUT%\macro_rejected.log" 2>&1
if not errorlevel 1 (echo run-msvc: FAIL - the shipped header compiled with NF_TRANSPORT_TESTING & exit /b 1)
findstr /c:"NF_TRANSPORT_TESTING is not supported by the shipped transport" "%OUT%\macro_rejected.log" >nul || (echo run-msvc: FAIL - compile failed for another reason & type "%OUT%\macro_rejected.log" & exit /b 1)
echo PASS 9 NF_TRANSPORT_TESTING against the shipped header is a compile error
echo == compile test_winhttp (test CA via tests\nf_winhttp_testing.hpp)
cl %CXXFLAGS% "%HERE%tests\test_winhttp.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_winhttp.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1
echo == compile test_ingest (case 10: gRPC ingest transport)
cl %CXXFLAGS% "%HERE%tests\test_ingest.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_ingest.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1
rem Case 10 HTTP/2 cases: compiled always (so they stay buildable), RUN only with a grpcio venv.
echo == compile test_ingest_grpc (case 10 HTTP/2; runs only if NF_GRPC_PYTHON is set)
cl %CXXFLAGS% "%HERE%tests\test_ingest_grpc.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_ingest_grpc.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1
echo == compile test_release (release: no test hooks)
cl %CXXFLAGS% "%HERE%tests\test_release.cpp" /Fo"%OUT%\\" /Fe"%OUT%\test_release.exe" /link "%LIBDIR%\neuroforge.dll.lib" || exit /b 1

rem Both clients run inside ONE server session (one set of temp certs and ports).
> "%OUT%\clients.cmd" echo @echo off
>> "%OUT%\clients.cmd" echo "%OUT%\test_winhttp.exe" ^|^| exit /b 1
>> "%OUT%\clients.cmd" echo "%OUT%\test_ingest.exe" ^|^| exit /b 1
>> "%OUT%\clients.cmd" echo "%OUT%\test_release.exe" ^|^| exit /b 1
set "GRPC_FLAG="
if defined NF_GRPC_PYTHON (
  >> "%OUT%\clients.cmd" echo "%OUT%\test_ingest_grpc.exe" ^|^| exit /b 1
  set "GRPC_FLAG=--grpc"
  echo == case 10 HTTP/2 tests ON: gRPC server from %NF_GRPC_PYTHON%
) else (
  echo == case 10 HTTP/2 tests SKIPPED: NF_GRPC_PYTHON not set ^(grpcio venv not installed; owner item^)
)
echo == conformance run (local TLS server)
"%NF_PYTHON%" "%HERE%..\run_conformance.py" %GRPC_FLAG% -- cmd /c "%OUT%\clients.cmd"
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (echo run-msvc: WinHTTP conformance passed) else (echo run-msvc: WinHTTP conformance FAILED with %RC%)
endlocal & exit /b %RC%
