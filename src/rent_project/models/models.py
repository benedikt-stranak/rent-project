"""Various models."""

import numpy as np
import pandas as pd


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