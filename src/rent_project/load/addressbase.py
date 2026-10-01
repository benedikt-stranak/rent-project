"""Load, harmonise and build address keys from AddressBase Plus."""

from pathlib import Path
from zipfile import ZipFile

import duckdb
import pandas as pd

LONDON_BOROUGHS = [
    "LONDON",
    "GREATER LONDON",
    "CITY OF WESTMINSTER",
    "TOWER HAMLETS",
    "LB OF TOWER HAMLETS",
    "WANDSWORTH",
    "CROYDON",
    "BARNET",
    "LONDON BOROUGH OF BARNET",
    "SOUTHWARK",
    "LAMBETH",
    "EALING",
    "BROMLEY",
    "LONDON BOROUGH OF BROMLEY",
    "CAMDEN",
    "BRENT",
    "LEWISHAM",
    "NEWHAM",
    "ENFIELD",
    "GREENWICH",
    "LONDON BOROUGH OF GREENWICH",
    "HACKNEY",
    "ISLINGTON",
    "HILLINGDON",
    "HARINGEY",
    "LONDON BOROUGH OF HARINGEY",
    "WALTHAM FOREST",
    "HOUNSLOW",
    "LONDON BOROUGH OF HOUNSLOW",
    "HAMMERSMITH AND FULHAM",
    "HAMMERSMITH",
    "LBHF",
    "REDBRIDGE",
    "HAVERING",
    "LONDON BOROUGH OF HAVERING",
    "KENSINGTON AND CHELSEA",
    "BEXLEY",
    "MERTON",
    "HARROW",
    "RICHMOND UPON THAMES",
    "BARKING AND DAGENHAM",
    "SUTTON",
    "KINGSTON UPON THAMES",
    "CITY OF LONDON",
]
COLUMNS_TO_KEEP = [
    "uprn",
    "parent_uprn",
    "multi_occ_count",
    "udprn",
    "addressbase_postal",
    "state",
    "class",
    "level",
    "x_coordinate",
    "y_coordinate",
    "usrn",
    "ward_code",
    "parish_code",
    "local_custodian_code",
    "country",
    "state_date",
    "la_start_date",
    "rm_start_date",
    "last_update_date",
    "entry_date",
    "department_name",
    "rm_organisation_name",
    "sub_building_name",
    "building_name",
    "building_number",
    "po_box_number",
    "dependent_thoroughfare",
    "thoroughfare",
    "double_dependent_locality",
    "dependent_locality",
    "post_town",
    "postcode",
    "postcode_type",
    "delivery_point_suffix",
    "la_organisation",
    "sao_text",
    "sao_start_number",
    "sao_start_suffix",
    "sao_end_number",
    "sao_end_suffix",
    "pao_text",
    "pao_start_number",
    "pao_start_suffix",
    "pao_end_number",
    "pao_end_suffix",
    "street_description",
    "area_name",
    "locality",
    "town_name",
    "administrative_area",
    "postcode_locator",
    "rpc",
    "usrn_match_indicator",
    "official_flag",
    "os_address_toid",
    "os_address_toid_version",
    "os_roadlink_toid",
    "os_roadlink_toid_version",
    "os_topo_toid",
    "os_topo_toid_version",
    "voa_ct_record",
    "voa_ndr_record",
    "voa_ndr_p_desc_code",
    "voa_ndr_scat_code",
]
COLUMNS_TO_RENAME = {
    "rm_udprn": "udprn",
    "postal_address": "addressbase_postal",
    "start_date": "la_start_date",
    "organisation_name": "rm_organisation_name",
    "dependent_thoroughfare_name": "dependent_thoroughfare",
    "thoroughfare_name": "thoroughfare",
    "welsh_dependent_thoroughfare_name": "welsh_dependent_thoroughfare",
    "welsh_thoroughfare_name": "welsh_thoroughfare",
    "organisation": "la_organisation",
    "locality_name": "locality",
}

# ----------------------------------------
# Loading AddressBase Plus Schema
# ----------------------------------------


