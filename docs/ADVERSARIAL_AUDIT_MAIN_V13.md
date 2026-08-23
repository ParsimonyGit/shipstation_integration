# Adversarial QA/QC Audit — `shipstation_integration` (`main-v13`)

**Audience:** Product Manager (fulfillment / ERP). Not an engineering task list.  
**Scope:** Read-only review of `ParsimonyGit/shipstation_integration` @ `main-v13` (`ea09a02`), cross-checked against production coupling in `ParsimonyGit/fps_customizations` @ `develop`.  
**Date:** 2026-08-23  
**Constraint honored:** No merge, no deploy, no migration, no live ShipStation API calls.

Docs in the README were treated as untrusted. Claims below are from code.

---

## Executive stand

This app is **not safe to treat as a finished production integration**. On FPS it is the order-intake pipe that warehouse scanners depend on (`check_sales_order` accepts a Sales Order name **or** `shipstation_order_id`; roll length/width are written only in the before-submit hook). The sync is a 24-hour UTC poll with **no unique constraint**, **no order-status filter**, and **idempotency keyed by `shipstation_order_id` on submitted docs only**. That combination can duplicate Sales Orders, skip cancelled/on-hold orders into inventory, miss anything older than 24 hours, and — when FPS auto-invoicing and ShipStation shipment flags overlap — create a second Delivery Note or Sales Invoice. Label generation is a paid ShipStation API call gated only in JavaScript. Tests are an empty stub. Open PRs #57 and #80 are bitrot and must not be merged onto FPS. **Do not upgrade this site off ERPNext v13, do not add a second ShipStation Settings account, and do not run leftover FPS “fire-drill” patches.** Stabilize identity + dual-write paths on v13 before any version or feature work.

---

## Verdict table

| Area | Verdict | Severity | Why it matters on FPS |
|---|---|---|---|
| Order identity / duplicates | **FAIL** | Critical | No unique index; exists-check is `docstatus=1` only; FPS also re-queues `list_orders` on scheduler `all` |
| Cancelled / on-hold import | **FAIL** | Critical | `list_orders` never filters `orderStatus`; cancelled SS orders can become submitted SOs |
| 24-hour lookback + UTC | **FAIL** | High | Missed jobs permanently drop orders; scanners then show “no submitted order” |
| Split / multi-package shipments | **FAIL** | High | SI / DN / Shipment idempotency is by **order id**, not shipment id; second package is dropped |
| Label generation (money) | **FAIL** | High | Whitelisted; `enable_label_generation` is client-side only; each click buys a label |
| FPS scanner contract | **FAIL** | Critical | Before-submit hook does a live `get_order`; any exception leaves a **draft** SO scanners cannot see |
| FPS dual invoice / DN paths | **FAIL** | Critical | Scanner invoices + `DN.on_submit` → `create_erpnext_shipment` + daily `complete_deliveries` can double-write |
| Second ShipStation account | **FAIL** | High | Integration loops all settings; FPS uses `get_last_doc` and will hit the wrong account |
| Leftover FPS fire-drill patches | **FAIL** | Critical | Not in `patches.txt`; several call live ShipStation or mass-create invoices |
| Ounce → pound (live code) | **FAIL** | High | `shipments.py` still divides `weight.value` by 16 with no unit check; prior FPS patch was a one-time backfill |
| Shopify-via-ShipStation (VBS) | **PASS** | — | `shopify_store` field does not exist on the store DocType, so Shopify hook never steals these orders |
| Settings API secret storage | **WARN** | Medium | Password fields; listed in list view; System Manager full access; no dedicated role |
| Product sync | **WARN** | Medium | README claims periodic product fetch; only a manual button; first-page count is wrong |
| Tests / CI | **FAIL** | High | Empty `TestCase`; CircleCI only `semantic-release` on obsolete `master` |
| ERPNext v14 / v15 / v16 | **FAIL** | High | `main-v13` asset pipeline and custom-field `insert_after` will break; no v16 branch |
| PRs #57 / #80 | **FAIL** (do not merge) | High | Bitrot; #57 would fight the FPS roll-dimension hook; #80 is dirty against `main-v14` |
| `shipstation-client` pin | **WARN** | High | Git `@master` on a private fork; upstream AgriTheory now requires Python 3.10+ |
| Warehouse filter / `since_date` | **PASS** | — | Implemented; empty warehouse list means “all warehouses” (documented in the field) |
| Amazon hook off-ramp | **WARN** | Medium | Requires `amazon_seller_setup` on the store row — that field is **not** in this app’s DocType |

