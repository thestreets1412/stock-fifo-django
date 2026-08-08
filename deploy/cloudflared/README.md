# Cloudflare Tunnel config

`config.yml.example` is the tracked source of truth for the tunnel's ingress
rules. The Pi never hand-edits its live config; it copies this file and
substitutes the tunnel UUID.

## First install

```bash
sudo mkdir -p /etc/cloudflared
sudo cp /home/minotaur/stock-fifo-django/deploy/cloudflared/config.yml.example \
        /etc/cloudflared/config.yml
sudo sed -i "s/<TUNNEL-ID>/$TUNNEL_ID/g" /etc/cloudflared/config.yml
sudo cloudflared tunnel ingress validate --config /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
```

## Changing ingress later

Edit `config.yml.example` in the repo, commit, then on the Pi:

```bash
git pull
sudo cp deploy/cloudflared/config.yml.example /etc/cloudflared/config.yml
sudo sed -i "s/<TUNNEL-ID>/$(sudo grep -oP '(?<=^tunnel: ).*' /etc/cloudflared/config.yml.bak)/g" /etc/cloudflared/config.yml
sudo cloudflared tunnel ingress validate --config /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
```

Simpler in practice: keep the UUID in a note and re-run the first-install
substitution. The UUID never changes for the life of the tunnel.

## What must never be added

- No `hostname` rule for port 445, 139, or any SMB service.
- No rule pointing at `0.0.0.0:8000`. Gunicorn's loopback bind is what makes
  `SECURE_PROXY_SSL_HEADER` safe to trust.
- The catch-all `http_status:404` stays last. Without it cloudflared errors on
  startup.