def load_schema_old(header_path):
    """Build the read schema for pre-epoch-39 (pre-2016) AddressBase Plus files.

    Reads column names from the header file and assigns a pandas dtype
    to each column. Used for the 2011 data.

    Parameters
    ----------
    header_path : Path
        CSV file whose first row contains the column names.

    Returns
    -------
    dict
        "columns": lowercase column names, in file order.
        "dtypes": column name -> pandas dtype, for pd.read_csv.
        "date_columns": columns to parse as dates.
    """

    columns = (
        pd.read_csv(header_path, header=None, dtype=str).iloc[0].str.lower().tolist()
    )
    int_columns = [
        "uprn",
        "rm_udprn",
        "parent_uprn",
        "local_custodian_code",
        "sao_start_number",
        "sao_end_number",
        "pao_start_number",
        "pao_end_number",
        "usrn",
        "os_address_toid_version",
        "os_roadlink_toid_version",
        "os_topo_toid_version",
        "voa_ct_record",
        "voa_ndr_record",
        "multi_occ_count",
    ]
    float_columns = ["x_coordinate", "y_coordinate"]
    date_columns = [
        "state_date",
        "start_date",
        "end_date",
        "last_update_date",
        "entry_date",
        "process_date",
    ]
    string_columns = [
        c for c in columns if c not in int_columns + float_columns + date_columns
    ]
    dtypes = {
        **{c: "Int64" for c in int_columns},
        **{c: "float64" for c in float_columns},
        **{c: "string" for c in string_columns},
    }
    return {"columns": columns, "dtypes": dtypes, "date_columns": date_columns}


def load_schema_new(header_path):
    """Build the read schema for epoch-39+ (2016 onwards) AddressBase Plus files.

    Same as load_schema_old, but for the newer column layout.
    Used for the 2021 and 2026 data.

    Parameters
    ----------
    header_path : Path
        CSV file whose first row contains the column names.

    Returns
    -------
    dict
        "columns": lowercase column names, in file order.
        "dtypes": column name -> pandas dtype, for pd.read_csv.
        "date_columns": columns to parse as dates.
    """

    columns = (
        pd.read_csv(header_path, header=None, dtype=str).iloc[0].str.lower().tolist()
    )
    int_columns = [
        "uprn",
        "udprn",
        "parent_uprn",
        "local_custodian_code",
        "building_number",
        "sao_start_number",
        "sao_end_number",
        "pao_start_number",
        "pao_end_number",
        "usrn",
        "os_address_toid_version",
        "os_roadlink_toid_version",
        "os_topo_toid_version",
        "voa_ct_record",
        "voa_ndr_record",
        "multi_occ_count",
    ]
    float_columns = ["x_coordinate", "y_coordinate", "latitude", "longitude"]
    date_columns = [
        "state_date",
        "la_start_date",
        "last_update_date",
        "entry_date",
        "rm_start_date",
    ]
    string_columns = [
        c for c in columns if c not in int_columns + float_columns + date_columns
    ]
    dtypes = {
        **{c: "Int64" for c in int_columns},
        **{c: "float64" for c in float_columns},
        **{c: "string" for c in string_columns},
    }
    return {"columns": columns, "dtypes": dtypes, "date_columns": date_columns}


# ----------------------------------------
# Building AddressBase Plus 2026
# ----------------------------------------


def unzip_all(zip_dir, extract_dir):
    """Extract every .zip in zip_dir into its own folder in extract_dir.

    Each zip is extracted to extract_dir / <zip name>. Zips whose folder
    already exists are skipped.

    Parameters
    ----------
    zip_dir : Path
        Folder containing one or more .zip files.
    extract_dir : Path
        Destination folder (created if it does not exist).
    """

    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_paths = sorted(Path(zip_dir).glob("*.zip"))
    for zip_path in zip_paths:
        target = extract_dir / (zip_path.stem)
        if target.exists():
            print(f"Skipping {zip_path.name} (already extracted)")
            continue
        print(f"Extracting {zip_path.name}")
        with ZipFile(zip_path) as zf:
            zf.extractall(target)


