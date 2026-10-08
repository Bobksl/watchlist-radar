param([ValidateSet('Register','Status','Run','Remove','DryRun')][string]$Action = 'Status',
      [string]$Python = 'C:\Python314\python.exe')
$ErrorActionPreference = 'Stop'
$taskName = 'Watchlist Radar Daily'
$daily = Join-Path $PSScriptRoot 'daily.py'
if ($Action -eq 'DryRun') { & $Python -B $daily --dry-run; exit $LASTEXITCODE }
if ($Action -eq 'Register') {
    if (!(Test-Path -LiteralPath $Python)) { throw 'Python executable missing' }
    & $Python -B $daily --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Calendar preflight failed' }
    # Current interactive user: OpenD and local Git credentials belong to that session.
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $scanAction = New-ScheduledTaskAction -Execute $Python -Argument ('-B "' + $daily + '"') -WorkingDirectory $PSScriptRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 15)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $taskName -Action $scanAction -Trigger $trigger -Settings $settings -Principal $principal -Description 'Check every 15 min; one scan at/after 10:00 ET per NYSE session, automatic public artifact push.'
}
if ($Action -eq 'Run') { Start-ScheduledTask -TaskName $taskName }
if ($Action -eq 'Remove') { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
if ($Action -in @('Register','Status','Run')) {
    Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, Actions, Triggers
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime, LastTaskResult, NextRunTime
}
