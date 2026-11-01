# MOSDAC Products Report (Phase 0)

Generated 2026-10-29T04:56:00+00:00 from the anonymous MOSDAC catalogue (`https://mosdac.gov.in/apios/datasets.json`). Machine-readable copy: `nowcast/config/products.yaml`.

Backfill window: 2026-05-01 to 2026-10-28. Completeness = files found / (days x 48 half-hourly slots).

| Dataset ID | Description | Mean file | Slots (UTC min) | Archive since | Window files | Window GB | Completeness |
|---|---|---|---|---|---|---|---|
| `3SIMG_L1B_STD` | Level 1B full disk, 6 channels, satellite projection | 413.6 MB | :00, :30 | 2024-05-16 | 8114 | 3362.8 | 93% |
| `3SIMG_L1C_ASIA_MER` | Level 1C Asia sector, Mercator projection | 23.7 MB | :00, :30 | 2024-05-16 | 8116 | 196.8 | 93% |
| `3SIMG_L2B_CMK` | Level 2 cloud mask (label) | 9.1 MB | :00, :30 | 2024-06-11 | 6997 | 64.0 | 80% |
| `3SIMG_L2B_CTP` | Level 2 cloud top pressure / temperature | 2.0 MB | :00, :30 | 2024-07-13 | 6974 | 15.1 | 80% |
| `3SIMG_L2C_FOG` | Level 2 fog flag (winter IGP check) | 0.1 MB | :00, :30 | 2024-05-16 | 5281 | 0.6 | 61% |
| `3SIMG_L2C_INS` | Level 2 surface insolation (Goal 2) | 19.3 MB | :00, :30 | 2024-06-14 | 6498 | 135.5 | 75% |
| `3SIMG_L2P_AMV` | Level 2 atmospheric motion vectors (motion cross-check) | 0.8 MB | :00, :30 | 2024-05-16 | 7267 | 5.8 | 84% |
| `3RIMG_L1B_STD` | Level 1B full disk, 6 channels, satellite projection | 408.4 MB | :15, :45 | 2016-10-11 | 7848 | 3361.8 | 90% |
| `3RIMG_L1C_ASIA_MER` | Level 1C Asia sector, Mercator projection | 21.4 MB | :15, :45 | 2016-10-03 | 7857 | 190.2 | 90% |
| `3RIMG_L2B_CMK` | Level 2 cloud mask (label) | 9.1 MB | :15, :45 | 2016-10-11 | 7026 | 64.5 | 81% |
| `3RIMG_L2B_CTP` | Level 2 cloud top pressure / temperature | 2.1 MB | :15, :45 | 2018-11-30 | 7023 | 16.3 | 81% |
| `3RIMG_L2C_FOG` | Level 2 fog flag (winter IGP check) | 0.1 MB | :15, :45 | 2016-10-26 | 6054 | 0.7 | 70% |
| `3RIMG_L2C_INS` | Level 2 surface insolation (Goal 2) | 17.7 MB | :15, :45 | 2016-11-09 | 6486 | 129.3 | 75% |
| `3RIMG_L2P_AMV` | Level 2 atmospheric motion vectors (motion cross-check) | not available | | | | | |

## Filename examples

- `3SIMG_29OCT2026_0400_L1B_STD_V01R00.h5`
- `3SIMG_29OCT2026_0400_L1C_ASIA_MER_V01R00.h5`
- `3SIMG_29OCT2026_0400_L2B_CMK_V01R00.h5`
- `3SIMG_29OCT2026_0400_L2B_CTP_V01R00.h5`
- `3SIMG_29OCT2026_0030_L2C_FOG_V01R00.h5`
- `3SIMG_29OCT2026_0400_L2C_INS_V01R00.h5`
- `3SIMG_29OCT2026_0400_L2P_AMV_V01R00.h5`
- `3RIMG_29OCT2026_0415_L1B_STD_V01R00.h5`
- `3RIMG_29OCT2026_0415_L1C_ASIA_MER_V01R00.h5`
- `3RIMG_29OCT2026_0415_L2B_CMK_V01R00.h5`
- `3RIMG_29OCT2026_0415_L2B_CTP_V01R00.h5`
- `3RIMG_29OCT2026_0415_L2C_FOG_V01R00.h5`
- `3RIMG_29OCT2026_0415_L2C_INS_V01R00.h5`

## Download volume for the backfill window (streamed, then deleted)

| Route | Inputs GB | Cloud mask GB | Total GB to download |
|---|---|---|---|
| Full disk L1B_STD + CMK | 6725 | 128 | 6853 |
| Asia sector L1C_ASIA_MER + CMK | 387 | 128 | 516 |

Free disk at report time: 80 GB.

Open items, resolved by `python -m nowcast.phase0.inspect_h5` once credentials are set:
channels and resolution inside L1C_ASIA_MER, cloud-mask class codes, lat/lon layout of L1B.
