# ShipStation Integration

A custom ShipStation application built on top of the [Frappe](https://github.com/frappe/frappe) framework and [ERPNext](https://github.com/frappe/erpnext).

## Compatibility

The default branch (`main-v13`) targets **Frappe / ERPNext v13**.

## Features

The following workflows are available in this application:

- Sync multiple ShipStation accounts with a single ERPNext instance.
- Configure individual stores in each ShipStation account to different companies, warehouses, cost centers and account heads.
- Periodically fetch products, orders and shipments from all ShipStation accounts.
- Identify stores connected to the Amazon marketplace, and add hooks for other Frappe applications to process Amazon orders.
- Shipping label generation (can be enabled per ShipStation account)

## Installation

```bash
# get the application onto your bench (v13 branch)
bench get-app https://github.com/ParsimonyGit/shipstation_integration --branch main-v13

# install the application onto a site
bench --site <site_name> install-app shipstation_integration

# apply migrations after install or upgrade
bench --site <site_name> migrate
```

## Configuration

After installation, open **ShipStation Settings** in the desk to:

1. Connect one or more ShipStation accounts (API key / secret).
2. Map each ShipStation store to the right company, warehouse, cost center, and account heads.
3. Enable scheduled sync and optional shipping label generation per account.

## Dependencies

- [ShipStation Python client](https://github.com/agritheory/shipstation-client) by [AgriTheory](https://github.com/agritheory)

## License

[MIT](https://opensource.org/licenses/MIT)
