"""
Main pipeline: load SA boundaries + fetch OSM data, compute urbanism metrics.

Usage
-----
    python main.py                        # all statistical areas
    python main.py --muni 5000 5100       # filter by municipality codes
    python main.py --max 50               # process first 50 areas (testing)
    python main.py --resume               # skip already-processed areas
    python main.py --list-layers          # show GDB layer names and exit
"""

import argparse
import os
import sys
import warnings

import pandas as pd
from tqdm import tqdm

import config
from load_boundaries import load_statistical_areas, list_gdb_layers
from calculate_metrics import calculate_sa_metrics


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Compute Israeli SA-level urbanism metrics.")
    p.add_argument(
        "--muni", nargs="*", type=str, default=None,
        dest="muni_codes",
        help="Municipality codes to process. Default: all.",
    )
    p.add_argument(
        "--max", type=int, default=None,
        dest="max_areas",
        help="Cap number of statistical areas processed.",
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Skip areas already present in the checkpoint file.",
    )
    p.add_argument(
        "--list-layers", action="store_true",
        help="List GDB layer names and exit.",
    )
    return p.parse_args()


# ── Checkpointing ─────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    path = config.CHECKPOINT_FILE
    if not os.path.exists(path):
        return set()
    df = pd.read_csv(path, usecols=["sa_code"], dtype=str)
    return set(df["sa_code"].dropna())


def append_checkpoint(rows: list[dict]):
    path = config.CHECKPOINT_FILE
    df = pd.DataFrame(rows)
    header = not os.path.exists(path)
    df.to_csv(path, mode="a", index=False, header=header)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.list_layers:
        print("GDB layers:", list_gdb_layers())
        return

    muni_codes = args.muni_codes or config.FILTER_MUNICIPALITIES
    max_areas = args.max_areas or config.MAX_AREAS

    # 1. Load boundaries
    gdf = load_statistical_areas(muni_codes=muni_codes)

    # 2. Resume: skip already-processed areas
    if args.resume:
        done = load_checkpoint()
        n_skip = gdf["sa_code"].astype(str).isin(done).sum()
        if n_skip:
            gdf = gdf[~gdf["sa_code"].astype(str).isin(done)].copy()
            print(f"  Resuming – skipping {n_skip:,} already-processed areas.")

    # 3. Apply cap
    if max_areas:
        gdf = gdf.head(max_areas)

    print(f"\nProcessing {len(gdf):,} statistical areas …\n")

    results = []
    errors = 0
    batch_size = 20

    for _, row in tqdm(gdf.iterrows(), total=len(gdf), unit="SA"):
        metrics = calculate_sa_metrics(row)
        results.append(metrics)
        if metrics.get("error"):
            errors += 1
        if len(results) % batch_size == 0:
            append_checkpoint(results[-batch_size:])

    remainder = len(results) % batch_size
    if remainder:
        append_checkpoint(results[-remainder:])

    # 4. Save final output
    df = pd.DataFrame(results)
    front = ["sa_code", "sa_name", "muni_code", "muni_name", "area_km2"]
    rest = [c for c in df.columns if c not in front + ["error"]]
    df = df[[c for c in front if c in df.columns] + rest + ["error"]]

    df.to_csv(config.METRICS_OUTPUT_FILE, index=False)
    print(f"\nDone. Results saved to: {config.METRICS_OUTPUT_FILE}")
    print(f"  Statistical areas processed : {len(df):,}")
    print(f"  Errors                      : {errors:,}")

    disp_cols = ["sa_code", "sa_name", "junction_density",
                 "street_density_km_km2", "walkability_index"]
    disp_cols = [c for c in disp_cols if c in df.columns]
    print(f"\nSample:\n{df[disp_cols].head(10).to_string(index=False)}")


if __name__ == "__main__":
    main()
