# -*- coding: utf-8 -*-
"""
自检。用法： py selftest.py
1. 指标算得对不对：挑 10 条规则，在 BTC 上用最直白的逐日循环重写一遍，仓位必须逐日相同。
2. 未来函数：把数据截到 2024-06-30 重算，截止日之前每条规则的收益和换手必须不变。
3. 自助法：用前缀和算的块均值，和直接按日期取数算的必须相同。
4. 错位对照：把收益和仓位错开几百天再做同样的检验，p 值不应该偏小。
5. ETH 上最好那条规则的 t，和另一种写法的回归函数算出来的对比。
"""
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

CUT = "2024-06-30"
HERE = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 1 and sys.argv[1] == "--dump":
    import specs as R
    D = R.build()
    n = len(R.IDX)
    np.savez(os.path.join(HERE, "results", "_trunc.npz"), n=n, **{"%s_%s" % (a, k): D[a][k] for a in ("G", "G1", "TO") for k in R.START})
    sys.exit(0)

import specs as R      # noqa: E402
import study as S       # noqa: E402

nan = float("nan")
ok = True
D = R.build()
pos = {n: D["POS_BTC"][:, k] for k, n in enumerate(D["names"])}
c = R.C["BTCUSDT"].values
h, l = R._hl("high")["BTCUSDT"].values, R._hl("low")["BTCUSDT"].values
T = len(c)


def ew(x, a, n):
    out, y, cnt = [nan] * len(x), None, 0
    for i, v in enumerate(x):
        if v != v:
            continue
        y = v if y is None else a * v + (1 - a) * y
        cnt += 1
        if cnt >= n:
            out[i] = y
    return out


def hy(enter, leave):
    p, out = 0, []
    for e, x in zip(enter, leave):
        p = 0 if x else (1 if e else p)
        out.append(p)
    return np.array(out, dtype=bool)


win = lambda x, i, n: x[i - n + 1:i + 1] if i >= n - 1 else None
tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, T)]
ret = [nan] + [c[i] / c[i - 1] - 1 for i in range(1, T)]
chk = {}
# SMA(100) 带宽 2%
m = [np.mean(win(c, i, 100)) if i >= 99 else nan for i in range(T)]
chk["SMA(100) 带宽 2%"] = hy([c[i] > m[i] * 1.02 for i in range(T)], [c[i] < m[i] * 0.98 for i in range(T)])
# RSI(14) <30 买 >70 卖
d = [nan] + [c[i] - c[i - 1] for i in range(1, T)]
up, dn = ew([max(x, 0) if x == x else nan for x in d], 1 / 14, 14), ew([max(-x, 0) if x == x else nan for x in d], 1 / 14, 14)
rsi = [100 - 100 / (1 + up[i] / dn[i]) if up[i] == up[i] and dn[i] > 0 else nan for i in range(T)]
chk["RSI(14) <30 买 >70 卖"] = hy([x < 30 for x in rsi], [x > 70 for x in rsi])
# 通道突破 20 / 10
chk["突破 20 日高点买 跌破 10 日低点卖"] = hy([i >= 20 and c[i] > max(h[i - 20:i]) for i in range(T)], [i >= 10 and c[i] < min(l[i - 10:i]) for i in range(T)])
# 布林(50,1.5) 破上轨买 回中轨卖
mid = [np.mean(win(c, i, 50)) if i >= 49 else nan for i in range(T)]
sd = [np.std(win(c, i, 50)) if i >= 49 else nan for i in range(T)]
chk["布林(50,1.5) 破上轨买 回中轨卖"] = hy([c[i] > mid[i] + 1.5 * sd[i] for i in range(T)], [c[i] < mid[i] for i in range(T)])
# CCI(50) >100 买 <0 卖
tp = (h + l + c) / 3
cci = [nan] * T
for i in range(49, T):
    w = tp[i - 49:i + 1]
    cci[i] = (tp[i] - w.mean()) / (0.015 * np.abs(w - w.mean()).mean())
chk["CCI(50) >100 买 <0 卖"] = hy([x > 100 for x in cci], [x < 0 for x in cci])
# MACD(12,26,9) 在信号线上方
e12, e26 = ew(c, 2 / 13, 12), ew(c, 2 / 27, 26)
line = [e12[i] - e26[i] for i in range(T)]
sig = ew(line, 2 / 10, 9)
chk["MACD(12,26,9) 在信号线上方"] = np.array([line[i] > sig[i] for i in range(T)])
# SuperTrend(10,3)
atr = ew(tr, 1 / 10, 10)
fu = fl = nan
upt, st = False, []
for i in range(T):
    bu, bl = (h[i] + l[i]) / 2 + 3 * atr[i], (h[i] + l[i]) / 2 - 3 * atr[i]
    if i > 0:
        if c[i] > fu:
            upt = True
        elif c[i] < fl:
            upt = False
        fu = bu if (fu != fu or bu < fu or c[i - 1] > fu) else fu
        fl = bl if (fl != fl or bl > fl or c[i - 1] < fl) else fl
    else:
        fu, fl = bu, bl
    st.append(upt)
