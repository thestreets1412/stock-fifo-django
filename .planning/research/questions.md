# Open research questions

## NAS on the backup drive — remaining unknowns

_Raised 2026-07-27 during `/gsd-explore`. Context: [[nas-samba-on-backup-drive]]._

### 1. What is the home LAN subnet?

Needed to write `hosts allow` in the Samba share. Guessing `192.168.1.0/24` is wrong often
enough to lock the user out of their own share.

```bash
ip -4 addr show
```

Take the subnet from the `wlan0` (or `eth0`) inet line.

**Status:** open.

### 2. Is the USB backup tier actually populated?

`df -h /mnt/backup` reports 12M used on a 29G drive. That is close to empty, which is
inconsistent with a 60-day mirror having been running. Either the mirror has only run a
handful of times, or Task 2 Step 8 of the backup plan was never executed.

```bash
ls -la /mnt/backup/stock-fifo/
systemctl list-timers | grep -i backup
```

Matters because the NAS risk assessment leans on the USB tier being a real second copy.
If it is empty, the drive currently holds nothing worth protecting — which makes the NAS
work *safer* to do now, but means the backup system is not yet proven.

**Status:** open.

### 3. Space budget — how fast does the backup tier grow?

29G shared between backups and NAS files. Documents will not fill it, but the growth rate
of the 60-day tier is unmeasured. Size of one `db_*.sqlite3` snapshot plus one
`media_*.tar.gz`, times 60, gives the steady-state floor.

```bash
du -sh /home/minotaur/backups/*
```

Only becomes a real constraint if evidence-photo uploads grow a lot. exFAT supports no
per-directory quota, so the only lever is `max disk size` in the Samba share or discipline
about what goes in the NAS folder.

**Status:** open, low urgency.
