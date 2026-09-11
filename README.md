# Rent project

Tools to construct lists of residential addresses in the UK from OS AddressBase Plus epoch files and to estimate individual property prices and rental values.

## Setup

Requires Python >= 3.12

```bash
uv sync
mkdir data
```

The repo does not include any of the source datasets, as these include licensed and safeguarded datasets:
- OS AddressBase Plus 2011, 2021 and 2026 epochs
- HASP WhenFresh/Zoopla Property Rentals
- Land Registry Price Paid
- EPC

`data/` is gitignored.
