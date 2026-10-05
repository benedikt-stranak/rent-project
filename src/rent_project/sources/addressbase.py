"""Load, harmonise and build spine and address keys from AddressBase Plus."""

from pathlib import Path
from zipfile import ZipFile

import duckdb
import geopandas as gpd
import pandas as pd

BNG_CRS = "EPSG:27700"  # British National Grid, the CRS of AddressBase x/y

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
    "oa11cd",  # added by clip_to_output_areas (2011 only)
    "lsoa11cd",  # added by add_area_codes (2011 only)
    "lad11cd",  # added by add_area_codes (2011 only)
    "oa21cd",  # added by clip_to_output_areas (2021 and 2026)
    "lsoa21cd",  # added by add_area_codes (2021 and 2026)
    "lad21cd",  # added by add_area_codes (2021 and 2026)
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
AREA_CODE_COLUMNS = [
    "oa11cd",
    "lsoa11cd",
    "lad11cd",
    "oa21cd",
    "lsoa21cd",
    "lad21cd",
]


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

    tile = pd.read_csv(
        file_path,
        header=None,
        names=schema["columns"],
        dtype=schema["dtypes"],
        parse_dates=schema["date_columns"],
    )
    return tile


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
    tiles = [load_tile(schema, csv_path) for csv_path in csv_paths]
    addressbase = pd.concat(tiles, ignore_index=True)
    print(f"Loaded {len(addressbase):,} rows from {len(tiles)} tiles.")
    return addressbase


