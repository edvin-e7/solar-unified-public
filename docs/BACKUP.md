# Backup + Restore

Solar-unified håller prospect-data + scan-bilder + learning-journal i lokalt filsystem. Ett kraschat disk = miste alla scans + ownership-data. Den här guiden sätter upp daglig backup.

## Snabbstart (Mac Mini / Linux self-host)

```bash
# 1. Skapa backup-target
mkdir -p ~/backups

# 2. Smoketest
scripts/backup.sh

# 3. Lägg till i crontab (kör kl 04:00 lokal tid)
(crontab -l 2>/dev/null; echo "0 4 * * * cd ~/solar-unified && ./scripts/backup.sh >> /tmp/solar-backup.log 2>&1") | crontab -

# 4. Verifiera nästa morgon
ls ~/backups/solar-unified/daily/
```

## Backup-target prio-ordning

`backup.sh` väljer första writable-target i denna ordning:
1. `$SOLAR_BACKUP_DIR` env-override
2. `~/backups/solar-unified` (default på self-host)
3. `/Volumes/Backup/solar-unified` (extern disk-pattern på Mac)

## Vad som backas upp

- **`backend/data/prospects.db`** → atomic via `sqlite3 .backup` (eller `cp` fallback). Snapshot per körning, tidsstämplad filnamn.
- **`backend/data/images/*.jpg`** → rsync incremental (eller `cp -a` fallback om rsync saknas). Mirror-state, inga snapshot-historik (bilder är immutable så det räcker).
- **`backend/prompts/learned/*`** → snapshot per körning (journal.jsonl + summary.md + errors.jsonl + prompts_log.jsonl).

## Retention

| Frekvens | Vad behålls |
|---|---|
| Daily | 7 senaste prospects-db + learned-snapshots |
| Weekly | 4 senaste söndag-snapshots (promoteras från daily) |
| Monthly | Alla 1:a-i-månaden-snapshots (db är ~25 KB per stk, billigt) |

## Restore

```bash
# Lista tillgängliga snapshots
scripts/restore.sh

# Återställ senaste daily
scripts/restore.sh latest

# Återställ specifik snapshot
scripts/restore.sh ~/backups/solar-unified/daily/prospects-2026-05-15T04-00-00Z.db
```

Restore-script:
- Refuses om uvicorn körs (måste stoppa backend först)
- Sparar nuvarande `prospects.db` som `.before-restore` (safety-net)
- Skriver INTE över images/ (immutable) — endast db

För images: kopiera manuellt från `~/backups/solar-unified/images/` om disk-loss.

## Offsite backup (rekommenderat för paying customers)

Lokala daily-snapshots skyddar mot kod-bugs och accidental-delete. För disk-crash + lokala-disasters behövs offsite-tier. Två gratis options:

### Backblaze B2 (10 GB free tier)
```bash
brew install b2-tools
b2 authorize-account <keyId> <appKey>
# I crontab, lägg till efter backup.sh:
0 5 * * * b2 sync ~/backups/solar-unified/monthly b2://solar-backups/monthly
```

### Storj DCS (25 GB free tier)
```bash
# Same flow, uthan vendor-lock-in (S3-kompatibelt)
aws s3 sync ~/backups/solar-unified/monthly s3://solar-backups/monthly --endpoint-url=https://gateway.eu1.storjshare.io
```

## Vad om jag förlorar BÅDE primary disk och backup-disk?

GitHub har repo-koden (private repo `edvin-e7/solar-unified`). Det Edvin förlorar är:
- `backend/data/prospects.db` — historiska scan-results + ownership-data
- `backend/data/images/` — alla cached satellite-bilder
- `backend/prompts/learned/` — learning-journal-historik

Disaster-recovery-flow:
1. Klona repo: `gh repo clone edvin-e7/solar-unified`
2. `./install.sh` — venv + deps + tom .env
3. Re-kör pipeline på samma adresser → ny `prospects.db` + nya images
4. Learning-journal startar tom, kommer fyllas i av nya cykler

Data-förlust är inte fatal eftersom hela pipelinen kan reproducera state. Men: 30 GB images representerar ~50 timmars Moondream-inference på CPU. Offsite-backup räddar tid > pengar.
