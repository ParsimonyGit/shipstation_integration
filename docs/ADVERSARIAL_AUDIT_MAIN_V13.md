# Adversarial QA/QC Audit — `shipstation_integration` (`main-v13`)

**Audience:** Product Manager (fulfillment / ERP) and Repo Boss (routing only). Not an engineering task list.  
**Scope:** Read-only review of `ParsimonyGit/shipstation_integration` @ `main-v13` (`ea09a02`), cross-checked against production coupling in `ParsimonyGit/fps_customizations` @ `develop` on **fps.parsimony.com**.  
**Date:** 2026-08-23 (addendum folded same day)  
**Constraint honored:** No merge, no deploy, **no migrate recommendation**, no live ShipStation API calls.

Docs in the README were treated as untrusted. Claims below are from code.

### Routing legend (Repo Boss)

Use the **Route** column to hand work to the right repo **via Product Manager**. Do not assign people from this document.

| Tag | Meaning |
|---|---|
| `SS` | Finding lives in `shipstation_integration` (`main-v13`) |
| `FPS` | Finding lives in `fps_customizations` (`develop`) — route to FPS via PM |
| `BOTH` | Split: integration contract here, production writer/hook there |
| `SCANNER` | Touches the must-protect warehouse scanner contract (see below) |
| `HOLD` | Do not ship / do not migrate / do not merge |

### Must-protect scanner contract (do not remove or “simplify”)

Verified on FPS `develop`. **Keep these behaviors.** Any `SS` change that stops firing the hook, changes its arguments `(store, so)`, or submits the SO before the hook returns, **breaks the floor**.

| Surface | Path | Contract |
|---|---|---|
| Scan lookup | `fps_customizations/api/selling.py` `check_sales_order` | Accepts Sales Order **name** **or** `shipstation_order_id`; requires `docstatus=1`; refuses fully delivered stock qty |
| Roll L/W | hook `update_shipstation_order_before_submit` → `fps_customizations/hook_events/sales_order.py` `update_order_item_details` | Writes `order_roll_length` / `order_roll_width` (and custom-order description) onto SO items **before submit** |
| Writer | `shipstation_integration/orders.py` `create_erpnext_order` | `save` → hook `(store, so)` → `save` → `submit` |

Resilience work (catch API errors so the SO still submits) is allowed **only if** roll L/W still lands when ShipStation options exist. Do **not** propose deleting this hook.

---

## Executive stand

This app is **not safe to treat as a finished production integration**. On **fps.parsimony.com** it is the order-intake pipe for warehouse scanners (`check_sales_order` + protected roll L/W hook). Sync is a 24-hour UTC poll with **no unique constraint**, **no order-status filter**, and **idempotency keyed by `shipstation_order_id` on submitted docs only**. FPS re-queues the same `list_orders` job on scheduler `all` (dedupe via `is_job_queued`) on the **same DO box** as warehouse scans, stretching the long queue with one extra live `get_order` per SO. That combination can duplicate Sales Orders, import cancelled/on-hold orders, miss anything older than 24 hours, and — when scanner invoicing, ShipStation shipment flags, `DN.on_submit` → `create_shipment`, and `daily_long` `complete_deliveries` overlap — double-write Delivery Notes or Sales Invoices. `CustomShipment.on_submit` only `db_set`s status Submitted. Label generation is a paid API call gated only in JavaScript. Leftover FPS fire-drill scripts are not in `patches.txt`. Tests are an empty stub. PRs #57 and #80 are bitrot. **Do not migrate this site off ERPNext v13. Do not add a second ShipStation Settings account. Do not run leftover patches. Do not break the roll L/W hook.** Stabilize identity and dual-write paths on v13 in place.

---

## Verdict table

