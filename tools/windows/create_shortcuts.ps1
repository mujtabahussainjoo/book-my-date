$ErrorActionPreference = "Stop"

$root = (Get-Item (Join-Path $PSScriptRoot "..\..")).FullName
$launcher = Join-Path $root "launcher.py"
$icon = Join-Path $root "book_my_date\assets\app.ico"

$python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $pythonPath = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $pythonPath) {
        $py = (Get-Command py.exe -ErrorAction SilentlyContinue).Source
        if ($py) {
            $pythonPath = (& $py -3 -c "import sys; print(sys.executable)").Trim()
        }
    }
    if ($pythonPath) {
        $candidate = Join-Path (Split-Path $pythonPath) "pythonw.exe"
        $python = if (Test-Path $candidate) { $candidate } else { $pythonPath }
    }
}
if (-not $python) {
    throw "Python was not found. Install Python 3.9 or newer, then run this script again."
}

$consolePython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $consolePython) {
    $py = (Get-Command py.exe -ErrorAction SilentlyContinue).Source
    if ($py) {
        $consolePython = (& $py -3 -c "import sys; print(sys.executable)").Trim()
    }
}
if (-not $consolePython) {
    throw "python.exe was not found. Install Python 3.9 or newer, then run this script again."
}

$shell = New-Object -ComObject WScript.Shell
$shortcuts = @(
    @{
        Name = "Start Book My Date"
        Arguments = "`"$launcher`""
        Description = "Open Book My Date"
    },
    @{
        Name = "Setup Book My Date"
        Arguments = "`"$launcher`" --setup"
        Description = "Set up or repair Book My Date"
    },
    @{
        Name = "Uninstall Book My Date"
        Arguments = "`"$root\uninstaller\uninstall.py`" --all --purge --yes --force"
        Description = "Remove Book My Date from this computer"
        Console = $true
    }
)

foreach ($item in $shortcuts) {
    $path = Join-Path $root ($item.Name + ".lnk")
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = if ($item.Console) { $consolePython } else { $python }
    $shortcut.Arguments = $item.Arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Description = $item.Description
    $shortcut.Save()
    Write-Output $path
}
