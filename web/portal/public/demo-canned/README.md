# Demo canned outputs

Pre-captured JSON responses for the demo stops 2–6 (scene map in
`docs/specs/demo-script-radivault.md §4`). Each file is loaded by the BFF
when the Demo Operator Mode "Canned overlay" toggle is active and the
live upstream call fails or times out.

Layout:

```
scene-2/home-facets.json
scene-3/hospital-stats.json
scene-3/hospital-gateway-health.json
scene-3/hospital-orders.json
scene-3/hospital-audit.json
scene-4/search-studies-page1.json
scene-4/search-facets.json
scene-4/order-create-success.json
scene-5/order-detail-ready.json
scene-5/download-urls.json
scene-6/hospital-stats-after.json
```

v0.1 ships empty placeholder files so the key shape is reserved. The
actual captures are taken against the running demo stack one day before
the live demo (rehearsal R-1 in dev-spec §8.4).
