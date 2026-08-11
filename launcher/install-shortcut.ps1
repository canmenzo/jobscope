<#
Creates two shortcuts on the Desktop and in the Start Menu:
  Job Scope        - runs a fresh hunt (~20s of fetching), then opens it
  Job Scope (Open) - just rebuilds and opens the last result, no network

    powershell -ExecutionPolicy Bypass -File launcher\install-shortcut.ps1

The shortcut targets cmd.exe rather than the .bat directly, because Windows
only offers "Pin to taskbar" for shortcuts whose target is an executable.
#>
$launcher = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $launcher
$shortcuts = @(
    @{ Name = 'Job Scope'; Bat = 'run-jobscope.bat'; Icon = 'jobscope.ico'
       Desc = 'Run a fresh job hunt and open the dashboard' },
    @{ Name = 'Job Scope (Open)'; Bat = 'open-dashboard.bat'; Icon = 'jobscope-open.ico'
       Desc = 'Open the last dashboard without fetching anything' }
)
foreach ($s in $shortcuts) {
    foreach ($f in @((Join-Path $launcher $s.Bat), (Join-Path $launcher $s.Icon))) {
        if (-not (Test-Path $f)) { throw "missing: $f (run make_icon.py first?)" }
    }
}

$targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('Programs')) 'Job Scope')
)

$shell = New-Object -ComObject WScript.Shell
foreach ($dir in $targets) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    foreach ($s in $shortcuts) {
        $lnk = $shell.CreateShortcut((Join-Path $dir "$($s.Name).lnk"))
        $lnk.TargetPath = "$env:SystemRoot\System32\cmd.exe"
        $lnk.Arguments = "/c `"`"$(Join-Path $launcher $s.Bat)`"`""
        $lnk.WorkingDirectory = $root
        $lnk.IconLocation = "$(Join-Path $launcher $s.Icon),0"
        $lnk.Description = $s.Desc
        $lnk.WindowStyle = 1
        $lnk.Save()
        Write-Host "created $(Join-Path $dir "$($s.Name).lnk")"
    }
}
