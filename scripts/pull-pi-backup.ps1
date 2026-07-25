# Pull Stock FIFO backups from the Raspberry Pi to this laptop.
# Runs unattended from Task Scheduler. Safe to run when the Pi is unreachable.
#
# Requires an SSH host alias named 'pi-stockfifo' in %USERPROFILE%\.ssh\config
# pointing at the Pi with a passwordless key.

$ErrorActionPreference = "Stop"

$Dest     = "D:\Backups\stock-fifo"
$LogFile  = "D:\Backups\stock-fifo-pull.log"
$KeepDays = 60

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Reachability check first, so an unreachable Pi logs one clear line
# instead of a wall of scp errors. BatchMode=yes guarantees the scheduled
# task can never block on a password prompt.
ssh -o ConnectTimeout=10 -o BatchMode=yes pi-stockfifo "exit" 2>$null
if (-not $?) {
    Write-Log "SKIP: Pi not reachable"
    exit 0
}

scp -q -o BatchMode=yes "pi-stockfifo:/home/minotaur/backups/*" $Dest
if ($?) {
    $count = (Get-ChildItem $Dest -File -Filter "db_*.sqlite3" | Measure-Object).Count
    Write-Log "OK: pulled backups, $count db snapshots now held locally"
} else {
    Write-Log "FAIL: scp returned an error"
    exit 1
}

# Prune copies older than the retention window.
$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem $Dest -File | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
    Remove-Item $_.FullName -Force
    Write-Log "pruned: $($_.Name)"
}