| Area | Verdict | Severity | Route | Why it matters on FPS |
|---|---|---|---|---|
| Order identity / duplicates | **FAIL** | Critical | `BOTH` + `SCANNER` | No unique index; exists-check is `docstatus=1` only; FPS re-queues `list_orders` on `all` on the same DO box as scans |
| Cancelled / on-hold import | **FAIL** | Critical | `SS` + `SCANNER` | No `orderStatus` filter; cancelled SS orders become submitted SOs the floor can scan |
| 24-hour lookback + UTC | **FAIL** | High | `SS` + `SCANNER` | Missed jobs permanently drop orders; scanners show “no submitted order” |
| Same-box queue contention | **FAIL** | High | `FPS` + `SCANNER` | `enqueue_list_orders` + hook `get_order` share the long queue with warehouse-scan load |
| Split / multi-package shipments | **FAIL** | High | `SS` | SI / DN / Shipment idempotency is by **order id**, not shipment id |
| Label generation (money) | **FAIL** | High | `SS` | Whitelisted; `enable_label_generation` is client-side only |
| Scanner hook failure → draft SO | **FAIL** | Critical | `BOTH` + `SCANNER` | Live `get_order` in protected hook; uncaught exception leaves draft; **do not remove the hook** |
| Dual invoice / DN paths | **FAIL** | Critical | `BOTH` + `SCANNER` | Scanner SI + SS poll + `DN.on_submit` → `create_shipment` + `complete_deliveries` |
| `CustomShipment.on_submit` | **WARN** | Medium | `FPS` | Only `db_set` status Submitted; skips parent `Shipment.on_submit` |
| Single-account assumption | **FAIL** | High | `FPS` | Integration loops all settings; FPS `get_last_doc` hits the wrong account if a second row exists |
| Leftover fire-drill scripts | **FAIL** | Critical | `FPS` | Not in `patches.txt`; live API or mass invoices |
| Ounce → pound (live writer) | **FAIL** | High | `BOTH` | `shipments.py` still `/16` with no unit; FPS patch was a one-time backfill |
| COGS on Shipment | **WARN** | Medium | `FPS` | $0 COGS when a DN already has more than one Shipment |
| Shopify-via-ShipStation (VBS) | **PASS** | — | `BOTH` | Stores “VBS Amazon”, “Vapor Barrier Supply” stay on SS path; do not wire `shopify_store` |
| `mark_items_for_purchase` | **PASS** | — | `FPS` | Store custom field + `update_shipstation_item_before_save`; new items only |
| Settings API secret storage | **WARN** | Medium | `SS` | Password fields; `in_list_view`; System Manager full access |
| Product sync | **WARN** | Medium | `SS` | README claims periodic fetch; only a manual button |
| Tests / CI | **FAIL** | High | `SS` | Empty `TestCase`; CircleCI on obsolete `master` |
| ERPNext v14 / v15 / v16 | **FAIL** | High | `HOLD` | Do **not** migrate `fps.parsimony.com`; v13 assets/fields break on v14+ |
| PRs #57 / #80 | **FAIL** | High | `HOLD` | Bitrot; #57 would fight the protected roll L/W hook |
| `shipstation-client` pin | **WARN** | High | `SS` | Git `@master`; upstream AgriTheory is Python 3.10+ |
| Warehouse filter / `since_date` | **PASS** | — | `SS` | Empty warehouse list means all warehouses (field description) |
| Amazon hook off-ramp | **WARN** | Medium | `BOTH` | `amazon_seller_setup` is not on this app’s Store DocType; FPS invoicing reads it |

---

## Repo Boss routing (via Product Manager)

Findings that **touch `fps_customizations` or the scanner** — route to FPS through PM. Findings tagged `SS` only can stay on this repo.