def load_full_addressbase(schema, file_path):
    """Load a combined AddressBase Plus CSV that has a header row.

    Unlike load_tile, column names are read from the file itself and
    lowercased, so they match the schema whatever case the file uses.
    The schema only supplies dtypes and date columns.

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

    header = pd.read_csv(file_path, nrows=0).columns
    names = [c.lower() for c in header]
    addressbase = pd.read_csv(
        file_path,
        header=0,
        names=names,
        dtype=schema["dtypes"],
        parse_dates=schema["date_columns"],
    )
    return addressbase


def load_harmonised_addressbase(file_path):
    """Load a clipped and harmonised AddressBase Plus parquet file.

    Parquet stores column types in the file, so no schema is needed.
    """

    return pd.read_parquet(file_path)


def load_oa_boundaries(file_path):
    """Load an output area boundary geoparquet in British National Grid.

    The file has one non-geometry column holding the OA code (OA11CD or
    OA21CD). That column is lowercased (oa11cd / oa21cd) to match the
    AddressBase column naming. The index is reset so that sjoin always
    names the joined index column index_right.

    Parameters
    ----------
    file_path : Path
        Geoparquet of output area polygons.

    Returns
    -------
    geopandas.GeoDataFrame
        Columns: the lowercased OA code column and geometry.
    """

    oa_boundaries = gpd.read_parquet(file_path)
    if oa_boundaries.crs is None:
        raise ValueError(f"{file_path.name} has no CRS set")
    oa_boundaries = oa_boundaries.to_crs(BNG_CRS).reset_index(drop=True)

    code_column = oa_boundaries.columns.drop(oa_boundaries.geometry.name)[0]
    return oa_boundaries.rename(columns={code_column: code_column.lower()})


def load_oa_lookup(file_path, columns):
    """Load an ONS output area lookup CSV, keeping and renaming some columns.

    Column names are lowercased before selecting, since ONS files vary
    in case. utf-8-sig strips the byte-order mark some ONS CSVs start with.

    Parameters
    ----------
    file_path : Path
        ONS lookup CSV.
    columns : dict
        Lowercase column name in the file -> name to use in the output.

    Returns
    -------
    pandas.DataFrame
        The selected columns, renamed, as strings.
    """

    lookup = pd.read_csv(file_path, dtype=str, encoding="utf-8-sig")
    lookup.columns = lookup.columns.str.lower()
    return lookup[list(columns)].rename(columns=columns)


def clip_to_output_areas(addressbase, oa_boundaries):
    """Keep rows whose point falls in an output area, and add its OA code.

    Points are built from x_coordinate / y_coordinate (British National Grid).
    A point lying exactly on a boundary shared by two OAs matches both; the
    first match is kept so every row gets exactly one OA code.

    Parameters
    ----------
    addressbase : pandas.DataFrame
        AddressBase Plus rows.
    oa_boundaries : geopandas.GeoDataFrame
        Output of load_oa_boundaries.

    Returns
    -------
    pandas.DataFrame
        The rows inside the boundaries, with the OA code column added
        (oa11cd or oa21cd). Plain DataFrame, no geometry column.
    """

    points = gpd.GeoDataFrame(
        addressbase,
        geometry=gpd.points_from_xy(
            addressbase["x_coordinate"], addressbase["y_coordinate"]
        ),
        crs=BNG_CRS,
    )
    joined = gpd.sjoin(points, oa_boundaries, how="inner", predicate="intersects")
    joined = joined[~joined.index.duplicated(keep="first")].sort_index()

    n_kept, n_total = len(joined), len(addressbase)
    print(f"Kept {n_kept:,} of {n_total:,} rows inside the output areas")
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"]))


def add_area_codes(addressbase, lookup, oa_column):
    """Add LSOA and LAD codes to addressbase by joining on its OA code.

    Raises if the lookup has duplicate OA codes, or if any row's OA code
    is not in the lookup.

    Parameters
    ----------
    addressbase : pandas.DataFrame
        AddressBase Plus rows with an OA code column (oa11cd or oa21cd).
    lookup : pandas.DataFrame
        Output of load_oa_lookup, containing oa_column.
    oa_column : str
        The column to join on ("oa11cd" or "oa21cd").

    Returns
    -------
    pandas.DataFrame
    """

    addressbase = addressbase.merge(
        lookup, on=oa_column, how="left", validate="many_to_one"
    )
    added_columns = [c for c in lookup.columns if c != oa_column]
    n_unmatched = addressbase[added_columns[0]].isna().sum()
    if n_unmatched:
        raise ValueError(f"{n_unmatched:,} rows have an {oa_column} not in the lookup")
    return addressbase


def rename_columns(addressbase):
    """Rename pre-epoch-39 columns to their epoch-39+ names (see COLUMNS_TO_RENAME).

    This lets all years share one set of column names.
    """

    return addressbase.rename(columns=COLUMNS_TO_RENAME)


def align_columns(addressbase):
    """Give addressbase exactly the COLUMNS_TO_KEEP columns, in that order.

    Columns in COLUMNS_TO_KEEP that addressbase lacks are added and filled
    with NA.
    Columns not in COLUMNS_TO_KEEP are dropped. Both lists are printed.

    Parameters
    ----------
    addressbase : pandas.DataFrame
        One year of AddressBase Plus.

    Returns
    -------
    pandas.DataFrame
    """

    missing = [c for c in COLUMNS_TO_KEEP if c not in addressbase.columns]
    dropped = [c for c in addressbase.columns if c not in COLUMNS_TO_KEEP]
    print("missing:", missing)
    print("dropped:", dropped)
    return addressbase.reindex(columns=COLUMNS_TO_KEEP)


def add_is_residential(addressbase):
    """Return addressbase with an added boolean column is_residential_space.

    True where class is "R" (residential, not further classified) or starts
    with "RD" (dwelling) or "RH" (house in multiple occupation), as recorded
    in this year's snapshot. NA where class is missing.
    """

    is_unclassified_residential = addressbase["class"].eq("R")
    is_dwelling_or_hmo = addressbase["class"].str[:2].isin(["RD", "RH"])
    return addressbase.assign(
        is_residential_space=is_unclassified_residential | is_dwelling_or_hmo
    )


def build_addressbase_spine(addressbase_by_year):
    """Build one row per UPRN that appears in any year.

    For each year, records whether the UPRN was residential and its state
    in that year (NA if the UPRN was absent). Coordinates and area codes
    come from the most recent year in which the UPRN has a value: 2021
    codes from 2026 or 2021, and 2011 codes from 2011 only (so they are
    NA for UPRNs absent from 2011).

    Assumes each UPRN appears at most once per year.

    Parameters
    ----------
    addressbase_by_year : dict
        Year -> AddressBase Plus DataFrame, with is_residential_space added.

    Returns
    -------
    pandas.DataFrame
        Columns: uprn, x_coordinate, y_coordinate, oa11cd, lsoa11cd,
        lad11cd, oa21cd, lsoa21cd, lad21cd, then is_residential_<year>
        and state_<year> for each year.
    """

    uprns = pd.Index(
        pd.concat(
            [addressbase["uprn"] for addressbase in addressbase_by_year.values()]
        ).unique(),
        name="uprn",
    )
    spine = pd.DataFrame(index=uprns)
    coords = pd.DataFrame(
        index=uprns, columns=["x_coordinate", "y_coordinate"], dtype=float
    )
    area_codes = pd.DataFrame(index=uprns, columns=AREA_CODE_COLUMNS, dtype="string")
    for year, addressbase in sorted(addressbase_by_year.items()):
        addressbase = addressbase.set_index("uprn")[
            [
                "is_residential_space",
                "state",
                "x_coordinate",
                "y_coordinate",
                *AREA_CODE_COLUMNS,
            ]
        ].reindex(uprns)
        spine[f"is_residential_{year}"] = addressbase["is_residential_space"]
        spine[f"state_{year}"] = addressbase["state"]
        coords = addressbase[["x_coordinate", "y_coordinate"]].combine_first(coords)
        area_codes = (
            addressbase[AREA_CODE_COLUMNS].astype("string").combine_first(area_codes)
        )
    return pd.concat([coords, area_codes, spine], axis=1).reset_index()


def filter_addressbase_spine(spine):
    """Keep UPRNs that were residential and in use, vacant (or missing a state) in at least one year.

    Keeps the following "state" values:
    2 In use
    3 Unoccupied / vacant / derelict
    NA (because state variable is optional in AddressBase)

    Drops the following "state" values:
    1 Under construction
    4 No longer existing
    6 Planning permission granted

    Expects the residential_ and state_ columns for 2011, 2021 and 2026, as built by
    build_addressbase_spine.
    """

    mask = (
        (
            spine["is_residential_2011"]
            & (spine["state_2011"].isin(["2", "3"]) | spine["state_2011"].isna())
        )
        | (
            spine["is_residential_2021"]
            & (spine["state_2021"].isin(["2", "3"]) | spine["state_2021"].isna())
        )
        | (
            spine["is_residential_2026"]
            & (spine["state_2026"].isin(["2", "3"]) | spine["state_2026"].isna())
        )
    )
    return spine[mask.fillna(False)].copy()


def build_la_addresses(addressbase):
    """Build a single address string per row from the local authority fields.

    Combines organisation, secondary and primary addressable objects
    (SAO and PAO), street, locality and town into one comma-separated string.

    Parameters
    ----------
    addressbase : pandas.DataFrame
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
        FROM addressbase
    """
    result = duckdb.sql(query).df()
    result['postcode'] = result['postcode'].str.replace(r'\s+', ' ', regex=True)
    return result


def build_rm_addresses(addressbase):
    """Build a single address string per row from the Royal Mail (PAF) fields.

    Combines department, organisation, building, thoroughfare, locality
    and post town into one comma-separated string. Rows without a Royal Mail
    address get an empty string.

    Parameters
    ----------
    addressbase : pandas.DataFrame
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
        FROM addressbase
    """
    result = duckdb.sql(query).df()
    result['postcode'] = result['postcode'].str.replace(r'\s+', ' ', regex=True)
    return result


def build_address_list(spine, addressbase_by_year):
    """Build LA and Royal Mail addresses for every spine UPRN in every year.

    Royal Mail addresses are not built for 2011.
    Blank addresses are dropped. Each unique (uprn, address, postcode) appears
    once, with a list of every type and year it was found in.

    Parameters
    ----------
    spine : pandas.DataFrame
        Output of filter_addressbase_spine; only its uprn column is used.
    addressbase_by_year : dict
        Year -> harmonised AddressBase Plus DataFrame.

    Returns
    -------
    pandas.DataFrame
        Columns: uprn, address, postcode, appears_in
        (e.g. "LA 2011, LA 2021, RM 2021, LA 2026, RM 2026").
    """
    uprns = set(spine["uprn"])
    address_tables = []

    for year, addressbase in addressbase_by_year.items():
        addressbase = addressbase[addressbase["uprn"].isin(uprns)]

        la_addresses = build_la_addresses(addressbase)
        la_addresses["source"] = f"LA {year}"
        address_tables.append(la_addresses)

        if year != 2011:  # 2011 has no usable Royal Mail fields
            rm_addresses = build_rm_addresses(addressbase)
            rm_addresses["source"] = f"RM {year}"
            address_tables.append(rm_addresses)

    addresses = pd.concat(address_tables, ignore_index=True)

    is_blank = addresses["address"].fillna("").str.strip(" ,") == ""
    addresses = addresses[~is_blank]

    addresses = (
        addresses.groupby(["uprn", "address", "postcode"], dropna=False)["source"]
        .agg(lambda s: ", ".join(s.unique()))
        .reset_index(name="appears_in")
    )

    return addresses
