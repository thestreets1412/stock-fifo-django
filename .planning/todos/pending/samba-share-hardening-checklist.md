# Samba share hardening checklist

---
title: Harden the Samba NAS share before exposing it on the home LAN
date: 2026-07-27
priority: high
blocks: NAS setup on the Pi
---

Do every item below when the Samba share is set up. The share sits on the same exFAT
filesystem as the FIFO ledger backups, and exFAT gives no filesystem-level permission
backstop — Samba config is the only wall. Context: [[nas-samba-on-backup-drive]].

## Must not skip

- [ ] **Keep `[homes]` disabled in `/etc/samba/smb.conf`.**
      Most Samba tutorials tell you to uncomment it. Do not. `[homes]` auto-shares
      `/home/minotaur`, which contains the live `stock-fifo-django/db.sqlite3` that
      gunicorn is writing to, and `/home/minotaur/backups/` (14 days of ledger snapshots).
      Debian ships it commented out — leave it that way.
      Verify: `testparm -s` must show no `[homes]` section.

- [ ] **Never point any share at `/mnt/backup` or `/home/minotaur`.**
      Only `/mnt/backup/nas`. A client browsing the parent would see every backup copy.

- [ ] **`guest ok = no` and `map to guest = never`.**
      Guest-writable would let any device on the WiFi — including a compromised IoT
      device — read and delete files. Windows 11 24H2 refuses guest SMB shares anyway,
      so an authenticated user is required regardless.

- [ ] **Create `/mnt/backup/nas` only while the drive is mounted.**
      If the directory is created while the drive is unplugged, it lands on the SD card
      and Samba will happily fill the SD card until the app dies. This is the same trap
      `backup.sh:51` guards against with `mountpoint -q`.
      ```bash
      mountpoint -q /mnt/backup && mkdir -p /mnt/backup/nas && echo OK
      ```

- [ ] **`server min protocol = SMB3`.** Never enable SMB1.

- [ ] **`hosts allow` scoped to the home subnet.**
      Confirm the actual subnet first with `ip -4 addr show` — see
      [[nas-space-budget-question]].

- [ ] **Dedicated Samba account, not the Linux login name.**
      `sudo smbpasswd -a nasuser` plus `force user = minotaur` in the share (only uid 1000
      can write to the exFAT mount). Samba passwords are stored separately from Unix
      passwords, so this is a distinct credential.

## Strongly recommended

- [ ] **Enable the recycle VFS module.** Deleting over SMB is permanent — one bad
      drag-and-drop in Explorer and the file is gone with no undo.
      ```ini
      vfs objects = recycle
      recycle:repository = .recycle
      recycle:keeptree = yes
      recycle:versions = yes
      ```

- [ ] **Disable printer sharing** — `load printers = no`, `printcap name = /dev/null`,
      `disable spoolss = yes`. Not used, removes surface.

- [ ] **Confirm the `nofail` mount survives.** The existing fstab line already carries
      `nofail,x-systemd.device-timeout=5`. Adding Samba must not change it — without
      `nofail` a boot with the drive missing drops to emergency mode and takes the web
      app and tunnel offline, breaking the "reachable at all times" milestone goal.

## Verify after setup

- [ ] `testparm -s` clean, no `[homes]`, no unexpected shares
- [ ] `\\stockfifo.local\nas` mounts from Win10 and from Win11
- [ ] `\\stockfifo.local\stock-fifo` and `\\stockfifo.local\minotaur` both fail
- [ ] Reboot the Pi, confirm the app and tunnel still come up and the share reconnects
- [ ] Unplug the drive, confirm the Pi still boots and Samba refuses the share rather
      than writing to the SD card

## Order of work

Run Task 4 (restore drill) of
`docs/superpowers/plans/2026-07-25-automated-backup-usb-and-laptop-pull.md` first.
Proving a laptop copy restores cleanly means a NAS misstep on this drive is recoverable.
