"""Working with AddressBase Plus"""

from pathlib import Path
from zipfile import ZipFile

import duckdb
import pandas as pd

LONDON_BOROUGHS = ['LONDON','GREATER LONDON','CITY OF WESTMINSTER','TOWER HAMLETS','LB OF TOWER HAMLETS','WANDSWORTH','CROYDON','BARNET','LONDON BOROUGH OF BARNET','SOUTHWARK','LAMBETH','EALING','BROMLEY','LONDON BOROUGH OF BROMLEY','CAMDEN','BRENT','LEWISHAM','NEWHAM','ENFIELD','GREENWICH','LONDON BOROUGH OF GREENWICH','HACKNEY','ISLINGTON','HILLINGDON','HARINGEY','LONDON BOROUGH OF HARINGEY','WALTHAM FOREST','HOUNSLOW','LONDON BOROUGH OF HOUNSLOW','HAMMERSMITH AND FULHAM','HAMMERSMITH','LBHF','REDBRIDGE','HAVERING','LONDON BOROUGH OF HAVERING','KENSINGTON AND CHELSEA','BEXLEY','MERTON','HARROW','RICHMOND UPON THAMES','BARKING AND DAGENHAM','SUTTON','KINGSTON UPON THAMES','CITY OF LONDON']
COLUMNS_KEEP = ['uprn', 'parent_uprn', 'multi_occ_count', 'udprn', 'addressbase_postal', 'state', 'class', 'level', 'x_coordinate', 'y_coordinate', 'usrn', 'ward_code', 'parish_code', 'local_custodian_code', 'country', 'state_date', 'la_start_date', 'rm_start_date', 'last_update_date', 'entry_date', 'department_name', 'rm_organisation_name', 'sub_building_name', 'building_name', 'building_number', 'po_box_number', 'dependent_thoroughfare', 'thoroughfare', 'double_dependent_locality', 'dependent_locality', 'post_town', 'postcode', 'postcode_type', 'delivery_point_suffix', 'la_organisation', 'sao_text', 'sao_start_number', 'sao_start_suffix', 'sao_end_number', 'sao_end_suffix', 'pao_text', 'pao_start_number', 'pao_start_suffix', 'pao_end_number', 'pao_end_suffix', 'street_description', 'area_name', 'locality', 'town_name', 'administrative_area', 'postcode_locator', 'rpc', 'usrn_match_indicator', 'official_flag', 'os_address_toid', 'os_address_toid_version', 'os_roadlink_toid', 'os_roadlink_toid_version', 'os_topo_toid', 'os_topo_toid_version', 'voa_ct_record', 'voa_ndr_record', 'voa_ndr_p_desc_code', 'voa_ndr_scat_code']
COLUMN_RENAME = {
    "rm_udprn": "udprn",
    "postal_address": "addressbase_postal",
    "start_date": "la_start_date",
    "organisation_name": "rm_organisation_name",
    "dependent_thoroughfare_name": "dependent_thoroughfare",
    "thoroughfare_name": "thoroughfare",
    "welsh_dependent_thoroughfare_name": "welsh_dependent_thoroughfare",
    "welsh_thoroughfare_name": "welsh_thoroughfare",
    "organisation": "la_organisation",
    "locality_name": "locality"
}

# ----------------------------------------
# Loading AddressBase Plus Schema
# ----------------------------------------

