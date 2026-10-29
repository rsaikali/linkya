"""Matched-filter detector: profiles are learned from signatures, nothing is hard-coded (no wattage, no clock)."""

import numpy as np

from src.nilm.detectors import matched_filter as mf

T0 = 1_780_000_000.0  # arbitrary epoch: the detector must not depend on the time of day


def curve(loads, n=12 * 360, step=7.0, seed=0):
    """Event-like samples every ~7 s. loads = (start_s, end_s, watts[, droop_fraction]) added on a noisy baseline."""
    rng = np.random.default_rng(seed)
    t = T0 + step * np.arange(n)
    y = 300.0 + rng.normal(0, 4, n)
    for load in loads:
        a, b, w = load[:3]
        droop = load[3] if len(load) > 3 else 0.0
        m = (t >= T0 + a) & (t < T0 + b)
        y[m] += w * (1 - droop * (1 - np.exp(-(t[m] - T0 - a) / 180.0)))
    return t, y


def sig_edges(loads_for_sig, t, y):
    return [mf.window_edges(t, y, T0 + a, T0 + b) for a, b in loads_for_sig]


def heater_history():
    """Eighteen 3 kW cycles of ~15 min in a quiet house (the 'signatures')."""
    cyc = [(300 + 1500 * k, 1200 + 1500 * k, 3050.0, 0.04) for k in range(18)]
    t, y = curve(cyc, n=12 * 400)
    return t, y, [(a, b) for a, b, *_ in cyc]


def test_learn_profile_from_signatures():
    t, y, wins = heater_history()
    (prof,) = mf.learn_profile(sig_edges(wins, t, y))
    assert abs(prof.mu_up - 3050) < 80 and abs(prof.mu_dn - 3050 * 0.97) < 120
    assert prof.sig_up / prof.mu_up < 0.05


def test_too_few_or_noisy_signatures_give_no_profile():
    t, y, wins = heater_history()
    assert mf.learn_profile(sig_edges(wins[:5], t, y)) == []
    rng = np.random.default_rng(1)  # multi-state appliance: edge heights all over the place
    noisy = [(float(w), float(w) * 0.9, 1000.0) for w in rng.uniform(300, 2500, 20)]
    assert mf.learn_profile(noisy) == []


def test_detects_a_cycle_anywhere_in_time():
    t, y, wins = heater_history()
    prof = mf.learn_profile(sig_edges(wins, t, y))
    t2, y2 = curve([(5000, 6000, 3040.0, 0.04), (20000, 20800, 3060.0, 0.04)], n=12 * 600)
    ev = mf.detect(t2, y2, {"heater": prof})
    assert [round(e["start"] - T0, -2) for e in ev] == [5000, 20000]
    assert all(abs(e["avg_w"] - 3000) < 150 for e in ev)


def test_look_alike_load_is_not_the_appliance():
    t, y, wins = heater_history()
    prof = mf.learn_profile(sig_edges(wins, t, y))
    t2, y2 = curve([(5000, 6000, 2650.0)])  # an oven-like 2.65 kW load: well outside the learned band
    assert mf.detect(t2, y2, {"heater": prof}) == []


def test_composite_edges_are_balanced_by_the_other_load():
    t, y, wins = heater_history()
    prof = mf.learn_profile(sig_edges(wins, t, y))
    # another 1.3 kW load switches on with the appliance and off 4 min later: the up edge is 3.05 + 1.3 kW
    t2, y2 = curve([(5000, 6000, 3040.0, 0.04), (5000, 5240, 1300.0)])
    ev = mf.detect(t2, y2, {"heater": prof})
    assert len(ev) == 1 and ev[0]["composite"] and abs(ev[0]["start"] - T0 - 5000) < 30
    # the same excess with nothing to balance it is not accepted
    t3, y3 = curve([(5000, 6000, 3040.0, 0.04), (5000, 9000, 1300.0)])
    assert mf.detect(t3, y3, {"heater": prof}) == []


def test_two_appliances_are_told_apart():
    t, y, wins = heater_history()
    heater = mf.learn_profile(sig_edges(wins, t, y))
    cyc = [(500 + 1400 * k, 900 + 1400 * k, 1250.0) for k in range(18)]
    tb, yb = curve(cyc, n=12 * 400)
    small = mf.learn_profile(sig_edges([(a, b) for a, b, _ in cyc], tb, yb))
    t2, y2 = curve([(3000, 3900, 3040.0, 0.04), (3200, 3600, 1250.0), (9000, 9500, 1250.0)], n=12 * 600)
    ev = mf.detect(t2, y2, {"heater": heater, "small": small})
    assert sorted((e["appliance"], round(e["start"] - T0, -2)) for e in ev) == [("heater", 3000), ("small", 3200), ("small", 9000)]


def test_negative_signature_pulls_look_alikes_away():
    t, y, wins = heater_history()
    pos = sig_edges(wins, t, y)
    # a negative signature sitting between the learned band and the candidate: closer to the candidate than the profile
    near = (3050.0 - 150.0, 2960.0 - 150.0, 600.0)
    prof = mf.learn_profile(pos, [near])[0]
    assert prof.neg and mf._look_alike(prof, near[0], near[1]) and not mf._look_alike(prof, 3050.0, 2960.0)


def test_modes_for_multi_power_appliance():
    cyc = [(500 + 1700 * k, 900 + 1700 * k, 1000.0 if k % 2 else 2000.0) for k in range(20)]
    t, y = curve(cyc, n=12 * 700)
    modes = mf.learn_profile(sig_edges([(a, b) for a, b, _ in cyc], t, y))
    assert len(modes) == 2 and sorted(round(m.mu_up, -2) for m in modes) == [1000, 2000]


def test_running_cycle_is_provisional_only_when_data_is_fresh():
    t, y, wins = heater_history()
    prof = mf.learn_profile(sig_edges(wins, t, y))
    t2, y2 = curve([(2000, 99999, 3040.0, 0.04)], n=int(2600 / 7))  # still on at the end of the data
    assert mf.detect(t2, y2, {"h": prof}) == []  # replay of history: no provisional events
    ev = mf.detect(t2, y2, {"h": prof}, now_epoch=t2[-1] + 20)
    assert len(ev) == 1 and ev[0]["provisional"]


def test_build_profiles_self_check_refuses_look_alikes():
    # 80 identical cycles on the curve: labeling all is fine; labeling 16 leaves 64 unexplained look-alikes
    cyc = [(500 + 900 * k, 900 + 900 * k, 3050.0, 0.04) for k in range(80)]
    t, y = curve(cyc, n=12 * 1100)

    def fetch(a, b):
        m = (t >= a) & (t <= b)
        return t[m], y[m]

    def wins(n):
        return [(T0 + a, T0 + b) for a, b, *_ in cyc[:n]]

    sparse = [w for k, w in enumerate(wins(80)) if k % 5 == 0]  # 16 labeled of 80 cycles: 20 % self precision
    ok, rep = mf.build_profiles({"all": {"positive": wins(80)}, "few": {"positive": sparse}}, fetch)
    assert "all" in ok and "few" not in ok and "look-alike" in rep["few"]
