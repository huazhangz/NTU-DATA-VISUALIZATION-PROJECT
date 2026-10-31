# 扩展初步分析（Extended preliminary analysis）报告

生成时间（Generated）：2026-10-31T22:34:51+08:00

## 1. 范围

核心 EDA 只用了 40 项年龄调整指标中的 3 项（糖尿病、肥胖、缺乏体育活动）。本轮对全部 40 项做描述性初步分析：覆盖范围、指标间的县级共变、州级轮廓，以及粗率与年龄调整率的方法检查。

输入：已验收清洗表，SHA-256 `58a324b2918d1e6571056235afc4f1d8fd2817e00c09f1833355de515fadf201`，3,143 行。

## 2. 覆盖范围（Coverage）

| 年份 | 指标数 | 有值县数 | 未发布的州 |
| ---: | ---: | ---: | --- |
| 2022 | 5 | 3,143 | 无 |
| 2023 | 7 | 2,299 | CO FL KY OR PA SD TN TX VT WA WY |
| 2023 | 28 | 2,956 | KY PA |

- 空白表示未发布，一律保留为缺失，不补零、不插补。
- 2022 年的 5 项（结直肠癌筛查、看牙、乳腺 X 光、睡眠不足、65 岁以上全口无牙）不与 2023 指标做相关，也不连成趋势。
- `ACCESS2`（18–64 岁）、`BPMED`（高血压患者）、`COLON_SCREEN`、`MAMMOUSE`、`TEETHLOST` 的人群不是全部成年人。`BPMED` 只在表格中保留，不进入图表，因为它的分母（已诊断高血压者）使县间比较难以直观解读。
- `LONELINESS` 按交接约定标为 Loneliness（字段字典仍写 socially isolated；发布说明称已改为孤独）。

## 3. 指标间共变（Related measures）

方法：35 项 2023 指标两两计算 Spearman 等级相关 `ρ`，使用两两都有值的县（Pairwise complete）。社会需求（HRSN）指标参与的配对只有 2,299 县，其余为 2,956 县，因此两类配对的 `ρ` 不是在同一组县上算的，只宜粗略比较。

强度用语：|ρ| ≥ 0.7 为强，0.4–0.7 为中等，0.2–0.4 为弱，< 0.2 为几乎无关。595 对中：强 236、中等 225、弱 78、几乎无关 56。其中强正相关 234 对，中等及以上负相关 48 对。

与三项核心指标关联最强的其他指标：

- 糖尿病：Fair or poor general health `0.92`；Mobility disability `0.92`；Self-care disability `0.91`；Vision disability `0.91`；Food insecurity `0.91`
- 肥胖：Physical inactivity `0.72`；Current smoking `0.71`；High blood pressure `0.70`；Coronary heart disease `0.68`；COPD (chronic lung disease) `0.65`
- 缺乏体育活动：Mobility disability `0.89`；Fair or poor general health `0.87`；Diabetes `0.86`；Self-care disability `0.86`；Coronary heart disease `0.85`

最强正相关：Vision disability × Self-care disability `0.98`；Vision disability × Food insecurity `0.98`；Food insecurity × Housing insecurity `0.98`；Food insecurity × Lack of reliable transportation `0.98`；Vision disability × Lack of reliable transportation `0.98`。

最强负相关：Cholesterol check in past 5 years × Hearing disability `-0.73`；Binge drinking × Housing insecurity `-0.70`；Binge drinking × Utility shut-off threat `-0.69`；Binge drinking × Diabetes `-0.68`；Binge drinking × Food insecurity `-0.67`。

可靠性检查：最强的一对（Vision disability × Self-care disability，`ρ = 0.98`）在 38 个至少 20 县的州内各自计算，州内 `ρ` 中位数为 0.99，最低 0.95。数值已与原始 CSV 逐格核对一致，不是计算错误。两个概念上不同的指标在几乎每个州内都接近完全同步，说明这种极高相关主要来自 PLACES 小域模型共用同一组县级人口与社会经济协变量，而不是两种现象之间的独立证据。因此图中只用“同步程度”描述，不作因果或机制解读，并对 |ρ| ≥ 0.9 的配对加注。

