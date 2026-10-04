# Dependencies

**[Run Bravado](README.md#run) · [Build](README.md#build) · [Full licence notices](THIRD_PARTY_NOTICES.txt)**

## Install only what is missing

| Requirement | Release user action | Official source |
| --- | --- | --- |
| Windows x64 | Use a supported Windows installation | [Windows](https://www.microsoft.com/windows) |
| Equalizer APO | Install, select the playback device, follow restart instructions | [Download](https://sourceforge.net/projects/equalizerapo/) · [Setup](https://sourceforge.net/p/equalizerapo/wiki/Documentation/) |
| Microsoft Edge WebView2 Runtime | Usually already present; install Evergreen x64 if missing | [Runtime download](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) · [Distribution guide](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution) |
| .NET Framework 4.6.2 or later | Usually already present; use a supported release for your Windows version | [Microsoft download](https://dotnet.microsoft.com/en-us/download/dotnet-framework) |
| Python and Python packages | **Do not install for the portable release.** Bundled in `_internal` | Build inventory below |

Bravado checks its desktop runtimes before opening the panel. It does not install
drivers or runtimes automatically. APO is separate; without it, preview and export
still work. Peace is not a dependency.

## Build inventory

Use [CPython 3.12 x64](https://www.python.org/downloads/windows/), then run
`build_exe.cmd`. All Python package versions are pinned in
[requirements-build.txt](requirements-build.txt). Links below lead to their exact
PyPI releases. No Node.js, npm, Electron, Qt or C++ compiler is required.

| Package | Version / official package | Role |
| --- | --- | --- |
| NumPy | [2.3.5](https://pypi.org/project/numpy/2.3.5/) | Filter calculations, response plots, impulse generation |
| pywebview | [6.2.1](https://pypi.org/project/pywebview/6.2.1/) | Native desktop window and WebView2 host |
| pythonnet | [3.2.0](https://pypi.org/project/pythonnet/3.2.0/) | Windows .NET bridge |
| clr_loader | [0.3.1](https://pypi.org/project/clr_loader/0.3.1/) | .NET runtime loading |
| cffi | [2.1.1](https://pypi.org/project/cffi/2.1.1/) | Foreign-function support |
| pycparser | [3.0](https://pypi.org/project/pycparser/3.0/) | CFFI dependency |
| proxy_tools | [0.1.0](https://pypi.org/project/proxy_tools/0.1.0/) | pywebview dependency |
| bottle | [0.13.4](https://pypi.org/project/bottle/0.13.4/) | pywebview dependency; Bravado's API uses the standard library |
| typing_extensions | [4.16.0](https://pypi.org/project/typing_extensions/4.16.0/) | Compatibility types |
| PyInstaller | [6.22.3](https://pypi.org/project/pyinstaller/6.22.3/) | Builds the portable executable |
| pyinstaller-hooks-contrib | [2026.8](https://pypi.org/project/pyinstaller-hooks-contrib/2026.8/) | Dependency collection rules |
| altgraph | [0.17.5](https://pypi.org/project/altgraph/0.17.5/) | Build dependency analysis |
| packaging | [26.3](https://pypi.org/project/packaging/26.3/) | Package/version metadata |
| pefile | [2024.8.26](https://pypi.org/project/pefile/2024.8.26/) | Windows executable inspection |
| pywin32-ctypes | [0.2.3](https://pypi.org/project/pywin32-ctypes/0.2.3/) | Build-time Windows bindings |
| setuptools | [84.0.0](https://pypi.org/project/setuptools/84.0.0/) | Build tooling |

The prepared release uses CPython 3.12.14. The build accepts CPython 3.12 x64;
choosing another patch release changes the bundled interpreter. Diagnostics show
the actual runtime and module paths. Consult [Python's licence](https://docs.python.org/3/license.html).

## What ships and why

The portable folder includes Python, the required NumPy libraries and the desktop
host dependency closure. pywebview supplies the
[Microsoft.Web.WebView2 SDK 1.0.3856.49](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49)
host assemblies and loader. These are distinct from the **installed WebView2 Runtime**;
the browser engine is not duplicated in the ZIP. See the [SDK licence](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49/License).

NumPy's wheel includes additional numerical/runtime components covered by its
bundled notices. PyInstaller's bootloader uses its
[distribution exception](https://pyinstaller.org/en/stable/license.html), allowing
the packaged application to keep its own licence. Equalizer APO is not bundled,
linked into Bravado or relicensed; Bravado writes its documented configuration format.

[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) preserves the applicable texts,
including CPython, NumPy's bundled components and the desktop host. These grants
remain separate from Bravado's [PolyForm licence](LICENSE). `proxy_tools` has
inconsistent metadata: its package claims MIT while its
[upstream licence](https://github.com/jtushman/proxy_tools/blob/master/LICENSE.txt)
is BSD; the upstream notice is retained. When upgrading a package, update the
pin, inspect its bundled licence files, refresh notices, rebuild and rerun tests.

## Release check

Run the packaged `--self-test` and `--diagnose` commands from [README](README.md#build).
Move the complete folder to another path and repeat. For a public release,
also test on a clean supported Windows machine with the prerequisites above.
Do not package your `bravado-data` folder. Keep the dependency notices, licence,
README, this guide, preset guide and `requirements-build.txt` in the distribution.
