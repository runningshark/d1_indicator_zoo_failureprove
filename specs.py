# -*- coding: utf-8 -*-
"""
技术指标规则大全的检验：数据、币池、每条规则的收益、Reality Check、判定。
规则、统计量和通过标准来自《事先登记_第三轮.md》，这里只是照着实现。
登记了两组资产：A · BTC 和 B · 30 币等权。本档案归档的是失败的 B 组；ETH 是不用来判定的参考。
"""
import math
import os

import numpy as np
import pandas as pd

import study as S
import zoo

END = os.environ.get("R3_END") or None          # 自检未来函数时用：只读到这一天为止的数据
P = S.load(end=END)
IDX = P.close.index
DATA_END = IDX[-1]
START = {"A": "2018-09-01", "B": "2020-04-01", "ETH": "2018-09-01"}
NAME = {"A": "BTC", "B": "30 币等权", "ETH": "ETH"}
P_PASS, P_WATCH = 0.0024, 0.05                 # 0.05 ÷ 累计 21 个检验
NBOOT, BLOCK, SEED = 10000, 10, 20261126
N_POOL = 30

# 币池：周日确定，用到下个周日
_u = S.universe(P, N_POOL, need_perp=False, min_hist=365).astype(float)
_u[~P.weekly] = np.nan
UW = _u.ffill().fillna(0.0).astype(bool)
COINS = sorted(set(UW.columns[UW.loc[START["B"]:].any(axis=0)]) | {"BTCUSDT", "ETHUSDT"})
C = P.close[COINS]


def _hl(name):
    x = pd.read_csv(os.path.join(S.DATA, name + ".csv.gz"), index_col=0, parse_dates=True).reindex(index=IDX, columns=COINS)
    return x.ffill(limit=3).where(C.notna())


def build(shift=0):
    """把 467 条规则都算一遍。返回每组资产的 毛收益 和 换手（日期 × 规则），以及规则的名字和类别。
    G1 是晚一天执行的毛收益。shift：把收益整体错开这么多天（自检用：仓位和收益对不上时，不应该检验出任何东西）。"""
    H, L, V = _hl("high"), _hl("low"), P.qvol[COINS]
    R = np.nan_to_num(P.ret[COINS].values)
    if shift:
        R = np.roll(R, shift, axis=0)
    uw = UW[COINS].values
    ib, ie = COINS.index("BTCUSDT"), COINS.index("ETHUSDT")
    T = len(IDX)
    fams, names, g, to, ex = [], [], {k: [] for k in START}, {k: [] for k in START}, {k: [] for k in START}
    g1, posa = {k: [] for k in START}, []
    for fam, name, pos in zoo.rules(C, H, L, V):
        fams.append(fam)
        names.append(name)
        for key, j in (("A", ib), ("ETH", ie)):
            p = pos[:, j].astype(float)
            gg, tt, dd = np.zeros(T), np.zeros(T), np.zeros(T)
            gg[1:] = p[:-1] * R[1:, j]
            dd[2:] = p[:-2] * R[2:, j]
            tt[1:] = np.abs(np.diff(p, prepend=0.0))[:-1]
            g[key].append(gg)
            g1[key].append(dd)
            if key == "A":
                posa.append(pos[:, j].copy())
            to[key].append(tt)
            ex[key].append(np.concatenate([[0.0], p[:-1]]))
        W = (pos & uw) / float(N_POOL)
        gg, tt, dd = np.zeros(T), np.zeros(T), np.zeros(T)
        gg[1:] = (W[:-1] * R[1:]).sum(axis=1)
        dd[2:] = (W[:-2] * R[2:]).sum(axis=1)
        g1["B"].append(dd)
        tt[1:] = np.abs(np.diff(W, axis=0, prepend=np.zeros((1, W.shape[1])))).sum(axis=1)[:-1]
        g["B"].append(gg)
        to["B"].append(tt)
        ex["B"].append(np.concatenate([[0.0], W[:-1].sum(axis=1)]))
    G = {k: np.column_stack(v) for k, v in g.items()}
    TO = {k: np.column_stack(v) for k, v in to.items()}
    EX = {k: np.column_stack(v) for k, v in ex.items()}
    G1 = {k: np.column_stack(v) for k, v in g1.items()}
    bench = dict(BTC=R[:, ib].copy(), ETH=R[:, ie].copy())
    ew = np.zeros(T)
    ew[1:] = ((uw[:-1] / float(N_POOL)) * R[1:]).sum(axis=1)
    bench["EW"] = ew
    return dict(G=G, G1=G1, TO=TO, EX=EX, POS_BTC=np.column_stack(posa), fams=np.array(fams), names=np.array(names), bench=bench)


FACTORS = {"A": ("BTC",), "B": ("BTC", "EW"), "ETH": ("ETH",)}