def load_schema_old(header_path):
    """Parse a pre-2016 (epoch 38-) header file into column names.
    Define dtypes schema (same for all csv tiles).
    
    Parameters
    -----
    header_path: a path to a csv file with column names.
    """

    columns = pd.read_csv(header_path,header=None,dtype=str).iloc[0].str.lower().tolist()    
    INT_COLUMNS = ['uprn','rm_udprn','parent_uprn','local_custodian_code','sao_start_number','sao_end_number','pao_start_number','pao_end_number','usrn','os_address_toid_version','os_roadlink_toid_version','os_topo_toid_version','voa_ct_record','voa_ndr_record','multi_occ_count']
    FLOAT_COLUMNS = ['x_coordinate', 'y_coordinate']
    DATE_COLUMNS = ['state_date','start_date','end_date','last_update_date','entry_date','process_date']
    STRING_COLUMNS = [c for c in columns if c not in INT_COLUMNS + FLOAT_COLUMNS + DATE_COLUMNS]
    DTYPES = {
        **{c: "Int64" for c in INT_COLUMNS},
        **{c: "float64" for c in FLOAT_COLUMNS},
        **{c: "string" for c in STRING_COLUMNS},
    }
    return {"columns" : columns, "dtypes": DTYPES, "date_columns": DATE_COLUMNS}

def load_schema_new(header_path):
    """Parse a post-2016 (epoch 39+) header file nto column names.
    Define dtypes schema (same for all csv tiles).
    
    Parameters
    -----
    header_path: a path to a csv file with column names.
    """

    columns = pd.read_csv(header_path,header=None,dtype=str).iloc[0].str.lower().tolist()
    INT_COLUMNS = ['uprn','udprn','parent_uprn','local_custodian_code','building_number','sao_start_number','sao_end_number','pao_start_number','pao_end_number','usrn','os_address_toid_version','os_roadlink_toid_version','os_topo_toid_version','voa_ct_record','voa_ndr_record','multi_occ_count']
    FLOAT_COLUMNS = ['x_coordinate', 'y_coordinate', 'latitude', 'longitude']
    DATE_COLUMNS = ['state_date','la_start_date','last_update_date','entry_date','rm_start_date']
    STRING_COLUMNS = [c for c in columns if c not in INT_COLUMNS + FLOAT_COLUMNS + DATE_COLUMNS]
    DTYPES = {
        **{c: "Int64" for c in INT_COLUMNS},
        **{c: "float64" for c in FLOAT_COLUMNS},
        **{c: "string" for c in STRING_COLUMNS},
    }
    return {"columns" : columns, "dtypes": DTYPES, "date_columns": DATE_COLUMNS}

# ----------------------------------------
# Building AddressBase Plus 2026
# ----------------------------------------

def unzip_all(zip_dir, extract_dir):
    """Extract each .zip in zip_dir into extract_dir
    Skip if a folder in extract_dir already exists

    Parameters
    -----
    zip_dir:     path to a directory with one or more .zip files
    extract_dir: path to target directory (existing or new)
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
    
    Parameters
    -----
    schema:    a dictionary with a pre-parsed schema (same for all csv tiles)
    file_path: path to this specific tile's data CSV
    """

    df = pd.read_csv(
        file_path,header=None,
        names=schema["columns"],dtype=schema["dtypes"],
        parse_dates=schema["date_columns"]
    )
    return df

def load_and_concatenate(schema, extract_dir):
    """Load all CSVs and concatenate into a single DataFrame.
    
    Parameters
    -----
    schema: a dictionary with a pre-parsed schema (same for all csv tiles)
    extract_dir: path to a directory with CSV files to be loaded
    """

    csv_paths = sorted(Path(extract_dir).rglob("*.csv"))
    print(f"Loading {len(csv_paths)} tiles")
    tiles = [load_tile(schema,p) for p in csv_paths]
    combined = pd.concat(tiles, ignore_index=True)
    print(f"Loaded {len(combined):,} rows from {len(tiles)} tiles.")
    return combined

# ----------------------------------------
# Loading and filtering AddressBase Plus
# ----------------------------------------

def load_full_addressbase(schema, file_path):
    """Load a full AddressBase Plus CSV.
    
    Parameters
    -----
    schema:    a dictionary with a pre-parsed schema (pre or post epoch 39)
    file_path: path to full AddressBase Plus CSV
    """

    df = pd.read_csv(
        file_path,
        dtype=schema["dtypes"],
        parse_dates=schema["date_columns"]
    )
    return df


