# Factual Sales Boost Inventory

`yandex_boost.factual_inventory_cli` is a local read-only diagnostic over a sanitized HAR
inspection report. It never calls Yandex and does not alter campaigns, bids, or budgets.

The identifiers have different meanings:

- `businessId` identifies the business.
- seller/page `campaignId` is page context and is not a Sales Boost strategy ID.
- `salesCampaignId` and `strategyId` identify the factual Sales Boost strategy when observed
  in the confirmed Sales Boost schema.
- `offerId` is the current factual product identity. It is not inferred as a seller SKU.

Campaign names can yield `legacy_name_hint`, but the hint is not a factual SKU. A factual
SKU requires a separately observed endpoint linking the `dcmp-...` offer ID to a seller SKU.

Run from the repository root:

```cmd
.venv\Scripts\python.exe -m yandex_boost.factual_inventory_cli local_data\reports\sales_boost_inventory_report.json local_data\reports\factual_sales_boost_diagnostic.json --force
```

The diagnostic reports factual Sales Boost IDs, names, offer IDs, observed fees and statuses,
missing fields, conflicting observations, and offer IDs shared by multiple campaigns. Unknown
schemas fail explicitly; a known empty `campaigns` collection is reported as a legitimate empty
inventory.
