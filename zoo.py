# -*- coding: utf-8 -*-
"""
技术指标规则大全：21 类、467 条只做多的日线规则（清单见《事先登记_第三轮.md》第 3 节）。
rules(C, H, L, V) 逐条给出 (类别, 规则名, 仓位)，仓位是 日期 × 币 的 0/1 矩阵：当天收盘后持有（1）还是空仓（0）。
所有指标只用到当天收盘为止的数据。入场和出场条件同一天都成立时按出场处理。
"""
import itertools

import numpy as np
import pandas as pd

NS = [5, 10, 20, 30, 50, 100, 150, 200]


def hyst(enter, leave):
    """入场条件成立变 1，出场条件成立变 0，都不成立保持原样。"""
    s = pd.DataFrame(np.nan, index=enter.index, columns=enter.columns)
    s = s.mask(enter.fillna(False).astype(bool), 1.0).mask(leave.fillna(False).astype(bool), 0.0)
    return s.ffill().fillna(0.0).values.astype(bool)


def state(cond):
    return cond.fillna(False).values.astype(bool)


def sma(x, n):
    return x.rolling(n, min_periods=n).mean()


def ema(x, n):
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(x, n):
    return x.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(C, n):
    d = C.diff()
    up, dn = wilder(d.clip(lower=0), n), wilder(-d.clip(upper=0), n)
    return 100.0 - 100.0 / (1.0 + up / dn)


def true_range(C, H, L):
    pc = C.shift(1)
    return pd.concat([H - L, (H - pc).abs(), (L - pc).abs()]).groupby(level=0).max().reindex(C.index)


def hold(trigger, m):
    """触发当天收盘买入，持有 m 天。"""
    return trigger.astype(float).rolling(m, min_periods=1).max().fillna(0.0).values.astype(bool)


def mean_abs_dev(x, n):
    """滚动平均绝对离差（CCI 用）。按列分块算，免得占太多内存。"""
    v = x.values
    out = np.full(v.shape, np.nan)
    for j0 in range(0, v.shape[1], 40):
        w = np.lib.stride_tricks.sliding_window_view(v[:, j0:j0 + 40], n, axis=0)        # (T-n+1, 列, n)
        out[n - 1:, j0:j0 + 40] = np.abs(w - w.mean(axis=2, keepdims=True)).mean(axis=2)
    return pd.DataFrame(out, index=x.index, columns=x.columns)


def supertrend(C, H, L, n, mult):
    atr = wilder(true_range(C, H, L), n).values
    mid = ((H + L) / 2.0).values
    c = C.values
    bu, bl = mid + mult * atr, mid - mult * atr
    fu, fl = bu.copy(), bl.copy()
    up = np.zeros(c.shape, dtype=bool)
    for t in range(1, len(c)):
        pu, pl, pc_ = fu[t - 1], fl[t - 1], c[t - 1]
        with np.errstate(invalid="ignore"):
            fu[t] = np.where(np.isnan(pu) | (bu[t] < pu) | (pc_ > pu), bu[t], pu)
            fl[t] = np.where(np.isnan(pl) | (bl[t] > pl) | (pc_ < pl), bl[t], pl)
            up[t] = np.where(c[t] > pu, True, np.where(c[t] < pl, False, up[t - 1]))
    return up


