# Plane demo for Joey (2026-10-05). Run from the repo root in PowerShell:  .\tools\demo_planes.ps1
# Plays the warp-corrected and plain plane animations at 60 fps, 20 s each, blue only (LED currents untouched).
# Stop the whole demo at once: create STOPALL, then STOP, in the repo root
#   (New-Item STOPALL; New-Item STOP). STOPALL alone stops after the current scene; STOP alone ends only it.
# A scene that fails (rig busy: another program holds the rig lock) ends the demo.
$py = "python"
Set-Location (Split-Path $PSScriptRoot -Parent)   # repo root
foreach ($s in "fwc_static", "fwc_scan", "fwc_stack", "fwc_split", "fwc_rock", "fwc_ripple", "fw_rain", "fw_ribbon", "fw_breathe", "ribbon") {
    if (Test-Path STOPALL) { "stopped (STOPALL)"; break }
    "== $s"
    & $py -m vol2.volplay $s --seconds 20 2>&1 | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { "stopped: $s exited with $LASTEXITCODE (rig busy?)"; break }
}
