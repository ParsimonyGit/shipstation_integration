import frappe


def get_marketplace(id=None, name=None, region=None, domain=None):
	if id in MARKETPLACES:
		return frappe._dict(MARKETPLACES[id])

	if name:
		for data in MARKETPLACES.values():
			if data["name"] == name:
				return frappe._dict(data)
	if region:
		for data in MARKETPLACES.values():
			if data["region"] == region:
				return frappe._dict(data)

	if domain:
		for data in MARKETPLACES.values():
			if data["domain"] == domain:
				return frappe._dict(data)

	return frappe._dict()


MARKETPLACES = {
	"A2EUQ1WTGCTBG2": {
		"name": "Canada",
		"domain": "amazon.ca",
		"currency": "CAD",
		"id": "A2EUQ1WTGCTBG2",
		"region": "CA",
		"sales_partner": "Amazon Canada",
		"default_zip_code": "M4B 3N6",
	},
	"A1AM78C64UM0Y8": {
		"name": "Mexico",
		"domain": "amazon.com.mx",
		"currency": "MXN",
		"id": "A1AM78C64UM0Y8",
		"region": "MX",
		"sales_partner": "Amazon Mexico",
		"default_zip_code": "06140",
	},
	"ATVPDKIKX0DER": {
		"name": "United States",
		"domain": "amazon.com",
		"currency": "USD",
		"id": "ATVPDKIKX0DER",
		"region": "US",
		"sales_partner": "Amazon US",
		"default_zip_code": "90001",
	},
	"A1F83G8C2ARO7P": {
		"name": "United Kingdom",
		"domain": "amazon.co.uk",
		"currency": "GBP",
		"id": "A1F83G8C2ARO7P",
		"region": "UK",
		"sales_partner": "Amazon UK",
		"default_zip_code": "WC1B 5BE",
	},
	"A1RKKUPIHCS9HS": {
		"name": "Spain",
		"domain": "amazon.es",
		"currency": "EUR",
		"id": "A1RKKUPIHCS9HS",
		"region": "ES",
		"sales_partner": "Amazon Spain",
	},
	"A1VC38T7YXB528": {
		"name": "Japan",
		"domain": "amazon.co.jp",
		"currency": "JPY",
		"id": "A1VC38T7YXB528",
		"region": "JP",
		"sales_partner": "Amazon Japan",
	},
	"APJ6JRA9NG5V4": {
		"name": "Italy",
		"domain": "amazon.it",
		"currency": "EUR",
		"id": "APJ6JRA9NG5V4",
		"region": "IT",
		"sales_partner": "Amazon Italy",
	},
	"A21TJRUUN4KGV": {
		"name": "India",
		"domain": "amazon.in",
		"currency": "INR",
		"id": "A21TJRUUN4KGV",
		"region": "IN",
		"sales_partner": "Amazon India",
	},
	"A1PA6795UKMFR9": {
		"name": "Germany",
		"domain": "amazon.de",
		"currency": "EUR",
		"id": "A1PA6795UKMFR9",
		"region": "DE",
		"sales_partner": "Amazon Germany",
	},
	"A13V1IB3VIYZZH": {
		"name": "France",
		"domain": "amazon.fr",
		"currency": "EUR",
		"id": "A13V1IB3VIYZZH",
		"region": "FR",
		"sales_partner": "Amazon France",
	},
	"AAHKV2X7AFYLW": {
		"name": "China",
		"domain": "amazon.cn",
		"currency": "CNY",
		"id": "AAHKV2X7AFYLW",
		"region": "CN",
		"sales_partner": "Amazon China",
	},
	"A2Q3Y263D00KWC": {
		"name": "Brazil",
		"domain": "amazon.com.br",
		"currency": "BRL",
		"id": "A2Q3Y263D00KWC",
		"region": "BR",
		"sales_partner": "Amazon Brazil",
	},
	"A39IBJ37TRP1C6": {
		"name": "Australia",
		"domain": "amazon.com.au",
		"currency": "AUD",
		"id": "A39IBJ37TRP1C6",
		"region": "AU",
		"sales_partner": "Amazon Australia",
	},
	"A17E79C6D8DWNP": {
		"name": "Saudi Arabia",
		"domain": "amazon.sa",
		"currency": "SAR",
		"id": "A17E79C6D8DWNP",
		"region": "SA",
		"sales_partner": "Amazon Saudi Arabia",
	},
	"A1805IZSGTT6HS": {
		"name": "Netherlands",
		"domain": "amazon.nl",
		"currency": "ANG",
		"id": "A1805IZSGTT6HS",
		"region": "NL",
		"sales_partner": "Amazon Netherlands",
	},
	"A19VAU5U5O7RUS": {
		"name": "Singapore",
		"domain": "amazon.sg",
		"currency": "SGD",
		"id": "A19VAU5U5O7RUS",
		"region": "SG",
		"sales_partner": "Amazon Singapore",
	},
	"A2NODRKZP88ZB9": {
		"name": "Sweden",
		# "domain": "amazon.se",  # TODO: set this when it exists
		"currency": "SEK",
		"id": "A2NODRKZP88ZB9",
		"region": "SE",
		"sales_partner": "Amazon Sweden",
	},
	"A2VIGQ35RCS4UG": {
		"name": "United Arab Emirates",
		"domain": "amazon.ae",
		"currency": "AED",
		"id": "A2VIGQ35RCS4UG",
		"region": "AE",
		"sales_partner": "Amazon United Arab Emirates",
	},
	"A33AVAJ2PDY3EV": {
		"name": "Turkey",
		"domain": "amazon.com.tr",
		"currency": "TRY",
		"id": "A33AVAJ2PDY3EV",
		"region": "TR",
		"sales_partner": "Amazon Turkey",
	},
	"ARBP9OOSHTCHU": {
		"name": "Egypt",
		# "domain": "amazon.eg",  # TODO: set this when it exists
		"currency": "EGP",
		"id": "ARBP9OOSHTCHU",
		"region": "EG",
		"sales_partner": "Amazon Egypt",
	},
}
