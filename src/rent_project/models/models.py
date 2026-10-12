"""Various models."""

import numpy as np
import pandas as pd

from rent_project.config import (
    DATA_DIRECTORY,
)


def add_private_rented(spine, oa_targets_2011, oa_targets_2021):
    """
    Allocate private rented dwellings in the spine to match 2011 and 2021 targets.

    For each census year and each output area (OA), occupied dwellings are
    randomly selected as private rented until the OA's census target is met.
    Dwellings with a `hasp_property_id` are selected first; other occupied
    dwellings are only selected once those are exhausted. If an OA has fewer
    occupied dwellings than its target, all of them are flagged. Selection is
    reproducible (seed 0).

    Parameters
    ----------
    spine : pd.DataFrame
        Dwelling-level spine with a unique index and columns `hasp_property_id`,
        `oa11cd`, `is_residential_2011`, `state_2011`, `oa21cd`,
        `is_residential_2021` and `state_2021`.
    oa_targets_2011 : pd.DataFrame
        One row per 2011 OA with columns `oa11cd` and `private_rented` (the
        number of private rented dwellings).
    oa_targets_2021 : pd.DataFrame
        One row per 2021 OA with columns `oa21cd` and `private_rented`.

    Returns
    -------
    pd.DataFrame
        A copy of `spine` with boolean columns `private_rented_2011` and
        `private_rented_2021` added. The input `spine` is not modified.
    """
    spine = spine.copy()
    rng = np.random.default_rng(0)

    for year, oa_targets in [(2011, oa_targets_2011), (2021, oa_targets_2021)]:
        oa_col = f"oa{str(year)[2:]}cd"

        res = spine[f"is_residential_{year}"].fillna(False).astype(bool)
        state = spine[f"state_{year}"]
        occupied = res & (state.eq("2") | state.isna()) & spine[oa_col].notna()

        cand = pd.DataFrame({
            "oa": spine.loc[occupied, oa_col],
            "has_hasp": spine.loc[occupied, "hasp_property_id"].notna(),
            "rand": rng.random(occupied.sum()),
        })
        targets = oa_targets.set_index(oa_col)["private_rented"].fillna(0).astype(int)
        cand["target"] = cand["oa"].map(targets).fillna(0).astype(int)

        cand = cand.sort_values(["oa", "has_hasp", "rand"], ascending=[True, False, True])
        cand["rank"] = cand.groupby("oa").cumcount()

        chosen = cand.index[cand["rank"] < cand["target"]]
        spine[f"private_rented_{year}"] = spine.index.isin(chosen)

    return spine


def add_uprated_rents(spine, target_years):
    """
    Estimate rent in target years by uprating or downrating the nearest listing.

    For each address with at least one listing (`listed_rent_YYYY` columns),
    the listing closest in time to each target year is scaled by the local
    authority's cumulative rent growth between the listing year and the target
    year. Ties go to the earlier listing year. Addresses with no listing get NaN.

    In the rent index, `rent_growth_Y` is the growth ratio from year Y-1 to year Y
    (e.g. 1.053 for 5.3%).

    Parameters
    ----------
    spine : pd.DataFrame
        Address-level spine with columns `lad11cd`, `lad21cd` (each address
        has at least one; they are interchangeable) and `listed_rent_YYYY`.
    target_years : iterable of int
        Years for which to estimate rent.

    Returns
    -------
    pd.DataFrame
        A copy of `spine` with float columns `est_rent_YYYY` added for each
        target year. The input `spine` is not modified.
    """
    spine = spine.copy()
    rent_indices = pd.read_csv(
        DATA_DIRECTORY / "interim/area-housing-data/lad-amalgamated-rental-index.csv"
    )

    rent_cols = sorted(c for c in spine.columns if c.startswith("listed_rent_"))
    listed_years = np.array([int(c[-4:]) for c in rent_cols])
    rents = spine[rent_cols].to_numpy(dtype=float)

    growth = rent_indices.set_index("ladcd")
    cum = growth.filter(like="rent_growth_").rename(columns=lambda c: int(c[-4:]))
    cum = cum.loc[:, 2012:2026].cumprod(axis=1)
    cum.insert(0, 2011, 1.0)

    lad = spine["lad21cd"].fillna(spine["lad11cd"]).astype(object)
    idx = cum.reindex(lad.values)
    idx_arr = idx.to_numpy()

    rows = np.arange(len(spine))
    has_listing = ~np.isnan(rents).all(axis=1)

    for t in target_years:
        dist = np.where(np.isnan(rents), np.inf, np.abs(listed_years - t))
        nearest = dist.argmin(axis=1)
        src_year = listed_years[nearest]
        src_rent = rents[rows, nearest]

        idx_src = idx_arr[rows, src_year - 2011]
        idx_tgt = idx[t].to_numpy()
        est = src_rent * idx_tgt / idx_src

        spine[f"est_rent_{t}"] = np.where(has_listing, est, np.nan)

    return spine
    

