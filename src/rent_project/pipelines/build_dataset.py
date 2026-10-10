"""Pipeline: build the AddressBase Plus address dataset.

Run with: uv run build-dataset
"""

import pandas as pd

from rent_project.config import (
    ADDRESSBASE_DIRECTORY_INTERIM,
    ADDRESSBASE_DIRECTORY_RAW,
    HASP_DIRECTORY,
    LOOKUP_DIRECTORY,
    OA_DIRECTORY,
)
from rent_project.models.models import (
    add_private_rented,
)
from rent_project.sources.addressbase import (
    add_area_codes,
    add_is_residential,
    align_columns,
    build_address_list,
    build_addressbase_spine,
    clip_to_output_areas,
    filter_addressbase_spine,
    load_and_concatenate,
    load_full_addressbase,
    load_harmonised_addressbase,
    load_oa_boundaries,
    load_oa_lookup,
    load_schema_new,
    load_schema_old,
    rename_columns,
    unzip_all,
)
from rent_project.sources.census import (
    oa_tenure_targets_2011,
    oa_tenure_targets_2021,
)
from rent_project.sources.hasp import (
    add_hasp_property_id,
)

USE_TEST_AREA = False  # set to False for the full Greater London run


# Helpers: used inside steps, not called from main()


def _interim_path(stem, is_test):
    """Path to an interim parquet file.

    Test runs get a "_test" suffix so they never overwrite a full run.
    """

    suffix = "_test" if is_test else ""
    return ADDRESSBASE_DIRECTORY_INTERIM / f"{stem}{suffix}.parquet"


def _load_addressbase(year):
    """Load one year's clipped and harmonised parquet.

    Raises if any UPRN appears more than once, since the spine assumes
    one row per UPRN per year.
    """

    input_path = (
        ADDRESSBASE_DIRECTORY_INTERIM
        / f"greater_london_{year}_abplus_harmonised.parquet"
    )
    print(f"Loading {year} AddressBase Plus (clipped and harmonised)")
    addressbase = load_harmonised_addressbase(input_path)
    n_dupes = addressbase["uprn"].duplicated().sum()
    assert n_dupes == 0, f"{n_dupes:,} duplicate UPRNs in {year}"
    return addressbase


def _clip_test_area(addressbase_by_year, method="oa"):
    """Keep only rows in a test area, for quick test runs.

    method="bbox" filters on a British National Grid bounding box.
    method="oa" filters on the 2021 output area code.
    Returns a new dict of year -> DataFrame.
    """

    # Chippendale Street
    x_min, x_max = 535642, 535701
    y_min, y_max = 186022, 186074
    oa_cd = "E00008915"

    test_area_by_year = {}
    for year, addressbase in addressbase_by_year.items():
        if method == "bbox":
            test_area_by_year[year] = addressbase[
                (addressbase["x_coordinate"] >= x_min)
                & (addressbase["x_coordinate"] <= x_max)
                & (addressbase["y_coordinate"] >= y_min)
                & (addressbase["y_coordinate"] <= y_max)
            ]
        else:
            oa_col = "oa11cd" if year == 2011 else "oa21cd"
            test_area_by_year[year] = addressbase[addressbase[oa_col] == oa_cd]

    return test_area_by_year


def _load_spine_and_addresses(is_test):
    """Load parquet files with AddressBase spine and address keys."""

    file_path_spine = _interim_path("greater_london_abplus_spine", is_test)
    file_path_addresses = _interim_path("greater_london_abplus_addresses", is_test)
    return pd.read_parquet(file_path_spine), pd.read_parquet(file_path_addresses)


def _load_rent_properties():
    """Load rent_properties parquet file."""

    file_path = HASP_DIRECTORY / "wfz_rent_properties.parquet"
    return pd.read_parquet(file_path)


def _load_spine_hasp(is_test):
    """Load parquet file with the spine including HASP property id."""

    return pd.read_parquet(_interim_path("greater_london_abplus_spine_hasp", is_test))


# Steps: called from main(), in order


