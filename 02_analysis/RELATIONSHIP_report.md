# 关系分析（Relationship Analysis）报告

生成时间（Generated）：2026-10-31T22:34:47+08:00

## 1. 分析问题（Research question）

2023 年美国县级年龄调整糖尿病患病率（Diagnosed diabetes）与肥胖（Obesity）、缺乏体育活动（No leisure-time physical activity）之间呈现怎样的县级关联（County-level association）？三项指标的较高值在多大程度上共同出现？

## 2. 方法（Methods）

- 使用 2,956 个三项指标均有已发布估计的县或县等价区（Complete cases）。Kentucky 和 Pennsylvania 因该组 2023 指标未发布而不在分析中。
- Pearson correlation（`r`）描述线性关系；Spearman rank correlation（`ρ`）描述单调排序关系。
- 散点图中的直线是最小二乘趋势线（Least-squares trend），仅用于描述，不代表因果效应。
- “共同高值（Joint high burden）”定义为三项指标均大于或等于各自的第 75 百分位（Upper quartile）：糖尿病 12.5%，肥胖 40.6%，缺乏体育活动 30.5%。这是探索性分组，不是健康排名或临床阈值。

## 3. 相关结果（Correlation results）

| 指标对（Metric pair） | Pearson `r` | Spearman `ρ` | 完整县数 |
| --- | ---: | ---: | ---: |
| 糖尿病 × 肥胖 | 0.683 | 0.653 | 2,956 |
| 糖尿病 × 缺乏体育活动 | 0.873 | 0.863 | 2,956 |
| 肥胖 × 缺乏体育活动 | 0.746 | 0.717 | 2,956 |

三对指标均呈正相关（Positive association）。其中，糖尿病与缺乏体育活动的关联最强（Pearson `r = 0.873`）；糖尿病与肥胖的关联相对较弱，但仍然明显（`r = 0.683`）。Pearson 与 Spearman 的结果方向和强弱顺序一致，支持这些关联在整体排序中也普遍存在；但仍需通过散点分布检查局部异常值。

## 4. 共同高值重叠（Joint high-burden overlap）

共有 377 个县在三项指标上都达到或超过各自第 75 百分位，占完整样本的 12.8%。如果三项指标互不相关，按各自实际达标比例（约 25%，含并列值）相乘，三者同时达标的期望比例约为 1.6%；实际重叠远高于该参考值，与三项指标的正相关一致。

这些县应用于后续空间分析（Spatial analysis），检查是否形成地理集聚；不应把它们表述为“最不健康县排名”。

## 5. 解读边界（Interpretation limits）

- 这是县级生态关联（Ecological association），不能推断个人层面的风险，并需要避免生态谬误（Ecological fallacy）。
- 横截面关联（Cross-sectional association）不能证明肥胖或缺乏运动导致了糖尿病。
- 三项估计来自同一 PLACES 小域模型体系，共同的建模结构和未观测县级因素可能影响相关性。
- 本分析未控制年龄调整以外的混杂因素（Confounders），也未考虑空间自相关（Spatial autocorrelation）。
- 第 75 百分位只是为了识别共同高值模式，不是 CDC 定义的风险分界值。
