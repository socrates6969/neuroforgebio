# Verify the Unity SDK once the Unity editor is installed

Written for the owner, Marius Carlsson. It needs no programming: every step is a click or one
copy-and-paste command. Allow about 20 minutes, most of it waiting on the first import.

Until these steps have been run, the Unity SDK is **unverified**: its C# code has never been compiled.

---

## Step 1: install the editor (Unity Hub)

1. Open **Unity Hub**, sign in, then go to **Installs > Install Editor**.
2. Pick the newest **Unity 6 LTS** (a version that starts with `6000.`, marked "LTS").
3. On the **modules** screen:
   - **Tick:** *Windows Build Support (IL2CPP)*. Not needed for the tests, but it's needed to build a Windows game later.
   - **Untick:** *Microsoft Visual Studio Community*. It isn't needed, and Visual Studio Build Tools are already on this PC.
   - **Leave unticked:** Android, iOS, WebGL, Mac and Linux build support, and Documentation. None of them are needed. The SDK doesn't support WebGL.
4. Press **Install** and wait until the Hub shows the editor under *Installs*.

The editor installs to `C:\Program Files\Unity\Hub\Editor\6000.x.yf1\`, and the test script finds it there by itself.

## Step 2: close Unity, then run the one command

Unity must **not** have the test project open while this runs. Close any Unity editor window first.

Open **Command Prompt**: press the Windows key, type `cmd`, then press Enter. Paste this line and press Enter:

```
C:\Users\mariu\neuro-worktrees\engine\bindings\unity\Samples~\SdkTestProject\run-tests.cmd
```

The command does four things on its own:
- it builds the NeuroForge library (`neuroforge.dll`) from source with cargo (about 1 minute; it's the same build the C++ tests use);
- it writes a small test recording to `C:\Users\mariu\neuro-worktrees\engine\target\unity-tests\fixture`;
- it copies `neuroforge.dll` into the package folder (`bindings\unity\Plugins\x86_64\`), which is the "staging" step;
- it starts Unity **without a window**, opens the test project and runs every EditMode test.

No window appears for the Unity part. The first run takes several minutes, because Unity imports the project and downloads
two official Unity packages: the Test Framework and Newtonsoft JSON. Later runs take about 1 minute.

When it finishes, the last line is one of:
- `run-tests: all EditMode tests passed` means **pass**;
- `run-tests: Unity exited with 2 ...` means some tests failed;
- anything else, such as exit code 1 or "Unity 6 editor not found", means the run itself didn't work. See "If something goes wrong" below.

> This uses the heavy-lane slot rule: ask the team lead, who asks bci-queen, before running it while agents are building.

## Step 3: what a pass looks like

Open `C:\Users\mariu\neuro-worktrees\engine\target\unity-tests\editmode-results.xml` in Notepad. Near the top is a line like:

```
<test-run ... total="22" passed="22" failed="0" inconclusive="0" skipped="0" ...>
```

A pass is **total="22", passed="22", failed="0"**. The 22 tests are:

| Group | Tests | What they prove |
|---|---|---|
| VectorTests | 4 | Library version check. Every official hash/ID test vector gives the same result inside Unity as in the Rust core, including the 5 training-manifest cases. |
| RecordingAndReplayTests | 5 | Recordings are read exactly. Replay is lossless, runs at the right speed, loops, stops promptly, and never uses unbounded memory. The chunk cache verifies hashes. |
| CaptureAndProvenanceTests | 4 | Captured samples become signed chunks in the encrypted log. With a persistent (DPAPI) key, the log keeps unsent data across a restart. The provenance chain verifies. Device tokens verify. |
| HandleAndLeakTests | 2 | Errors come back as clear exceptions. No memory leaks over 100,000 create/free loops. |
| NeuroStreamTests | 2 | The game component delivers every sample and the newest values, and reports a missing recording instead of crashing. |
| ReviewRegressionTests | 5 | The fixes from the code review: wrong sample types are refused, the cache is safe on two threads, shutting down mid-stream is safe, old library versions are refused, and restarting from inside a handler is safe. |

If a test reports **inconclusive** (the memory counter isn't available), that isn't a failure; please mention it.

### Optional: see it in the editor

After Step 2 has run once, you can also watch the tests in the editor:
1. In Unity Hub, go to **Projects > Add > Add project from disk** and pick the folder
   `C:\Users\mariu\neuro-worktrees\engine\bindings\unity\Samples~\SdkTestProject`.
2. Open it, then in the top menu choose **Window > General > Test Runner**.
3. Pick the **EditMode** tab and press **Run All**. The list should turn green: 22 tests.
4. Close Unity afterwards, before running Step 2 again.

## Step 4: report these three things back

Send them to the team lead (a copy-paste in the chat is fine):

1. **The result line**: the `<test-run ... total= passed= failed= ...>` line from `editmode-results.xml`, and the last
   line the command printed.
2. **The Unity version**: the folder name under `C:\Program Files\Unity\Hub\Editor\`, for example `6000.0.xxf1`.
3. **What Unity downloaded or created**: the file
   `C:\Users\mariu\neuro-worktrees\engine\bindings\unity\Samples~\SdkTestProject\Packages\packages-lock.json`,
   which lists the exact package versions downloaded. Also mention whether new `.meta` files appeared in
   `bindings\unity`. The agents commit both.

If anything failed, also send `C:\Users\mariu\neuro-worktrees\engine\target\unity-tests\editmode.log`. It's long, so the
file itself is fine and an agent will read it.

## If something goes wrong

| Message | What to do |
|---|---|
| `Unity 6 editor not found; set UNITY_EXE` | The editor is in a different folder. In the same Command Prompt, type `set UNITY_EXE=C:\path\to\Editor\Unity.exe` (the path to `Unity.exe`), press Enter, and run the command again. |
| `cargo` is not recognised | Rust isn't on PATH in this window. Report it; don't install anything. |
| Exit code 1 with "another Unity instance is running" in the log | Close every Unity window (and check the Task Manager for `Unity.exe`), then run again. |
| `The process cannot access the file ... neuroforge.dll` | A Unity window still has the DLL loaded. Close Unity and run again. |
| Tests fail | Nothing to fix by hand. Send the three items and `editmode.log`. |

---

## Step 5 (owner item): the TLS 1.3 check (CABI-M1 open item E1)

This step decides whether Unity's built-in web requests can be the SDK's default network transport. Only
you can run it, because it needs your editor. The test (`TlsSpikeTests`) is in the test project, **written but never run**.

1. Run the same command as in Step 2, but first type `set NF_TLS_SPIKE=1` in the same Command Prompt window.
   It uses the project's Python (`neuro-company\.venv`) for the local server, and Git's `openssl.exe` for the test certificates.
2. The spike starts a small test server on this PC only (127.0.0.1, ports 47000-47099; nothing is reachable
   from outside), with test certificates that are deleted afterwards.
3. It checks three things and prints a line for each:
   - whether Unity can connect to a TLS 1.3-only server;
   - whether Unity refuses a TLS 1.2-only server;
   - whether Unity follows a redirect.
4. The command prints the lines at the end; they're also saved in
   `C:\Users\mariu\neuro-worktrees\engine\target\unity-tests\tls-spike.txt`. Send the file back with the Step 4 report.

If Unity accepts the TLS 1.2-only server, the SDK must not use Unity's web requests for uploads. That's expected and
fine, and the agents will choose another transport.

## What this does NOT verify (Unity)

These stay unverified after a green run, and are tracked for later:
- building a Windows **player** (IL2CPP or Mono) and running the sample scene in it. The EditMode tests run inside the editor only;
- the Play-mode behaviour of `MainThreadDispatcher` (it runs only in Play mode);
- macOS and Linux (`Plugins/macOS`, `Plugins/Linux` are placeholders);
- the xUnit suite in `Tests~/`. It needs a separate .NET SDK, which isn't allowed on this PC; the EditMode suite covers the same ground.

## Still needs Unreal: **not planned yet**

The team lead chose Unity first, and **installing Unreal is not planned yet**. Until it is, the following stay
**unverified in-editor**. Only the plugin's engine-free C++ core is verified, with MSVC: 84/84 checks.

- compiling the Unreal module at all (`NeuroForge.Build.cs`, `NeuroForge.uplugin`, UHT code generation);
- `FNeuroForgeModule`: loading `neuroforge.dll` by absolute path, and the "DLL missing" and "old library version" error paths;
- `UNeuroForgeStreamComponent`: Blueprint events on the game thread, and stopping or restarting from inside an `OnSamples` handler;
- `UNeuroForgeBlueprintLibrary`: the Blueprint nodes;
- `Scripts/stage-sdk.cmd` and staging the DLL into a packaged game;
- Mac and Linux.
