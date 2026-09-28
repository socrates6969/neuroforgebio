# SdkTestProject

This is a minimal Unity project that exists only to run the `com.neuroforge.sdk` EditMode tests
(`bindings/unity/Tests/Editor`). It references the package in place (`Packages/manifest.json`:
`file:../../..`) and lists it under `testables`. There are no assets.

Run `..\run-tests.cmd`. Unity creates `Library/`, `Logs/`, `UserSettings/` and `ProjectSettings/` on first open; none of them are committed.
