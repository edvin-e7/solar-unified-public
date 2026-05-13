# Spec: POST /api/enrich/person

**Kontrakt**: klienten skickar en adress, API returnerar alla hittade kontakter sorterade efter match-score mot begärd adress. Best_contact är högst-rankad. Confidence är explicit. 404 bara om ingen kontakt ens är i samma stad.

## Request

```json
{ "address": "string, 3..200 chars, required", "name": "string, optional" }
```

## Response

### 200 OK


```json
{
  "name": "<best_contact.name or null>",
  "age": null,
  "phone": "<best_contact.telephone or null>",
  "source": "hitta",
  "contacts": [ ... alla hittade, sorterade på score desc ... ],
  "total_hits": N,
  "match": {
    "requested": "Kungsgatan 1 Stockholm",
    "normalized": {"street": "kungsgatan", "number": "1", "city": "stockholm"},
    "best_score": 0..1,
    "best_kind": "exact" | "same-street-different-number" | "same-postal" | "same-city",
    "confidence_label": "sannolik" | "möjlig" | "närliggande"
  }
}
```

### 404 Not Found

Bara när `max(score) < 0.2` — ingen kontakt i ens samma stad.

### 422 — input invalid (< 3 chars, > 200 chars, whitespace-only)

### 502 — hitta nåddes inte

## Scoring (det som gör kontraktet äkta utan att kasta värde)

- Exakt gata + nummer: **1.0** (label: sannolik, confidence > 0.8)
- Exakt gata, annat nummer: **0.6** (label: möjlig)
- Samma postnummer: **0.4** (label: möjlig)
- Samma stad: **0.2** (label: närliggande)
- Övrigt: **0.0** → uteslutes

## Normalisering (båda sidor, innan jämförelse)

- `.lower().strip()`
- Ta bort: `, . : ;` och dubbel-whitespace
- Transliterera som fallback: å→a, ä→a, ö→o, é→e
- Extrahera `<street> <number>` via regex: `^(.+?)\s+(\d+)[A-Za-z]?\b`
- Postnummer: 5 siffror `^\d{3}\s?\d{2}$`

## Invariant

- `best_contact.street_address` returneras **tillsammans med** `match.best_score` och `match.best_kind` — downstream kan aldrig missförstå "200" som "exakt match".
- `contacts[]` alltid sorterad: score desc, sedan name asc som tiebreak.
- `match.normalized` synligt i response → debug utan att läsa loggar.

## Downstream-regler (följer av detta kontrakt)

- **Frontend**: färgkoda rader efter `confidence_label`. "Närliggande" visas gråare, inte som "hittat".
- **Batch-executor**: räknar `outcome="passed"` bara om `best_score >= 0.8`.
- **Learning-loop**: aggregerar `best_score` per adress-typ för att hitta var scoringen är fel (t.ex. hög felprocent på lantliga adresser).