def clip_greater_london(df):
    """Takes pandas dataframe
    Returns it filtered by administrative_area column.

    Parameters
    -----
    df: pandas dataframe with administrative_area column
    """
    df = df[df['administrative_area'].isin(LONDON_BOROUGHS)]
    return df


def rename_columns(addressbase_single_year):
    """Rename columns in AddressBase.
    
    Parameters
    -----
    addressbase_single_year: pandas cotaining one year of AddressBase Plus
    """
    renamed = addressbase_single_year.rename(columns=COLUMN_RENAME)
    return renamed


def align_columns(addressbase_by_year):
    """Add docstring"""
    aligned = {}
    for year, df in addressbase_by_year.items():
        missing = [c for c in COLUMNS_KEEP if c not in df.columns]
        dropped = [c for c in df.columns if c not in COLUMNS_KEEP]
        print(year, "missing:", missing)
        print(year, "dropped:", dropped)
        aligned[year] = df.reindex(columns=COLUMNS_KEEP)
    return aligned


def identify_current_residential(df):
    """Add docstring"""
    df['is_residential_space'] = df['class'].eq('R') | df['class'].str[:2].isin(['RD', 'RH'])
    return df


def build_addressbase_spine(dictionary):
    """Add docstring"""
    uprns = pd.Index(pd.concat([df['uprn'] for df in dictionary.values()]).unique(), name='uprn')
    out = pd.DataFrame(index=uprns)
    coords = pd.DataFrame(index=uprns, columns=['x_coordinate', 'y_coordinate'], dtype=float)
    for year in sorted(dictionary):
        df = dictionary[year]
        wave = df.set_index('uprn')[['is_residential_space','state','x_coordinate','y_coordinate']].reindex(uprns)
        out[f'residential_{year}'] = wave['is_residential_space']
        out[f'state_{year}'] = wave['state']
        coords = wave[['x_coordinate', 'y_coordinate']].combine_first(coords)
    return pd.concat([coords,out], axis=1).reset_index()


def filter_addressbase_spine(df):
    mask = (
        (df['residential_2011'] & df['state_2011'].isin(['2', '3'])) |
        (df['residential_2021'] & df['state_2021'].isin(['2', '3'])) |
        (df['residential_2026'] & df['state_2026'].isin(['2', '3']))
    )
    return df[mask.fillna(False)].copy()


# ----------------------------------------
# Building AddressBase Plus addresses
# ----------------------------------------

# this is old

#def build_canonical_address_list(spine, dictionary):
#    uprns = set(spine['uprn'])
#    keys = []
#    for year, df in dictionary.items():
#        matches = df[df['uprn'].isin(uprns)]
#        for index,row in matches.iterrows():
#            key_la = build_la_address(row)
#            key_rm = build_rm_address(row)
#            uprn = row['uprn']
#            keys.append({
#                'uprn': uprn,
#                'address': key_la['address'],
#                'postcode': key_la['postcode'],
#                'year': year,
#                'type': 'LA'
#            })
#            keys.append({
#                'uprn': uprn,
#                'address': key_rm['address'],
#                'postcode': key_rm['postcode'],
#                'year': year,
#                'type': 'RM'
#            })
#    return pd.DataFrame(keys)


# these are new - SQL, vectorised

## DuckDB can ingest data from pandas:
### pandas_df = pd.DataFrame({"a": [42]})
### duckdb.sql("SELECT * FROM pandas_df")

## DuckDB can convert query results into pandas:
### duckdb.sql("SELECT 42").df()


def build_la_address(df):
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


def build_rm_address(df):
    """Add docstring"""
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


def build_canonical_address_list(spine, addressbase_by_year):
    uprns = set(spine["uprn"])
    keys = []
    for year, df in addressbase_by_year.items():
        df = df[df["uprn"].isin(uprns)]
        la = build_la_address(df)
        la["year"] = year
        la["type"] = "LA"
        rm = build_rm_address(df)
        rm["year"] = year
        rm["type"] = "RM"
        keys.extend([la, rm])
    return pd.concat(keys, ignore_index=True)