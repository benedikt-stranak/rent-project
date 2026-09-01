"""Working with AddressBase Plus"""

from pathlib import Path
from zipfile import ZipFile

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

def rename_columns(addressbase_single_year):
    """Rename columns in AddressBase.
    
    Parameters
    -----
    addressbase_single_year: pandas cotaining one year of AddressBase Plus
    """
    renamed = addressbase_single_year.rename(columns=COLUMN_RENAME)
    return renamed

def align_columns(addressbase_by_year):
    """ K.
    """
    aligned = {}
    for year, df in addressbase_by_year.items():
        missing = [c for c in COLUMNS_KEEP if c not in df.columns]
        dropped = [c for c in df.columns if c not in COLUMNS_KEEP]
        print(year, "missing:", missing)
        print(year, "dropped:", dropped)
        aligned[year] = df.reindex(columns=COLUMNS_KEEP)
    return aligned
   

def clip_greater_london(df):
    """Takes pandas dataframe
    Returns it filtered by administrative_area column.

    Parameters
    -----
    df: pandas dataframe with administrative_area column
    """
    df = df[df['administrative_area'].isin(LONDON_BOROUGHS)]
    return df

def build_addressbase_spine(dictionary):
    """K

    Parameters
    -----
    dictionary:
    """
    uprns = pd.Index(pd.concat([df['uprn'] for df in dictionary.values()]).unique(), name='uprn')
    out = pd.DataFrame({'uprn': uprns})
    for year, df in dictionary.items():
        out[f'in{year}'] = uprns.isin(df['uprn'])
    return out
