"""Orchestration only"""

from rent_project.config import (
    ADDRESSBASE_DIRECTORY_INTERIM,
    ADDRESSBASE_DIRECTORY_RAW,
)
from rent_project.load.addressbase import (
    clip_greater_london,
    load_and_concatenate,
    load_full_addressbase,
    load_schema_new,
    load_schema_old,
    unzip_all,
)


def step_build_addressbase2026(addressbase_schema_new):
    """Extracts zip AddressBase 2026 tiles.
    Loads all tiles and concatenates them.
    Then a combined AddressBase 2026 csv.
    Does nothing if the combined CSV already exists.
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
        ADDRESSBASE_DIRECTORY_RAW / "2026" / "extracted"
    )

    # Load and concatenate all tiles (2026)
    print("Loading and concatenating tiles")
    addressbase_2026 = load_and_concatenate(
        addressbase_schema_new,
        ADDRESSBASE_DIRECTORY_RAW / "2026" / "extracted"
    )

    # Save 2026 Address Base as csv
    print("Writing 2026 AddressBase Plus (csv)")
    addressbase_2026.to_csv(output_path,index=False)


def step_clip_addressbase_all_years(addressbase_schema_old, addressbase_schema_new):
    """Loads AddressBase Plus 2011, 2021, 2026.
    Clips each to Greater London.
    Writes a new csv for each.
    Does nothing if the clipped CSVs already exists.
    """
    
    schema_by_year = {
        2011: addressbase_schema_old,
        2021: addressbase_schema_new,
        2026: addressbase_schema_new,
    }

    ADDRESSBASE_DIRECTORY_INTERIM.mkdir(parents=True, exist_ok=True)
    
    for year in [2011, 2021, 2026]:
        output_path = ADDRESSBASE_DIRECTORY_INTERIM / f"greater_london_{year}_abplus_clipped.csv"
        if output_path.exists():
            print(f"Skipped clipping {year} AddressBase Plus (already exists)")
            continue

        print(f"Loading {year} AddressBase Plus")
        addressbase = load_full_addressbase(
            schema_by_year[year],
            ADDRESSBASE_DIRECTORY_RAW / str(year) / f"greater_london_{year}_abplus.csv"
        )
        print(f"Clipping {year} AddressBase Plus")
        addressbase = clip_greater_london(addressbase)
        print(f"Writing {year} AddressBase Plus (clipped csv)")
        addressbase.to_csv(output_path, index=False)


def step_load_addressbase_by_year(addressbase_schema_old, addressbase_schema_new):
    """Loads the clipped AddressBase Plus CSVs for 2011, 2021, 2026.
    Returns AddressBase Plus dictionary.
    """

    schema_by_year = {
        2011: addressbase_schema_old,
        2021: addressbase_schema_new,
        2026: addressbase_schema_new,
    }

    addressbase_by_year = {}
    for year in [2011, 2021, 2026]:
        print(f"Loading {year} AddressBase Plus (clipped)")
        input_path = ADDRESSBASE_DIRECTORY_INTERIM / f"greater_london_{year}_abplus_clipped.csv"
        addressbase_by_year[year] = load_full_addressbase(schema_by_year[year], input_path)

    return addressbase_by_year

def step_clip_addressbase_test_area(addressbase_dictionary):
    """Takes AddressBase Plus dictionary.
    Filters it by British National Grid x and y mins and maxes.
    Returns filtered AddressBase Plus dictionary.
    """

    # Chippendale Street
    x_min, x_max = 535642, 535701
    y_min, y_max = 186022, 186074

    test_area = {}
    for year, df in addressbase_dictionary.items():
        test_area[year] = df[
            (df["x_coordinate"] >= x_min) & (df["x_coordinate"] <= x_max) &
            (df["y_coordinate"] >= y_min) & (df["y_coordinate"] <= y_max)
        ]
    
    return test_area


def main():

    addressbase_schema_old = load_schema_old(ADDRESSBASE_DIRECTORY_RAW / "addressbase-plus-pre-e-39-header.csv")
    addressbase_schema_new = load_schema_new(ADDRESSBASE_DIRECTORY_RAW / "addressbase-plus-post-e-39-header.csv")

    step_build_addressbase2026(addressbase_schema_new)
    step_clip_addressbase_all_years(addressbase_schema_old, addressbase_schema_new) # Greater London extent
    addressbase_by_year = step_load_addressbase_by_year(addressbase_schema_old, addressbase_schema_new)
    addressbase_by_year = step_clip_addressbase_test_area(addressbase_by_year) # test area

    # step_build_addressbase_panel()
    # step_filter_residential() - filter by state; class
    # next step goes here


if __name__ == "__main__":
    main()