| Finding | Route | FPS / scanner touch |
|---|---|---|
| Duplicate SOs from overlapping `list_orders` | `BOTH` + `SCANNER` | FPS `enqueue_list_orders` on `all` + same-box long queue; scanner sees first submitted SO |
| Same-box scan vs sync contention | `FPS` + `SCANNER` | `is_job_queued` does not protect warehouse request workers from long-queue saturation |
| Hook throw → draft SO | `BOTH` + `SCANNER` | **Protect** `update_shipstation_order_before_submit`; harden caller + hook, do not remove |
| Dual SI/DN + `complete_deliveries` | `BOTH` + `SCANNER` | Scanner `create_delivery_note`; FPS `DN.on_submit` → `create_shipment`; `daily_long` auto-submit |
| `CustomShipment.on_submit` status-only | `FPS` | Override skips parent submit behavior |
| Single-account / `get_last_doc` | `FPS` | Explicit “one instance” comments; leftover patches same assumption |
| Fire-drills not in `patches.txt` | `FPS` | `fetch_missing_shipstation_shipments`, `update_shipstation_order_details`, `create_invoices_for_delivered_orders` |
| Ounce/COGS historical patches | `BOTH` | Live `/16` is `SS`; one-time patches + COGS math are `FPS` |
| VBS Shopify-via-SS | `BOTH` | Do not add `shopify_store` on “VBS Amazon” / “Vapor Barrier Supply” |
| `mark_items_for_purchase` | `FPS` | Custom field + `update_shipstation_item_before_save`; new items only |
| v13→v16 / #57 / #80 | `HOLD` | Do **not** migrate fps.parsimony.com; #57 fights protected roll L/W |

---

## Architecture (FPS production, not the README)

```
ShipStation API
    ^
    |  hourly_long: list_orders + list_shipments          [SS]
    |  scheduler all: enqueue_list_orders (if not queued) [FPS]  ← same DO box as scanners
    v
create_erpnext_order
    save SO (draft)
    → update_shipstation_order_before_submit  [FPS, PROTECT]
         client.get_order → order_roll_length / order_roll_width
    save + submit SO
    → check_sales_order(name | shipstation_order_id)      [FPS scanner]
    → create_delivery_note (often invoices here)          [FPS scanner]
    → DN.on_submit → enqueue _create_shipment             [FPS]
         get_last_doc(Shipstation Settings)               [FPS single-account]
         create_erpnext_shipment (SI/DN/Shipment flags)   [SS]
    → CustomShipment.on_submit = db_set status only       [FPS]
    → daily_long complete_deliveries submits draft DNs    [FPS]
```

README “multi-account + periodic products” is **not** the FPS architecture. FPS is **one** Shipstation Settings row; products are manual; Shopify marketplace volume for VBS is this path, not `shopify_integration`.

---

## Top 10 risks (with paths)

### 1. Duplicate Sales Orders (money + warehouse chaos) — `BOTH` + `SCANNER`

**Paths:** `shipstation_integration/orders.py` (`validate_order`, `create_erpnext_order`); `fps_customizations/hooks.py` (`scheduler_events["all"]`); `fps_customizations/hook_events/shipstation.py` (`enqueue_list_orders`); `parsimony/utils/__init__.py` (`is_job_queued`).

`validate_order` only skips if a **submitted** Sales Order already has that `shipstation_order_id`. There is no unique index. `create_erpnext_order` saves, optionally runs the FPS hook, submits, then `frappe.db.commit()`. Two overlapping workers that both pass the exists-check create two submitted SOs for one marketplace order.

FPS makes this likely: `shipstation_integration` already runs `list_orders` on `hourly_long`, and FPS **re-enqueues the same method** on scheduler `all` (~every 4 minutes) if `is_job_queued(..., queue="long")` is false. `is_job_queued` only inspects RQ jobs whose `job_name` equals that string **and** whose queue name contains `"long"`. It does not serialize against a scheduler tick that has not yet appeared in RQ, and it does not lock the database.

**Same DO box as warehouse scans:** `list_orders` plus the protected hook’s extra `get_order` per SO occupy the **long** queue on the same machine that serves scanner HTTP (`check_sales_order` / `create_delivery_note`). Deduping the job name does not stop CPU, DB, or ShipStation rate-limit contention with pickers. A long-running sync widens the duplicate-SO window **and** slows scan lookups.

**FPS / scanner impact:** `check_sales_order` returns the first matching submitted SO. Pickers can fulfill one copy while billing/stock land on the other.

### 2. Cancelled / on-hold / unpaid ShipStation orders become live ERP orders — `SS` + `SCANNER`

**Path:** `shipstation_integration/orders.py` (`list_orders` parameters).