---

## Top 10 risks (with paths)

### 1. Duplicate Sales Orders (money + warehouse chaos)

**Paths:** `shipstation_integration/orders.py` (`validate_order`, `create_erpnext_order`); `fps_customizations/hooks.py` (`scheduler_events["all"]`); `fps_customizations/hook_events/shipstation.py` (`enqueue_list_orders`); `parsimony/utils/__init__.py` (`is_job_queued`).

`validate_order` only skips if a **submitted** Sales Order already has that `shipstation_order_id`. There is no unique index. `create_erpnext_order` saves, optionally runs the FPS hook, submits, then `frappe.db.commit()`. Two overlapping workers that both pass the exists-check create two submitted SOs for one marketplace order.

FPS makes this likely: `shipstation_integration` already runs `list_orders` on `hourly_long`, and FPS **re-enqueues the same method** on scheduler `all` (~every 4 minutes) if `is_job_queued(..., queue="long")` is false. `is_job_queued` only inspects RQ jobs whose `job_name` equals that string **and** whose queue name contains `"long"`. It does not serialize against a scheduler tick that has not yet appeared in RQ, and it does not lock the database. During warehouse-scan load the long queue is also doing one extra live `get_order` per SO (FPS hook). That stretches runtime and widens the overlap window.

**FPS impact:** `check_sales_order` returns the first matching submitted SO. Pickers can fulfill one copy while billing/stock land on the other.

### 2. Cancelled / on-hold / unpaid ShipStation orders become live ERP orders

**Path:** `shipstation_integration/orders.py` (`list_orders` parameters).

Parameters sent: `store_id`, `modify_date_start`, `modify_date_end`. No `orderStatus`. ShipStation will return cancelled, on-hold, and awaiting-payment orders. Those pass `validate_order` and are submitted. That is unearned revenue and phantom demand on inventory.

### 3. Anything older than 24 hours UTC is silently dropped

**Path:** `shipstation_integration/orders.py` lines 61–76; same pattern in `shipments.py` lines 60–80.

Lookback is `datetime.utcnow() - 24h`, hardcoded. Comment admits the API “behaves oddly” on shorter windows. If a job fails, the queue backs up, or ShipStation rate-limits past that window, those orders **never retry**. Scanners then return *“No submitted order found against this ID”*. There is no cursor / watermark stored on Shipstation Settings.

### 4. FPS scanner contract breaks when the before-submit hook fails

**Must-protect contract (verified):**

| Surface | Path | Behavior |
|---|---|---|
| Scan lookup | `fps_customizations/api/selling.py` `check_sales_order` | Accepts SO **name** or `shipstation_order_id`; requires `docstatus=1`; refuses fully delivered stock qty |
| Roll dimensions | `fps_customizations/hook_events/sales_order.py` `update_order_item_details` | Wired as `update_shipstation_order_before_submit` |
| Writer | `shipstation_integration/orders.py` `create_erpnext_order` | `save` → hook → `save` → `submit` |

The FPS hook calls `settings.client().get_order(so.shipstation_order_id)` and maps option names containing `length` / `width` onto `order_roll_length` / `order_roll_width`. Those fields drive CTO BOM matching in `get_active_boms`.

If `get_order` throws (timeout, 429, 401), the exception is **not** caught in `create_erpnext_order` (only `frappe.LinkValidationError` is). The SO remains **draft**. Scanners only query `docstatus=1`. Floor result: barcode / SS order id does nothing, while the order sits in drafts.

### 5. Double Delivery Note / double Sales Invoice (money + inventory)

Three writers exist on the same SO:

