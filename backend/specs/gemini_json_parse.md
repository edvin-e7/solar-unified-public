---
name: gemini_json_parse
description: Spec for robust JSON extraction from LLM responses (Gemini + Ollama)
type: spec
audience: claude
---

# Spec: `_extract_json` parser hardening

**Kontrakt**: `services.gemini._extract_json(raw: str) -> Any` tar en rå LLM-respons och returnerar parsed JSON. Måste tåla typiska LLM-output-defekter utan att krascha autonom-cykeln.

## Why

Errors.jsonl visar 8+ `JSONDecodeError`-incidenter i `cove-questions` / `cove-answers` över bara 2 dagar. Mönster:
1. **Empty response** → `Expecting value: line 1 column 1 (char 0)`. `qwen2.5:1.5b` returnerar tom sträng när den inte kan följa JSON-formatet.
2. **Extra data** → `Extra data: line 4 column 4`. Modellen ger giltig JSON följt av förklarande text.
3. **Array-fallback saknas** — fallback-grenen letar bara efter `{...}`, inte `[...]`. cove-questions returnerar lista, faller inte rätt.

Autonom-cykeln fastnar i `infra-degraded-skip` loop: cove-verify failar transient → journal/ledger fylls med ovan, ingen riktig förbättring godkänns.

Fix: en parser med tolerant `raw_decode`-strategi + tom-sträng-detektering + array-aware fallback. Spec + matrix här. Implementation i `services/gemini.py`.

## Public API

```python
def _extract_json(raw: str) -> Any: ...
```

**Kontrakt:**
- Input: str — kan vara JSON, JSON-i-fence, JSON följt av prosa, prosa följt av JSON, tom, eller ren prosa.
- Output: dict | list | scalar (vad JSON än är).
- Fel: höjer `json.JSONDecodeError` ENDAST när ingen tolkbar JSON finns. Tom input → höjer `ValueError("empty response")` (caller fångar och degraderar gracefully).

## Invariants

1. **I1 — Tom input.** `_extract_json("")` höjer `ValueError`, inte `JSONDecodeError`. Caller kan särskilja transient vs. korrupt.
2. **I2 — Whitespace-only input.** `"   \n  "` → `ValueError`, samma som tom.
3. **I3 — Naken JSON.** `'{"a": 1}'` → `{"a": 1}`. `'[1,2,3]'` → `[1,2,3]`.
4. **I4 — JSON i ```json-fence.** ```` ```json\n{"a":1}\n``` ```` → `{"a": 1}`. Fence kan vara ```` ```` ```` också (ingen lang-tag).
5. **I5 — JSON följt av prosa (Extra data).** `'[1,2,3]\nFörklaring: ...'` → `[1,2,3]`. Använd `JSONDecoder.raw_decode` på prefixet.
6. **I6 — Prosa följt av JSON.** `'Här kommer svaret:\n{"a": 1}'` → `{"a": 1}`. Hitta första `{` eller `[`, försök parsa därifrån.
7. **I7 — Nested brackets.** `'[{"a":[1,2]}, {"b":[3]}]'` → korrekt 2-elements lista. Inte stoppa vid första inre `]`.
8. **I8 — Array OCH object i fallback.** Både `{...}` och `[...]` måste återfinnas i prosa.
9. **I9 — Ren prosa, ingen JSON.** `'Jag kan inte svara'` → höjer `JSONDecodeError`. Caller degraderar.
10. **I10 — Trasig JSON (saknad citationstecken e.dyl.).** Höjer `JSONDecodeError` (kan inte räddas).
11. **I11 — Unicode.** `'{"namn": "Åsa"}'` parsas korrekt. UTF-8 antagning.
12. **I12 — Idempotent.** `_extract_json(_extract_json(...) → str)` är ej kontrakt — funktionen är str → Any, inte Any → Any.

## Adversarial matrix (tests måste täcka)

| Case | Input | Expected |
|---|---|---|
| empty | `""` | `ValueError` |
| whitespace | `"   "` | `ValueError` |
| naked object | `'{"a":1}'` | `{"a":1}` |
| naked array | `'[1,2,3]'` | `[1,2,3]` |
| array with nested | `'[{"a":[1,2]},{"b":3}]'` | 2-elem list |
| fenced json | `'```json\n{"a":1}\n```'` | `{"a":1}` |
| fenced no-lang | `'```\n[1,2]\n```'` | `[1,2]` |
| extra-data after array | `'[1,2,3]\n\nFörklaring följer'` | `[1,2,3]` |
| extra-data after object | `'{"a":1}\nNot JSON anymore'` | `{"a":1}` |
| prose-prefix object | `'Svaret är:\n{"x": 9}'` | `{"x":9}` |
| prose-prefix array | `'Här:\n[1]'` | `[1]` |
| only prose | `'Jag kan inte'` | `JSONDecodeError` |
| broken json | `'{"a": '` | `JSONDecodeError` |
| unicode | `'{"namn":"Åsa"}'` | `{"namn":"Åsa"}` |
| swedish prose then json | `'Tänker...\n{"sv": "åäö"}'` | `{"sv":"åäö"}` |
