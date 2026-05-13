# Spike-1 install-probe wrap script.
#
# Why this exists:
#   colbert-ai's Checkpoint init JIT-compiles a C++ extension (segmented_maxsim_cpp)
#   at load time, requiring ninja + MSVC. Standard PowerShell sessions do NOT have
#   cl.exe on PATH even when VS Build Tools / VS Pro is installed; you have to
#   source vcvarsall.bat first. This wrap does that automatically per-invocation
#   so spike runners don't have to remember to launch from "x64 Native Tools
#   Command Prompt for VS 2022" every time.
#
# Usage (from spike/pre-m1-retrieval/):
#   .\run-probe.ps1
#
# Prerequisites:
#   - Visual Studio (any edition) or VS Build Tools, with the
#     "Desktop development with C++" workload installed.
#   - Spike venv created + dependencies installed:
#       python -m venv .venv
#       .\.venv\Scripts\python.exe -m pip install --only-binary :all: -r requirements.txt
#
# Per docs/decisions/colbert-wrapper-revision.md the locked stack uses colbert-ai
# direct (not RAGatouille). The C++ extension load is intrinsic to colbert-ai
# 0.2.22's Checkpoint class -- not a workaround we can route around in user code.

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Locate vswhere.exe (ships with the VS Installer; present on any host that
#    has any VS product installed via the standard channel).
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    Write-Error "vswhere.exe not found at $vswhere. Install Visual Studio (any edition) or VS Build Tools 2022 with the 'Desktop development with C++' workload."
    exit 2
}

# 2. Find the LATEST VS install with the VC++ tools workload component.
#    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 ensures cl.exe is present.
$vsInstallPath = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsInstallPath) {
    Write-Error "No VS install with the VC.Tools.x86.x64 component found. Install the 'Desktop development with C++' workload via the VS Installer."
    exit 2
}
Write-Host "[run-probe] Using VS install: $vsInstallPath"

$vcvars = Join-Path $vsInstallPath 'VC\Auxiliary\Build\vcvarsall.bat'
if (-not (Test-Path $vcvars)) {
    Write-Error "vcvarsall.bat not found at $vcvars. The VS install at $vsInstallPath may be corrupt."
    exit 2
}

# 3. Source vcvarsall.bat amd64 env into current session by spawning cmd, running
#    vcvarsall, then dumping its env via `set`. Filter the output for env-var
#    assignments and apply them to PowerShell's process env.
Write-Host "[run-probe] Sourcing vcvarsall.bat amd64..."
$envSnapshot = & cmd.exe /c "`"$vcvars`" amd64 && set"
$applied = 0
foreach ($line in $envSnapshot) {
    # Match standard env-var assignment lines; banner lines don't match.
    if ($line -match '^([A-Za-z_][A-Za-z0-9_()]*?)=(.*)$') {
        Set-Item -Path "env:$($matches[1])" -Value $matches[2] -Force
        $applied++
    }
}
Write-Host "[run-probe] Applied $applied env-var assignments from vcvarsall."

# 4. Prepend the spike venv's Scripts dir to PATH so ninja.exe is findable
#    (it's installed in the venv but not on the system PATH).
$venvScripts = Join-Path $here '.venv\Scripts'
if (-not (Test-Path $venvScripts)) {
    Write-Error "Spike venv not found at $venvScripts. Create it first: python -m venv .venv && .\.venv\Scripts\python.exe -m pip install --only-binary :all: -r requirements.txt"
    exit 2
}
$env:PATH = "$venvScripts;$env:PATH"

# 5. Run the install probe.
$python = Join-Path $venvScripts 'python.exe'
$probe = Join-Path $here 'install_probe.py'
Write-Host "[run-probe] Invoking: $python $probe"
& $python $probe
exit $LASTEXITCODE