chk["SuperTrend(10,3)"] = np.array(st)
# 连跌 3 天买 持有 5 天
trig = [i >= 3 and ret[i] < 0 and ret[i - 1] < 0 and ret[i - 2] < 0 for i in range(T)]
chk["连跌 3 天买 持有 5 天"] = np.array([any(trig[max(0, i - 4):i + 1]) for i in range(T)])
# 过滤规则
chk["距 50 日低点涨 5% 买 距高点跌 5% 卖"] = hy([i >= 49 and c[i] >= min(c[i - 49:i + 1]) * 1.05 for i in range(T)], [i >= 49 and c[i] <= max(c[i - 49:i + 1]) * 0.95 for i in range(T)])
# 日历
chk["只在星期一持有"] = np.array([(R.IDX[i] + pd.Timedelta(days=1)).dayofweek == 0 for i in range(T)])
bad = [k for k, v in chk.items() if not np.array_equal(v, pos[k])]
print("1. 逐日循环重写 %d 条规则：%s" % (len(chk), "仓位全部逐日相同" if not bad else "不一致 → " + "、".join(bad)))
ok &= not bad

# ---- 2. 未来函数 ----
subprocess.run([sys.executable, "-W", "ignore", os.path.abspath(__file__), "--dump"], check=True, env=dict(os.environ, R3_END=CUT), cwd=HERE)
z = np.load(os.path.join(HERE, "results", "_trunc.npz"))
n = int(z["n"])
worst = max(float(np.abs(D[a][k][:n] - z["%s_%s" % (a, k)]).max()) for a in ("G", "G1", "TO") for k in R.START)
os.remove(os.path.join(HERE, "results", "_trunc.npz"))
print("2. 未来函数：截止日前 %d 天、%d 条规则、3 组资产，收益和换手的最大差异 %.1e %s" % (n, len(pos), worst, "通过" if worst < 1e-12 else "不通过"))
ok &= worst < 1e-12

# ---- 3. 自助法的块均值 ----
rng = np.random.default_rng(1)
F = rng.standard_normal((500, 7))
cs = np.vstack([np.zeros((1, 7)), np.cumsum(np.vstack([F, F]), axis=0)])
st_, ln = rng.integers(0, 500, 60), rng.integers(1, 40, 60)
a = (cs[st_ + ln] - cs[st_]).sum(axis=0)
b = sum(F[np.arange(s_, s_ + n_) % 500].sum(axis=0) for s_, n_ in zip(st_, ln))
bm = R.boot_means(F, nboot=4000, block=10, seed=3)
print("3. 自助法：前缀和与直接取数的差 %.1e；4000 次重抽的均值和样本均值的差（以标准误计）最大 %.2f" % (
    float(np.abs(a - b).max()), float(np.abs((bm.mean(axis=0) - F.mean(axis=0)) / (bm.std(axis=0) / math.sqrt(4000))).max())))
ok &= float(np.abs(a - b).max()) < 1e-9

# ---- 4. 错位对照（BTC）：收益错开，仓位不动 ----
ps = []
r = D["bench"]["BTC"]
P_ = D["POS_BTC"].astype(float)
for k in range(180, 2900, 68):
    rr = np.roll(r, k)
    g = np.zeros(P_.shape)
    g[1:] = P_[:-1] * rr[1:, None]
    D2 = dict(G={"A": g}, G1={"A": g}, TO={"A": D["TO"]["A"]}, EX={"A": D["EX"]["A"]}, fams=D["fams"], names=D["names"], bench=dict(BTC=rr))
    ps.append(R.analyze(D2, "A", nboot=2000, detail=False)["rc_p"])
ps = np.array(ps)
print("4. 错位对照 %d 次：p 值中位数 %.2f，最小 %.3f，小于 0.05 的 %d 次" % (len(ps), np.median(ps), ps.min(), int((ps < 0.05).sum())))
ok &= np.median(ps) > 0.2 and (ps < 0.05).mean() <= 0.15

# ---- 5. 和另一种写法的回归函数对比（ETH） ----
i0 = R.IDX.searchsorted(pd.Timestamp(R.START["ETH"]))
re_ = D["bench"]["ETH"]
Y = (D["G"]["ETH"] - S.COST * D["TO"]["ETH"])[i0:]
_, _, _, t = R.alpha_t(Y, re_[i0:, None])
j = int(np.nanargmax(t))
a_, b_, t_ = S.ols_alpha(pd.Series(Y[:, j]), pd.Series(re_[i0:]))
print("5. ETH 上最好的规则（%s）：这里的 t %.3f，另一种写法 %.3f" % (D["names"][j], t[j], t_))
ok &= abs(t[j] - t_) < 0.1
print("自检：" + ("全部通过" if ok else "有没通过的"))
sys.exit(0 if ok else 1)
