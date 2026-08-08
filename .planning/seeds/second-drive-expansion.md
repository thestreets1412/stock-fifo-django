---
title: Adding a second drive (SSD or flash) for NAS storage
trigger_condition: An SSD module or additional USB flash drive is acquired for the Pi
planted_date: 2026-07-27
---

# Second drive expansion

Captured from a `/gsd-explore` question after the single-drive NAS share went live.
Nothing here is implemented. Context: [[nas-samba-on-backup-drive]].

## The core decision: separate mount point, not a folder

Use `/mnt/nas` as its own mount point. Do **not** create `/mnt/backup/nas2`.

The folder-split approach on the existing drive was forced by having only one disk. It
came with four accepted costs — no journaling, no per-directory quota, shared fate on
disk failure, and Samba's `path =` as the only permission wall. A second physical drive
removes all four for free. Putting `nas2` back inside `/mnt/backup` would pay those costs
for nothing.

`nas2` is fine as a *share name*. It is the on-disk location that must be separate.

## The trap that destroys data: `/dev/sdX` is not stable

Plugging in a second drive can make the kernel enumerate it as `sda`, pushing the
existing `STOCKFIFO` drive to `sdb`. Enumeration order depends on probe timing and is not
deterministic.

Always identify by LABEL/UUID before touching anything:

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT
```

Confirm the target is **not** labelled `STOCKFIFO` before any `mkfs`. A wrong `mkfs`
permanently erases the 60-day backup tier.

Verify the existing fstab entry is UUID-based (it should be, per the backup plan) so the
existing mount survives reordering:

```bash
grep backup /etc/fstab
```

## Steps for a new drive

1. **Format ext4, not exFAT.** Real per-directory permissions (so Samba's `path =` stops
   being the only wall), journaling that survives power loss, and no Windows
   `System Volume Information` folder. The cost — Windows can't read it when plugged in
   directly — doesn't matter for a drive accessed over SMB. The backup drive stays exFAT
   deliberately, for emergency recovery on a Windows machine.

2. **fstab by UUID with `nofail`:**

   ```
   UUID=<new-uuid>  /mnt/nas  ext4  defaults,nofail,x-systemd.device-timeout=5  0  2
   ```

   `nofail` is not optional — without it a boot with the drive missing drops to emergency
   mode and takes the web app offline.

3. **Create the directory only while mounted:**

   ```bash
   mountpoint -q /mnt/nas && mkdir -p /mnt/nas/shared && echo OK
   ```

4. **Append a section to `deploy/samba/nas-share.conf`.** This is the payoff of the
   config-as-code choice: the file is already `include`d wholesale, so a new share is an
   append plus `git pull` and `systemctl restart smbd`. `/etc/samba/smb.conf` is never
   touched again.

   ```ini
   [nas2]
      comment = SSD storage
      path = /mnt/nas/shared
      browseable = yes
      read only = no
      guest ok = no
      valid users = nasuser
      force user = minotaur
      force group = minotaur
      vfs objects = recycle
      recycle:repository = .recycle
      recycle:keeptree = yes
   ```

   `valid users` and `guest ok` are share-level and must be repeated per section.
   `hosts allow`, `interfaces`, and `server min protocol` live in `[global]` and are
   inherited.

5. **Add a retention line to `/etc/tmpfiles.d/nas-recycle.conf`** for the new `.recycle`.

## SSD-specific concerns

- **Power.** The Pi 4's total USB budget is around 1.2 A; an SSD can spike to ~0.9 A on
  spin-up. With the existing flash drive also attached this may exceed budget. The
  symptom is the drive silently dropping off the bus, not a clean error. Fix is a powered
  USB hub.
- **No native M.2.** The Pi 4 needs a USB3 enclosure.
- **UASP quirks.** Some JMicron/ASMedia USB3-SATA bridges hang and reset repeatedly on
  the Pi. If that happens, find the vendor:product id in `dmesg | grep -i usb` and add
  `usb-storage.quirks=<vid:pid>:u` as a kernel parameter. Recent enclosures mostly avoid
  this.

## Decide what the SSD is actually for

Three different projects, not one:

| Purpose | Payoff | Effort |
|---|---|---|
| More NAS space | More/faster shared storage | Easy — the 5 steps above |
| Move backup tier 2 to SSD | More durable than flash, which wears from repeated writes | Medium — change `USB_MOUNT` in `scripts/backup.sh` |
| Move OS + DB off the SD card | Removes the Pi's single most common failure mode | Hard — its own milestone |

The third is the most valuable long-term. SD cards wear from writes, and the current
workload is exactly the profile that kills them: gunicorn writing `db.sqlite3`
continuously plus a nightly snapshot into `/home/minotaur/backups`. The Pi 4 has
supported USB boot since the 2020 firmware.

## Invariants that hold for any new drive

1. `lsblk` and check LABEL/UUID before any `mkfs`
2. fstab by UUID with `nofail` — always
3. `mkdir` only behind a `mountpoint -q` guard
4. Shares point at a subdirectory, never at a mount point root
5. `testparm -s` must show only the intended shares

## Related

- [[nas-samba-on-backup-drive]] — why the single-drive folder split was chosen
- [[samba-share-hardening-checklist]] — security items that apply to any new share
- [[win11-mdns-local-resolution]] — unresolved client-side issue, unaffected by this
