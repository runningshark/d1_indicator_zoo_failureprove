# d1_indicator_zoo_failureprove

**技术指标规则大全（467 条，30 币等权）**：属于 [量化失败合集 quant-failure-archive](https://github.com/runningshark/quant-failure-archive) 的第 30 条。

把常见技术指标展开成 467 条只做多的日线规则，放在成交额最高的 30 个币上，一次测完。最好的一条超额 t 2.85；校正“试了 467 条”之后 p = 0.16，和运气分不出来。

- 档案：[FAILURE_REPORT.md](FAILURE_REPORT.md)
- 测之前写下的规则清单和通过标准：[事先登记_第三轮.md](事先登记_第三轮.md)，它的 SHA-256 在 [登记哈希.txt](登记哈希.txt)
- 复现：`py verify.py`（需要 pandas、numpy），结果写到 `results/output.txt`
- 代码：`zoo.py`（467 条规则）、`specs.py`（币池、收益、Reality Check、判定）、`study.py`（读数据和统计函数）、`selftest.py`（自检）、`tools/make_reports.py`（把归档数字填进档案）
- 数据：`data/`，币安现货日线（收盘、最高、最低、成交额，含已下架的币），截至 2026-11-25；`download_data.py` 可以重新下载
- 每条规则一行的明细：`results/rules_B.csv`（30 币等权）、`results/rules_ETH.csv`（ETH，参考）

```bash
git clone https://github.com/runningshark/d1_indicator_zoo_failureprove
cd d1_indicator_zoo_failureprove
pip install pandas numpy
py verify.py
```

不构成任何投资建议。
