# -*- coding: utf-8 -*-
"""
复现本档案：技术指标规则大全（21 类、467 条日线规则）在“30 币等权”上的 Reality Check。

  py verify.py

会打印：最好一条规则的 t、Reality Check 的 p 值、成本和块长的敏感性、样本外的情况、每一类的情况、判定，
然后和 results/expected.json 里归档时的数字核对。ETH 单独的结果作为参考一并给出（不是登记的主检验）。
结果同时写到 results/output.txt；每条规则一行的明细在 results/rules_B.csv 和 results/rules_ETH.csv。

需要 pandas 和 numpy：  pip install pandas numpy
"""
import json
import math
import os
import sys
import time

T0 = time.time()
import study as S          # noqa: E402
import specs               # noqa: E402

LINES = []
pc = lambda x: "%+.1f%%" % (100 * x)


def out(s=""):
    print(s)
    LINES.append(s)


def show(r):
    out("=" * 78)
    out("%s  %s → %s（%d 天）  规则 %d 条（参与 %d 条）" % (r["name"], r["start"], r["end"], r["days"], r["rules"], r["rules_used"]))
    out("  最好一条：%s〔%s〕，超额 t %.2f" % (r["best"], r["best_family"], r["max_t"]))
    out("  Reality Check：p = %.4f（如果 467 条全都没有择时能力，最大 t 的 95%% 分位是 %.2f）" % (r["rc_p"], r["crit95"]))
    out("  超额为正的规则占 %.0f%%，t > 2 的占 %.1f%%，t 的中位数 %.2f" % (100 * r["share_pos"], 100 * r["share_t2"], r["median_t"]))
    tb, td = r["train_best"], r["top_decile"]
    out("  训练段最好的规则：%s（训练段 t %.2f）→ 验证段超额 %s，t %.2f" % (tb["name"], tb["t_train"], pc(tb["alpha_test"]), tb["t_test"]))
    out("  训练段前 10%%（%d 条）合在一起 → 验证段超额 %s，t %.2f；训练段和验证段 t 的秩相关 %.2f；验证段超额为正的占 %.0f%%" % (
        td["n"], pc(td["alpha_test"]), td["t_test"], r["spearman"], 100 * r["share_pos_test"]))
    if "cost2" in r:
        out("  成本翻倍：p %.4f（最大 t %.2f）；零成本：p %.4f（最大 t %.2f）；晚一天执行：p %.4f（最大 t %.2f）" % (
            r["cost2"]["rc_p"], r["cost2"]["max_t"], r["cost0"]["rc_p"], r["cost0"]["max_t"], r["delay1"]["rc_p"], r["delay1"]["max_t"]))
        out("  块长 5 天：p %.4f；块长 20 天：p %.4f" % (r["block5"], r["block20"]))
    h, b = r["hold"], r["best_sharpe"]
    out("  一直持有：年化 %s，夏普 %.2f，最大回撤 %s" % (pc(h["ret"]), h["sharpe"], pc(h["mdd"])))
    out("  夏普最高的规则：%s，年化 %s，夏普 %.2f，最大回撤 %s，超额 t %.2f；夏普超过“一直持有”的规则占 %.0f%%" % (
        b["name"], pc(b["ret"]), b["sharpe"], pc(b["mdd"]), b["t_alpha"], 100 * b["share_beating_hold"]))
    out("  各类的情况（类别｜条数｜超额为正｜t 中位数｜最好一条的 t｜类内 p｜训练段 / 验证段 t 中位数｜平均仓位｜年换手｜最好一条）")
    for f in r["families"]:
        out("    %s｜%d｜%.0f%%｜%+.2f｜%.2f｜%.3f｜%+.2f / %+.2f｜%.0f%%｜%.0f｜%s" % (
            f["family"], f["n"], 100 * f["share_pos"], f["median_t"], f["best_t"], f["p_family"], f["median_t_train"], f["median_t_test"],
            100 * f["exposure"], f["turnover"], f["best"]))
    out("  t 最高的 5 条：" + "；".join("%s %.2f（训练段 %.2f，验证段 %.2f）" % (x["name"], x["t"], x["t_train"], x["t_test"]) for x in r["top10"][:5]))
    if "verdict" in r:
        miss = [k for k, v in r["checks"].items() if not v]
        out("  判定：%s。没有满足的标准：%s" % (r["verdict"], "；".join(miss) if miss else "无"))


def compare(r, e):
    bad = []
    if abs(r["max_t"] - e["max_t"]) > 0.005:
        bad.append("最大 t")
    if abs(r["rc_p"] - e["rc_p"]) > 0.01:
        bad.append("p 值")
    if r["best"] != e["best"]:
        bad.append("最好的规则")
    if r.get("verdict") != e.get("verdict"):
        bad.append("判定")
    return bad


def main():
    update = "--update" in sys.argv
    efn = os.path.join(S.RES, "expected.json")
    expected = json.load(open(efn, encoding="utf-8")) if os.path.exists(efn) else {}
    out("数据：币安现货日线 %s 到 %s，%d 个品种（其中已下架 %d 个）；进过币池的币 %d 个" % (
        specs.IDX[0].date(), specs.DATA_END.date(), specs.P.close.shape[1], int((specs.P.meta.status != "TRADING").sum()), len(specs.COINS) - 2))
    D = specs.build()
    out("规则：%d 条，%d 类" % (len(D["names"]), len(set(D["fams"]))))
    res = {"B": specs.evaluate(D, "B"), "ETH": specs.analyze(D, "ETH")}
    ok = 0
    for k in ("B", "ETH"):
        if k == "ETH":
            out("")
            out("以下是 ETH 单独的结果，只作参考，不是登记的主检验：")
        show(res[k])
        if update or k not in expected:
            out("  核对：没有归档数字可比（这次的结果已记为归档数字）" if update else "  核对：results/expected.json 里没有这一项")
            expected[k] = specs.clean(res[k])
            ok += 1 if update else 0
            continue
        bad = compare(res[k], expected[k])
        out("  核对：和归档数字不一致 → %s" % "、".join(bad) if bad else "  核对：和归档数字一致")
        ok += 0 if bad else 1
    out("=" * 78)
    out("结果：%d / 2 项和归档数字一致；30 币等权的判定：%s。用时 %.0f 秒" % (ok, res["B"]["verdict"], time.time() - T0))
    os.makedirs(S.RES, exist_ok=True)
    if update:
        json.dump(expected, open(efn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for k in ("B", "ETH"):
            specs.rule_table(D, k).to_csv(os.path.join(S.RES, "rules_%s.csv" % k), index=False, float_format="%.4f", encoding="utf-8-sig")
    with open(os.path.join(S.RES, "output.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LINES) + "\n")
    sys.exit(0 if ok == 2 else 1)


if __name__ == "__main__":
    main()
