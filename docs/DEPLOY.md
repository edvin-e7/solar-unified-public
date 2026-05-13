# Deploy — Mac Mini self-host + Cloudflare Tunnel

Recommended deploy: Mac Mini M4 self-host + Cloudflare Tunnel. Zero hosting-cost, GDPR-edge (data stannar i Sverige), Ollama-friendly (lokal GPU på Mac Mini). Setup-tid: ~30 min en gång.

## Varför inte Fly.io / Render / Hetzner?

| Option | Pros | Cons för solar |
|---|---|---|
| **Fly.io free** | 3 shared-cpu VMs | Inga GPU. Moondream ~5-10x långsammare. Free tier raderas efter inaktivitet. |
| **Render free** | Simpel deploy | 15-min sleep = 30s cold-start vid varje request. Brutalt på sales-demo. |
| **Hetzner CX22** | €5/mån, dedicated | Ingen GPU. Du betalar för CPU + RAM som du redan har på Mac Mini. |
| **Mac Mini self-host** | GPU (M-chip), 0 kr/mån, lokal data | Beror på din ström + nät hemma. Inte ett problem om nätet är stabilt. |

Mac Mini M4 = bästa-valet för Edvin när den anländer. Innan dess: använd vilken Linux-maskin du har (Chromebook duger för demo, inte för paying-customer-prod).

## Förutsättningar på host

```bash
# 1. Docker + docker compose
brew install docker         # eller orbstack om du gillar det

# 2. Ollama med vision-model
brew install ollama         # eller installer från ollama.com
ollama serve &               # bakgrundsdaemon
ollama pull moondream        # ~1.5 GB
ollama pull qwen2.5:1.5b     # ~940 MB (för text-tasks)

# 3. Cloudflare-konto + tunnel (gratis)
brew install cloudflared
cloudflared tunnel login                       # browser-OAuth
cloudflared tunnel create solar-prod           # skapar tunnel
cloudflared tunnel token solar-prod            # spara token för .env.production
```

## Setup-flow

```bash
# 1. Klona + bygga
cd ~/Apps/        # eller där du gillar
gh repo clone edvin-e7/solar-unified
cd solar-unified

# 2. Skapa .env.production (NO placeholders)
cp .env.example .env.production
# Edit .env.production:
#   GEMINI_API_KEY=...           # tom om du kör ren free-mode
#   GOOGLE_MAPS_API_KEY=...      # tom (Solar API är paid, off-by-default)
#   ALLOW_GOOGLE_SOLAR_API=0
#   ALLOW_EXTERNAL_LLM=0
#   LLM_PROVIDER=ollama
#   DETECTION_BACKEND=moondream
#   TUNNEL_TOKEN=<cloudflared tunnel token>
#   CORS_ORIGINS=https://solar.dittprojekt.se   # din custom-domain

# 3. Konfigurera Cloudflare-tunnel-DNS
cloudflared tunnel route dns solar-prod solar.dittprojekt.se

# 4. Start backend + tunnel
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# 5. Verifiera
curl -sf https://solar.dittprojekt.se/api/health   # via tunnel
docker compose -f docker-compose.prod.yml logs -f backend

# 6. Aktivera backup-cron (per docs/BACKUP.md)
(crontab -l; echo "0 4 * * * cd ~/Apps/solar-unified && ./scripts/backup.sh >> /tmp/solar-backup.log 2>&1") | crontab -
```

## Cloudflare Tunnel-konfig (för referens)

`cloudflared tunnel route dns solar-prod solar.dittprojekt.se` creates the DNS record. Tunnel-config genereras automatiskt vid `tunnel run` — den routar all trafik till `http://localhost:8000` på host.

För avancerad konfig (rate-limit, geofence till Sverige), se Cloudflare Dashboard → Zero Trust → Access policies.

## Operations

| Operation | Kommando |
|---|---|
| **Logs** | `docker compose -f docker-compose.prod.yml logs -f backend` |
| **Restart** | `docker compose -f docker-compose.prod.yml restart backend` |
| **Stop** | `docker compose -f docker-compose.prod.yml down` |
| **Update code** | `git pull && docker compose -f docker-compose.prod.yml up -d --build` |
| **Backup status** | `tail /tmp/solar-backup.log` |
| **DB size** | `du -sh backend/data/prospects.db` |
| **Images size** | `du -sh backend/data/images/` |
| **Restore from backup** | `docker compose ... down && ./scripts/restore.sh latest && docker compose ... up -d` |

## Skala när du har 5+ paying customers

Tecken på att Mac Mini räcker inte längre:
- prospects.db > 1 GB (10k+ scanned addresses) → migrera till PostgreSQL
- Moondream-inference > 30s consistent → uppgradera till bigger model + GPU-host
- Concurrent installer-requests > 5/s → behöver load-balancing

Vid den punkten: VPS med GPU (Genesis Cloud / RunPod). ~€100-200/mån. Du har då paying customers som dräker det.

## Säkerhet på host

- **Cloudflare Tunnel** = ingen öppen port på din router. Trafik kommer in via Cloudflare's edge → tunnel → localhost. Säkrare än traditional port-forwarding.
- **Backend binder 127.0.0.1:8000** = inte exponerad direkt. Tunnel är enda sätt utifrån.
- **ALLOW_EXTERNAL_LLM=0** = ingen accidentell Gemini-billing.
- **.env.production har 600 permissions** — `chmod 600 .env.production` så bara du läser den.
- **Backup-disk separat** från huvuddisk om möjligt — extern USB eller annan partition.

## Disaster recovery

Om Mac Mini kraschar / blir stulen:
1. Git clone repo på ny maskin
2. Restore prospects.db från senaste backup-disk
3. Pull moondream + qwen2.5 via Ollama
4. Tunnel-config: cloudflared tunnel route dns solar-prod solar.dittprojekt.se (DNS kvar i Cloudflare)
5. docker compose -f docker-compose.prod.yml up -d --build

Time-to-recovery: 30-60 min beroende på image-rebuild + ollama-pull.
