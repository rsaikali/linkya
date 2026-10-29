"""Matched-filter detector for on/off appliances on a single-meter power curve.

Model: an on/off appliance (water heater, oven element, dishwasher heating phase, ...) shows up as an up edge of
height ~mu_up, a roughly flat plateau, and a down edge of height ~mu_dn. Both heights are learned per appliance from
its positive signatures (robust median / MAD, so no wattage is hard-coded); negative signatures give the heights of
look-alike loads. A candidate cycle is an up edge and a down edge, both within k sigma of the profile, with a
duration inside the learned range. An edge may also carry another load (composite): it is accepted only if its excess
is balanced by an opposite edge of the same size nearby (mass balance), so concurrent loads neither hide nor
fake a cycle. No clock, tariff or house constant is used. Appliances whose edges are not repeatable (multi-state:
washing machine, ...) get no valid profile and stay on the legacy matcher.
"""

import logging
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, median_filter

logger = logging.getLogger(__name__)

DT = 10  # seconds, working grid
MAX_GAP_S = 7200.0  # no data for longer than this stays a hole (NaN)
K_SIGMA = 4.0  # acceptance band around the learned edge heights
K_WIDE = 6.5  # looser band for one edge when the other one is almost exact (edge heights have heavier tails than a normal law)
K_EXACT = 2.0
MIN_SIGNATURES = 15  # positive signatures needed for a profile
MAX_REL_SPREAD = 0.08  # edge height spread (sigma / mu) above which the appliance is not a repeatable on/off load
SIGMA_FLOOR = 0.01  # relative floor on sigma
VERSION = 2  # bump when the profile content changes: invalidates cached profiles
MIN_COVERAGE = 0.6  # share of the signatures the retained modes must explain
MIN_SELF_PRECISION = 0.3  # share of detections that must fall on the appliance's own signatures (they are not exhaustive)


@dataclass
class Profile:
    """Learned edge statistics of one appliance (W, seconds)."""

    mu_up: float
    sig_up: float
    mu_dn: float
    sig_dn: float
    dur_min: float
    dur_max: float
    n: int
    neg: list = field(default_factory=list)  # [(up, dn)] edge heights of negative signatures
    level: float = 0.0  # median power while on, above the baseline (0 = use the mean of the two edges)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return Profile(**{**d, "neg": [tuple(x) for x in d.get("neg", [])]})

    @property
    def power(self):
        return self.level if self.level > 0 else 0.5 * (self.mu_up + self.mu_dn)

    @property
    def amp_min(self):
        """Smallest edge height worth looking at (balance search): a fraction of the appliance edge."""
        return max(150.0, 0.15 * min(self.mu_up, self.mu_dn))


