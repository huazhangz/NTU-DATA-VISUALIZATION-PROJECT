# Analysis

当前状态：清洗 CSV 已于 2026-10-29 通过 EDA 输入验收（16 PASS、0 FAIL），现作为正式 EDA 输入。

- `validate_eda_input.py`：EDA 输入验收脚本。
- `outputs/input_validation_report.md`：人类可读的验收报告。
- `outputs/input_validation.json`：机器可读的完整检查结果。
- `outputs/input_missingness_by_metric.csv`：首轮核心指标缺失统计。
- `outputs/input_missingness_by_state.csv`：按州和指标展开的缺失统计。

重新验收：

```bash
python3 02_analysis/validate_eda_input.py
```

基础 EDA 已于 2026-10-29 完成，范围为糖尿病、肥胖和缺乏体育活动三个 2023 年年龄调整指标。

- `basic_eda.py`：可复现的基础 EDA 脚本，要求验收结果为 PASS 且输入哈希未变。
- `EDA_report.md`：当前正式 EDA 报告。
- `outputs/basic_*`：当前基础 EDA 的表格与运行清单。
- `../03_visualisations/exploratory/basic_*`：当前基础 EDA 探索图。

重新运行：

```bash
python3 02_analysis/basic_eda.py
```

新的正式 EDA 必须读取已验收的清洗 CSV。若清洗表不存在、验收未通过或文件哈希已变，分析流程应停止并明确报错，不得静默改用原始 CSV。