Parameters sent: `store_id`, `modify_date_start`, `modify_date_end`. No `orderStatus`. ShipStation will return cancelled, on-hold, and awaiting-payment orders. Those pass `validate_order` and are submitted. That is unearned revenue and phantom demand on inventory. Those SOs are then **scan-eligible** via `check_sales_order`.

### 3. Anything older than 24 hours UTC is silently dropped — `SS` + `SCANNER`

**Path:** `shipstation_integration/orders.py` lines 61–76; same pattern in `shipments.py` lines 60–80.

Lookback is `datetime.utcnow() - 24h`, hardcoded. Comment admits the API “behaves oddly” on shorter windows. If a job fails, the queue backs up (including behind warehouse-scan load), or ShipStation rate-limits past that window, those orders **never retry**. Scanners then return *“No submitted order found against this ID”*. There is no cursor / watermark stored on Shipstation Settings.

### 4. Protected scanner hook fails closed (draft SO) — `BOTH` + `SCANNER`

The FPS hook calls `settings.client().get_order(so.shipstation_order_id)` and maps option names containing `length` / `width` onto `order_roll_length` / `order_roll_width`. Those fields drive CTO BOM matching in `get_active_boms`.

If `get_order` throws (timeout, 429, 401), the exception is **not** caught in `create_erpnext_order` (only `frappe.LinkValidationError` is). The SO remains **draft**. Scanners only query `docstatus=1`. Floor result: barcode / SS order id does nothing, while the order sits in drafts.

**Protect, do not remove:** keep `update_shipstation_order_before_submit` → `update_order_item_details(store, so)`. Allowed change is resilience (SO still submits; retry L/W) without changing hook name, signature, or field writes. Merging PR #57 option-mapping onto the same items **is** a break of this contract.

### 5. Double Delivery Note / double Sales Invoice (money + inventory) — `BOTH` + `SCANNER`

Three writers exist on the same SO:

1. **Warehouse scanner** — `fps_customizations/api/selling.py` `create_delivery_note` creates and submits a Sales Invoice for any store that is **not** (`is_amazon_store` **and** `amazon_seller_setup`), then builds a DN (draft or submitted).
2. **ShipStation shipment poll** — `shipstation_integration/shipments.py` `create_erpnext_shipment` optionally creates SI + DN + Shipment. Idempotency for SI and DN is **submitted row by `shipstation_order_id`**, not shipment id. **Draft DNs do not count.**
3. **Daily auto-submit** — `fps_customizations/hook_events/delivery_note.py` `complete_deliveries` (`daily_long`) submits **all** matching draft DNs site-wide. `DN.on_submit` then enqueues `_create_shipment`, which calls `create_erpnext_shipment` again.

Race that hurts: ShipStation poll submits a DN while the scanner still holds a draft DN for the same order → two DNs, stock issued twice. Invoice race is partially mitigated if an SI already exists for that order id, but the scanner path does not look up by `shipstation_order_id` — it uses `per_billed < 100`. A second SI is possible if the first is still in draft or `per_billed` has not updated.

`amazon_seller_setup` is **not** a field on this app’s `Shipstation Store` DocType. FPS reads it anyway. If the Amazon app did not add that custom field, the guard is always false and **Amazon-named stores get invoiced by the scanner**.

### 6. Paid labels can be purchased by any logged-in Desk user — `SS`

**Paths:** `shipstation_integration/shipping.py` `create_shipping_label` / `_create_shipping_label`; `public/js/shipping.js`.

`enable_label_generation` is checked only in JS. The server checks `settings.enabled`, then calls `client.create_label_for_order`. No idempotency. Repeat clicks = repeat carrier charges. Method is `@frappe.whitelist()` with no role decorator.

`push_attachment_update` publishes `eval_js` with the attachment name interpolated into JavaScript. That is a separate desk-security defect.

### 7. Multi-shipment / split orders are discarded after the first — `SS`

**Path:** `shipstation_integration/shipments.py` `create_sales_invoice`, `create_delivery_note`, `create_shipment`.

