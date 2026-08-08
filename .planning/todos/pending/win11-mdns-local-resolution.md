---
title: Fix .local (mDNS) name resolution on the Win11 laptop
date: 2026-07-27
priority: low
---

`\\stockfifo.local\nas` resolves and connects fine from the Win10 laptop, but fails on
Win11 with `DNS name does not exist`. `\\10.15.30.131\nas` works on both. Not blocking —
both laptops already exchange files correctly via the IP-based `Z:` mapping.

Likely cause: `.local` resolution depends on mDNS (multicast), which Windows suppresses
when the network connection profile is `Public` instead of `Private` — IP-based SMB
still works because it's plain unicast and needs no discovery step.

Check and, if the home WiFi is misclassified, fix:

```powershell
Get-NetConnectionProfile
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```

Then retry `\\stockfifo.local\nas` from the Win11 machine.

Trade-off of leaving this unfixed: the IP-based `Z:` mapping breaks if the Pi's DHCP
lease changes. `.local` would survive that. Low urgency since the lease has been stable
so far — see [[nas-samba-on-backup-drive]].

## Update 2026-08-08

Lower priority still. The app moved to `https://fifo-by-minotaur.uk` and no
longer depends on `.local` resolution at all. This todo now only affects
reaching the Samba share by name — `\\10.15.30.131\nas` remains the reliable
route on the Win11 machine.
