# Shipstation Integration

A custom ShipStation application built on top of the [Frappe](https://github.com/frappe/frappe) framework and [ERPNext](https://github.com/frappe/erpnext).

## Features

The following workflows are available in this application:

- Sync multiple ShipStation accounts with a single ERPNext instance.
- Configure individual stores in each ShipStation account to different companies, warehouses, cost centers and account heads.
- Periodically fetch products, orders and shipments from all ShipStation accounts.
- Identify stores connected to the Amazon marketplace, and add hooks for other Frappe applications to process Amazon orders.
- Shipping label generation (can be enabled per Shipstation account)

## Installation

```bash
# get the application onto your bench
bench get-app https://github.com/ParsimonyGit/shipstation_integration

# install the application onto a new site
bench --site <site_name> install-app shipstation_integration
```

## Contribution

Contributions are welcome! Please see the [contribution guidelines](CONTRIBUTING.md) for more information.

## Dependencies

- [ShipStation Python client](https://github.com/agritheory/shipstation-client) by [AgriTheory](https://github.com/agritheory)

## License

[MIT](https://opensource.org/licenses/MIT)