def load_tile(schema, file_path):
    """Load a single AddressBase Plus tile CSV.

    Tile CSVs have no header row, so column names come from the schema.

    Parameters
    ----------
    schema : dict
        Schema from load_schema_new or load_schema_old.
    file_path : Path
        Path to the tile CSV.

    Returns
    -------
    pandas.DataFrame
    """

    df = pd.read_csv(
        file_path,
        header=None,
        names=schema["columns"],
        dtype=schema["dtypes"],
        parse_dates=schema["date_columns"],
    )
    return df


def load_and_concatenate(schema, extract_dir):
    """Load every tile CSV in extract_dir (including subfolders) into one DataFrame.

    Parameters
    ----------
    schema : dict
        Schema from load_schema_new or load_schema_old.
    extract_dir : Path
        Folder to search for tile CSVs.

    Returns
    -------
    pandas.DataFrame
        All tiles stacked, with a fresh 0..n index.
    """

    csv_paths = sorted(Path(extract_dir).rglob("*.csv"))
    print(f"Loading {len(csv_paths)} tiles")
    tiles = [load_tile(schema, p) for p in csv_paths]
    combined = pd.concat(tiles, ignore_index=True)
    print(f"Loaded {len(combined):,} rows from {len(tiles)} tiles.")
    return combined


# ----------------------------------------
# Loading and filtering AddressBase Plus
# ----------------------------------------


def load_full_addressbase(schema, file_path):
    """Load a combined AddressBase Plus CSV that has a header row.

    Unlike load_tile, column names are read from the file itself;
    the schema only supplies dtypes and date columns.

    Parameters
    ----------
    schema : dict
        Schema matching the file's epoch (old or new).
    file_path : Path
        Path to the CSV.

    Returns
    -------
    pandas.DataFrame
    """

    df = pd.read_csv(
        file_path, dtype=schema["dtypes"], parse_dates=schema["date_columns"]
    )
    return df


def load_clipped_addressbase(file_path):
    """Load a clipped AddressBase Plus parquet file.

    Parquet stores column types in the file, so no schema is needed.
    """

    return pd.read_parquet(file_path)


def clip_greater_london(df):
    """Keep only rows whose administrative_area is in LONDON_BOROUGHS."""

    df = df[df["administrative_area"].isin(LONDON_BOROUGHS)]
    return df


def rename_columns(df):
    """Rename pre-epoch-39 columns to their epoch-39+ names (see COLUMNS_TO_RENAME).

    This lets all years share one set of column names.
    """

    renamed = df.rename(columns=COLUMNS_TO_RENAME)
    return renamed


def align_columns(addressbase_by_year):
    """Give every year the same columns, in the same order (COLUMNS_TO_KEEP).

    Columns in COLUMNS_TO_KEEP that a year lacks are added and filled with NA.
    Columns not in COLUMNS_TO_KEEP are dropped. Both lists are printed per year.

    Parameters
    ----------
    addressbase_by_year : dict
        Year -> AddressBase Plus DataFrame.

    Returns
    -------
    dict
        Year -> DataFrame with exactly the COLUMNS_TO_KEEP columns.
    """

    aligned = {}
    for year, df in addressbase_by_year.items():
        missing = [c for c in COLUMNS_TO_KEEP if c not in df.columns]
        dropped = [c for c in df.columns if c not in COLUMNS_TO_KEEP]
        print(year, "missing:", missing)
        print(year, "dropped:", dropped)
        aligned[year] = df.reindex(columns=COLUMNS_TO_KEEP)
    return aligned


def add_is_residential(df):
    """Return df with an added boolean column is_residential_space.

    True where class is "R" (residential, not further classified) or starts
    with "RD" (dwelling) or "RH" (house in multiple occupation), as recorded
    in this year's snapshot. NA where class is missing.
    """

    is_residential = df["class"].eq("R") | df["class"].str[:2].isin(["RD", "RH"])
    return df.assign(is_residential_space=is_residential)


