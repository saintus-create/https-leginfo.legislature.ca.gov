# Legislative citation contract

The application should expose citations as structured data, not only internal corpus identifiers.

For a California code section, the canonical source is constructed as:

`https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=<section>.&lawCode=<CODE>`

The implementation lives in `src/leginfo/citations.ts`.

## API shape

```json
{
  "label": "FAM § 432.5",
  "lawCode": "FAM",
  "sectionNum": "432.5",
  "url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=432.5.&lawCode=FAM"
}
```

Retrieval and answer layers should carry `lawCode` and `sectionNum` with every result. The answer renderer can then emit `label` as the visible citation and `url` as the source link.

`citationFromUid()` is deliberately best-effort. It recognizes simple `CODE:SECTION`, `CODE-SECTION`, and `CODE/SECTION` identifiers, but returns `null` for ambiguous UIDs. The system must not manufacture a legal citation from an identifier it cannot parse confidently.

The LegInfo source should remain the authoritative destination. Internal R2 object keys and D1 identifiers are implementation metadata and should not be presented as the legal source citation.
