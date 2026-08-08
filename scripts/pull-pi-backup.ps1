# Pull Stock FIFO backups from the Raspberry Pi to this laptop.
# Runs unattended from Task Scheduler. Safe to run when the Pi is unreachable.
#
# Requires SSH host aliases in %USERPROFILE%\.ssh\config pointing at the Pi
# with a passwordless key.
#
# Two aliases are tried in order because neither route is reliable alone:
# mDNS (.local) breaks on mobile hotspots that limit multicast, and the raw
# IP breaks whenever DHCP hands out a new lease. Trying both means only one
# has to work on any given night.

$Hosts    = @("pi-stockfifo", "pi-stockfifo-ip")
$Dest     = "D:\Backups\stock-fifo"
$LogFile  = "D:\Backups\stock-fifo-pull.log"
$KeepDays = 60

# NOTE: $ErrorActionPreference stays at its default here on purpose.
# Under "Stop", Windows PowerShell 5.1 turns any stderr line written by a
# native exe into a terminating NativeCommandError -- so a single failed ssh
# probe would kill the script before the second host was ever tried.
# Native command success is therefore checked via $LASTEXITCODE, not $?.

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Test-PiHost($sshHost) {
    ssh -o ConnectTimeout=10 -o BatchMode=yes $sshHost "exit" 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Find a route that answers, so an unreachable Pi logs one clear line
# instead of a wall of scp errors. BatchMode=yes guarantees the scheduled
# task can never block on a password prompt.
$Reachable = $null
foreach ($h in $Hosts) {
    if (Test-PiHost $h) { $Reachable = $h; break }
}

if (-not $Reachable) {
    Write-Log "SKIP: Pi not reachable via $($Hosts -join ', ')"
    exit 0
}

scp -q -o BatchMode=yes "${Reachable}:/home/minotaur/backups/*" $Dest 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    $count = (Get-ChildItem $Dest -File -Filter "db_*.sqlite3" | Measure-Object).Count
    Write-Log "OK: pulled via $Reachable, $count db snapshots now held locally"
} else {
    Write-Log "FAIL: scp via $Reachable exited $LASTEXITCODE"
    exit 1
}

# Prune copies older than the retention window.
$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem $Dest -File | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
    Remove-Item $_.FullName -Force
    Write-Log "pruned: $($_.Name)"
}
