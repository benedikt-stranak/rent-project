"""Pipeline: build the AddressBase Plus address dataset.

Run with: uv run build-dataset
"""

from rent_project.config import (
    ADDRESSBASE_DIRECTORY_INTERIM,
    ADDRESSBASE_DIRECTORY_RAW,
)
from rent_project.load.addressbase import (
    add_is_residential,
    align_columns,
    build_address_list,
    build_addressbase_spine,
    clip_greater_london,
    filter_addressbase_spine,
    load_and_concatenate,
    load_clipped_addressbase,
    load_full_addressbase,
    load_schema_new,
    load_schema_old,
    rename_columns,
    unzip_all,
)

USE_TEST_AREA = True  # set to False for the full Greater London run


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


def step_clip_addressbase_by_year(schema_by_year):
    """Clip each year's AddressBase Plus to Greater London.

    Reads the raw CSV for each year and writes the clipped version to
    interim/address-base-plus/ as parquet. Years whose output already
    exists are skipped.
    """

    ADDRESSBASE_DIRECTORY_INTERIM.mkdir(parents=True, exist_ok=True)
    for year, schema in schema_by_year.items():
        output_path = (
            ADDRESSBASE_DIRECTORY_INTERIM
            / f"greater_london_{year}_abplus_clipped.parquet"
        )
        if output_path.exists():
            print(f"Skipped clipping {year} AddressBase Plus (already exists)")
            continue
        print(f"Loading {year} AddressBase Plus")
        addressbase = load_full_addressbase(
            schema,
            ADDRESSBASE_DIRECTORY_RAW / str(year) / f"greater_london_{year}_abplus.csv",
        )
        print(f"Clipping {year} AddressBase Plus")
        addressbase = clip_greater_london(addressbase)
        print(f"Writing {year} AddressBase Plus (clipped parquet)")
        addressbase.to_parquet(output_path, index=False)


def step_load_addressbase_by_year(years):
    """Load the clipped parquet files. Returns a dict of year -> DataFrame."""

    addressbase_by_year = {}
    for year in years:
        print(f"Loading {year} AddressBase Plus (clipped)")
        input_path = (
            ADDRESSBASE_DIRECTORY_INTERIM
            / f"greater_london_{year}_abplus_clipped.parquet"
        )
        addressbase_by_year[year] = load_clipped_addressbase(input_path)
    return addressbase_by_year


def step_harmonise_addressbase(addressbase_by_year):
    """Give all years the same column names and columns.

    Renames the 2011 columns to their newer names, then aligns every
    year to COLUMNS_TO_KEEP. Returns a new dict of year -> DataFrame.
    """

    addressbase_by_year = dict(addressbase_by_year)
    addressbase_by_year[2011] = rename_columns(addressbase_by_year[2011])
    addressbase_by_year = align_columns(addressbase_by_year)
    return addressbase_by_year


def step_add_is_residential(addressbase_by_year):
    """Add an is_residential_space column to each year's AddressBase."""
    result = {}
    for year, df in addressbase_by_year.items():
        result[year] = add_is_residential(df)
    return result


def step_clip_test_area(addressbase_by_year):
    """Keep only rows in a specified bounding box.

    For quick test runs. The box is in British National Grid coordinates.
    Returns a new dict of year -> DataFrame.
    """

    # Chippendale Street
    x_min, x_max = 535642, 535701
    y_min, y_max = 186022, 186074
    test_area = {}
    for year, df in addressbase_by_year.items():
        test_area[year] = df[
            (df["x_coordinate"] >= x_min)
            & (df["x_coordinate"] <= x_max)
            & (df["y_coordinate"] >= y_min)
            & (df["y_coordinate"] <= y_max)
        ]
    return test_area


def step_write_outputs(spine, addresses, is_test):
    """Write the spine and address list to interim/address-base-plus/.

    Test runs get a "_test" suffix so they never overwrite a full run.
    Existing files are overwritten.
    """

    ADDRESSBASE_DIRECTORY_INTERIM.mkdir(parents=True, exist_ok=True)
    suffix = "_test" if is_test else ""

    spine_path = (
        ADDRESSBASE_DIRECTORY_INTERIM / f"greater_london_abplus_spine{suffix}.csv"
    )
    print(f"Writing spine ({len(spine):,} rows) to {spine_path.name}")
    spine.to_csv(spine_path, index=False)

    addresses_path = (
        ADDRESSBASE_DIRECTORY_INTERIM / f"greater_london_abplus_addresses{suffix}.csv"
    )
    print(f"Writing addresses ({len(addresses):,} rows) to {addresses_path.name}")
    addresses.to_csv(addresses_path, index=False)


def main():
    """Run the AddressBase Plus pipeline end to end."""

    schema_old = load_schema_old(
        ADDRESSBASE_DIRECTORY_RAW / "addressbase-plus-pre-e-39-header.csv"
    )
    schema_new = load_schema_new(
        ADDRESSBASE_DIRECTORY_RAW / "addressbase-plus-post-e-39-header.csv"
    )
    schema_by_year = {2011: schema_old, 2021: schema_new, 2026: schema_new}

    # Stage 1: one-off preparation (skipped if outputs already exist)
    step_build_addressbase_2026(schema_new)
    step_clip_addressbase_by_year(schema_by_year)

    # Stage 2: load and harmonise
    addressbase_by_year = step_load_addressbase_by_year([2011, 2021, 2026])
    addressbase_by_year = step_harmonise_addressbase(addressbase_by_year)
    addressbase_by_year = step_add_is_residential(addressbase_by_year)
    # write a file at this point?

    if USE_TEST_AREA:
        addressbase_by_year = step_clip_test_area(addressbase_by_year)

    # Stage 3: spine and canonical addresses
    spine = build_addressbase_spine(addressbase_by_year)
    spine = filter_addressbase_spine(spine)
    addresses = build_address_list(spine, addressbase_by_year)

    # Stage 4: save
    step_write_outputs(spine, addresses, is_test=USE_TEST_AREA)


if __name__ == "__main__":
    main()