Comments in `orders.py` say split ShipStation orders are intentionally not imported so ERP can have multiple DNs against one SO. The shipment writer then **refuses** a second SI/DN/Shipment for the same `shipstation_order_id`. Partial marketplace fulfillments after the first package do not land. Inventory and freight cost go missing.

Voided shipments call `cancel()` on SI / DN / Shipment. If the SI is paid or the DN is billed, cancel throws and the rest of that store’s shipment batch stops (no per-shipment try/except in `list_shipments`).

### 8. A second ShipStation Settings document breaks FPS — `FPS`

**Integration:** `list_orders` / `list_shipments` iterate **all** `enabled` settings. That part scales.

**FPS (explicit comments: “FPS only has one Shipstation instance”):**

- `get_last_doc("Shipstation Settings")` in `delivery_note._create_shipment` and in leftover patches
- `set_roll_length_in_orders.py`, `set_ordered_items_for_custom_orders.py`, `update_shipment_amount_in_shipments.py`, `fetch_missing_shipstation_shipments.py`

`get_last_doc` is “most recently modified,” not “the enabled one,” not “the one on this DN.” A sandbox or second account silently retargets warehouse shipment creation and any fire-drill.

### 9. Leftover fire-drill scripts are live-API / mass-money bombs — `FPS`

**`fps_customizations/patches.txt` does not list these** (they will not run on migrate, but they are importable and look like patches). **Do not add them to `patches.txt` and do not migrate to “clean this up.”**

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

### 10. Client pin + empty tests = no safety net — `SS`

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

Shopify traffic for **“VBS Amazon”** and **“Vapor Barrier Supply”** is ShipStation-store intake, not `shopify_integration`. On this app, `is_shopify_store` is set when the marketplace name contains `"Shopify"`, but `validate_order` only diverts if `store.shopify_store` is set — and **that field does not exist** on `shipstation_store.json`. Those orders stay on this create-SO path. That matches the FPS design. **Do not add a `shopify_store` link on those rows** (would skip SO create and starve the scanner).

`mark_items_for_purchase` is an FPS custom field on `Shipstation Store` (`fps_customizations/setup.py`). `update_shipstation_item_before_save` → `mark_item_as_purchase` sets `is_purchase_item` **only when `item.is_new()`**, so a later SS match on an existing SKU will not flip purchase flags. Route: `FPS`.

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

**Do not migrate `fps.parsimony.com`.** This audit is not a green light to move FPS to `main-v14` / `main-v15` / v16. The protected scanner hook, `CustomShipment` override, `mark_items_for_purchase`, and `enqueue_list_orders` are v13-era FPS coupling. A version jump is a separate Product decision after identity and dual-write FAILs are closed **in place**.

---

## Tests

| What exists | What it does |
|---|---|
| `test_shipstation_settings.py` | Empty `unittest.TestCase` / `pass` |
| No tests for orders, shipments, items, shipping, customer, hooks | — |
| CircleCI | `npx semantic-release` on `master` only — does not run unit tests |

**Can they run without a live ShipStation account?** The stub can, and it asserts nothing. Any real test of `client()`, `get_orders`, `get_items`, `create_shipping_label`, or the FPS before-submit hook **will call the live API** unless a fake `ShipStation` is injected. There is no fixture, no `httpx` mock, no sandbox flag.

**Sandbox rule (operational, FPS):** a copied site of fps.parsimony.com with production Password fields **is** the live ShipStation account. Blank or rotate keys before any use. Do not press Get Orders / Get Shipments / Get Items / Shipping Label. Do not execute leftover patches. Do not enqueue `list_orders` against prod keys. Do not run `bench migrate` as a way to “apply the audit.”

---

## Stale open PRs

### #57 — `feat: metadata import` → `main-v13`

- Open since 2022-09-21; last comment 2023-03-10 (author said they would rebase to v14).
- Adds `hours_to_fetch`, Shipstation Option mapping, and custom field factory on Settings.
- During order import it **saves Settings for every unseen option name** (write amplification + dirty Settings during sync).
- **Unsafe for FPS / scanner:** it writes item option values onto SO Item fields in the same pipeline as the **protected** roll L/W hook. Two mappers, one SO. Also uses v14-oriented Virtual DocType patterns the reviewer said v13 does not support well.
- **Recommendation:** close as abandoned; do not merge onto the FPS bench. Merging it is a scanner-contract break.

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

