import re

import mne
import numpy as np
import pandas as pd

from braindecode.datasets import BaseConcatDataset, RawDataset
from braindecode.preprocessing.windowers import create_fixed_length_windows


def _make_raw_dataset(n_times=256, age=30):
    info = mne.create_info(["C1", "C2", "C3"], sfreq=128, ch_types="eeg")
    raw = mne.io.RawArray(np.random.RandomState(0).randn(3, n_times), info)
    desc = pd.Series({"age": age, 777: "lucky"})
    return RawDataset(raw, description=desc)


def test_rawdataset_repr_is_descriptive():
    ds = _make_raw_dataset(n_times=256, age=30)
    rep = repr(ds)
    # Custom repr should not be the default object representation
    assert "object at" not in rep
    assert "RawDataset" in rep


def test_rawdataset_html_repr_contains_metadata():
    ds = _make_raw_dataset(n_times=128, age=42)
    html = ds._repr_html_()
    html_lower = html.lower()
    assert "<table" in html_lower
    assert "age" in html_lower
    assert "777" in html
    assert "lucky" in html


def test_concatdataset_repr_contains_summary():
    ds1 = _make_raw_dataset(n_times=256, age=30)
    ds2 = _make_raw_dataset(n_times=512, age=31)
    concat = BaseConcatDataset([ds1, ds2])
    rep = repr(concat)
    assert "object at" not in rep
    assert "BaseConcatDataset" in rep or "Concat" in rep
    # Summary should mention recordings/datasets and count
    assert re.search(r"\b2\b", rep)


def test_windows_dataset_repr_contains_window_info():
    ds1 = _make_raw_dataset(n_times=256, age=30)
    concat = BaseConcatDataset([ds1])
    windows = create_fixed_length_windows(
        concat,
        window_size_samples=64,
        window_stride_samples=64,
        drop_last_window=True,
    )
    rep = repr(windows).lower()
    assert "object at" not in rep
    assert "window" in rep
    assert re.search(r"\b4\b", rep)
