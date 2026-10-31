# 扩展探索分析（Extended preliminary analysis）报告

生成时间（Generated）：2026-10-31T21:54:25+08:00

## 1. 为什么扩展

核心 EDA 只用了 40 项年龄调整指标中的 3 项（糖尿病、肥胖、缺乏体育活动）。本轮对其余 37 项做初步分析，回答三个描述性问题：

1. 35 项 2023 指标之间的县级共变结构（Measure landscape）是什么样的？
2. 各州的县级中位数相对全国县级中位数偏高还是偏低（State profiles）？
3. 粗率（Crude）与年龄调整率（Age-adjusted）差多少，哪些指标、哪些县受人口年龄结构影响最大？

## 2. 数据范围

- 输入：已验收清洗表，SHA-256 `58a324b2918d1e6571056235afc4f1d8fd2817e00c09f1833355de515fadf201`，3,143 行。
- 35 项指标为 2023 年估计；`COLON_SCREEN`、`DENTAL`、`MAMMOUSE`、`SLEEP`、`TEETHLOST` 5 项为 2022 年估计，3,143 县全有值。2022 指标不进入第 3 节的相关矩阵，避免混合年份。
- Kentucky、Pennsylvania 无 2023 估计；7 项社会需求（HRSN）指标另在 CO、FL、OR、SD、TN、TX、VT、WA、WY 空白，只有 2,299 县有值。空白一律保留为缺失，不补零。
- `LONELINESS` 按交接文件的约定标为 Loneliness（字段字典描述仍写 socially isolated；发布说明称已改为孤独）。
- `ACCESS2`（18–64 岁）、`BPMED`（高血压患者）、`COLON_SCREEN`、`MAMMOUSE`、`TEETHLOST` 的分母不是全部成年人，只与自身比较。

## 3. 指标共变结构（Measure landscape）

方法：两两完整县（Pairwise complete）的 Spearman `ρ`；以 `1 − ρ` 为距离做平均连接层次聚类（Average-linkage / UPGMA），在高度 0.55 处切分成组。社会需求指标与其他指标的配对只有 2,299 县，其余配对为 2,956 县。

| 组 | 成员 |
| ---: | --- |
| 1 | Current asthma, Depression |
| 2 | High cholesterol, BP medication (among high BP), Routine checkup |
| 3 | Hearing disability, Obesity, No health insurance (18–64), Arthritis, Frequent mental distress, Coronary heart disease, COPD, Current smoking, High blood pressure, Received food stamps, Physical inactivity, Cognitive disability, Any disability, Frequent physical distress, Stroke, Fair or poor health, Mobility disability, Independent-living disability, Diagnosed diabetes, Utility shut-off threat, Food insecurity, Housing insecurity, Lack of transportation, Vision disability, Self-care disability, Loneliness, Lack of emotional support |
| 4 | Cholesterol screening |
| 5 | Binge drinking, Cancer (non-skin) |

最强正相关：Vision disability × Self-care disability `ρ = 0.98`；Vision disability × Food insecurity `ρ = 0.98`；Food insecurity × Housing insecurity `ρ = 0.98`；Food insecurity × Lack of transportation `ρ = 0.98`；Vision disability × Lack of transportation `ρ = 0.98`。

最强负相关：Cholesterol screening × Hearing disability `ρ = -0.73`；Binge drinking × Housing insecurity `ρ = -0.70`；Binge drinking × Utility shut-off threat `ρ = -0.69`；Binge drinking × Diagnosed diabetes `ρ = -0.68`；Cancer (non-skin) × Housing insecurity `ρ = -0.67`。

社会需求与其他类别关联最强的配对：Vision disability × Food insecurity `ρ = 0.98`；Vision disability × Lack of transportation `ρ = 0.98`；Self-care disability × Lack of transportation `ρ = 0.97`；Self-care disability × Food insecurity `ρ = 0.96`；Vision disability × Housing insecurity `ρ = 0.95`；Stroke × Lack of transportation `ρ = 0.95`。

