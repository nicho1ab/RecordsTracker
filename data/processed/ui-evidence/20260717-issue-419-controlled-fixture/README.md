# Issue #419 controlled fixture evidence

This packet is controlled fixture evidence for `/ccld/facilities/intelligence`.
It is not real-corpus evidence, hosted acceptance evidence, production evidence,
or QNAP evidence.

The local-only fixture contained 51 authorized facilities and was served on
`127.0.0.1`. The temporary server was stopped after capture.

## Captured states

- desktop first page: `Showing 1–25 of 51 facilities`;
- desktop middle page: `Showing 26–50 of 51 facilities`;
- desktop last page: `Showing 51–51 of 51 facilities`;
- semantic first-page Previous disabled and last-page Next disabled;
- keyboard focus on Previous and Next with the Civic Ledger focus outline;
- approximately 500 px and mobile 390 px normal-flow layouts;
- applied filters and empty filtered result;
- a 720 CSS-pixel layout-equivalent capture for a 1440 px viewport at 200%;
- print CSS presence, pagination hiding, and sticky reset.

Every captured browser state reported no page-level horizontal overflow.

## Continuation integrity correction

`query-and-adjacent-page-regressions.xml` and `query-evidence.md` were
regenerated after the continuation position correction. The screenshots and
`browser-observations.json` were retained unchanged because the correction does
not alter rendering, layout, focus, responsive, disabled, applied-filter,
empty-result, or print behavior.

## Tool limitations

The controlled in-app browser could not change actual browser zoom or emulate
print media. `10-200-percent-layout-equivalent.png` is explicitly a layout
equivalent, not a true browser-zoom measurement. Print behavior is proven by
the print CSS assertions recorded in `browser-observations.json`; a true print
preview screenshot remains part of later hosted acceptance.

## Figma authority

Addendum `59:463`; state nodes `59:469`, `59:505`, `59:541`, `59:577`,
`59:613`, `59:649`, `59:685`, `59:721`, `59:757`, `59:793`, `59:829`,
`59:868`, and `59:904`.