def step_build_addressbase_2026(schema):
    """Combine the 2026 tiles into one CSV.

    Unzips the tiles, loads and stacks them, and writes
    raw/address-base-plus/2026/greater_london_2026_abplus.csv.
    Skipped if that file already exists.
    """

    output_path = ADDRESSBASE_DIRECTORY_RAW / "2026" / "greater_london_2026_abplus.csv"
    # Check if already exists
    if output_path.exists():
        print("Skipped building 2026 AddressBase Plus (already exists)")
        return
    # Extract zipped tile files
    print("Extracting zip tiles")
    unzip_all(
        ADDRESSBASE_DIRECTORY_RAW / "2026" / "compressed",
        ADDRESSBASE_DIRECTORY_RAW / "2026" / "extracted",
    )
    # Load and concatenate all tiles (2026)
    print("Loading and concatenating tiles")
    addressbase_2026 = load_and_concatenate(
        schema, ADDRESSBASE_DIRECTORY_RAW / "2026" / "extracted"
    )
    # Save 2026 Address Base as csv
    print("Writing 2026 AddressBase Plus (csv)")
    addressbase_2026.to_csv(output_path, index=False)


def step_clip_and_harmonise_addressbase(year, schema, oa_path, lookup):
    """Clip one year to London output areas, add area codes, harmonise, and save as parquet.

    Loads the raw CSV, keeps points inside the OA boundaries (adding oa11cd
    or oa21cd), adds LSOA and LAD codes from the OA lookup, renames 2011
    columns to their newer names, aligns to COLUMNS_TO_KEEP, adds the
    is_residential_space column, and writes
    interim/address-base-plus/greater_london_<year>_abplus_harmonised.parquet.
    Skipped if that file already exists.
    """

    output_path = (
        ADDRESSBASE_DIRECTORY_INTERIM
        / f"greater_london_{year}_abplus_harmonised.parquet"
    )
    if output_path.exists():
        print(f"Skipped {year} AddressBase Plus (already clipped and harmonised)")
        return
    ADDRESSBASE_DIRECTORY_INTERIM.mkdir(parents=True, exist_ok=True)

    print(f"Loading {year} AddressBase Plus")
    addressbase = load_full_addressbase(
        schema,
        ADDRESSBASE_DIRECTORY_RAW / str(year) / f"greater_london_{year}_abplus.csv",
    )

    print(f"Clipping {year} AddressBase Plus to {oa_path.name}")
    oa_boundaries = load_oa_boundaries(oa_path)
    addressbase = clip_to_output_areas(addressbase, oa_boundaries)

    print(f"Adding LSOA and LAD codes to {year} AddressBase Plus")
    oa_column = "oa11cd" if year == 2011 else "oa21cd"
    addressbase = add_area_codes(addressbase, lookup, oa_column)

    print(f"Harmonising {year} AddressBase Plus")
    if year == 2011:  # pre-epoch-39 column names
        addressbase = rename_columns(addressbase)
    addressbase = align_columns(addressbase)

    print(f"Adding residential indicator to {year} AddressBase Plus")
    addressbase = add_is_residential(addressbase)

    print(f"Writing {year} AddressBase Plus to {output_path.name}")
    addressbase.to_parquet(output_path, index=False)


def step_build_spine_and_addresses(is_test):
    """Build the spine and canonical address list, and save as parquet.

    Loads each year's clipped and harmonised parquet, keeps only the test
    area if is_test, builds and filters the spine, builds the address list,
    and writes both to interim/address-base-plus/.
    Test runs get a "_test" suffix so they never overwrite a full run.
    Skipped if both files already exist.
    """

    spine_path = _interim_path("greater_london_abplus_spine", is_test)
    addresses_path = _interim_path("greater_london_abplus_addresses", is_test)
    if spine_path.exists() and addresses_path.exists():
        print(f"Skipped building spine and addresses ({spine_path.stem} exists)")
        return

    addressbase_by_year = {
        2011: _load_addressbase(2011),
        2021: _load_addressbase(2021),
        2026: _load_addressbase(2026),
    }

    if is_test:
        print("Clipping to test area")
        addressbase_by_year = _clip_test_area(addressbase_by_year)

    print("Building spine")
    spine = build_addressbase_spine(addressbase_by_year)
    spine = filter_addressbase_spine(spine)

    print("Building address list")
    addresses = build_address_list(spine, addressbase_by_year)

    print(f"Writing spine ({len(spine):,} rows) to {spine_path.name}")
    spine.to_parquet(spine_path, index=False)

    print(f"Writing addresses ({len(addresses):,} rows) to {addresses_path.name}")
    addresses.to_parquet(addresses_path, index=False)