1. **Warehouse scanner** — `fps_customizations/api/selling.py` `create_delivery_note` creates and submits a Sales Invoice for any store that is **not** (`is_amazon_store` **and** `amazon_seller_setup`), then builds a DN (draft or submitted).
2. **ShipStation shipment poll** — `shipstation_integration/shipments.py` `create_erpnext_shipment` optionally creates SI + DN + Shipment. Idempotency for SI and DN is **submitted row by `shipstation_order_id`**, not shipment id. **Draft DNs do not count.**
3. **Daily auto-submit** — `fps_customizations/hook_events/delivery_note.py` `complete_deliveries` (`daily_long`) submits **all** matching draft DNs site-wide. `DN.on_submit` then enqueues `_create_shipment`, which calls `create_erpnext_shipment` again.

Race that hurts: ShipStation poll submits a DN while the scanner still holds a draft DN for the same order → two DNs, stock issued twice. Invoice race is partially mitigated if an SI already exists for that order id, but the scanner path does not look up by `shipstation_order_id` — it uses `per_billed < 100`. A second SI is possible if the first is still in draft or `per_billed` has not updated.

`amazon_seller_setup` is **not** a field on this app’s `Shipstation Store` DocType. FPS reads it anyway. If the Amazon app did not add that custom field, the guard is always false and **Amazon-named stores get invoiced by the scanner**.

### 6. Paid labels can be purchased by any logged-in Desk user

**Paths:** `shipstation_integration/shipping.py` `create_shipping_label` / `_create_shipping_label`; `public/js/shipping.js`.

`enable_label_generation` is checked only in JS. The server checks `settings.enabled`, then calls `client.create_label_for_order`. No idempotency. Repeat clicks = repeat carrier charges. Method is `@frappe.whitelist()` with no role decorator.

`push_attachment_update` publishes `eval_js` with the attachment name interpolated into JavaScript. That is a separate desk-security defect.

### 7. Multi-shipment / split orders are discarded after the first

**Path:** `shipstation_integration/shipments.py` `create_sales_invoice`, `create_delivery_note`, `create_shipment`.

Comments in `orders.py` say split ShipStation orders are intentionally not imported so ERP can have multiple DNs against one SO. The shipment writer then **refuses** a second SI/DN/Shipment for the same `shipstation_order_id`. Partial marketplace fulfillments after the first package do not land. Inventory and freight cost go missing.

Voided shipments call `cancel()` on SI / DN / Shipment. If the SI is paid or the DN is billed, cancel throws and the rest of that store’s shipment batch stops (no per-shipment try/except in `list_shipments`).

### 8. A second ShipStation Settings document breaks FPS

**Integration:** `list_orders` / `list_shipments` iterate **all** `enabled` settings. That part scales.

**FPS (explicit comments: “FPS only has one Shipstation instance”):**

- `get_last_doc("Shipstation Settings")` in `delivery_note._create_shipment` and in leftover patches
- `set_roll_length_in_orders.py`, `set_ordered_items_for_custom_orders.py`, `update_shipment_amount_in_shipments.py`, `fetch_missing_shipstation_shipments.py`

`get_last_doc` is “most recently modified,” not “the enabled one,” not “the one on this DN.” A sandbox or second account silently retargets warehouse shipment creation and any fire-drill.

### 9. Leftover fire-drill scripts are live-API / mass-money bombs

**`fps_customizations/patches.txt` does not list these** (they will not run on migrate, but they are importable and look like patches):

| File | Live ShipStation? | What it does |
|---|---|---|
| `patches/fetch_missing_shipstation_shipments.py` | **Yes** | `get_last_doc`, hardcoded `create_date_start` `01-03-2023`, `create_erpnext_shipment` (can create SI/DN/Shipment) |
| `patches/update_shipstation_order_details.py` | **Yes** | `client.get_order` + `update_amazon_order` on unshipped Amazon SOs |
| `patches/create_invoices_for_delivered_orders.py` | No API | `make_sales_invoice` + submit for **every** submitted SO with `per_billed < 100` and `per_delivered > 0` — site-wide double-billing |
| `patches/set_roll_length_in_orders.py` | **Yes** (docstring) | Manual; intended to call ShipStation many times |
| `patches/set_ordered_items_for_custom_orders.py` | **Yes** (docstring) | Same |
| `patches/update_internal_notes_in_sales_orders.py` | **Yes** (docstring) | Same |

**Sandbox rule:** any test copy of FPS that still has production API keys in Shipstation Settings will bill labels and mutate production ShipStation if these are executed. `Get Items` / `Get Orders` / `Get Shipments` buttons on the Settings form also hit live API with no dry-run.

