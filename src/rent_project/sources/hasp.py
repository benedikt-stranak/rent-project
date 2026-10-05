"""Tools to work with HASP WhenFresh/Zoopla datasets."""

from pathlib import Path
from zipfile import ZipFile

import duckdb
import pandas as pd
from uk_address_matcher import AddressMatcher

ADDRESS_COLUMNS = ['address_1', 'address_2', 'address_3', 'address_4', 'address_5', 'address_6']

def add_hasp_property_id(spine, addresses, rent_properties):
    """K."""
    rent_properties['address'] = rent_properties[ADDRESS_COLUMNS].apply(lambda row: ', '.join(row.dropna()), axis=1)

    con = duckdb.connect()

    canonical_addresses = addresses[["uprn","address","postcode"]]
    addresses_to_match = rent_properties[["property_id","address","postcode"]]

    matcher = AddressMatcher(
        canonical_addresses=canonical_addresses,
        addresses_to_match=addresses_to_match,
        con=con,
    )
    result = matcher.match()
    matches_df = result.matches().to_df()




