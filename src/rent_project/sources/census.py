"""Tools to work with 2011 and 2021 Census datasets."""

import pandas as pd

from rent_project.config import (
    DATA_DIRECTORY,
)

TENURE_2011_PATH = (
    DATA_DIRECTORY / "raw/area-housing-data/tenure/census-tenure-2011-oa-QS405EW-machine-readable.csv"
)
TENURE_2021_PATH = (
    DATA_DIRECTORY / "raw/area-housing-data/tenure/census-tenure-2021-oa-TS054-machine-readable.csv"
)


def oa_tenure_targets_2011(spine):
    """
    Build 2011 OA-level dwelling counts by tenure, plus unoccupied dwellings.

    Parameters
    ----------
    spine : pd.DataFrame
        Dwelling-level spine with columns `oa11cd`, `is_residential_2011`
        and `state_2011`.

    Returns
    -------
    pd.DataFrame
        One row per OA with `oa11cd`, tenure counts (Int64), and `unoccupied`.
    """

    # Identify unoccupied dwellings in each OA
    # FUTURE: check dwelling totals against Census (OA, see data-checks)
    # FUTURE: calibrate unoccupied counts to Census (probably LSOA)

    res = spine["is_residential_2011"].fillna(False).astype(bool)
    state = spine["state_2011"]

    flags = pd.DataFrame({
        "oa11cd": spine["oa11cd"],
        "dwellings": res & (state.isin(["2", "3"]) | state.isna()),
        "unoccupied": res & state.eq("3"),
        "occupied": res & (state.eq("2") | state.isna()),
    })

    oa_dwellings_2011 = flags.groupby("oa11cd", as_index=False).sum()

    # Allocate tenure to dwellings proportionally to household tenure shares
    # FUTURE: calibrate this to subnational estimates of dwellings by tenure (LAD)

    oa_households_2011 = pd.read_csv(TENURE_2011_PATH)
    tenure_cols = [
        c for c in oa_households_2011.columns if c not in ("oa11cd", "households")
    ]

    shares = oa_households_2011[tenure_cols].div(
        oa_households_2011["households"], axis=0
    )
    oa_household_proportions_2011 = pd.concat(
        [oa_households_2011[["oa11cd"]], shares], axis=1
    )

    merged = oa_dwellings_2011.merge(
        oa_household_proportions_2011, on="oa11cd", how="left", validate="1:1"
    )

    oa_dwellings_2011_tenure = merged[["oa11cd"]].copy()
    for c in tenure_cols:
        oa_dwellings_2011_tenure[c] = merged[c] * merged["occupied"]
    oa_dwellings_2011_tenure[tenure_cols] = (
        oa_dwellings_2011_tenure[tenure_cols].round().astype("Int64")
    )
    oa_dwellings_2011_tenure["unoccupied"] = merged["unoccupied"]

    return oa_dwellings_2011_tenure


def oa_tenure_targets_2021(spine):
    """
    Build 2021 OA-level dwelling counts by tenure, plus unoccupied dwellings.

    Parameters
    ----------
    spine : pd.DataFrame
        Dwelling-level spine with columns `oa11cd`, `is_residential_2021`
        and `state_2021`.

    Returns
    -------
    pd.DataFrame
        One row per OA with `oa21cd`, tenure counts (Int64), and `unoccupied`.
    """

    # Identify unoccupied dwellings in each OA
    # FUTURE: check dwelling totals against Census (OA, see data-checks)
    # FUTURE: calibrate unoccupied counts to Census (probably LSOA)

    res = spine["is_residential_2021"].fillna(False).astype(bool)
    state = spine["state_2021"]

    flags = pd.DataFrame({
        "oa21cd": spine["oa21cd"],
        "dwellings": res & (state.isin(["2", "3"]) | state.isna()),
        "unoccupied": res & state.eq("3"),
        "occupied": res & (state.eq("2") | state.isna()),
    })

    oa_dwellings_2021 = flags.groupby("oa21cd", as_index=False).sum()

    # Allocate tenure to dwellings proportionally to household tenure shares
    # FUTURE: calibrate this to subnational estimates of dwellings by tenure (LAD)

    oa_households_2021 = pd.read_csv(TENURE_2021_PATH)
    tenure_cols = [
        c for c in oa_households_2021.columns if c not in ("oa21cd", "households")
    ]

    shares = oa_households_2021[tenure_cols].div(
        oa_households_2021["households"], axis=0
    )
    oa_household_proportions_2021 = pd.concat(
        [oa_households_2021[["oa21cd"]], shares], axis=1
    )

    merged = oa_dwellings_2021.merge(
        oa_household_proportions_2021, on="oa21cd", how="left", validate="1:1"
    )

    oa_dwellings_2021_tenure = merged[["oa21cd"]].copy()
    for c in tenure_cols:
        oa_dwellings_2021_tenure[c] = merged[c] * merged["occupied"]
    oa_dwellings_2021_tenure[tenure_cols] = (
        oa_dwellings_2021_tenure[tenure_cols].round().astype("Int64")
    )
    oa_dwellings_2021_tenure["unoccupied"] = merged["unoccupied"]

    return oa_dwellings_2021_tenure