Registered (already-migrated) money patches:

- `convert_ounces_to_pounds_in_shipments` — one-time `/16` of **all** `Shipment Parcel.weight` values
- `update_cost_of_goods_in_shipments` — backfill `cost_of_goods`
- `update_shipment_amount_in_shipments` — **live API** per zero-amount Shipment (already in `patches.txt`; re-running migrate will not re-fire, but copying the file onto a sandbox with prod keys will)

### 10. Client pin + empty tests = no safety net

**Paths:** `requirements.txt`; `shipstation_integration/shipstation_integration/doctype/shipstation_settings/test_shipstation_settings.py`; `.circleci/config.yml`.

`requirements.txt` is:

```
shipstation-client @ git+https://github.com/ParsimonyGit/shipstation-client.git@master#egg=shipstation-client
```

That is a **moving `master`**, not a commit or version. The private Parsimony fork still advertises Python ^3.8. Upstream `agritheory/shipstation-client` `master` is Python **>=3.10,<3.13** (`str | int` syntax). A casual “update the client” on a v13 bench can make the whole app fail to import.

The only test class is `pass`. CircleCI releases from branch `master`, which no longer exists (`main-v13` / `main-v14` / `main-v15`). **No suite can run without a live ShipStation account today, because nothing is mocked.**

---

## Entry points (verified)

### This app (`main-v13`)

| Kind | Location | Notes |
|---|---|---|
| Scheduler | `hooks.py` `hourly_long` | `orders.list_orders`, `shipments.list_shipments` |
| Migrate | `hooks.py` `before_migrate` | `setup.setup_custom_fields` every migrate |
| Desk JS | `doctype_js` Sales Order / Delivery Note | `public/js/sales_order.js`, `delivery_note.js` → `shipping.js` |
| Bundled JS | `app_include_js` → `public/build.json` | v13 `shipstation_integration.min.js` only |
| Whitelist (Settings doc) | `shipstation_settings.py` | `get_orders`, `get_shipments`, `get_items`, `update_carriers_and_stores`, `update_warehouses` |
| Whitelist (module) | `shipping.py` | `create_shipping_label`, `fetch_shipment`, `get_carrier_services`, `get_shipstation_settings`, `update_carriers_and_stores`, `push_attachment_update`, `get_shipstation_address` |
| Document events | none in this app | FPS owns `DN.on_submit` and `Shipment` override |
| Product scheduler | **none** | README feature is false |

`shipping.update_carriers_and_stores` is commented “scheduled daily” and is **not** in `scheduler_events`.

### FPS (`develop`) — production coupling

| Kind | Location | Notes |
|---|---|---|
| Scheduler `all` | `fps_customizations/hooks.py` | `enqueue_list_orders` (and Amazon enqueue) |
| Scheduler `daily_long` | same | `complete_deliveries` |
| Hook | `update_shipstation_order_before_submit` | `update_order_item_details` (roll L/W) |
| Hook | `update_shipstation_item_before_save` | `mark_item_as_purchase` if `store.mark_items_for_purchase` and item is new |
| `DN.on_submit` | `hook_events/delivery_note.py` | Enqueue `_create_shipment` if `shipstation_order_id` |
| `Shipment` class | `override_doctype_class` | `CustomShipment.on_submit` **only** `db_set("status", "Submitted")` |
| `Shipment.validate` | `set_cost_of_goods` | COGS from DN incoming rate; **0** if that DN already has >1 Shipment |
| Scanner API | `api/selling.py` | `check_sales_order`, `get_sales_order`, `create_delivery_note` |
| Store custom field | `fps_customizations/setup.py` | `Shipstation Store.mark_items_for_purchase` |

Shopify traffic for **“VBS Amazon”** and **“Vapor Barrier Supply”** is ShipStation-store intake, not `shopify_integration`. On this app, `is_shopify_store` is set when the marketplace name contains `"Shopify"`, but `validate_order` only diverts if `store.shopify_store` is set — and **that field does not exist** on `shipstation_store.json`. Those orders stay on this create-SO path. That matches the FPS design. Do not add a `shopify_store` link on those rows without a coordinated cutover.

---

## Sync pipeline notes

### Idempotency