import numpy as np
from scipy.spatial import cKDTree


def add_estimated_rents(spine, target_years):
    """
    Fill missing rent estimates for private-rented addresses using nearby addresses.

    Targets are addresses that are private rented in 2011 or 2021 and have no
    rent estimate. Each target gets, for every target year, the median of the
    8 nearest addresses with an estimate, ignoring any further than 1 km.
    Targets with no donor within 1 km stay NaN. Donors are never imputed values.

    An address either has all `est_rent_YYYY` values or none of them, so the
    neighbour search is done once and reused for every year.

    Parameters
    ----------
    spine : pd.DataFrame
        Address-level spine with columns `x_coordinate`, `y_coordinate`,
        `private_rented_2011`, `private_rented_2021` and `est_rent_YYYY` for
        each target year.
    target_years : iterable of int
        Years for which to fill rent estimates.

    Returns
    -------
    pd.DataFrame
        A copy of `spine` with missing `est_rent_YYYY` values filled in, plus
        columns `est_rent_imputed` (bool), `est_rent_n_donors` (donors found)
        and `est_rent_donor_dist` (mean distance to them, in metres). The
        latter two are NaN for addresses that were not targets. The input
        `spine` is not modified.
    """
    
    spine = spine.copy()
    rent_cols = [f"est_rent_{y}" for y in target_years]

    # Donors have a rent estimate; targets are private rented without one
    is_donor = spine[rent_cols[0]].notna().to_numpy()
    is_rented = (spine["private_rented_2011"] | spine["private_rented_2021"]).to_numpy()
    is_target = is_rented & ~is_donor

    # Find the nearest donors for each target (once, for all years)
    xy = spine[["x_coordinate", "y_coordinate"]].to_numpy()
    tree = cKDTree(xy[is_donor])
    dist, neighbours = tree.query(xy[is_target], k=8, distance_upper_bound=3000)
    found = np.isfinite(dist)  # (n_targets, k); True where a neighbour slot holds a real donor

    # Median rent of the neighbours, for each year
    for col in rent_cols:
        donor_rents = spine.loc[is_donor, col].to_numpy(dtype=float)
        donor_rents = np.append(donor_rents, np.nan)  # padding for missing neighbours
        spine.loc[is_target, col] = np.nanmedian(donor_rents[neighbours], axis=1)

    mean_dist = np.nanmean(np.where(found, dist, np.nan), axis=1)

    # Flags, reported once
    n_donors = np.full(len(spine), np.nan)
    n_donors[is_target] = found.sum(axis=1)

    donor_dist = np.full(len(spine), np.nan)
    donor_dist[is_target] = mean_dist

    spine["est_rent_imputed"] = is_target & (n_donors > 0)
    spine["est_rent_n_donors"] = n_donors
    spine["est_rent_donor_dist"] = donor_dist

    return spine