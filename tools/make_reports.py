# -*- coding: utf-8 -*-
"""
生成 FAILURE_REPORT.md、README.md 和 entry.json。数字全部来自 results/expected.json（verify.py --update 写出的归档数字），不手抄。
用法：  py tools/make_reports.py
合集总仓库（quant-failure-archive）README 里这一条的表格行和小节也由这里生成：
设环境变量 MAIN_ROWS=<文件路径>、MAIN_SECTION=<文件路径> 再运行。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NO = 30
REPO = "d1_indicator_zoo_failureprove"
URL = "https://github.com/runningshark/" + REPO
ARCHIVE = "https://github.com/runningshark/quant-failure-archive"
CLONE = ["git clone " + URL, "cd " + REPO]
X = json.load(open(os.path.join(ROOT, "results", "expected.json"), encoding="utf-8"))
E, ETH = X["B"], X["ETH"]
FAM = {f["family"]: f for f in E["families"]}

pc = lambda x, d=1: ("%+.*f%%" % (d, 100 * x)).replace("-", "−")
pu = lambda x, d=1: ("%.*f%%" % (d, 100 * x)).replace("-", "−")
nm = lambda x, d=2: ("%.*f" % (d, x if round(x, d) != 0 else 0.0)).replace("-", "−")
TITLE = "技术指标规则大全（467 条，30 币等权）"
CONCL = "确认失败（最好的一条和运气分不出来）"
TREND = ["价格与均线", "双均线交叉", "MACD", "RSI 顺势", "布林带突破", "一目均衡表", "SuperTrend"]
REVERT = ["布林带回归", "RSI 超卖买入", "连跌接多", "日历"]

tb, td, h, bs = E["train_best"], E["top_decile"], E["hold"], E["best_sharpe"]
D = dict(n=E["rules"], max_t=nm(E["max_t"]), best=E["best"], best_family=E["best_family"], crit=nm(E["crit95"]), p=nm(E["rc_p"]),
         p0=nm(E["cost0"]["rc_p"], 3), t0=nm(E["cost0"]["max_t"]), p2=nm(E["cost2"]["rc_p"]), t2=nm(E["cost2"]["max_t"]),
         pd_=nm(E["delay1"]["rc_p"]), td_=nm(E["delay1"]["max_t"]), b5=nm(E["block5"]), b20=nm(E["block20"]),
         tb=tb["name"], tb_t=nm(tb["t_train"]), tb_test=nm(tb["t_test"]), tb_alpha=pc(tb["alpha_test"]), td_n=td["n"], td_t=nm(td["t_test"]), td_alpha=pc(td["alpha_test"]),
         rho=nm(E["spearman"]), pos=pu(E["share_pos"], 0), t2share=pu(E["share_t2"]), pos_test=pu(E["share_pos_test"], 0),
         hold_ret=pc(h["ret"]), hold_sh=nm(h["sharpe"]), hold_mdd=pu(h["mdd"]), bs=bs["name"], bs_ret=pc(bs["ret"]), bs_sh=nm(bs["sharpe"]), bs_mdd=pu(bs["mdd"]),
         beat=pu(bs["share_beating_hold"], 0), start=E["start"], end=E["end"],
         kd_n=FAM["随机指标 KD"]["n"], kd_med=nm(FAM["随机指标 KD"]["median_t"]), kd_pos=pu(FAM["随机指标 KD"]["share_pos"], 0),
         ma1=nm(FAM["价格与均线"]["median_t_test"]), ma2=nm(FAM["双均线交叉"]["median_t_test"]),
         rev_minp=nm(min(FAM[k]["p_family"] for k in REVERT)), trend_lo=pu(min(FAM[k]["share_pos"] for k in TREND), 0), trend_hi=pu(max(FAM[k]["share_pos"] for k in TREND), 0),
         to_lo="%.0f" % min(f["turnover"] for f in E["families"]), to_hi="%.0f" % max(f["turnover"] for f in E["families"]),
         eth_t=nm(ETH["max_t"]), eth_p=nm(ETH["rc_p"]), eth_best=ETH["best"])

RULE = ("21 类、467 条只做多的日线规则：均线、双均线、MACD、RSI、布林带、通道突破、动量、KD、KDJ、过滤规则、OBV、CCI、ADX、一目均衡表、SuperTrend、连跌接多、急跌接多、肯特纳通道、日历等，"
        "每条每天收盘给出持有或空仓。每周日确定成交额最高的 30 个币（连续历史不少于 365 天），每条规则在每个币上各自给信号，每个币占资金的 1/30。完整清单见[《事先登记_第三轮.md》](事先登记_第三轮.md)第 3 节。")
REASONS = [
    "**最好的一条经不起“试了 {n} 条”的校正。** 超额 t 最高的是“{best}”，t = {max_t}。如果 {n} 条全都没有择时能力，光靠运气，最大 t 的 95% 分位就有 {crit}。Reality Check 的 p = {p}，离登记的门槛 0.0024 很远。见 `verify.py` 输出的 Reality Check 一行。",
    "**成本。** 零成本时 p = {p0}（最大 t {t0}）；扣单边 0.10% 后 p = {p}；成本翻倍后 p = {p2}（最大 t {t2}）。",
    "**样本外。** 只看训练段，最好的规则是“{tb}”（训练段 t {tb_t}），它在验证段的超额 t 只有 {tb_test}。训练段前 10% 的 {td_n} 条规则合在一起，验证段 t 也只有 {td_t}。均线两类在验证段的 t 中位数是 {ma1} 和 {ma2}。",
    "**逆势、摆动类没有择时能力。** 随机指标 KD 的 {kd_n} 条规则超额全部为负（t 中位数 {kd_med}）。布林带回归、RSI 超卖买入、连跌接多、日历这几类，在类内部做同样的检验，p 都在 {rev_minp} 以上。见下面的分类表。",
]
LEFT = [
    "趋势类规则（均线、MACD、布林带突破、SuperTrend、一目均衡表等）超额为正的占 {trend_lo} 到 {trend_hi}，方向一致，但没有一条单独显著。它们实在的作用是降回撤：一直持有这 30 个币，夏普 {hold_sh}、最大回撤 {hold_mdd}；{n} 条里夏普超过持有的占 {beat}，夏普最高的一条（{bs}）夏普 {bs_sh}、最大回撤 {bs_mdd}。可以当风控，不能当成稳定的超额来源。",
    "训练段和验证段的 t 在规则之间的秩相关是 {rho}：规则的相对好坏有一些延续，但幅度不够把最好的那几条从运气里分出来。",
    "ETH 单独做同样的检验（只作参考，不是登记的主检验）：最大 t {eth_t}，p = {eth_p}，结论相同。",
    "同一轮登记的另一组（只在 BTC 上用这 {n} 条规则）没有被判为失败，属于“待观察”，不在失败档案里，这里不放它的结果。",
]
DEFECTS = [
    "检验本身偏乐观。把收益和仓位错开几百天再做同样的检验（这时不应该检验出任何东西），40 次里有 5 次 p < 0.05，高于应有的 5%（见 `selftest.py` 第 4 项）。行情有长达数月的涨跌阶段，10 天的块长低估了这种依赖。这里的结论是失败，偏乐观只会让结论更保守，不影响判定。块长换成 5 天和 20 天，p 分别是 {b5} 和 {b20}。",
    "假设按收盘价成交。晚一天执行时，最大 t {td_}，p = {pd_}。",
    "只做多，不做空，不加杠杆。",
    "每个币按资金的 1/30 计，不计仓位漂移，也不计把仓位调回 1/30 的成本；基准（一直持有这 30 个币）同样处理。",
    "超额用全区间固定的回归系数计算；仓位随行情变化的规则，这样算出来的超额里可能混有一部分择时以外的东西。",
    "规则清单是凭常见用法定的。没有包括需要开盘价的 K 线形态、抛物线 SAR、缠论、SMC、波浪和各种主观画线，这些不在本条的结论之内。",
    "只用了币安一家的现货日线；更高频的用法不在本条之内（合集第 02–08 条测过几种 1 小时规则）。",
    "同一项研究累计做了 21 个事先登记的检验，所以 p 的门槛是 0.05 ÷ 21 = 0.0024。",
    "完整的重新下载（`download_data.py`）没有从头到尾重跑过一遍；`data/` 里是下载当时生成的文件。",
]


def fam_table():
    rows = ["| 类别 | 条数 | 超额为正 | t 的中位数 | 最好一条 | 它的 t | 类内 p | 训练段 / 验证段 t 中位数 |", "|---|---|---|---|---|---|---|---|"]
    for f in E["families"]:
        rows.append("| %s | %d | %s | %s | %s | %s | %s | %s / %s |" % (f["family"], f["n"], pu(f["share_pos"], 0), nm(f["median_t"]), f["best"], nm(f["best_t"]), nm(f["p_family"], 3),
                                                             nm(f["median_t_train"]), nm(f["median_t_test"])))
    return "\n".join(rows)


def numbers():
    rows = [("全区间收益", "按指标买卖比一直拿着强", "一直持有这 30 个币：年化 {hold_ret}，夏普 {hold_sh}。夏普最高的规则（{bs}）：年化 {bs_ret}，夏普 {bs_sh}。{n} 条里夏普超过持有的占 {beat}"),
            ("样本外收益", "—", "训练段最好的规则（{tb}）在 2024-01-01 以后：超额年化 {tb_alpha}，t = {tb_test}"),
            ("最大回撤", "—", "一直持有 {hold_mdd}；夏普最高的规则 {bs_mdd}"),
            ("夏普", "—", "见上"),
            ("交易次数", "—", "各类规则平均每年进出 {to_lo} 到 {to_hi} 次（每个币）"),
            ("胜率 / 盈亏比", "—", "不适用：这里检验的是一整类规则，不是某一条"),
            ("最好一条的超额 t", "显著", "{max_t}；全靠运气时最大 t 的 95% 分位 {crit}；Reality Check p = {p}"),
            ("超额为正的规则", "—", "占 {pos}；t > 2 的占 {t2share}；验证段超额为正的占 {pos_test}")]
    return "| 项目 | 原声称 | 复核结果 |\n|------|--------|----------|\n" + "\n".join("| %s | %s | %s |" % (a, b, c.format(**D)) for a, b, c in rows)


def failure_report():
    L = ["# %d · %s" % (NO, TITLE), "",
         "属于 [量化失败合集](%s)。这是第三轮事先登记的研究：不是一条一条地测，而是把常见技术指标展开成 %d 条规则一次测完，再用 Reality Check 校正“试了很多条”。" % (ARCHIVE, E["rules"]), "",
         "## 一句话结论", "",
         "{n} 条指标规则里最好的一条 t {max_t}，校正后 p = {p}，和运气分不出来。".format(**D), "",
         "## 原始声称", "",
         "- 作者 / 出处：不是某一个人的策略，而是整套“看技术指标买卖”的说法：均线、MACD、RSI、布林带、KDJ、一目均衡表、SuperTrend 等，交易教程和行情软件里的常见用法。学术上的对照是 Sullivan、Timmermann、White《Data-Snooping, Technical Trading Rule Performance, and the Bootstrap》（Journal of Finance，1999），他们用 Reality Check 检验了 7846 条股票技术规则。",
         "- 声称的收益、回撤、样本外区间：按指标的信号买卖，比一直拿着强。每个指标各有各的说法，没有统一的数字。",
         "- 声称使用的数据与成本假设：流行的展示通常是单个币、单组参数、不扣成本、事后挑出来的那一段行情。", "",
         "## 复核方法", "",
         "- 被检验的规则：" + RULE,
         "- 数据来源与区间：币安现货全部 USDT 交易对的日线（收盘、最高、最低、成交额），**包含已下架的币**。区间 {start} 到 {end}（币池满 30 个币之后）。".format(**D),
         "- 复现方式（逐位复现 / 重写 / 只做统计检验）：重写加统计检验。规则清单、统计量和通过标准在计算任何一条规则的收益之前写进了《事先登记_第三轮.md》，文件的 SHA-256 记在 [登记哈希.txt](登记哈希.txt)；之后没有增删规则，也没有改参数范围。",
         "- 成本假设（手续费、滑点、资金费、借贷利息）：单边 0.10%，仓位每变一次付一次；币进出币池造成的买卖同样付。现货，不涉及资金费。",
         "- 是否样本外：是。训练段到 2023-12-31，验证段从 2024-01-01 起：只用训练段选出最好的规则，再看它在验证段的表现。",
         "- 统计量：每条规则的日净收益，对“一直持有 BTC”和“一直持有这 30 个币”两个因子回归，截距（超额）的 t 值衡量它的择时能力。Reality Check 取 {n} 条规则里 t 的最大值，用平稳自助法（平均块长 10 天，10000 次）得到“全都没有择时能力”时这个最大值的分布。通过标准是 p < 0.0024。".format(**D), "",
         "## 实际数字", "", numbers(), "",
         "分类（类内 p 是只在这一类内部做 Reality Check 的结果，只作描述，不用来判定）：", "", fam_table(), "",
         "每条规则一行的明细在 [results/rules_B.csv](results/rules_B.csv)。", "",
         "## 失败原因", ""]
    L += ["%d. %s" % (k + 1, s.format(**D)) for k, s in enumerate(REASONS)]
    miss = [k for k, v in E["checks"].items() if not v]
    L += ["", "按《事先登记_第三轮.md》第 5 节，没有满足的标准：" + "；".join(miss) + "。", "",
          "## 剩下的东西", ""]
    L += ["- " + s.format(**D) for s in LEFT]
    L += ["", "## 复现命令", "", "```bash"] + CLONE + ["pip install pandas numpy", "py verify.py      # 约 1 分钟；末尾一行是 “2 / 2 项和归档数字一致”", "py selftest.py    # 自检，约 3 分钟", "```", "",
          "归档时的完整输出在 [results/output.txt](results/output.txt)。", "",
          "## 已知缺陷 / 未验证部分", ""]
    L += ["- " + s.format(**D) for s in DEFECTS]
    L += ["", "不构成任何投资建议。", ""]
    return "\n".join(L)


def readme():
    L = ["# " + REPO, "",
         "**%s**：属于 [量化失败合集 quant-failure-archive](%s) 的第 %d 条。" % (TITLE, ARCHIVE, NO), "",
         "把常见技术指标展开成 {n} 条只做多的日线规则，放在成交额最高的 30 个币上，一次测完。最好的一条超额 t {max_t}；校正“试了 {n} 条”之后 p = {p}，和运气分不出来。".format(**D), "",
         "- 档案：[FAILURE_REPORT.md](FAILURE_REPORT.md)",
         "- 测之前写下的规则清单和通过标准：[事先登记_第三轮.md](事先登记_第三轮.md)，它的 SHA-256 在 [登记哈希.txt](登记哈希.txt)",
         "- 复现：`py verify.py`（需要 pandas、numpy），结果写到 `results/output.txt`",
         "- 代码：`zoo.py`（467 条规则）、`specs.py`（币池、收益、Reality Check、判定）、`study.py`（读数据和统计函数）、`selftest.py`（自检）、`tools/make_reports.py`（把归档数字填进档案）",
         "- 数据：`data/`，币安现货日线（收盘、最高、最低、成交额，含已下架的币），截至 %s；`download_data.py` 可以重新下载" % E["end"],
         "- 每条规则一行的明细：`results/rules_B.csv`（30 币等权）、`results/rules_ETH.csv`（ETH，参考）", "",
         "```bash"] + CLONE + ["pip install pandas numpy", "py verify.py", "```", "",
         "不构成任何投资建议。", ""]
    return "\n".join(L)


def main_row():
    key = "最大 t {max_t}，校正“试了 {n} 条”后 p **{p}**；成本翻倍 p {p2}；训练段最好的规则验证段 t **{tb_test}**；KD {kd_n} 条全负".format(**D)
    return "| %d | 日线 · %s | **确认失败**（最好的一条和运气分不出来） | %s | [%s](%s) |" % (NO, TITLE, key, REPO, URL)


def main_section():
    L = ["### %d · %s" % (NO, TITLE), "",
         "把常见技术指标（均线、MACD、RSI、布林带、KD、通道突破、一目均衡表、SuperTrend 等 21 类）展开成 {n} 条只做多的日线规则，每周日选成交额最高的 30 个币，每条规则在每个币上各自给信号。规则清单和通过标准同样是事先登记的。问的不是“哪一条好”，而是“最好的那一条，扣掉试了 {n} 条的运气之后还剩不剩”。".format(**D), ""]
    L += ["- " + s.format(**D).replace("见 `verify.py` 输出的 Reality Check 一行。", "").replace("见下面的分类表。", "") for s in REASONS]
    L += ["- 剩下的线索：" + LEFT[0].format(**D)]
    L += ["", "```bash"] + CLONE + ["py verify.py", "```", ""]
    return "\n".join(L)


def main():
    open(os.path.join(ROOT, "FAILURE_REPORT.md"), "w", encoding="utf-8").write(failure_report())
    open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8").write(readme())
    json.dump(dict(no=NO, id="B", name=TITLE, verdict=E["verdict"], conclusion=CONCL, rules=E["rules"], max_t=E["max_t"], rc_p=E["rc_p"], threshold_p=0.0024,
                   cumulative_tests=21, data_end=E["end"]), open(os.path.join(ROOT, "entry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.environ.get("MAIN_ROWS"):
        open(os.environ["MAIN_ROWS"], "w", encoding="utf-8").write(main_row() + "\n")
    if os.environ.get("MAIN_SECTION"):
        open(os.environ["MAIN_SECTION"], "w", encoding="utf-8").write(main_section())
    print("写好了 FAILURE_REPORT.md、README.md、entry.json")


if __name__ == "__main__":
    main()