初步解读：慢性病、健康状况、残疾和社会需求在县级普遍同向变化——一个县若在其中一项偏高，往往多项都偏高；暴饮、癌症、胆固醇检查与这一组多为反向。

## 4. 州级轮廓（State profiles）

方法：每州县级估计的中位数（“该州的典型县”）减全国县级中位数（“美国典型县”），单位为百分点。这不是州人口患病率，未按人口加权；县数少的州（DC 1 县、DE 3 县、HI 5 县）波动较大。

| 指标 | 美国典型县 | 最高的 3 州（差值） | 最低的 3 州（差值） |
| --- | ---: | --- | --- |
| Diabetes | 10.7% | MS +3.7, LA +3.6, GA +2.7 | VT -3.5, NH -3.1, RI -2.8 |
| Depression | 23.9% | WV +8.4, TN +7.3, ME +5.2 | NJ -7.6, HI -7.0, NE -5.5 |
| Food insecurity | 15.8% | MS +10.8, LA +10.8, NM +8.5 | RI -6.1, NH -5.5, ND -4.1 |
| Current smoking | 16.1% | WV +5.3, TN +4.9, LA +3.9 | DC -6.6, UT -5.7, RI -5.5 |
| Binge drinking | 17.6% | ND +5.1, MT +4.9, IA +4.9 | UT -5.3, MS -3.4, NM -2.5 |
| Routine checkup in past year | 75.4% | RI +7.8, LA +4.7, MS +4.4 | NM -9.4, AK -9.3, WY -8.5 |

完整 40 × 51 表见 `outputs/extended_state_medians.csv`。

## 5. 方法检查：粗率与年龄调整率（不做成图）

粗率（Crude）反映县里实际人口；年龄调整率（Age-adjusted）按 2000 年美国标准人口重新加权，用于县间公平比较。二者之差（粗率 − 调整率）：

| 指标 | 年份 | 中位差（百分点） | 5%–95% | 粗率更高的县占比 |
| --- | ---: | ---: | --- | ---: |
| Taking blood pressure medicine (adults with high BP) | 2023 | +20.00 | +14.1 至 +25.2 | 100% |
| High cholesterol | 2023 | +6.30 | +1.8 至 +10.0 | 98% |
| Colorectal cancer screening (ages 45–75) | 2022 | +6.20 | +3.4 至 +9.7 | 100% |
| Arthritis | 2023 | +5.30 | +0.0 至 +10.0 | 95% |
| High blood pressure | 2023 | +5.30 | -0.3 至 +10.2 | 94% |
| Loneliness | 2023 | -1.50 | -2.8 至 +0.5 | 8% |
| Frequent mental distress | 2023 | -1.50 | -3.0 至 +0.1 | 6% |
| Binge drinking | 2023 | -2.10 | -4.5 至 +0.0 | 5% |

结论：与年龄相关的慢性病差值可达数个百分点，方向随指标而变，所以县间比较必须使用年龄调整率（本项目所有图表都如此）。三项核心指标的中位差为：Diabetes +2.5，Physical inactivity +1.5，Obesity -0.1 个百分点。`BPMED` 的差值约 +20 个百分点，进一步说明它不适合放进面向大众的图表。

## 6. 解读边界

- 全部为县级生态描述，不推断个人风险，也不推断因果。
- 估计来自同一小域模型，共享协变量会抬高指标间相关（见第 3 节检查）。
- 州中位数不等于州患病率；未按人口加权。
- 不把 2022 与 2023 指标连成时间趋势。

## 7. 对应可视化

- `03_visualisations/final/interactive_related_measures/`：选择一项指标，查看其他 2023 指标与它的同步程度（排序条形图），点击条形查看县级散点。
- `03_visualisations/final/interactive_state_tiles/`：州瓦片地图 + 排名点图，可切换 39 项指标。