def nw_cols(e):
    """每一列的长期标准差（Newey-West，滞后 10 天）。e 已经减掉均值。"""
    T = len(e)
    s = (e * e).sum(axis=0) / T
    for k in range(1, 11):
        s += 2.0 * (1.0 - k / 11.0) * (e[k:] * e[:-k]).sum(axis=0) / T
    return np.sqrt(np.maximum(s, 0.0))


def alpha_t(Y, X):
    """每条规则的日净收益对基准回归。返回 (去掉基准后的序列 f, 超额日均, 长期标准差, t)。"""
    A = np.column_stack([np.ones(len(X)), X])
    beta = np.linalg.lstsq(A, Y, rcond=None)[0]
    f = Y - A[:, 1:] @ beta[1:]
    m = f.mean(axis=0)
    om = nw_cols(f - m)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(om > 0, math.sqrt(len(Y)) * m / om, np.nan)
    return f, m, om, t


def boot_means(F, nboot=NBOOT, block=BLOCK, seed=SEED):
    """平稳自助法：整块整块地重抽日期（块长服从几何分布，首尾相接），返回每次重抽后各列的均值。所有列用同一组日期。
    做法：先数出每次重抽里每一天被抽中几次，再和 F 做一次矩阵乘法。"""
    T, K = F.shape
    rng = np.random.default_rng(seed)
    out = np.empty((nboot, K))
    m = int(T / block * 2) + 50
    for b0 in range(0, nboot, 250):
        nb = min(250, nboot - b0)
        d = np.zeros((nb, 2 * T + 1))
        for i in range(nb):
            lens = np.minimum(rng.geometric(1.0 / block, size=m), T)
            cum = np.cumsum(lens)
            n = int(np.searchsorted(cum, T)) + 1
            lens = lens[:n].copy()
            lens[-1] -= cum[n - 1] - T
            st = rng.integers(0, T, size=n)
            np.add.at(d[i], st, 1.0)
            np.add.at(d[i], st + lens, -1.0)
        cnt = np.cumsum(d, axis=1)[:, :2 * T]
        out[b0:b0 + nb] = ((cnt[:, :T] + cnt[:, T:]) @ F) / T
    return out


def sharpe(x):
    sd = x.std(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sd > 0, x.mean(axis=0) / sd * math.sqrt(365), np.nan)


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    ra, rb = pd.Series(a[ok]).rank().values, pd.Series(b[ok]).rank().values
    return float(np.corrcoef(ra, rb)[0, 1])


