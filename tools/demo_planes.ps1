# Plane demo for Joey (2026-10-05). Run from the repo root in PowerShell:  .\tools\demo_planes.ps1
# Plays the warp-corrected and plain plane animations at 60 fps, 20 s each, blue only (LED currents untouched).
# Stop the whole demo: create a file named STOPALL in this folder (stops after the current scene),
# or a file named STOP (ends the current scene at once).
$py = "python"
Set-Location (Split-Path $PSScriptRoot -Parent)   # repo root
foreach ($s in "fwc_static", "fwc_scan", "fwc_stack", "fwc_split", "fwc_rock", "fwc_ripple", "fw_rain", "fw_ribbon", "fw_breathe", "ribbon") {
    if (Test-Path STOPALL) { "stopped (STOPALL)"; break }
    "== $s"
    & $py -m vol2.volplay $s --seconds 20 2>&1 | Select-Object -Last 1
}
