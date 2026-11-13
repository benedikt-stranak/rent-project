# Rent project

Tools to build a property-level dataset of private rentals in Greater London for 2011, 2021 and 2026, with an estimated rental value for each property.

The data pipeline matches OS AddressBase Plus to WhenFresh/Zoopla rental listings, identifies privately rented properties using Census small-area tenure counts, and estimates rents.

This is a first working version.


## Data

This repository contains code only. The source data is licensed or safeguarded and cannot be redistributed.

| Source | Access |
|---|---|
| OS AddressBase Plus (2011, 2021 and 2026 epochs) | Research data agreement with Ordnance Survey |
| WhenFresh/Zoopla Property Rentals, 2014–2024 | Safeguarded, via the HASP Data Service |
| Census 2011 (QS405EW) and 2021 (TS054) tenure, output area level | Open (ONS) |
| ONS Price Index of Private Rents | Open (ONS) |
| OA to LSOA to LAD lookups, OA boundaries | Open (ONS Open Geography Portal) |


## Setup

Requires Python >= 3.12 and [uv]

```bash
uv sync
mkdir data
```

`data/` is gitignored. Place source files following the paths in `src/rent_project/config.py`:


## Usage

```bash
uv run build-dataset
```

Each step writes a parquet file and is skipped if that file already exists, so the pipeline can be resumed after an interruption. To rerun a step, delete its output and the outputs of all later steps. Otherwise, the later steps will be skipped and keep their old results.

The final dataset is written to `data/processed/greater_london_rents_dataset.parquet`.


## Pipeline

`main()` in `pipelines/build_dataset.py` runs seven steps in order. Interim outputs go to `data/interim/address-base-plus/`.

1. **Build the 2026 AddressBase file** (`step_build_addressbase_2026`). Unzips the 2026 tiles and stacks them into a single CSV. The 2011 and 2021 epochs already arrive as single files.
   Output: `raw/address-base-plus/2026/greater_london_2026_abplus.csv`

2. **Clip and harmonise each epoch** (`step_clip_and_harmonise_addressbase`, run once per year). Keeps addresses whose coordinates fall inside a Greater London output area (2011 OAs for 2011, 2021 OAs for 2021 and 2026) and adds OA, LSOA and LAD codes. It then renames the pre-epoch-39 columns in 2011 to their later names and keeps a common set of columns. Finally it adds `is_residential_space`, which is true where the AddressBase `class` is `R` (residential, unclassified) or starts with `RD` (dwelling) or `RH` (house in multiple occupation).
   Output: `greater_london_<year>_abplus_harmonised.parquet`

3. **Build the spine and address list** (`step_build_spine_and_addresses`). Combines the three epochs into a spine with one row per UPRN, recording `is_residential_<year>` and `state_<year>` for each epoch. Coordinates and 2021 area codes come from the latest epoch the UPRN appears in, and 2011 codes from 2011 only. The spine is then filtered to UPRNs that were residential with `state` 2 (in use), 3 (vacant or derelict) or missing in at least one epoch. This drops addresses that were only ever under construction (1), no longer existing (4) or with planning permission granted (6). The address list holds every distinct address string for each UPRN: built from the local authority fields in all epochs, and from the Royal Mail fields in 2021 and 2026.
   Output: `greater_london_abplus_spine.parquet`, `greater_london_abplus_addresses.parquet`

4. **Match Zoopla property IDs** (`step_match_hasp_property_id`). Matches WhenFresh/Zoopla property addresses to the address list with [uk_address_matcher](https://github.com/moj-analytical-services/uk_address_matcher), using its exact, peeled-address and unique-trigram stages. The probabilistic Splink stage is currently disabled. UPRNs matched by more than one Zoopla property are left unmatched.
   Output: `greater_london_abplus_spine_hasp.parquet`

5. **Flag privately rented properties** (`step_add_private_rented`). For each 2011 and 2021 output area, counts occupied dwellings in the spine (residential, with `state` 2 or missing) and multiplies them by the Census share of households renting privately to get a target. Occupied dwellings are then flagged as private rented until the target is reached: those matched to a Zoopla property first, then others at random (seed 0). If an OA has fewer occupied dwellings than its target, all are flagged.
   Output: `greater_london_abplus_spine_private_rented.parquet`

6. **Add rents** (`step_add_rents`). Drops listings outside £10–£10,000 per week and attaches one annual listed rent per property per listing year (weekly price × 52). For each target year (2011, 2014, 2021 and 2024), it takes the listing nearest in time, with ties going to the earlier year, and scales it by the local authority's cumulative rent growth between the two years. Properties flagged as private rented in 2011 or 2021 that have no listing get the unweighted mean of the 8 nearest properties with listings within 1 km. Imputed values are never used as donors.
   Output: `greater_london_abplus_spine_rents.parquet`

7. **Save the final dataset** (`step_save_processed_spine`). Copies the finished spine to the processed folder.
   Output: `data/processed/greater_london_rents_dataset.parquet`

Code is in `src/rent_project/`: data loading and cleaning in `sources/`, rent and tenure modelling in `models/`, and the orchestration in `pipelines/build_dataset.py`. Exploratory work is in `notebooks/` (see `data-checks.qmd`).


## Known limitations

- The number of residential units is higher than MHCLG estimates. A likely contributor is the `class` rule, which may count both an HMO parent record and the units within it.
- The number of privately rented units is further overestimated. Because targets are based on the spine's own dwelling counts, any overcount of residential units carries through. In addition, vacant/second homes are identified only through AddressBase `state` 3.
- Allocating private-rented status within an output area is approximate. Not every rental appears in the Zoopla data; not every listing matches an address; property matched to a Zoopla listing in any year is prioritised, but in reality tenure may have changed over time.
- Imputed rents ignore property characteristics.
- Estimated average rents are higher than the ONS Price Index of Private Rents, as expected (listings vs existing tenancies, asking vs achieved rents).