def build_addressbase_spine(addressbase_by_year):
    """Build one row per UPRN that appears in any year.

    For each year, records whether the UPRN was residential and its state
    in that year (NA if the UPRN was absent). Coordinates come from the
    most recent year in which the UPRN appears.

    Assumes each UPRN appears at most once per year.

    Parameters
    ----------
    addressbase_by_year : dict
        Year -> AddressBase Plus DataFrame, with is_residential_space added.

    Returns
    -------
    pandas.DataFrame
        Columns: uprn, x_coordinate, y_coordinate,
        then is_residential_<year> and state_<year> for each year.
    """

    uprns = pd.Index(
        pd.concat([df["uprn"] for df in addressbase_by_year.values()]).unique(),
        name="uprn",
    )
    out = pd.DataFrame(index=uprns)
    coords = pd.DataFrame(
        index=uprns, columns=["x_coordinate", "y_coordinate"], dtype=float
    )
    for year in sorted(addressbase_by_year):
        df = addressbase_by_year[year]
        wave = df.set_index("uprn")[
            ["is_residential_space", "state", "x_coordinate", "y_coordinate"]
        ].reindex(uprns)
        out[f"is_residential_{year}"] = wave["is_residential_space"]
        out[f"state_{year}"] = wave["state"]
        coords = wave[["x_coordinate", "y_coordinate"]].combine_first(coords)
    return pd.concat([coords, out], axis=1).reset_index()


def filter_addressbase_spine(spine):
    """Keep UPRNs that were residential and in use or vacant in at least one year.

    "In use or vacant" means state 2 or 3. Expects the residential_ and
    state_ columns for 2011, 2021 and 2026, as built by build_addressbase_spine.
    """

    mask = (
        (spine["is_residential_2011"] & spine["state_2011"].isin(["2", "3"]))
        | (spine["is_residential_2021"] & spine["state_2021"].isin(["2", "3"]))
        | (spine["is_residential_2026"] & spine["state_2026"].isin(["2", "3"]))
    )
    return spine[mask.fillna(False)].copy()


# ----------------------------------------
# Building AddressBase Plus addresses
# ----------------------------------------


def build_la_addresses(df):
    """Build a single address string per row from the local authority fields.

    Combines organisation, secondary and primary addressable objects
    (SAO and PAO), street, locality and town into one comma-separated string.

    Parameters
    ----------
    df : pandas.DataFrame
        AddressBase Plus rows (harmonised column names).

    Returns
    -------
    pandas.DataFrame
        Columns: uprn, address, postcode (from postcode_locator).
    """

    query = """
        SELECT
            uprn,
            (
                CASE WHEN la_organisation IS NOT NULL THEN la_organisation || ', ' ELSE '' END

                -- Secondary Addressable Information
                || CASE WHEN sao_text IS NOT NULL THEN sao_text || ', ' ELSE '' END
                || CASE
                    WHEN sao_start_number IS NOT NULL AND sao_start_suffix IS NULL AND sao_end_number IS NULL THEN sao_start_number::VARCHAR || ', '
                    WHEN sao_start_number IS NULL THEN ''
                    ELSE sao_start_number::VARCHAR
                END
                || CASE
                    WHEN sao_start_suffix IS NOT NULL AND sao_end_number IS NULL THEN sao_start_suffix || ', '
                    WHEN sao_start_suffix IS NOT NULL AND sao_end_number IS NOT NULL THEN sao_start_suffix
                    ELSE ''
                END
                || CASE
                    WHEN sao_end_suffix IS NOT NULL AND sao_end_number IS NOT NULL THEN '-'
                    WHEN sao_start_number IS NOT NULL AND sao_end_number IS NOT NULL THEN '-'
                    ELSE ''
                END
                || CASE
                    WHEN sao_end_number IS NOT NULL AND sao_end_suffix IS NULL THEN sao_end_number::VARCHAR || ', '
                    WHEN sao_end_number IS NULL THEN ''
                    ELSE sao_end_number::VARCHAR
                END
                || CASE WHEN sao_end_suffix IS NOT NULL THEN sao_end_suffix || ', ' ELSE '' END

                -- Primary Addressable Information
                || CASE WHEN pao_text IS NOT NULL THEN pao_text || ', ' ELSE '' END
                || CASE
                    WHEN pao_start_number IS NOT NULL AND pao_start_suffix is null AND pao_end_number IS NULL THEN pao_start_number::VARCHAR || ' '
                    WHEN pao_start_number IS NULL THEN ''
                    ELSE pao_start_number::VARCHAR
                END
                || CASE
                    WHEN pao_start_suffix IS NOT NULL AND pao_end_number IS NULL THEN pao_start_suffix || ', '
                    WHEN pao_start_suffix IS NOT NULL AND pao_end_number IS NOT NULL THEN pao_start_suffix
                    ELSE ''
                END
                || CASE
                    WHEN pao_end_suffix IS NOT NULL AND pao_end_number IS NOT NULL THEN '-'
                    WHEN pao_start_number IS NOT NULL AND pao_end_number IS NOT NULL THEN '-'
                    ELSE ''
                END
                || CASE
                    WHEN pao_end_number IS NOT NULL AND pao_end_suffix IS NULL THEN pao_end_number::VARCHAR || ', '
                    WHEN pao_end_number IS NULL THEN '' ELSE pao_end_number::VARCHAR
                END
                || CASE WHEN pao_end_suffix IS NOT NULL THEN pao_end_suffix || ', ' ELSE '' END

                || CASE WHEN street_description IS NOT NULL THEN street_description || ', ' ELSE '' END
                || CASE WHEN locality IS NOT NULL THEN locality || ', ' ELSE '' END
                || CASE WHEN town_name IS NOT NULL THEN town_name || '' ELSE '' END
            ) AS address,
            postcode_locator AS postcode
        FROM df
    """
    return duckdb.sql(query).df()


