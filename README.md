# Bravado Desktop

System-wide Windows EQ. Compact desktop panel. Local processing.

**[Source repository](https://github.com/leon-executes/bravado-desktop) · [Dependencies & downloads](DEPENDENCIES.md) · [Preset guide & research](PRESETS.md) · [Licence](LICENSE)**

<br>

![Bravado Desktop app UI 0](https://github.com/user-attachments/assets/40c4ee3d-2575-4e42-bbc2-0f9d0e1fc389)

![Bravado Desktop app UI 3](https://github.com/user-attachments/assets/d7306da1-b728-44e3-91f7-e853328e25ce)

**Note**: Due to having encountered issues with other audio solutions such as Peace, in the shape of abrupt volume ramp-ups that threatened my speakers, let alone my eardrums, I develop an elegant solution with a few high-fidelity presets.

## Run

1. Extract the Windows release into a writable folder. Keep `_internal` beside `Bravado.exe`.
2. Install [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) and attach it to your playback device. Follow its restart instructions.
3. Open `Bravado.exe`. Select a preset. Click **Enable**. Use **Apply changes** after edits.
4. No audible change? Open **Connection tools → Device setup**. Check the selected playback device.

No Python installation or browser launch. Requires Windows x64,
[WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
and [.NET Framework 4.6.2+](https://dotnet.microsoft.com/en-us/download/dotnet-framework).
See [dependencies](DEPENDENCIES.md) before installing anything.

## Use

- **Disable:** remove Bravado's processing. **Restore config:** recover the previous APO configuration.
- **Save as:** keep a personal preset. Factory presets cannot be overwritten or deleted.
- **Close:** stop the panel; the last applied EQ stays active. **Minimize:** keep the panel available.
- **Ctrl+Enter:** apply. **Ctrl+S:** save. **Esc:** dismiss a dialog; otherwise emergency mute.
- **Preamp:** lower it if playback distorts. Match listening volume when comparing presets.

| Preset | Choose it for |
| --- | --- |
| Bravado Signature Preset | The original vivid 14-band curve; preamp 0 dB |
| Pocket Physics | Deep foundation, dense kick-drum body and focused treble bite |
| Flat | An uncoloured reference |
| Nordrassil | Expansive body and broad strength between Signature and Pocket |
| Marble Alibi | Forward voices, firm bass and treble articulation |
| Red Herring | Deepest bass weight and hard punch |

Selecting a preset changes the preview. Apply to hear it. Start-up does not apply
a new preset. These are tonal choices, not device calibration; see [the listening guide](PRESETS.md#choose-and-compare).

## Build

Use **[CPython 3.12 x64](https://www.python.org/downloads/windows/)**. Close Bravado.
If you have used the existing `dist/Bravado` app, move that complete folder elsewhere
first; the build refuses to overwrite its saved data. Then run:

```bat
build_exe.cmd
```

For a custom Python location, set `BRAVADO_PYTHON` to its full executable path.
The script installs [pinned packages](requirements-build.txt) in `.build-venv`,
runs source tests, builds the app, copies the licence/docs, and tests the executable.
Output: `dist/Bravado/`. Reports: `build/source-tests.txt` and `build/packaged-tests.txt`.
The build script downloads packages; the finished app runs offline.

```bat
Bravado.exe --self-test --report tests.txt
Bravado.exe --diagnose --report diagnostics.json
Bravado.exe --export signature-export
```

Tests use temporary APO directories. `--export` writes Signature to an empty
destination. The build is unsigned.

## Put this on GitHub

```text
bravado.py                 Application, embedded UI and regression tests
bravado.ico                Application icon
build_exe.cmd              Windows release build
requirements-build.txt    Pinned build environment
README.md                  Start here
DEPENDENCIES.md            Requirements, downloads and package links
PRESETS.md                 Tuning choices, settings and research
LICENSE                    PolyForm Noncommercial 1.0.0
THIRD_PARTY_NOTICES.txt    Dependency licence texts
.gitignore                 Generated-file exclusions
```

Publish the complete portable folder as a ZIP through **GitHub Releases**.
Include its matching source ZIP. Keep the five documentation/licence files beside
the executable so their relative links work offline. Do not commit `build/`,
`dist/`, virtual environments or `bravado-data/`.

| Created during use | What to do |
| --- | --- |
| `bravado-data/presets.json` | Keep; these are your personal presets |
| `bravado-data/session.json`, `original-*.txt` | Keep on this PC for connection state and recovery |
| `bravado-data/launch.json`, `elevate-*`, `helper-process.json` | Private local process/authentication records; never publish |
| `bravado-data/webview/`, `startup-error.log` | Browser cache and error diagnostics |
| APO `config/bravado-*/` | Live processing assets; do not delete while active |

Move the application folder and personal presets to carry Bravado. APO must be
installed and connected on each PC. Machine-bound session ownership is discarded
on a different Windows installation. `--data-dir` selects another writable data folder.

## Licence

Copyright 2026 Parham (Leon) Faraji ([Leon-Executes](https://github.com/leon-executes)).

Bravado's original code and accompanying documentation/assets use
**[PolyForm Noncommercial 1.0.0](LICENSE)**. The standard licence permits
noncommercial purposes and expressly permits use by its listed institutions
regardless of funding. Read its terms for the exact scope. This is source-available
software. Dependencies retain their own licences in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).
Third-party brand references identify research inspirations; they imply no affiliation or endorsement.

## How it works

One sectioned Python file holds the data model, filter mathematics, storage,
Windows integration, APO transactions, local API, embedded HTML/CSS/JavaScript and
tests. No frontend build system, hosted assets, cloud service or added audio driver.
NumPy calculates responses and optional impulse assets. Equalizer APO runs the
actual system audio processing independently of the controller.

The main EQ uses APO's native parametric filters. Export preserves frequency,
gain, Q and filter type; it does not replace the curve with an approximation.
Preset preamps are explicit editable values. There is no automatic attenuation
or added limiter. Positive boosts can clip; the response estimate is advisory.
The Windows endpoint meter reports electrical output activity, not speaker power
or acoustic loudness. Exclusive/direct playback may bypass the Windows effects chain.

The fixed desktop window uses pywebview and the installed WebView2 engine. It
fits within the work area, up to 1120 × 800 logical pixels. Larger preset libraries
scroll inside their panel. The renderer, HTTP service, filter work and monitoring
run outside the native window message loop; moving the window does not stop APO.
Requests have time limits and polling does not overlap. Closing the window closes
the controller service. `--headless` runs the service for diagnostics.

The API binds only to `127.0.0.1` and requires a per-launch token. Configuration
writes use staging, verification and recovery copies. Administrator actions use
a short-lived, validated helper request. Restart replaces verified Bravado
controllers rather than terminating unrelated Python processes.

Separation changes the front stereo field; Room adds short static reflections.
Aligned double adds 6.02 dB. Bass double mixes a 120 Hz low-pass copy, with an
optional 0–10 ms delay. A delayed copy can cancel bass. All factory presets keep
these effects off so their tonal balance also translates to mono. Factory curves,
export parity and filter stability are covered by the embedded tests.
