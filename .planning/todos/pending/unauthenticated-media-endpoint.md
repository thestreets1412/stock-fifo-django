---
title: /media/ is served without an authentication check
date: 2026-08-08
priority: medium
---

`config/urls.py:32` routes `^media/(?P<path>.*)$` straight to
`django.views.static.serve`. No `LoginRequiredMixin`, no owner check. Any
evidence photo is readable by anyone who can reach the URL — including a
different logged-in user, if the app ever gains a second account.

Currently mitigated, not fixed:

- Cloudflare Access gates the whole hostname, so an anonymous internet client
  never reaches Django at all.
- The app has exactly one user, so cross-user leakage is not yet reachable.

Both mitigations are external to the code. If Access is ever removed, or a
second account is created, the gap is live.

Fix: route media through the existing owner-scoped views. `LotEvidenceView`
and `SaleEvidenceView` in `portfolio/views.py` already do the right check for
`/lots/<id>/evidence/` and `/sales/<id>/evidence/`. Point templates at those
and delete the `re_path` in `config/urls.py`.

Also relevant: `django.views.static.serve` is documented as unsuitable for
production traffic. At single-user scale the performance side does not bite.