def analyze(D, key, cost_mult=1.0, block=BLOCK, nboot=NBOOT, detail=True, delay=False):
    i0 = IDX.searchsorted(pd.Timestamp(START[key]))
    isp = IDX.searchsorted(S.SPLIT)
    Y = (D["G1" if delay else "G"][key] - S.COST * cost_mult * D["TO"][key])[i0:]
    X = np.column_stack([D["bench"][f] for f in FACTORS[key]])[i0:]
    traded = D["TO"][key][i0:].sum(axis=0) > 0
    T = len(Y)
    f, m, om, t = alpha_t(Y, X)
    t = np.where(traded, t, np.nan)
    bm = boot_means(f, nboot=nboot, block=block)
    with np.errstate(divide="ignore", invalid="ignore"):
        Z = math.sqrt(T) * (bm - m) / om                # 每次重抽、每条规则“去掉真实均值后”的 t
    Z[:, ~np.isfinite(t)] = -np.inf
    vmax = float(np.nanmax(t))
    best = int(np.nanargmax(t))
    res = dict(key=key, name=NAME[key], start=str(IDX[i0].date()), end=str(IDX[-1].date()), days=int(T), rules=int(len(t)), rules_used=int(np.isfinite(t).sum()),
               max_t=vmax, best=str(D["names"][best]), best_family=str(D["fams"][best]), rc_p=float((Z.max(axis=1) >= vmax).mean()),
               crit95=float(np.quantile(Z.max(axis=1), 0.95)), share_pos=float(np.nanmean(t > 0)), share_t2=float(np.nanmean(t > 2)), median_t=float(np.nanmedian(t)))
    if not detail:
        return res
    # 训练段、验证段各自回归
    k = isp - i0
    _, m1, _, t1 = alpha_t(Y[:k], X[:k])
    _, m2, _, t2 = alpha_t(Y[k:], X[k:])
    t1, t2 = np.where(traded, t1, np.nan), np.where(traded, t2, np.nan)
    bt = int(np.nanargmax(t1))
    top = np.argsort(-np.nan_to_num(t1, nan=-9e9))[: max(1, int(round(0.10 * np.isfinite(t1).sum())))]
    _, mp, _, tp = alpha_t(Y[k:][:, top].mean(axis=1, keepdims=True), X[k:])
    res.update(train_best=dict(name=str(D["names"][bt]), family=str(D["fams"][bt]), t_train=float(t1[bt]), alpha_test=float(m2[bt] * 365), t_test=float(t2[bt])),
               top_decile=dict(n=int(len(top)), alpha_test=float(mp[0] * 365), t_test=float(tp[0])),
               spearman=spearman(t1, t2), share_pos_test=float(np.nanmean(t2 > 0)))
    # 每一类
    fam = []
    for name in pd.unique(D["fams"]):
        c = (D["fams"] == name) & np.isfinite(t)
        if not c.any():
            continue
        j = int(np.where(c)[0][np.argmax(t[c])])
        fam.append(dict(family=str(name), n=int(c.sum()), share_pos=float((t[c] > 0).mean()), median_t=float(np.median(t[c])), best=str(D["names"][j]), best_t=float(t[j]),
                        p_family=float((Z[:, c].max(axis=1) >= t[j]).mean()), median_t_train=float(np.nanmedian(t1[c])), median_t_test=float(np.nanmedian(t2[c])),
                        exposure=float(D["EX"][key][i0:][:, c].mean()), turnover=float(D["TO"][key][i0:][:, c].sum(axis=0).mean() / (T / 365.0))))
    res["families"] = fam
    # 排在前面的规则
    sh = sharpe(Y)
    order = np.argsort(-np.nan_to_num(t, nan=-9e9))[:10]
    res["top10"] = [dict(name=str(D["names"][j]), family=str(D["fams"][j]), t=float(t[j]), alpha=float(m[j] * 365), sharpe=float(sh[j]),
                         t_train=float(t1[j]), t_test=float(t2[j])) for j in order]
    # 和“一直持有”比夏普
    bh = X[:, -1] if key == "B" else X[:, 0]
    eq = np.cumprod(1 + bh)
    js = int(np.nanargmax(np.where(traded, sh, np.nan)))
    eqs = np.cumprod(1 + Y[:, js])
    res["hold"] = dict(sharpe=float(sharpe(bh[:, None])[0]), ret=float(bh.mean() * 365), mdd=float((eq / np.maximum.accumulate(eq) - 1).min()))
    res["best_sharpe"] = dict(name=str(D["names"][js]), sharpe=float(sh[js]), ret=float(Y[:, js].mean() * 365), mdd=float((eqs / np.maximum.accumulate(eqs) - 1).min()),
                              t_alpha=float(t[js]), share_beating_hold=float(np.nanmean(np.where(traded, sh, np.nan) > res["hold"]["sharpe"])))
    return res


def rule_table(D, key):
    """每条规则一行：全区间、训练段、验证段的超额 t，年化超额，夏普，平均仓位，年换手。"""
    i0, isp = IDX.searchsorted(pd.Timestamp(START[key])), IDX.searchsorted(S.SPLIT)
    Y = (D["G"][key] - S.COST * D["TO"][key])[i0:]
    X = np.column_stack([D["bench"][f] for f in FACTORS[key]])[i0:]
    k = isp - i0
    _, m, _, t = alpha_t(Y, X)
    t1, t2 = alpha_t(Y[:k], X[:k])[3], alpha_t(Y[k:], X[k:])[3]
    return pd.DataFrame(dict(family=D["fams"], rule=D["names"], t=t, alpha_ann=m * 365, t_train=t1, t_test=t2, sharpe=sharpe(Y), ret_ann=Y.mean(axis=0) * 365,
                             exposure=D["EX"][key][i0:].mean(axis=0), turnover_per_year=D["TO"][key][i0:].sum(axis=0) / (len(Y) / 365.0)))


def evaluate(D, key):
    """主检验 + 压力和敏感性 + 判定。"""
    res = analyze(D, key)
    res["cost2"] = analyze(D, key, cost_mult=2.0, detail=False)
    res["cost0"] = analyze(D, key, cost_mult=0.0, detail=False)
    res["block5"] = analyze(D, key, block=5, detail=False)["rc_p"]
    res["block20"] = analyze(D, key, block=20, detail=False)["rc_p"]
    res["delay1"] = analyze(D, key, delay=True, detail=False)
    tb = res["train_best"]
    c = {"Reality Check 的 p < %.4f" % P_PASS: res["rc_p"] < P_PASS,
         "训练段选出的最好规则，验证段超额 t ≥ 2": tb["t_test"] >= 2.0,
         "成本翻倍后 p < 0.05": res["cost2"]["rc_p"] < P_WATCH}
    if all(c.values()):
        verdict = "通过"
    elif res["rc_p"] < P_WATCH and tb["alpha_test"] > 0:
        verdict = "待观察"
    else:
        verdict = "失败"
    res.update(checks=c, verdict=verdict)
    return res


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o
