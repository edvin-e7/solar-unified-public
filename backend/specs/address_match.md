---
name: address_match
version: 1
audience: claude
description: Canonical Swedish-address normalize + score. Single source of truth for every equality/similarity check across the project.
---

# Spec — `backend/services/address_match.py`

## Why

Exact-string equality over Swedish addresses silently drops real matches.
`"KUNGSGATAN 1, 11143 STOCKHOLM"` ≠ `"Kungsgatan 1"` by raw string, but it's the
same address. Every comparison in the codebase (enrich, dedup, import, batch)
must route through this module or diverge from the canon.

## Public API

- `normalize(raw: str) -> NormalizedAddress` — pure. Same input → same output.
- `score(a: NormalizedAddress, b: NormalizedAddress) -> tuple[float, MatchKind]`
  — pure. Symmetric: `score(a, b) == score(b, a)`.
- `confidence_label(score: float) -> ConfidenceLabel` — Swedish UI label for
  frontends. Pure.
- `NormalizedAddress` is a frozen dataclass — hashable, safe as dict key.

## Invariants

1. **Idempotent normalize** — `normalize(normalize(x).raw) == normalize(x)`.
2. **Case/whitespace/punct insensitive** — `"KUNGSGATAN 1"`, `"kungsgatan 1"`,
   `"Kungsgatan, 1"`, `"  Kungsgatan  1 "` all normalize to the same street +
   number.
3. **Umlaut fallback** — `"Göteborg"` and `"Goteborg"` match as `same-city`
   (score 0.2). Loss of umlaut must not drop the match, but preserved umlaut is
   still preferred display.
4. **Number-suffix preserved for display, stripped for match** — `"1A"` and
   `"1"` same-street-different-number (0.6). Display keeps "1A".
5. **Postal isolates city on match** — postal equality scores 0.4 even if
   street differs, because postal is a strong city-segment signal.
6. **City-only input** — `normalize("Stockholm")` sets `city="stockholm"` and
   empty street/number. Single-token inputs with no digits are city-only, never
   street-only.
7. **Empty/garbage input** — whitespace-only returns an empty
   `NormalizedAddress`; normalize never raises.
8. **Score bounds** — `0.0 <= score <= 1.0`. Exact match → 1.0. No-overlap → 0.0.
9. **Single source of truth** — nothing else in the codebase implements address
   normalization or scoring. New comparisons import from here.
10. **Score symmetry** — order of arguments does not change the score.

## Test matrix — see `test_address_match.py`

Adversarial cases: case-fold × whitespace × punctuation × umlaut × suffix ×
postal × city-only × empty × very-long-garbage × non-Latin characters ×
leading-zero postal × postal-with-space × repeat-tokens. Matrix must stay green
on every change — no exceptions.

## Consumers

- `api/enrich.py` — `_score_and_sort`, `_pick_best`, per-contact `match_score`
- CSV import dedup (future)
- Prospects dedup (future)
- Batch match executor (future)

A new consumer adds itself here and imports from this module. It does not
re-implement the logic.