def rules(C, H, L, V):
    """C、H、L、V：日期 × 币 的收盘、最高、最低、成交额。"""
    idx = C.index
    ret = C / C.shift(1) - 1
    ok = C.notna().values
    MA = {("SMA", n): sma(C, n) for n in NS}
    MA.update({("EMA", n): ema(C, n) for n in NS})

    def out(fam, name, pos):
        return fam, name, pos & ok

    # 1 价格与均线
    for kind, n, b in itertools.product(("SMA", "EMA"), NS, (0.0, 0.01, 0.02)):
        m = MA[(kind, n)]
        yield out("价格与均线", "%s(%d) 带宽 %g%%" % (kind, n, 100 * b), hyst(C > m * (1 + b), C < m * (1 - b)))
    # 2 双均线交叉
    for kind, (f, s), b in itertools.product(("SMA", "EMA"), itertools.combinations(NS, 2), (0.0, 0.01)):
        yield out("双均线交叉", "%s(%d/%d) 带宽 %g%%" % (kind, f, s, 100 * b), hyst(MA[(kind, f)] > MA[(kind, s)] * (1 + b), MA[(kind, f)] < MA[(kind, s)] * (1 - b)))
    # 3 MACD
    for f, s in itertools.product((6, 12, 19), (26, 39, 52)):
        line = ema(C, f) - ema(C, s)
        yield out("MACD", "MACD(%d,%d) 在零轴上方" % (f, s), state(line > 0))
        for g in (5, 9, 13):
            yield out("MACD", "MACD(%d,%d,%d) 在信号线上方" % (f, s, g), state(line > line.ewm(span=g, adjust=False, min_periods=g).mean()))
    # 4、5 RSI
    R = {n: rsi(C, n) for n in (7, 14, 21, 28)}
    for n, lo, hi in itertools.product((7, 14, 21), (20, 25, 30, 35), (50, 60, 70)):
        yield out("RSI 超卖买入", "RSI(%d) <%d 买 >%d 卖" % (n, lo, hi), hyst(R[n] < lo, R[n] > hi))
    for n, c in itertools.product((7, 14, 21, 28), (50, 55, 60)):
        yield out("RSI 顺势", "RSI(%d) >%d 持有" % (n, c), state(R[n] > c))
    # 6、7 布林带
    for n, k in itertools.product((10, 20, 30, 50), (1.5, 2.0, 2.5)):
        mid, sd = sma(C, n), C.rolling(n, min_periods=n).std(ddof=0)
        up, lo = mid + k * sd, mid - k * sd
        yield out("布林带回归", "布林(%d,%g) 破下轨买 回中轨卖" % (n, k), hyst(C < lo, C > mid))
        yield out("布林带回归", "布林(%d,%g) 破下轨买 到上轨卖" % (n, k), hyst(C < lo, C > up))
        yield out("布林带突破", "布林(%d,%g) 破上轨买 回中轨卖" % (n, k), hyst(C > up, C < mid))
        yield out("布林带突破", "布林(%d,%g) 破上轨买 破下轨卖" % (n, k), hyst(C > up, C < lo))
    # 8 通道突破
    for n in (5, 10, 20, 30, 55, 100, 200):
        for m in (n, (n + 1) // 2):
            yield out("通道突破", "突破 %d 日高点买 跌破 %d 日低点卖" % (n, m),
                      hyst(C > H.rolling(n, min_periods=n).max().shift(1), C < L.rolling(m, min_periods=m).min().shift(1)))
    # 9 动量
    for n, c in itertools.product((5, 10, 20, 30, 60, 90, 120, 180, 250, 365), (0.0, 0.05, 0.10)):
        yield out("动量", "%d 日涨幅 >%g%% 持有" % (n, 100 * c), state(C / C.shift(n) - 1 > c))
    # 10 随机指标 KD，11 KDJ
    def stoch(n):
        ll, hh = L.rolling(n, min_periods=n).min(), H.rolling(n, min_periods=n).max()
        return 100.0 * (C - ll) / (hh - ll)
    for n in (5, 9, 14, 21):
        k = stoch(n)
        yield out("随机指标 KD", "KD(%d) <20 买 >80 卖" % n, hyst(k < 20, k > 80))
        yield out("随机指标 KD", "KD(%d) <30 买 >70 卖" % n, hyst(k < 30, k > 70))
        yield out("随机指标 KD", "KD(%d) K>D 持有" % n, state(k > sma(k, 3)))
    for n in (9, 14):
        k = stoch(n).ewm(alpha=1.0 / 3, adjust=False, min_periods=1).mean()
        d = k.ewm(alpha=1.0 / 3, adjust=False, min_periods=1).mean()
        j = 3 * k - 2 * d
        yield out("KDJ", "KDJ(%d) J<0 买 J>100 卖" % n, hyst(j < 0, j > 100))
        yield out("KDJ", "KDJ(%d) K>D 持有" % n, state(k > d))
    # 12 过滤规则
    for x, n in itertools.product((0.02, 0.05, 0.10, 0.15, 0.20, 0.30), (10, 20, 50)):
        yield out("过滤规则", "距 %d 日低点涨 %g%% 买 距高点跌 %g%% 卖" % (n, 100 * x, 100 * x),
                  hyst(C >= C.rolling(n, min_periods=n).min() * (1 + x), C <= C.rolling(n, min_periods=n).max() * (1 - x)))
    # 13 OBV 均线
    obv = (np.sign(ret.fillna(0.0)) * V.fillna(0.0)).cumsum().where(C.notna())
    for f, s in itertools.combinations((5, 10, 20, 50, 100), 2):
        yield out("OBV 均线", "OBV 均线(%d/%d)" % (f, s), state(sma(obv, f) > sma(obv, s)))
    # 14 CCI
    tp = (H + L + C) / 3.0
    for n in (14, 20, 50):
        cci = (tp - sma(tp, n)) / (0.015 * mean_abs_dev(tp, n))
        yield out("CCI", "CCI(%d) >100 买 <0 卖" % n, hyst(cci > 100, cci < 0))
        yield out("CCI", "CCI(%d) <−100 买 >100 卖" % n, hyst(cci < -100, cci > 100))
        yield out("CCI", "CCI(%d) >0 持有" % n, state(cci > 0))
    # 15 ADX / DMI
    tr = true_range(C, H, L)
    upm, dnm = H.diff(), -L.diff()
    pdm, mdm = upm.where((upm > dnm) & (upm > 0), 0.0), dnm.where((dnm > upm) & (dnm > 0), 0.0)
    for n in (14, 20):
        atr = wilder(tr, n)
        pdi, mdi = 100 * wilder(pdm, n) / atr, 100 * wilder(mdm, n) / atr
        adx = wilder(100 * (pdi - mdi).abs() / (pdi + mdi), n)
        for a in (0, 20, 25):
            yield out("ADX / DMI", "DMI(%d) +DI>−DI 且 ADX>%d" % (n, a), state((pdi > mdi) & (adx > a)))
    # 16 一目均衡表
    for a, b, c in ((9, 26, 52), (20, 60, 120)):
        mid = lambda n: (H.rolling(n, min_periods=n).max() + L.rolling(n, min_periods=n).min()) / 2.0
        ten, kij = mid(a), mid(b)
        top = pd.concat([((ten + kij) / 2.0).shift(b), mid(c).shift(b)]).groupby(level=0).max().reindex(idx)
        yield out("一目均衡表", "一目(%d,%d,%d) 在云上方" % (a, b, c), state(C > top))
        yield out("一目均衡表", "一目(%d,%d,%d) 转换线>基准线" % (a, b, c), state(ten > kij))
        yield out("一目均衡表", "一目(%d,%d,%d) 云上方且转换线>基准线" % (a, b, c), state((C > top) & (ten > kij)))
    # 17 SuperTrend
    for n, m in itertools.product((7, 10, 14), (2, 3, 4)):
        yield out("SuperTrend", "SuperTrend(%d,%d)" % (n, m), supertrend(C, H, L, n, m))
    # 18 连跌接多，19 急跌接多
    down = (ret < 0)
    for n, m in itertools.product((2, 3, 4, 5), (1, 3, 5, 10)):
        yield out("连跌接多", "连跌 %d 天买 持有 %d 天" % (n, m), hold(down.astype(float).rolling(n, min_periods=n).sum() == n, m))
    for x, m in itertools.product((0.03, 0.05, 0.08, 0.10), (1, 3, 7)):
        yield out("急跌接多", "单日跌超 %g%% 买 持有 %d 天" % (100 * x, m), hold(ret < -x, m))
    # 20 肯特纳通道
    for n, k in itertools.product((20, 50), (1.0, 1.5, 2.0)):
        mid, atr = MA[("EMA", n)], wilder(tr, n)
        yield out("肯特纳通道", "肯特纳(%d,%g) 突破" % (n, k), hyst(C > mid + k * atr, C < mid))
        yield out("肯特纳通道", "肯特纳(%d,%g) 回归" % (n, k), hyst(C < mid - k * atr, C > mid))
    # 21 日历：仓位在收盘时定，吃的是下一天的涨跌，所以按“下一天是星期几”来定
    nxt = idx + pd.Timedelta(days=1)
    wd = np.asarray(nxt.dayofweek)
    ones = np.ones(C.shape, dtype=bool)
    names = "一二三四五六日"
    for d in range(7):
        yield out("日历", "只在星期%s持有" % names[d], ones & (wd == d)[:, None])
    for d in range(7):
        yield out("日历", "除了星期%s都持有" % names[d], ones & (wd != d)[:, None])
    yield out("日历", "只在周末持有", ones & (wd >= 5)[:, None])
    yield out("日历", "只在工作日持有", ones & (wd < 5)[:, None])
    dom, dim = np.asarray(nxt.day), np.asarray(nxt.days_in_month)
    yield out("日历", "只在月末 2 天和月初 3 天持有", ones & ((dom <= 3) | (dom > dim - 2))[:, None])