def step_match_hasp_property_id(is_test):
    """Match the zoopla property id to the spine, and save as parquet.

    Loads the spine, canonical addresses and rent properties, adds the HASP
    property id to the spine, and writes
    interim/address-base-plus/greater_london_abplus_spine_hasp.parquet.
    Test runs get a "_test" suffix so they never overwrite a full run.
    Skipped if that file already exists.
    """

    output_path = _interim_path("greater_london_abplus_spine_hasp", is_test)
    if output_path.exists():
        print(f"Skipped matching HASP property id ({output_path.name} exists)")
        return

    print("Loading spine, addresses and rent properties")
    spine, addresses = _load_spine_and_addresses(is_test)
    rent_properties = _load_rent_properties()

    print("Matching HASP property id to spine")
    spine = add_hasp_property_id(spine, addresses, rent_properties)
    # Full run: 80267 unmatched, output: 4151457x16

    print(f"Writing spine ({len(spine):,} rows) to {output_path.name}")
    spine.to_parquet(output_path, index=False)


def step_add_private_rented(is_test):
    """Identify privately rented properties, and save as parquet.

    Loads the spine with HASP property id, builds the 2011 and 2021 census
    tenure targets, adds the private-rented indicator, and writes
    interim/address-base-plus/greater_london_abplus_spine_private_rented.parquet.
    Test runs get a "_test" suffix so they never overwrite a full run.
    Skipped if that file already exists.
    """

    output_path = _interim_path("greater_london_abplus_spine_private_rented", is_test)
    if output_path.exists():
        print(f"Skipped identifying private rented ({output_path.name} exists)")
        return

    print("Loading spine with HASP property id")
    spine = _load_spine_hasp(is_test)

    print("Building census tenure targets")
    oa_targets_2011 = oa_tenure_targets_2011(spine)
    oa_targets_2021 = oa_tenure_targets_2021(spine)

    print("Identifying privately rented properties")
    spine = add_private_rented(spine, oa_targets_2011, oa_targets_2021)

    print(f"Writing spine ({len(spine):,} rows) to {output_path.name}")
    spine.to_parquet(output_path, index=False)


def step_load_spine_private_rented(is_test):
    """Load parquet file with the spine including the private-rented indicator."""

    return pd.read_parquet(
        _interim_path("greater_london_abplus_spine_private_rented", is_test)
    )


def main():
    """Run the AddressBase Plus pipeline end to end."""

    schema_old = load_schema_old(
        ADDRESSBASE_DIRECTORY_RAW / "addressbase-plus-pre-e-39-header.csv"
    )
    schema_new = load_schema_new(
        ADDRESSBASE_DIRECTORY_RAW / "addressbase-plus-post-e-39-header.csv"
    )

    oa_2011_path = OA_DIRECTORY / "oa_2011_bfe_london.parquet"
    oa_2021_path = OA_DIRECTORY / "oa_2021_bfe_london.parquet"

    lookup_2011 = load_oa_lookup(
        LOOKUP_DIRECTORY / "oa11_lsoa11_lad11_ew.csv",
        {"oa11cd": "oa11cd", "lsoa11cd": "lsoa11cd", "lad11cd": "lad11cd"},
    )
    lookup_2021 = load_oa_lookup(
        LOOKUP_DIRECTORY / "oa21_lsoa21_lad21_ew.csv",
        {"oa21cd": "oa21cd", "lsoa21cd": "lsoa21cd", "lad21cd": "lad21cd"},
    )

    # Stage 1: build the 2026 CSV from tiles
    step_build_addressbase_2026(schema_new)

    # Stage 2: clip to London OAs, add area codes, harmonise and add residential indicator
    step_clip_and_harmonise_addressbase(2011, schema_old, oa_2011_path, lookup_2011)
    step_clip_and_harmonise_addressbase(2021, schema_new, oa_2021_path, lookup_2021)
    step_clip_and_harmonise_addressbase(2026, schema_new, oa_2021_path, lookup_2021)

    # Stage 3: build spine and canonical addresses
    step_build_spine_and_addresses(is_test=USE_TEST_AREA)

    # Stage 4: match zoopla property id to spine
    step_match_hasp_property_id(is_test=USE_TEST_AREA)

    # Stage 4 1/2 (skip for now)
    # match which years have rental listings
    # match EPC data

    # Stage 5: identify privately rented properties
    step_add_private_rented(is_test=USE_TEST_AREA)

    # Stage 6: merge in rents and adjust rents to target years
    spine = step_load_spine_private_rented(is_test=USE_TEST_AREA)

    # Stage 7: estimate missing rents


if __name__ == "__main__":
    main()