| Document | Key used | Gap |
|---|---|---|
| Sales Order | `shipstation_order_id` + `docstatus=1` | Drafts and races; no DB unique |
| Sales Invoice | `shipstation_order_id` + submitted | Second shipment reused; not shipment-id |
| Delivery Note | `shipstation_order_id` + submitted | Drafts invisible; scanner race |
| Shipment | `shipment_id` **OR** `shipstation_order_id` | First hit wins; splits die |
| Item | SKU as `item_code`, else name; optional Parsimony `Item Alias` | Re-enables disabled items; first alias wins |

### Retries / partial failure

- HTTP errors on list fetch: log, `continue` to next store.
- Validate errors: log, `continue`.
- Create SO: only `LinkValidationError` is caught. Stock, mandatory, hook, and submit errors **abort the rest of that store’s page**.
- `list_shipments` has **no** per-shipment try/except.
- Each successful SO/DN/Shipment `commit()`s — partial batches stay.

### Timezone

Naive `datetime.utcnow()`. No site TZ. `since_date` uses `getdate(order.create_date)` (date only). Ship dates on SOs are `getdate(order.ship_date)` / `order.order_date`.

### Pagination

`shipstation-client` `Page` iterates pages in `__next__`. `list_orders` / `list_shipments` iteration is OK if the client version matches. `get_items` iterates products but reports `len(products.results)` (current page only). `__len__` on `Page` is also current-page length. Default `results: list = []` on the attrs class is a shared-mutable-default smell.

### Customer / address

`customer.py` `get_billing_address` SQL joins `tabAddress` and `tabDynamic Link` **without** `Address.name = Dynamic Link.parent`. That is a cartesian product and can attach **any** billing address in the site. Billing address create uses `order.customer_username` as the Customer link, which often is not the Customer name just created (email / id / ship-to). Territory is hardcoded `"United States"`. Customer Group and Price List `"ShipStation"` are created only via setup wizard / `setup_shipstation()`, not `after_install`.

---

## Settings / security

`Shipstation Settings` (`shipstation_settings.json`):

- `api_key` / `api_secret`: Password, **required**, **`in_list_view`: 1**.
- `enabled` default 1; `enable_label_generation` default 0, depends on enabled; turning `enabled` off also clears label generation.
- Store row: `enable_shipments` forced off if `enable_orders` is off (and SI/DN/Shipment flags cleared).
- Permissions: System Manager (full, permlevel 0); Administrator; permlevel 1 only on Administrator. Sync **buttons** are permlevel 1 — System Managers may not see Get Orders/Shipments/Items in the form, but they can still call the Python methods if they find them.
- No Shipstation Manager role. No field-level deny on secrets for desk users with Settings access.
- `store_ids` property reads `self.store_data` — **that field is not on the DocType**. Dead code; would throw if called.
- `amazon_seller_setup` / `shopify_store` are read in `orders.py` and FPS invoicing; **neither is defined** on `Shipstation Store` in this app.

Whitelisted shipping methods: login required (`allow_guest` absent), **no role check**.

---

## Compatibility matrix (v13 → v16)

Verified branches on the repo: `main-v13`, `main-v14`, `main-v15`. **No `main-v16`.**

