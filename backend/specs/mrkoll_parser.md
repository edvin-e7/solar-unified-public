# MrKoll Parser Service Spec

## Public API

### Functions

- **`parse_mrkoll_html(html: str) -> dict[str, Any]`**
  Extracts structured person and property information from raw MrKoll.se HTML content.
  - `html`: The raw HTML string fetched from mrkoll.se (usually via Electron).
  - **Returns**: A dictionary containing found fields. Missing fields are omitted.

---

## Invariants

- **I1 [Pure Logic]**: The parser MUST be a pure function with no external dependencies or side effects (I/O, network).
- **I2 [Omission of Missing Data]**: Fields not found in the HTML MUST be excluded from the result dictionary to allow callers to distinguish between "unsuccessful extraction" and "empty field".
- **I3 [Swedish Character Compatibility]**: Extraction patterns MUST account for Swedish characters (`åäöÅÄÖ`) in names, street addresses, and city names.
- **I4 [Numeric Sanitization]**: Age, income, and property values MUST be converted to `int`, with all internal whitespace and non-breaking spaces removed during normalization.
- **I5 [Phone Type Discrimination]**: Phone numbers starting with the `07` prefix MUST be labeled as `mobile`; all other Swedish-format numbers MUST be labeled as `phone`.
- **I6 [Heuristic Address Matching]**: Addresses MUST be matched using common Swedish street suffixes (e.g., *gatan*, *vägen*, *gränd*) to minimize false positives from surrounding text.
- **I7 [Business Rule Validation]**: Extracted numeric values MUST be validated against reasonable bounds (e.g., age between 1 and 120) before being added to the output.
- **I8 [First-Match Priority]**: For multi-value fields like phone numbers, the first valid match encountered in the document MUST take precedence.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Empty or nonsensical HTML | Returns `{}`. | I2 |
| Name with `<h1>` attributes | Regex `r"<h1[^>]*>"` correctly skips attributes to find text. | I3 |
| Age = "0 år" or "200 år" | Omitted from output. | I7 |
| Income = "250 000 kr" (with non-breaking spaces) | Correctly parsed as `250000`. | I4 |
| Multiple mobile numbers | Only the first `07...` number found is included. | I8 |
| Address with complex suffix | Handles *allé*, *plats*, *torget*, etc. | I6 |
| HTML with encoded entities | `re.search` on raw HTML may miss entities; should ideally be decoded before parsing if entities are common (current impl uses raw regex). | I3 |
