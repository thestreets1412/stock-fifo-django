# NAS (Samba) on the existing backup drive

---
title: NAS (Samba) share alongside backups on the single USB drive
date: 2026-07-27
context: /gsd-explore — feasibility of adding a Samba file share to the Pi without a second drive
status: exploration only, nothing implemented
---

## Goal

Two home laptops (Win10 + Win11) need a shared folder for documents (PDF, Excel, images)
so files stop moving by flash drive. Reachable as `\\stockfifo.local\nas` over the home
WiFi. Light use — not a media library.

## Decision: folder split, not repartition

One drive only. Split by directory, share only the NAS subfolder.

```
/mnt/backup/              mount point (exFAT, label STOCKFIFO, 29G)
├── stock-fifo/           backup.sh rsync target — NEVER shared
└── nas/                  the only exported path
```

No reformat, no repartition, no change to `backup.sh`. The `stock-fifo` folder name stays
as-is (rejected renaming it to `STOCKFIFO_BackUp` — `backup.sh:12` hardcodes
`USB_DIR="$USB_MOUNT/stock-fifo"` and renaming would strand existing copies).

## Verified facts from the live Pi (2026-07-27)

```
$ mount | grep /mnt/backup
/dev/sda1 on /mnt/backup type exfat (rw,relatime,uid=1000,gid=1000,fmask=0022,dmask=0022,iocharset=utf8,errors=remount-ro)

$ df -h /mnt/backup
/dev/sda1        29G   12M   29G   1% /mnt/backup
```

- `type exfat` — kernel driver, not `fuseblk`. No single-threaded FUSE CPU tax on transfers.
- `uid=1000,gid=1000` — whole filesystem owned by `minotaur`.
- `fmask=0022,dmask=0022` — files 644, dirs 755. Only uid 1000 writes.
- 29G total, 1% used. Space is not a constraint for documents.

**Open flag:** 12M used suggests the USB mirror has barely run. Task 2 Step 8 of the backup
plan (`docs/superpowers/plans/2026-07-25-automated-backup-usb-and-laptop-pull.md`) expects
`/mnt/backup/stock-fifo/` to hold `db_*.sqlite3` and `media_*.tar.gz`. Verify with
`ls -la /mnt/backup/stock-fifo/` before assuming the 60-day tier is live.

## Why the shared-drive risk is lower than first assessed

`backup.sh` writes three tiers, and USB is the second, not the only one:

| Tier | Location | Retention | Survives |
|---|---|---|---|
| 1 | `/home/minotaur/backups` (SD card) | 14 days | USB loss |
| 2 | `/mnt/backup/stock-fifo` (USB) | 60 days | SD card failure |
| 3 | Laptop via `pull-pi-backup.ps1` | — | Pi loss |

The snapshot is *created* on the SD card and mirrored outward. So exFAT corruption on the
USB drive is recoverable from tier 1 and tier 3. That is what makes sharing one drive
acceptable here.

## Permission model

exFAT stores no Unix permissions — the whole filesystem gets one uid/gid/umask from fstab.
`chmod` on a subdirectory does nothing. **The only wall between the NAS share and the
backup folder is the Samba `path =` directive.** There is no filesystem-level backstop.

Consequence: a dedicated Samba account with `force user = minotaur` is needed, since only
uid 1000 can write. Using a Samba username different from the Linux login means the
credential cached in Windows Credential Manager on two laptops is not the Pi's SSH account
name.

## Residual risks accepted

- **No journaling.** Power loss mid-write can damage the exFAT directory table for the
  whole filesystem, including `stock-fifo/`. Mitigated by tiers 1 and 3.
- **No per-directory quota.** NAS files and backups share 29G. At document scale this is
  not close to binding — see [[nas-space-budget-question]].
- **Shared fate on drive failure.** One physical disk. Same mitigation as above.

## Rejected alternatives

- **Second USB drive** — cleanest isolation, but user has one drive and light needs.
- **Two partitions (exFAT backup + ext4 NAS)** — real per-partition permissions and
  journaling for the NAS half, but requires repartitioning a drive that already holds
  backups. Not worth it at this scale.
- **Exposing the share through Cloudflare Tunnel** — rejected outright. SMB over the
  internet is a known ransomware vector and the tunnel is HTTP-oriented. LAN only.

## Related

- [[samba-share-hardening-checklist]] — the security items that must be done at setup time
- Backup plan: `docs/superpowers/plans/2026-07-25-automated-backup-usb-and-laptop-pull.md`
- Restore drill (Task 4 of that plan) should pass before any work touches this drive