def build_rm_addresses(df):
    """Build a single address string per row from the Royal Mail (PAF) fields.

    Combines department, organisation, building, thoroughfare, locality
    and post town into one comma-separated string. Rows without a Royal Mail
    address get an empty string.

    Parameters
    ----------
    df : pandas.DataFrame
        AddressBase Plus rows (harmonised column names).

    Returns
    -------
    pandas.DataFrame
        Columns: uprn, address, postcode.
    """

    query = """
        SELECT
            uprn,
            (
                CASE WHEN department_name IS NOT NULL THEN department_name || ', ' ELSE '' END
                || CASE WHEN rm_organisation_name IS NOT NULL THEN rm_organisation_name || ', ' ELSE '' END
                || CASE WHEN sub_building_name IS NOT NULL THEN sub_building_name || ', ' ELSE '' END
                || CASE WHEN building_name IS NOT NULL THEN building_name || ', ' ELSE '' END
                || CASE WHEN building_number IS NOT NULL THEN building_number::VARCHAR || ' ' ELSE '' END
                || CASE WHEN po_box_number IS NOT NULL THEN 'PO BOX ' || po_box_number || ', ' ELSE '' END
                || CASE WHEN dependent_thoroughfare IS NOT NULL THEN dependent_thoroughfare || ', ' ELSE '' END
                || CASE WHEN thoroughfare IS NOT NULL THEN thoroughfare || ', ' ELSE '' END
                || CASE WHEN double_dependent_locality IS NOT NULL THEN double_dependent_locality || ', ' ELSE '' END
                || CASE WHEN dependent_locality IS NOT NULL THEN dependent_locality || ', ' ELSE '' END
                || CASE WHEN post_town IS NOT NULL THEN post_town || '' ELSE '' END
            ) AS address,
            postcode
        FROM df
    """
    return duckdb.sql(query).df()


def build_address_list(spine, addressbase_by_year):
    """Build LA and Royal Mail addresses for every spine UPRN in every year.

    Duplicates are not removed: an address that is unchanged across years
    appears once per year and type.

    Parameters
    ----------
    spine : pandas.DataFrame
        Output of filter_addressbase_spine; only its uprn column is used.
    addressbase_by_year : dict
        Year -> harmonised AddressBase Plus DataFrame.

    Returns
    -------
    pandas.DataFrame
        Long format. Columns: uprn, address, postcode, year,
        type ("LA" or "RM").
    """

    uprns = set(spine["uprn"])
    addresses = []
    for year, df in addressbase_by_year.items():
        df = df[df["uprn"].isin(uprns)]
        la = build_la_addresses(df)
        la["year"] = year
        la["type"] = "LA"
        rm = build_rm_addresses(df)
        rm["year"] = year
        rm["type"] = "RM"
        addresses.extend([la, rm])
    return pd.concat(addresses, ignore_index=True)