| Topic | v13 (`main-v13`, FPS) | v14 (`main-v14`) | v15 (`main-v15`) | v16 |
|---|---|---|---|---|
| Desk assets | `build.json` → `shipstation_integration.min.js` | `app_include_js = ["shipstation_integration.bundle.js"]` | Same as v14 | Same pattern; v13 bundle **will not build** |
| Custom fields | `insert_after` `tax_id` / `return_against` / `amended_from` | Relocated to Tab Break `tb_commerce` after `company_address_display`; `frappe.reload_doc("custom","doctype","custom_field")` before create (#86) | Branched from v14 migrate | Unknown; field anchors move again in Workspace-heavy desks |
| Metadata import PRs | #57 open, dirty/stale, targets this branch | #80 open, `mergeable_state=dirty`, last human ping 2023-08 | Not ported | Not ported |
| Scheduler `hourly_long` | Supported | Supported | Supported | Still exists in Frappe; confirm on target |
| `Shipment` DocType | Present; FPS overrides `on_submit` | Present | Present | Confirm required fields / status machine |
| Python | v13 benches often 3.8–3.10 | 3.10 | 3.10+ | 3.12 typical |
| `shipstation-client` | Parsimony fork `@master`, poetry `^3.8.10` | Not in a `requirements.txt` on v14/v15 (file removed) | Same | Upstream AgriTheory **3.10–3.12 only** |
| `eval_js` realtime | Used | May be restricted / removed in later Frappe | Risk | Risk |
| `frappe.utils.file_manager.save_file` | Used for labels | Still present historically | Verify | Likely moved; label attach breaks |
| Modal CSS `modal-dialog` width | Bootstrap 3 | Bootstrap 4 | Bootstrap 5 | Label dialog layout breaks |
| `octicon` module icon | v13 desk | Deprecated | Gone | Gone |
| README | Claims v13 only | Code exists but README on v13 is the published story | — | **Do not install `main-v13` on v16** |

Concrete break if someone benches `main-v13` on v14+: missing `bundle.js`, custom fields inserted after vanished standard fields, no `reload_doc` on Custom Field, possible `create_custom_fields` import failures. v15 branch tip is still titled “migrate to v14” in places — treat v15 as **unfinished**, not a productized upgrade path. v16 is **unassessed in-repo**.

---

## Tests

| What exists | What it does |
|---|---|
| `test_shipstation_settings.py` | Empty `unittest.TestCase` / `pass` |
| No tests for orders, shipments, items, shipping, customer, hooks | — |
| CircleCI | `npx semantic-release` on `master` only — does not run unit tests |

**Can they run without a live ShipStation account?** The stub can, and it asserts nothing. Any real test of `client()`, `get_orders`, `get_items`, `create_shipping_label`, or the FPS before-submit hook **will call the live API** unless a fake `ShipStation` is injected. There is no fixture, no `httpx` mock, no sandbox flag.

**Sandbox rule (operational):** a copied site with production Password fields is a live account. Do not press Get Orders / Get Shipments / Get Items / Shipping Label. Do not execute leftover patches. Do not enqueue `list_orders` against prod keys.

---

## Stale open PRs

### #57 — `feat: metadata import` → `main-v13`

- Open since 2022-09-21; last comment 2023-03-10 (author said they would rebase to v14).
- Adds `hours_to_fetch`, Shipstation Option mapping, and custom field factory on Settings.
- During order import it **saves Settings for every unseen option name** (write amplification + dirty Settings during sync).
- **Unsafe for FPS:** it writes item option values onto SO Item fields in the same pipeline FPS already uses for roll length/width. Two mappers, one SO. Also uses v14-oriented Virtual DocType patterns the reviewer said v13 does not support well.
- **Recommendation:** close as abandoned; do not merge onto the FPS bench.

### #80 — `feat: metadata import (updated for v14)` → `main-v14`

- Open since 2023-03-28; `mergeable_state=dirty`; last human ask to merge 2023-08-29; GitHub `updated_at` 2026-02-05 (bot/noise, not a review).
- Same product idea, not a production-hardening PR. Typo `hidded` vs `hidden` in custom field update. Deletes custom fields from session flags.
- **Recommendation:** close or leave parked. Irrelevant to FPS-on-v13. Not a v14 upgrade plan.

Neither PR adds unique indexes, status filters, watermarking, tests, or label permission checks.

---

## `shipstation-client` coupling

| Question | Finding |
|---|---|
| Pinned version? | **No.** Git `@master` on `ParsimonyGit/shipstation-client`. |
| What `list_orders` / `list_shipments` return | `Page` iterable (paginated). |
| Known gaps | No timeout/retry policy beyond `client.timeout` set by callers (30–60s). `create_label_for_order` returns raw JSON on non-200 (app then looks for `ExceptionMessage`). `Page.__len__` is page-local. Mutable default `results=[]`. Upstream master is a different Python generation than the Parsimony fork. |
| FPS extra use | `get_order` once per imported SO (rate-limit / cost). Leftover patches call `list_shipments` / `get_order` in tight loops. |

---

## Ounce → pound and COGS (prior money bugs)

**Still not safe in live code.**

`shipstation_integration/shipments.py` `create_shipment`:

```python
weight_in_ounces = shipment.weight.value
weight_in_pounds = weight_in_ounces / 16
```

No `weight.units` check. Property setter labels the parcel field “Weight (Pounds)”. If ShipStation sends pounds, new shipments are stored at 1/16th weight (carrier/compliance). If it sends ounces, the math matches the field label.

FPS `convert_ounces_to_pounds_in_shipments` already ran (it is in `patches.txt`) and divided **every** existing parcel weight by 16 once. It must never be re-applied. It did not change the live writer.

COGS: `CustomShipment.on_submit` does **not** call `Shipment.on_submit`. Status is forced to Submitted. `set_cost_of_goods` on validate sums `incoming_rate * qty` only when that DN is linked to **≤1** Shipment. Multi-package DNs report **$0 COGS** on later shipments. The backfill patch used the same function, so historical rows have the same hole.

---

## Recommended immediate actions vs hold

### Do now (operations — no feature work)

1. **Treat FPS as single-account, v13-only.** Do not add a second Shipstation Settings row. Do not install `main-v14` / `main-v15` / unbranched v16 on `fps.parsimony.com`.
2. **Do not merge #57 or #80.** Close them or label `do-not-merge / bitrot`.
3. **Do not run leftover FPS patches** on production or on a sandbox that still has production API keys — especially `create_invoices_for_delivered_orders` and `fetch_missing_shipstation_shipments`.
4. **Confirm store flags on FPS** (read-only): for VBS / marketplace stores, whether `create_sales_invoice` / `create_delivery_note` are on. If both scanner invoicing and those flags are on, the double-write path is live. Also confirm whether `amazon_seller_setup` actually exists on `Shipstation Store`.
5. **Confirm `enable_label_generation` is off** unless a named role is supposed to buy labels. Assume the JS checkbox is not a control.
6. **Sandbox copies:** rotate or blank API key/secret before any test. No Get Orders / label button / enqueue of `list_orders`.

### Hold (do not start until Product accepts the risk register)

- Any ERPNext version upgrade that includes this app.
- Enabling a second ShipStation account “because the app supports multi-account” (README is true for this repo, **false for FPS**).
- Wiring `shopify_store` or `amazon_seller_setup` on VBS stores (would silently stop SO creation or change invoice ownership).
- Metadata-import features from #57/#80.
- Re-running ounce/COGS patches.
- Relying on README “periodic product sync.”

### Fix next (engineering, after PM priority) — outcomes, not a person-assigned list

These are **product outcomes**, not a named-owner punch list:

- **Identity:** unique `shipstation_order_id` on submitted Sales Orders; treat drafts as in-flight; serialize `list_orders` (one job, one watermark).
- **Intake filter:** only import the order statuses the warehouse is allowed to pick.
- **Lookback:** persist last successful sync timestamp; stop depending on “last 24 hours.”
- **One writer for SI/DN** on FPS: either the scanner or ShipStation shipment flags, not both; `complete_deliveries` must not submit ShipStation-linked drafts the floor still owns.
- **Hook resilience:** scanner-visible SO even if roll-dimension fetch fails; dimensions must still land before pick.
- **Labels:** server-side flag + role + one-label-per-shipment guard.
- **Tests that never touch `ssapi.shipstation.com`:** mocked client; CI on `main-v13`.
- **Pin `shipstation-client` to a commit** on the Parsimony fork.

---

## Explicit non-instruction

This report is for **Product Manager** decision-making (what is unsafe, what to freeze, what to fund). It is **not** a punch list for Steve or any individual. Assignment, sequencing, and comms sit with Product.

---

## Evidence snapshot

| Artifact | Ref |
|---|---|
| App branch | `ParsimonyGit/shipstation_integration` `main-v13` @ `ea09a02` |
| FPS coupling | `ParsimonyGit/fps_customizations` `develop` (hooks, `api/selling.py`, patches) |
| Client (pinned) | `ParsimonyGit/shipstation-client` `@master` (private fork, Python ^3.8) |
| Client (upstream) | `agritheory/shipstation-client` `master` (Python 3.10–3.12) |
| Open PRs | [#57](https://github.com/ParsimonyGit/shipstation_integration/pull/57), [#80](https://github.com/ParsimonyGit/shipstation_integration/pull/80) |
| Version branches | `main-v13`, `main-v14`, `main-v15` (no v16) |