def to_grid(times, values):
    """Event-driven samples (HA only emits changes) -> regular DT grid, sample-and-hold, holes > 2 h stay NaN."""
    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    if len(t) < 2:
        return np.array([]), np.array([])
    order = np.argsort(t)
    t, v = t[order], v[order]
    keep = np.r_[True, np.diff(t) > 0]
    t, v = t[keep], v[keep]
    half = DT / 2.0
    t0 = np.floor(t[0] / DT) * DT
    n = int((t[-1] - t0) // half) + 1
    n -= n % 2
    grid = t0 + half * np.arange(n)
    idx = np.searchsorted(t, grid, side="right") - 1
    ok = idx >= 0
    idx = np.clip(idx, 0, None)
    y = np.where(ok & ((grid - t[idx]) <= MAX_GAP_S), v[idx], np.nan)
    y10 = y.reshape(-1, 2).mean(axis=1)  # two half-steps -> one DT sample
    return grid[::2], y10


def edge_series(y):
    """Robust step across sample i, multi-scale: d3 = median(y[i:i+3]) - median(y[i-3:i]) and d5 over 5 samples
    (an edge the meter reports in two samples, 30 s apart, keeps its full height in d5). Returns (d, y filled)."""
    yy = pd.Series(y).ffill().bfill().to_numpy()
    n = len(yy)
    d = np.zeros(n)
    if n < 12:
        return d, yy
    m3 = median_filter(yy, size=3, mode="nearest")
    m5 = median_filter(yy, size=5, mode="nearest")
    d3 = np.zeros(n)
    d3[2:-2] = m3[3:-1] - m3[:-4]
    d5 = np.zeros(n)
    d5[5:-4] = m5[8:-1] - m5[2:-7]
    d = np.where(np.abs(d5) > np.abs(d3), d5, d3)
    return d, yy


def _peaks(d, sign, lo):
    """Indices of local extrema (+-2 samples) of sign*d that reach lo."""
    s = sign * d
    idx = np.where((s >= lo) & (s == maximum_filter1d(s, 5)))[0]
    return idx[(idx >= 3) & (idx < len(d) - 3)]


# ---------------------------------------------------------------- profile learning
def window_edges(times, values, start, end, margin=90.0):
    """(up, down, duration, plateau level) of one signature window [start, end] on its curve, or None."""
    g, y = to_grid(times, values)
    if len(g) < 40:
        return None
    d, _ = edge_series(y)
    i0, i1 = np.searchsorted(g, [start - margin, start + margin])
    j0, j1 = np.searchsorted(g, [end - margin, end + margin])
    if i1 - i0 < 3 or j1 - j0 < 3:
        return None
    up, dn = float(d[i0:i1].max()), float(-d[j0:j1].min())
    a, b = np.searchsorted(g, [start + 60.0, end - 20.0])
    c, e = np.searchsorted(g, [start - 120.0, start - 20.0])
    level = float(np.nanmedian(y[a:b]) - np.nanmedian(y[c:e])) if b - a > 3 and e - c > 3 else 0.0
    return (up, dn, float(end - start), level) if up > 0 and dn > 0 else None


def learn_profile(positives, negatives=()):
    """Profiles (one per mode) from signature edge heights: positives/negatives = [(up, dn, duration[, level])].

    An appliance with several power levels (oven, dishwasher programs) gives several clusters of up-edge height; each
    cluster with enough support and a small spread is one mode. Empty list = not a repeatable on/off load."""
    pos = sorted((p for p in positives if p), key=lambda p: p[0])
    if len(pos) < MIN_SIGNATURES:
        return []
    groups = [[pos[0]]]
    for p in pos[1:]:
        if p[0] - groups[-1][-1][0] > 0.06 * float(np.median([q[0] for q in groups[-1]])):
            groups.append([p])
        else:
            groups[-1].append(p)

    def robust(x):
        m = float(np.median(x))
        return m, max(1.4826 * float(np.median(np.abs(np.asarray(x) - m))), SIGMA_FLOOR * m)

    neg = [(n[0], n[1]) for n in negatives if n]
    out = []
    for grp in groups:
        if len(grp) < max(5, int(0.15 * len(pos))):
            continue
        mu_u, s_u = robust([q[0] for q in grp])
        mu_d, s_d = robust([q[1] for q in grp])
        if s_u / mu_u > MAX_REL_SPREAD or s_d / mu_d > MAX_REL_SPREAD or min(mu_u, mu_d) < 200.0:
            continue
        durs = np.array([q[2] for q in grp])
        levels = [q[3] for q in grp if len(q) > 3 and q[3] > 0]
        level = float(np.median(levels)) if levels else 0.0
        out.append(
            Profile(
                mu_u,
                s_u,
                mu_d,
                s_d,
                float(max(60.0, 0.5 * np.percentile(durs, 5))),
                float(min(2.0 * np.percentile(durs, 95), 6 * 3600.0)),
                len(grp),
                neg,
                level,
            )
        )
    if sum(m.n for m in out) < MIN_COVERAGE * len(pos):
        return []  # the modes explain too few signatures: edges are not repeatable
    return out


def _z(prof, up, dn):
    return max(abs(up - prof.mu_up) / prof.sig_up, abs(dn - prof.mu_dn) / prof.sig_dn)


def _look_alike(prof, up, dn):
    """True if the edge pair is closer to a negative signature than to the appliance profile."""
    zp = _z(prof, up, dn)
    return any(max(abs(up - nu) / prof.sig_up, abs(dn - nd) / prof.sig_dn) < zp for nu, nd in prof.neg)


# ---------------------------------------------------------------- detection
def _cycles(g, y, d, prof, allpk):
    """Edge pairs of one profile. Composite edges need a balancing opposite edge. Returns [(on, end, composite, z)]."""
    k, mu_u, mu_d = K_SIGMA, prof.mu_up, prof.mu_dn
    tol = max(k * min(prof.sig_up, prof.sig_dn), 0.07 * min(mu_u, mu_d))
    ups = _peaks(d, +1, mu_u - K_WIDE * prof.sig_up)
    dns = _peaks(d, -1, mu_d - K_WIDE * prof.sig_dn)

    def balanced(excess, i, j, side):
        lo, hi = np.searchsorted(allpk, [i - 60, j + 61])
        for p in allpk[lo:hi]:
            if p in (i, j):
                continue
            if side == "up" and d[p] < 0 and abs(-d[p] - excess) <= tol and p > i:
                return True
            if side == "down" and d[p] > 0 and abs(d[p] - excess) <= tol and p < j:
                return True
        return False

    out = []
    for i in ups:
        eu = d[i]
        for j in dns[(dns > i + prof.dur_min // DT) & (dns < i + prof.dur_max // DT)][:6]:
            ed = -d[j]
            zu, zd = abs(eu - mu_u) / prof.sig_up, abs(ed - mu_d) / prof.sig_dn
            cu = zu <= k or (zu <= K_WIDE and zd <= K_EXACT)
            cd = zd <= k or (zd <= K_WIDE and zu <= K_EXACT)
            if not (cu or cd):
                continue
            if not cu and not balanced(eu - mu_u, i, j, "up"):
                continue
            if not cd and not balanced(ed - mu_d, i, j, "down"):
                continue
            base = np.nanmedian(y[max(i - 8, 0) : i - 1])
            plateau = y[i + 6 : j - 2] - base
            if len(plateau) < 3 or np.nanpercentile(plateau, 5) < 0.35 * mu_d:
                continue
            if cu and cd and _look_alike(prof, eu, ed):
                continue
            z = max(abs(eu - mu_u) / prof.sig_up if cu else 0.0, abs(ed - mu_d) / prof.sig_dn if cd else 0.0)
            out.append((int(i), int(j), not (cu and cd), z + (0.0 if (cu and cd) else 2.0)))
            break
    return out


def detect(times, values, profiles, from_epoch=None, now_epoch=None, fresh_s=180.0):
    """Cycles of every profile ({name: [Profile, ...]}, one Profile per power mode) on the curve; events carry the appliance name.

    Events: appliance, start, end (epoch s), conf, composite, provisional. A cycle still running at the end of the
    data is reported (provisional) only if now_epoch is given and the data is fresh (live mode).
    """
    g, y = to_grid(times, values)
    if len(g) < 60 or not profiles:
        return []
    d, _ = edge_series(y)
    cand = []  # (z, on, end, name, composite, profile)
    modes = [(name, prof) for name, ps in profiles.items() for prof in (ps if isinstance(ps, (list, tuple)) else [ps])]
    for name, prof in modes:
        allpk = np.union1d(_peaks(d, +1, prof.amp_min), _peaks(d, -1, prof.amp_min))
        for on, end, comp, z in _cycles(g, y, d, prof, allpk):
            cand.append((z, on, end, name, comp, prof))
        if now_epoch is None or now_epoch - g[-1] >= fresh_s:
            continue
        for on in _peaks(d, +1, prof.mu_up - K_WIDE * prof.sig_up):  # still running at the end of the data
            if abs(d[on] - prof.mu_up) > K_SIGMA * prof.sig_up or g[-1] - g[on] < max(120.0, prof.dur_min / 2) or g[-1] - g[on] > prof.dur_max:
                continue
            if np.any(-d[on + 3 :] >= prof.mu_dn - K_SIGMA * prof.sig_dn):
                continue
            if np.nanmedian(y[-6:]) - np.nanmedian(y[max(on - 3, 0) : on]) >= 0.6 * prof.mu_dn:
                cand.append((_z(prof, d[on], prof.mu_dn), on, None, name, False, prof))
    cand.sort(key=lambda c: c[0])  # best match first
    kept = []
    for z, on, end, name, comp, prof in cand:
        e = end if end is not None else len(g) - 1
        clash = False
        for _z0, k_on, k_end, k_name, _c, _p in kept:
            k_e = k_end if k_end is not None else len(g) - 1
            same_edge = abs(on - k_on) <= 3 or (end is not None and k_end is not None and abs(end - k_end) <= 3)
            # two appliances may run at the same time, but not on the same edge; one appliance cannot overlap itself
            if same_edge or (name == k_name and on < k_e + 3 and e > k_on - 3):
                clash = True
                break
        if not clash:
            kept.append((z, on, end, name, comp, prof))
    out = []
    for z, on, end, name, comp, prof in sorted(kept, key=lambda c: c[1]):
        start = float(g[on])
        if from_epoch is not None and start < from_epoch:
            continue
        conf = float(np.clip(1.0 - 0.06 * z, 0.5, 0.99))
        last = end if end is not None else len(g) - 1
        avg_w = prof.power  # learned plateau level: another load switching during the cycle cannot bias it
        out.append(
            {
                "appliance": name,
                "start": start,
                "end": float(g[last]),
                "conf": conf,
                "composite": comp,
                "provisional": end is None,
                "avg_w": avg_w,
                "up": float(d[on]),
                "dn": float(-d[end]) if end is not None else 0.0,
                "z": float(z),
            }
        )
    return out


# ---------------------------------------------------------------- profile building (needs the curve)
def replay(modes, windows, fetch, span=7 * 86400.0):
    """Detector replayed over the signatures' own period (chunked). fetch(a, b) -> (times, values)."""
    lo, hi = min(w[0] for w in windows) - 3600.0, max(w[1] for w in windows) + 3600.0
    out, a = [], lo
    while a < hi:
        b = min(a + span, hi)
        t, v = fetch(a - 3600.0, b)
        out += detect(t, v, {"x": modes}, from_epoch=a)
        a = b
    return out


def self_precision(events, windows, slack=120.0):
    """Share of detections that overlap one of the appliance's own signatures.

    Low = the edge heights are shared by other loads (look-alikes), so the profile cannot tell this appliance apart."""
    hit = sum(any(e["start"] < w[1] + slack and e["end"] > w[0] - slack for w in windows) for e in events)
    return (hit / len(events) if events else 0.0), len(events)


def build_profiles(signatures, fetch, rounds=1, clean_z=3.0):
    """{appliance: {"positive": [(start, end)], "negative": [(start, end)]}} -> ({appliance: [Profile]}, report).

    1. learn the edge heights from the signatures;
    2. self-training: refit on the signatures plus the clean cycles the detector itself finds (both edges within
       clean_z sigma, no other load in the edges), which tightens the estimate of the spread without any new label;
    3. keep the appliance only if the replay attributes at least MIN_SELF_PRECISION of its detections to its
       signatures. Others stay on the legacy matcher."""
    profiles, report = {}, {}
    for name, sig in signatures.items():
        pos = [window_edges(*fetch(a - 300.0, b + 300.0), a, b) for a, b in sig.get("positive", [])]
        neg = [window_edges(*fetch(a - 300.0, b + 300.0), a, b) for a, b in sig.get("negative", [])]
        modes = learn_profile(pos, neg)
        if not modes:
            report[name] = "no repeatable edges (%d signatures)" % len([p for p in pos if p])
            continue
        events = replay(modes, sig["positive"], fetch)
        for _ in range(rounds):
            clean = [
                (e["up"], e["dn"], e["end"] - e["start"], e["avg_w"])
                for e in events
                if not e["composite"] and not e["provisional"] and e["z"] <= clean_z
            ]
            refit = learn_profile([p for p in pos if p] + clean, neg)
            if not refit:
                break
            modes = refit
            events = replay(modes, sig["positive"], fetch)
        prec, n = self_precision(events, sig["positive"])
        if prec < MIN_SELF_PRECISION:
            report[name] = "look-alike loads: only %.0f%% of %d detections on its signatures" % (100 * prec, n)
            continue
        profiles[name] = modes
        report[name] = "%d mode(s), self precision %.0f%% of %d detections" % (len(modes), 100 * prec, n)
    return profiles, report