初步解读：慢性病、健康状况、残疾和社会需求在县级高度同向共变，形成一个大的“负担”簇；暴饮（Binge drinking）、筛查与就诊类预防指标多与该簇负相关。高相关部分源于 PLACES 小域模型共享县级协变量，不能当作独立证据。

## 4. 州级轮廓（State profiles）

方法：每州县级估计的中位数减去全国县级中位数（百分点）。这是县的中位数，不是州人口患病率；县数少的州（DC 1 县、DE 3 县、HI 5 县）波动更大。

| 指标 | 全国县中位数 | 最高的 3 州（差值） | 最低的 3 州（差值） |
| --- | ---: | --- | --- |
| Depression | 23.9% | WV +8.4, TN +7.3, ME +5.2 | NJ -7.6, HI -7.0, NE -5.5 |
| Loneliness | 34.0% | GA +4.8, LA +4.0, MS +4.0 | ND -4.0, ID -3.6, NE -3.5 |
| Food insecurity | 15.8% | LA +10.8, MS +10.8, NM +8.5 | RI -6.1, NH -5.5, ND -4.1 |
| Current smoking | 16.1% | WV +5.3, TN +4.9, LA +3.9 | DC -6.6, UT -5.7, RI -5.5 |
| Binge drinking | 17.6% | ND +5.1, IA +4.9, DC +4.9 | UT -5.3, MS -3.4, OK -2.5 |
| Routine checkup | 75.4% | RI +7.8, LA +4.7, MS +4.4 | NM -9.4, AK -9.3, WY -8.5 |

完整 40 × 51 表见 `outputs/extended_state_medians.csv`。

## 5. 年龄调整差（Crude − age-adjusted）

差值为正表示该县成年人口比美国 2000 年标准人口更老，粗率因此高于年龄调整率。

| 指标 | 年份 | 中位差（百分点） | 5%–95% | 粗率更高的县占比 |
| --- | ---: | ---: | --- | ---: |
| BP medication (among high BP) | 2023 | +20.00 | +14.1 至 +25.2 | 100% |
| High cholesterol | 2023 | +6.30 | +1.8 至 +10.0 | 98% |
| Colorectal screening (45–75) | 2022 | +6.20 | +3.4 至 +9.7 | 100% |
| Arthritis | 2023 | +5.30 | +0.0 至 +10.0 | 95% |
| High blood pressure | 2023 | +5.30 | -0.3 至 +10.2 | 94% |
| Mobility disability | 2023 | +2.90 | -0.1 至 +5.6 | 94% |
| Housing insecurity | 2023 | -1.40 | -2.8 至 -0.4 | 1% |
| Frequent mental distress | 2023 | -1.50 | -3.0 至 +0.1 | 6% |
| Loneliness | 2023 | -1.50 | -2.8 至 +0.5 | 8% |
| Binge drinking | 2023 | -2.10 | -4.5 至 +0.0 | 5% |

8 项年龄相关慢性指标的县级差值彼此高度一致（两两相关中位数 0.97），说明差值主要反映同一个县级年龄结构因素。按这 8 项差值的平均 z 分数排序，差值最大的县为：Sumter, FL（+4.40）；La Paz, AZ（+3.87）；Jeff Davis, TX（+3.40）；Catron, NM（+3.39）；Kalawao, HI（+3.33）。

含义：比较县与县的健康负担时应使用年龄调整率（本项目已如此）；规划服务需求时，粗率更接近当地实际人数比例。

## 6. 解读边界

- 全部为县级生态描述，不推断个人风险，也不推断因果。
- 估计来自同一小域模型，共享协变量会抬高指标间相关。
- 聚类切分高度是为了可读性选定的探索参数，不是统计检验结果。
- 州中位数不等于州患病率；未按人口加权。

## 7. 对应可视化

- `03_visualisations/final/interactive_measure_landscape/`：聚类相关热力图 + 树状图（Dendrogram）+ 六边形分箱密度图（Hexbin）。
- `03_visualisations/final/interactive_state_tiles/`：州瓦片地图（Tile-grid cartogram）+ 发散色阶 + 州排名点图。
- `03_visualisations/final/interactive_age_gap/`：山脊图（Ridgeline）+ 县级哑铃图（Dumbbell）。
