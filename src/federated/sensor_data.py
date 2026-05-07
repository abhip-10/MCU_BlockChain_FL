"""
UCI HAR sensor data loader for federated learning.

Uses real per-subject recordings when the dataset is present.
Falls back to calibrated synthetic data (matching UCI HAR statistics)
when the dataset has not been downloaded — so the code always runs.

Download UCI HAR:
  https://archive.ics.uci.edu/dataset/240
  Extract to: data/UCI_HAR_Dataset/
  Expected layout:
    data/UCI_HAR_Dataset/train/X_train.txt
    data/UCI_HAR_Dataset/train/subject_train.txt
    data/UCI_HAR_Dataset/train/y_train.txt

8 features extracted (maps to MPU6050 / MAX30102 sensor outputs):
  0  accel_mag          — tBodyAccMag-mean()
  1  gyro_var           — mean(tBodyGyro-std()-XYZ)
  2  impact_peak        — max(|tBodyAccJerk-mean()-XYZ|)
  3  accel_std          — mean(tBodyAcc-std()-XYZ)
  4  gyro_mean_mag      — tBodyGyroMag-mean()
  5  jerk_mag           — tBodyAccJerkMag-mean()
  6  gravity_mean       — mean(tGravityAcc-mean()-XYZ)
  7  freq_accel_mean    — mean(fBodyAcc-mean()-XYZ)
"""
import os

import numpy as np

_HERE    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(_HERE, "..", "..", "data", "UCI HAR Dataset"))

SENSOR_DIM = 8

# UCI HAR 561-feature column indices (0-based) for our 8 features
_IDX = {
    "accel_mag":       200,
    "gyro_var":        (243, 244, 245),
    "impact_peak":     (40,  41,  42),
    "accel_std":       (3,   4,   5),
    "gyro_mean_mag":   240,
    "jerk_mag":        252,
    "gravity_mean":    (33,  34,  35),
    "freq_accel_mean": (316, 317, 318),
}

# Per-activity mean feature vectors (calibrated to UCI HAR normalised space [-1,1])
# Used only when the real dataset is absent.
_ACTIVITY_MEAN = {
    1: np.array([ 0.27,  0.05,  0.40,  0.12,  0.09,  0.20,  0.60,  0.25]),
    2: np.array([ 0.32,  0.08,  0.55,  0.18,  0.15,  0.28,  0.55,  0.30]),
    3: np.array([ 0.28,  0.06,  0.48,  0.14,  0.11,  0.22,  0.58,  0.27]),
    4: np.array([-0.02,  0.01,  0.05,  0.02,  0.01,  0.02,  0.71,  0.01]),
    5: np.array([-0.01,  0.01,  0.04,  0.01,  0.01,  0.01,  0.72,  0.01]),
    6: np.array([ 0.04,  0.01,  0.03,  0.01,  0.01,  0.02,  0.34,  0.01]),
}


def _extract(row: np.ndarray) -> np.ndarray:
    def col(idx):
        if isinstance(idx, tuple):
            return float(np.mean(np.abs(row[list(idx)])))
        return float(row[idx])
    return np.array([col(_IDX[k]) for k in _IDX], dtype=np.float64)


def _load_split(split: str):
    import pandas as pd
    base = os.path.join(DATA_DIR, split)
    X    = pd.read_csv(os.path.join(base, f"X_{split}.txt"),
                       sep=r"\s+", header=None).values
    subj = pd.read_csv(os.path.join(base, f"subject_{split}.txt"),
                       header=None).values.ravel().astype(int)
    return X, subj


def _synthetic_subject(subject_id: int) -> np.ndarray:
    """
    Calibrated synthetic mean for one subject when UCI HAR is absent.
    Each subject has a unique activity mix and body-size offset so FL
    sees genuine inter-node heterogeneity.
    """
    rng_s  = np.random.default_rng(subject_id * 137 + 42)
    offset = rng_s.normal(0, 0.04, SENSOR_DIM)

    # Active vs sedentary mix varies by subject (mimics fitness diversity)
    active_w = 0.3 + (subject_id % 5) * 0.1
    base     = (_ACTIVITY_MEAN[1] * active_w +
                _ACTIVITY_MEAN[4] * (1.0 - active_w))
    return np.clip(base + offset, -1.0, 1.0)


def load_subject_targets(n_subjects: int,
                         rng: np.random.Generator | None = None
                         ) -> list[np.ndarray]:
    """
    Return n_subjects 8-dim feature vectors — one per virtual node.

    Real UCI HAR: mean feature vector across all windows for each subject.
    Synthetic fallback: calibrated activity-mix model per subject.

    The FL global optimum is the mean across all returned targets.
    """
    rng = rng or np.random.default_rng(0)

    train_file = os.path.join(DATA_DIR, "train", "X_train.txt")
    if os.path.exists(train_file):
        print("  [sensor_data] UCI HAR found — loading real subject recordings")
        X_tr, subj_tr = _load_split("train")
        X_te, subj_te = _load_split("test")
        X_all    = np.vstack([X_tr, X_te])
        subj_all = np.concatenate([subj_tr, subj_te])
        targets  = []
        for sid in range(1, n_subjects + 1):
            rows = X_all[subj_all == sid]
            if len(rows) == 0:
                targets.append(_synthetic_subject(sid))
            else:
                feats = np.array([_extract(r) for r in rows], dtype=np.float64)
                targets.append(feats.mean(axis=0))
        return targets

    print("  [sensor_data] UCI HAR not found — using calibrated synthetic subject data")
    print("  To use real data: https://archive.ics.uci.edu/dataset/240")
    print("  Extract to: data/UCI_HAR_Dataset/")
    return [_synthetic_subject(i + 1) for i in range(n_subjects)]


def global_optimum(targets: list[np.ndarray]) -> np.ndarray:
    """Expected FedAvg convergence point — mean of all subject targets."""
    return np.mean(targets, axis=0)