## Ship vs hold

### Ship (operations only — no code, no migrate)

| Action | Route |
|---|---|
| Keep **one** Shipstation Settings row on fps.parsimony.com | `FPS` |
| Stay on ERPNext v13 + `main-v13`. **Do not migrate.** | `HOLD` |
| Do not merge #57 or #80 (scanner-contract / bitrot) | `HOLD` |
| Do not execute leftover FPS scripts, especially `create_invoices_for_delivered_orders` and `fetch_missing_shipstation_shipments` | `FPS` |
| Read-only confirm: store flags `create_sales_invoice` / `create_delivery_note` vs scanner invoicing; whether `amazon_seller_setup` exists | `BOTH` |
| Confirm `enable_label_generation` off unless a named role is meant to buy labels | `SS` |
| Sandbox copies: blank API key/secret **before** bench copy is used. No Get Orders / labels / `list_orders` enqueue / leftover patches | `BOTH` |
| Do not add `shopify_store` on “VBS Amazon” or “Vapor Barrier Supply” | `BOTH` + `SCANNER` |
| Do not re-run ounce or COGS patches | `FPS` |

### Hold (not a migrate plan)

- Any ERPNext / Frappe version upgrade of fps.parsimony.com.
- A second ShipStation account (“the app supports multi-account” is true for this repo, **false for FPS**).
- Removing, renaming, or bypassing `update_shipstation_order_before_submit`.
- Metadata import from #57/#80.
- “Periodic product sync” as documented in the README (it is not scheduled).

### Later outcomes (after PM priority) — not a person list

Keep the scanner contract. These are **outcomes**, not assignments:

| Outcome | Route | Constraint |
|---|---|---|
| Unique `shipstation_order_id`; drafts in-flight; one serialized `list_orders` + watermark | `BOTH` | Must still call the protected hook with `(store, so)` before submit |
| Import only pickable order statuses | `SS` | Scanners must not see cancelled SOs |
| One SI/DN writer on FPS; `complete_deliveries` must not steal floor drafts | `FPS` + `SCANNER` | |
| Hook **resilience** (SO still submits if `get_order` fails; L/W retry) | `BOTH` + `SCANNER` | **Do not remove the hook** |
| Reduce same-box contention (queue isolation or backoff during scan hours) | `FPS` | |
| Server-side label flag + role + one label per shipment | `SS` | |
| Mocked tests that never hit live ShipStation; pin client to a commit | `SS` | |

---

## Explicit non-instruction

This report is for **Product Manager** decision-making (what is unsafe, what to freeze, what to fund). **Repo Boss** uses the Route tags to send `FPS` / `SCANNER` items to the FPS repo **through Product**, not as a side channel. It is **not** a punch list for Steve or any individual. Assignment, sequencing, and comms sit with Product. **Do not migrate.**

---

## Evidence snapshot

| Artifact | Ref |
|---|---|
| App branch | `ParsimonyGit/shipstation_integration` `main-v13` @ `ea09a02` |
| FPS site | fps.parsimony.com — `fps_customizations` `develop` (hooks, `api/selling.py`, patches). **Do not migrate.** |
| Addendum | Product / Repo Boss: route `FPS`/`SCANNER` via PM; protect roll L/W hook; same-DO-box `enqueue_list_orders` |
| Client (pinned) | `ParsimonyGit/shipstation-client` `@master` (private fork, Python ^3.8) |
| Client (upstream) | `agritheory/shipstation-client` `master` (Python 3.10–3.12) |
| Open PRs | [#57](https://github.com/ParsimonyGit/shipstation_integration/pull/57), [#80](https://github.com/ParsimonyGit/shipstation_integration/pull/80) |
| Version branches | `main-v13`, `main-v14`, `main-v15` (no v16) |
