from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_FILE = Path("auto_diagnost_mock_data.csv")
SAMPLES_PER_CLASS = 600
RANDOM_SEED = 42


def generate_operating_points(
    rng: np.random.Generator,
    sample_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate plausible RPM, engine load, and baseline MAF values."""
    rpm = rng.integers(800, 5500, size=sample_count)
    engine_load = rng.uniform(15.0, 95.0, size=sample_count)

    # Approximation for a 2.3L four-stroke engine.
    volumetric_efficiency = rng.uniform(0.78, 0.98, size=sample_count)
    maf_baseline = 0.00018 * rpm * engine_load * volumetric_efficiency

    return rpm, engine_load, maf_baseline


def generate_normal_samples(
    rng: np.random.Generator,
    sample_count: int,
) -> pd.DataFrame:
    rpm, engine_load, maf_baseline = generate_operating_points(
        rng,
        sample_count,
    )

    maf = maf_baseline + rng.normal(0.0, 0.8, sample_count)
    short_term_trim = rng.normal(0.0, 2.0, sample_count)
    long_term_trim = rng.normal(0.0, 1.5, sample_count)

    return pd.DataFrame(
        {
            "RPM": rpm,
            "Engine_Load_pct": engine_load,
            "Short_Term_Fuel_Trim_pct": short_term_trim,
            "Long_Term_Fuel_Trim_pct": long_term_trim,
            "MAF_g_s": np.maximum(maf, 0.1),
            "Failure_Mode": "normal",
        }
    )


def generate_maf_failure_samples(
    rng: np.random.Generator,
    sample_count: int,
) -> pd.DataFrame:
    rpm, engine_load, maf_baseline = generate_operating_points(
        rng,
        sample_count,
    )

    # Failing MAF reports airflow too low and becomes noticeably unstable.
    maf_bias = rng.uniform(0.55, 0.75, sample_count)
    maf_noise = rng.normal(0.0, 3.0, sample_count)
    maf = (maf_baseline * maf_bias) + maf_noise

    short_term_trim = rng.normal(12.0, 4.0, sample_count)
    long_term_trim = rng.normal(8.0, 3.0, sample_count)

    return pd.DataFrame(
        {
            "RPM": rpm,
            "Engine_Load_pct": engine_load,
            "Short_Term_Fuel_Trim_pct": short_term_trim,
            "Long_Term_Fuel_Trim_pct": long_term_trim,
            "MAF_g_s": np.maximum(maf, 0.1),
            "Failure_Mode": "maf_sensor_failure",
        }
    )


def generate_supercharger_gasket_leak_samples(
    rng: np.random.Generator,
    sample_count: int,
) -> pd.DataFrame:
    rpm, engine_load, maf_baseline = generate_operating_points(
        rng,
        sample_count,
    )

    # Unmetered air enters after the MAF, so the MAF reading remains plausible.
    maf = maf_baseline + rng.normal(0.0, 1.0, sample_count)

    # The leak is most apparent at idle and low engine load.
    low_load_factor = np.clip((60.0 - engine_load) / 45.0, 0.0, 1.0)
    short_term_trim = rng.normal(8.0, 2.5, sample_count) + (
        low_load_factor * rng.normal(8.0, 2.0, sample_count)
    )
    long_term_trim = rng.normal(14.0, 3.0, sample_count) + (
        low_load_factor * rng.normal(5.0, 1.5, sample_count)
    )

    return pd.DataFrame(
        {
            "RPM": rpm,
            "Engine_Load_pct": engine_load,
            "Short_Term_Fuel_Trim_pct": short_term_trim,
            "Long_Term_Fuel_Trim_pct": long_term_trim,
            "MAF_g_s": np.maximum(maf, 0.1),
            "Failure_Mode": "supercharger_gasket_leak",
        }
    )


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)

    dataset = pd.concat(
        [
            generate_normal_samples(rng, SAMPLES_PER_CLASS),
            generate_maf_failure_samples(rng, SAMPLES_PER_CLASS),
            generate_supercharger_gasket_leak_samples(
                rng,
                SAMPLES_PER_CLASS,
            ),
        ],
        ignore_index=True,
    )

    dataset = dataset.sample(
        frac=1.0,
        random_state=RANDOM_SEED,
    ).reset_index(drop=True)

    dataset.to_csv(OUTPUT_FILE, index=False)

    print(f"Generated {len(dataset)} telemetry records.")
    print(f"Saved dataset to: {OUTPUT_FILE.resolve()}")
    print("\nClass distribution:")
    print(dataset["Failure_Mode"].value_counts())


if __name__ == "__main__":
    main()
