param([switch]$Unregister)

$ProjectRoot  = "D:\Application\Claude\shorts_auto"
$PythonExe    = "$ProjectRoot\.venv\Scripts\python.exe"
$TaskBaseName = "ShortsAuto"
$ScheduleTimes = @("09:00", "15:00", "21:00")

if ($Unregister) {
    foreach ($t in $ScheduleTimes) {
        $name = "${TaskBaseName}_$($t -replace ':','')"
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "[OK] Removed: $name"
        } else {
            Write-Host "[SKIP] Not found: $name"
        }
    }
    exit 0
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python venv not found: $PythonExe"
    exit 1
}

$LogDir = "$ProjectRoot\logs\scheduler"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

foreach ($schedTime in $ScheduleTimes) {
    $name    = "${TaskBaseName}_$($schedTime -replace ':','')"
    $logFile = "$LogDir\${name}.log"
    $parts   = $schedTime -split ":"
    $hour    = $parts[0]
    $min     = $parts[1]

    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
    }

    $action = New-ScheduledTaskAction `
        -Execute "$ProjectRoot\scripts\run_pipeline.bat" `
        -WorkingDirectory $ProjectRoot

    $trigger = New-ScheduledTaskTrigger -Daily -At "${hour}:${min}"

    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -WakeToRun:$false

    $principal = New-ScheduledTaskPrincipal `
        -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType Interactive `
        -RunLevel Limited

    $regParams = @{
        TaskName    = $name
        Action      = $action
        Trigger     = $trigger
        Settings    = $settings
        Principal   = $principal
        Description = "Shorts Auto Pipeline - $schedTime KST (FR-7)"
        Force       = $true
    }
    Register-ScheduledTask @regParams | Out-Null

    Write-Host "[OK] Registered: $name  ($schedTime KST)"
}

Write-Host ""
Write-Host "Registered tasks:"
Get-ScheduledTask -TaskName "${TaskBaseName}_*" | Format-Table TaskName, State -AutoSize

Write-Host "Log dir: $LogDir"
Write-Host ""
Write-Host "Manual test run:"
Write-Host "  Start-ScheduledTask -TaskName ShortsAuto_0900"
Write-Host ""
Write-Host "Remove all:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\register_scheduler.ps1 -Unregister"
