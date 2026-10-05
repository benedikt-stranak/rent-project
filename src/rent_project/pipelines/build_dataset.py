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
from rent_project.sources.addressbase import (
    add_area_codes,
    # add_hasp_property_id,
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

USE_TEST_AREA = False  # set to False for the full Greater London run


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
    columns to their newer names, aligns to COLUMNS_TO_KEEP, and writes
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

    print(f"Writing {year} AddressBase Plus to {output_path.name}")
    addressbase.to_parquet(output_path, index=False)


def step_load_addressbase(year):
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


def step_add_is_residential(addressbase_by_year):
    """Add an is_residential_space column to each year's AddressBase."""
    addressbase_by_year_flagged = {}
    for year, addressbase in addressbase_by_year.items():
        addressbase_by_year_flagged[year] = add_is_residential(addressbase)
    return addressbase_by_year_flagged


def step_clip_test_area(addressbase_by_year, method="oa"):
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


def step_write_outputs(spine, addresses, is_test):
    """Write the spine and address list to interim/address-base-plus/.

    Test runs get a "_test" suffix so they never overwrite a full run.
    Existing files are overwritten.
    """

    ADDRESSBASE_DIRECTORY_INTERIM.mkdir(parents=True, exist_ok=True)
    suffix = "_test" if is_test else ""

    spine_path = (
        ADDRESSBASE_DIRECTORY_INTERIM / f"greater_london_abplus_spine{suffix}.parquet"
    )
    print(f"Writing spine ({len(spine):,} rows) to {spine_path.name}")
    spine.to_parquet(spine_path, index=False)

    addresses_path = (
        ADDRESSBASE_DIRECTORY_INTERIM
        / f"greater_london_abplus_addresses{suffix}.parquet"
    )
    print(f"Writing addresses ({len(addresses):,} rows) to {addresses_path.name}")
    addresses.to_parquet(addresses_path, index=False)

def step_load_spine_and_addresses():
    """Load parquet file with AddressBase spine and address keys."""

    file_path_spine = ADDRESSBASE_DIRECTORY_INTERIM / "greater_london_abplus_spine.parquet"
    file_path_addresses = ADDRESSBASE_DIRECTORY_INTERIM / "greater_london_abplus_addresses.parquet"
    return pd.read_parquet(file_path_spine), pd.read_parquet(file_path_addresses)

def step_load_rent_properties():
    """Load rent_properties parquet file."""

    file_path = HASP_DIRECTORY / "wfz_rent_properties.parquet"
    return pd.read_parquet(file_path)

# def step_add_hasp_property_id(spine, addresses, rent_properties):
#    """."""
#    spine=add_hasp_property_id(spine, addresses, rent_properties)
#    return spine


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

    # Stage 2: clip to London OAs, add area codes and harmonise
    step_clip_and_harmonise_addressbase(2011, schema_old, oa_2011_path, lookup_2011)
    step_clip_and_harmonise_addressbase(2021, schema_new, oa_2021_path, lookup_2021)
    step_clip_and_harmonise_addressbase(2026, schema_new, oa_2021_path, lookup_2021)

    # Stage 3: load and add residential indicator
    addressbase_by_year = {
        2011: step_load_addressbase(2011),
        2021: step_load_addressbase(2021),
        2026: step_load_addressbase(2026),
    }
    addressbase_by_year = step_add_is_residential(addressbase_by_year)

    if USE_TEST_AREA:
        addressbase_by_year = step_clip_test_area(addressbase_by_year)

    # Stage 4: spine and canonical addresses
    spine = build_addressbase_spine(addressbase_by_year)
    spine = filter_addressbase_spine(spine)
    addresses = build_address_list(spine, addressbase_by_year)
    step_write_outputs(spine, addresses, is_test=USE_TEST_AREA)
    # change Stage 3 and 4 to save the outputs (and be skipped if already exist)

    # Stage 5: match zoopla property id to spine
    # spine, addresses = step_load_spine_and_addresses()
    # rent_properties = step_load_rent_properties()
    # spine = step_add_hasp_property_id(spine, addresses, rent_properties)

    # Stage 6: identify privately rented properties

    # Stage 7: merge in rents and adjust rents to target years

    # Stage 8: estimate missing rents


if __name__ == "__main__":
    main()
