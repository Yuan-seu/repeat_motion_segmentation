import numpy as np
import scipy
from numba import jit, prange
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def gaussian_sequence(n, inverted=False):
    mu = (n - 1) / 2.0
    sig = (n - mu) / 2.5
    x = np.arange(n)
    t = (0.5 / (sig * sig)) * ((x - mu) ** 2)
    y = np.exp(-t)
    if inverted:
        y = 1.0 - y

    return y


def generate_sequence(n, curve='sine', noise=True, noise_level=0.005, tp=1.0):
    if n < 1:
        logger.warning("Sequence length is 0. Returning empty array")
        return np.array([])

    ni = nf = 0
    if noise:
        a = (0.15 - 0.1) * np.random.rand() + 0.1
        ni = max(1, int(np.floor(a * n)))
        a = (0.15 - 0.1) * np.random.rand() + 0.1
        nf = max(1, int(np.floor(a * n)))

    m = n - ni - nf
    if curve == 'sine':
        x = np.sin(((2.0 * np.pi) / (tp * m)) * np.arange(m))
    elif curve == 'cosine':
        x = np.cos(((2.0 * np.pi) / (tp * m)) * np.arange(m))
    elif curve == 'gaussian':
        x = gaussian_sequence(m)
    elif curve == 'gaussian_inverted':
        x = gaussian_sequence(m, inverted=True)
    else:
        raise ValueError("Invalid value '{}' for parameter 'curve'".format(curve))

    if noise:
        x = x + noise_level * np.random.rand(x.shape[0])
        # Append noise values close to 0 of length `noise_interval` at the start and end of the sequence
        if ni > 0:
            xi = noise_level * np.random.rand(ni)
            x = np.concatenate([xi, x])

        if nf > 0:
            xf = noise_level * np.random.rand(nf)
            x = np.concatenate([x, xf])

    return x[:, np.newaxis]


def normalize_maxmin(x):
    """
    Perform max-min normalization that scales the values to lie in the range [0, 1].

    :param x: numpy array of shape `(n, d)`. Normalization should be done along the row dimension.
    :return: normalized array of same shape as the input.
    """
    x_min = np.min(x, axis=0)
    x_max = np.max(x, axis=0)

    y = np.ones_like(x)
    mask = x_max > x_min
    if np.all(mask):
        y = (x - x_min) / (x_max - x_min)
    else:
        logger.warning("Maximum and minimum values are equal along %d dimensions. "
                       "Setting the normalized values to 1 along these dimension(s).", x.shape[1] - np.sum(mask))
        y[:, mask] = (x[:, mask] - x_min[mask]) / (x_max[mask] - x_min[mask])

    return y


def find_max_combinations(n, k=None):
    """
    Given `n` templates, what is the number of templates `k` to sample such that the term
    n choose(n - 1, k) is maximized.

    :param n: (int) number of templates.
    :param k: int or None. Specify the value of `k`. If set to None, the value that maximizes `n choose(n - 1, k)` is
              found.
    :return:
    """
    # Adding a small value to break ties and give preference to the larger `k` in case of ties
    vals = {i: (n * scipy.special.comb(n - 1, i) + 1e-6 * i) for i in range(1, n)}
    if k not in vals:
        k = max(vals, key=vals.get)

    v = int(np.floor(vals[k]))
    return k, v


@jit(nopython=True)
def sakoe_chiba_mask(sz1, sz2, warping_window):
    """
    Slightly modified version of the Sakoe-Chiba mask computed in the `tslearn` library.

    :param sz1: (int) length of the first time series.
    :param sz2: (int) length of the second time series.
    :param warping_window: float in [0, 1] specifying the warping window as a fraction.

    :return: boolean array of shape (sz1, sz2).
    """
    # The warping window cannot be smaller than the difference between the length of the sequences
    w = max(int(np.ceil(warping_window * max(sz1, sz2))),
            abs(sz1 - sz2) + 1)
    mask = np.full((sz1, sz2), np.inf)
    if sz1 <= sz2:
        for i in prange(sz1):
            lower = max(0, i - w)
            upper = min(sz2, i + w) + 1
            mask[i, lower:upper] = 0.
    else:
        for i in prange(sz2):
            lower = max(0, i - w)
            upper = min(sz1, i + w) + 1
            mask[lower:upper, i] = 0.

    return mask


# @jit(nopython=True)
def stratified_sample(labels, n, k):
    if k < n:
        label_set = np.unique(labels)
        index_labels = [np.random.permutation(np.where(labels == lab)[0]) for lab in label_set]
        index = []
        m = 0
        i = 0
        while m < k:
            arr = [v[i] for v in index_labels if i < v.shape[0]]
            index.extend(arr)
            m += len(arr)
            i += 1

        index = np.array(index[:k], dtype=np.int)
    else:
        index = np.random.permutation(n)

    return index
