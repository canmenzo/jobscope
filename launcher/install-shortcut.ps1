<#
Creates the "Job Scope" shortcut on the Desktop and in the Start Menu.
Clicking it runs a fresh hunt and opens the dashboard in the browser.

    powershell -ExecutionPolicy Bypass -File launcher\install-shortcut.ps1

The shortcut targets cmd.exe rather than the .bat directly, because Windows
only offers "Pin to taskbar" for shortcuts whose target is an executable.
#>
$launcher = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $launcher
$bat = Join-Path $launcher 'run-jobscope.bat'
$icon = Join-Path $launcher 'jobscope.ico'

foreach ($f in @($bat, $icon)) {
    if (-not (Test-Path $f)) { throw "missing: $f (run make_icon.py first?)" }
}

$targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'Job Scope')
)

$shell = New-Object -ComObject WScript.Shell
foreach ($dir in $targets) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $lnk = $shell.CreateShortcut((Join-Path $dir 'Job Scope.lnk'))
    $lnk.TargetPath = "$env:SystemRoot\System32\cmd.exe"
    $lnk.Arguments = "/c `"`"$bat`"`""
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = "$icon,0"
    $lnk.Description = 'Run a fresh job hunt and open the dashboard'
    $lnk.WindowStyle = 1
    $lnk.Save()
    Write-Host "created $(Join-Path $dir 'Job Scope.lnk')"
}
