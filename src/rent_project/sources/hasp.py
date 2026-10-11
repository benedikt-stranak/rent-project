"""Tools to work with HASP WhenFresh/Zoopla datasets."""

from pathlib import Path

import duckdb
import pandas as pd
from uk_address_matcher import (
    AddressMatcher,
    ExactMatchStage,
    PeeledAddressStage,
    SplinkStage,
    UniqueTrigramStage,
)

HASP_ADDRESS_COLUMNS = [
    "address_1",
    "address_2",
    "address_3",
    "address_4",
    "address_5",
    "address_6",
]


def add_hasp_property_id(spine, addresses, rent_properties):
    """Add the HASP property_id to the AddressBase spine by address matching.

    Concatenates the HASP address columns, matches them against the canonical
    AddressBase addresses
    and left-joins the resulting property_id onto the spine by UPRN.
    Prints the matcher's match metrics.

    PROVISIONAL: skipping SplinkStage (probabilistic matching).

    PROVISIONAL: any UPRN matched by more than one HASP property is dropped
    entirely, so those spine rows get a missing hasp_property_id.

    Parameters
    ----------
    spine : pandas.DataFrame
        Output of build_addressbase_spine(); one row per UPRN.
    addresses : pandas.DataFrame
        Output of build_address_list(): uprn, address, postcode.
    rent_properties : pandas.DataFrame
        HASP rent_properties table with property_id, postcode and address columns (HASP_ADDRESS_COLUMNS). Not modified.

    Returns
    -------
    pandas.DataFrame
        The spine with an added hasp_property_id column (NA where unmatched).
    """

    # Concatenate the address columns (vectorised), skipping missing parts
    out = None
    for col in HASP_ADDRESS_COLUMNS:
        s = rent_properties[col].astype("string")
        if out is None:
            out = s
        else:
            out = out.str.cat(s, sep=", ").fillna(out).fillna(s)
    address = out.fillna("")
    del out, s

    hasp_addresses_df = pd.DataFrame(
        {
            "unique_id": rent_properties["property_id"],
            "address_concat": address,
            "postcode": rent_properties["postcode"],
        }
    )
    addressbase_addresses_df = pd.DataFrame(
        {
            "unique_id": addresses["uprn"],
            "address_concat": addresses["address"],
            "postcode": addresses["postcode"],
        }
    )

    with duckdb.connect() as con:
        matcher = AddressMatcher(
            canonical_addresses=con.from_df(addressbase_addresses_df),
            addresses_to_match=con.from_df(hasp_addresses_df),
            con=con,
            stages=[
                ExactMatchStage(),
                PeeledAddressStage(),
                UniqueTrigramStage(),
                # SplinkStage(
                #    final_match_weight_threshold=10,  # recommended 10.0
                #    final_distinguishability_threshold=2.1,  # recommended 1.0; initial testing: >2.0
                # ),
            ],
        )
        result = matcher.match()
        print(result.match_metrics())
        matches = (
            result.matches()
            .to_df()
            .rename(
                columns={
                    "resolved_canonical_id": "uprn",
                    "unique_id": "hasp_property_id",
                }
            )
            .dropna(subset=["uprn"])
        )

    matches["uprn"] = matches["uprn"].astype("Int64")

    # PROVISIONAL: drop every UPRN that more than one HASP property matched
    matches = matches[~matches.duplicated("uprn", keep=False)]

    spine_hasp = spine.merge(
        matches[["hasp_property_id", "uprn"]],
        how="left",
        on="uprn",
        validate="one_to_one",
    )
    return spine_hasp


def add_listed_rents(spine, listings):
    """
    Add annual listed rents from property listings to the spine, one column per year.

    Listings are pivoted so that each property has one row, with a column for
    each `source_year`. Prices are converted from per calendar week (pcw) to
    per annum (pa) by multiplying by 52. These are joined onto spine rows that
    have a `hasp_property_id`. Spine rows without a `hasp_property_id` are kept
    unchanged, with missing values in the new columns.

    Parameters
    ----------
    spine : pd.DataFrame
        Dwelling-level spine with a column `hasp_property_id`.
    listings : pd.DataFrame
        Listings data with columns `property_id`, `source_year` and
        `listed_price` (rent per calendar week). Must have at most one row per
        `property_id` and `source_year` combination.

    Returns
    -------
    pd.DataFrame
        A copy of `spine` with one `listed_rent_{year}` column (rent per annum)
        added for each `source_year` in `listings`. Rows are reordered so that
        those with a `hasp_property_id` come first, followed by those without.
        The input `spine` is not modified.
    """
    listings_wide = (
        listings.pivot(
            index="property_id",
            columns="source_year",
            values="listed_price",
        )
        .mul(52)
        .add_prefix("listed_rent_")
        .rename_axis(columns=None)
        .reset_index()
        .rename(columns={"property_id": "hasp_property_id"})
    )

    mask = spine["hasp_property_id"].notna()

    spine_matched = spine.loc[mask].merge(
        listings_wide,
        how="left",
        on="hasp_property_id",
        validate="one_to_one",
    )
    spine_unmatched = spine.loc[~mask]

    return pd.concat([spine_matched, spine_unmatched], ignore_index=True)
