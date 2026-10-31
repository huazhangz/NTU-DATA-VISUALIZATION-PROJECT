# 基础探索性数据分析（Basic EDA）报告

生成时间（Generated）：2026-10-31T22:34:47+08:00

## 1. 分析范围（Scope）

本轮正式探索性数据分析（Exploratory Data Analysis, EDA）使用已通过验收的清洗数据表，聚焦三个 2023 年县级年龄调整患病率估计（Age-adjusted prevalence estimates）：诊断糖尿病（Diagnosed diabetes）、肥胖（Obesity）和无休闲时间体育活动（No leisure-time physical activity）。

本阶段包括数据覆盖情况（Coverage）、单变量分布（Univariate distributions）、分位数（Quantiles）、州内县级中位数（State-level county medians）和尾部数值诊断。本报告尚未检验指标之间的关联（Association），也不作因果推断（Causal inference）。

## 2. 数据覆盖情况（Coverage）

每个指标均有 2,956 个已发布的县级估计，并有 187 行缺失，缺失率为 5.95%。所有缺失行均来自 Kentucky（KY）、Pennsylvania（PA）。这些空白值代表未发布（Unpublished），本分析保留其缺失状态，未将其替换为 0，也未进行插补（Imputation）。

## 3. 分布摘要（Distribution summary）

| 指标（Measure） | 均值（Mean） | 中位数（Median） | 四分位距（IQR） | 第 10–90 百分位 | 最小–最大值 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 诊断糖尿病（Diagnosed diabetes） | 11.17% | 10.70% | 9.50–12.50% | 8.70–14.20% | 6.00–23.80% |
| 肥胖（Obesity） | 37.63% | 38.20% | 35.10–40.60% | 31.40–43.00% | 17.10–54.00% |
| 无休闲时间体育活动（No leisure-time physical activity） | 27.02% | 26.50% | 23.40–30.50% | 20.50–34.30% | 12.20–48.90% |

## 4. 初步发现（Initial observations）

1. 在三个指标中，肥胖（Obesity）的典型县级估计最高：其中位数（Median）为 38.2%；无休闲时间体育活动为 26.5%；诊断糖尿病为 10.7%。三者衡量的是不同现象，因此不应把数值大小解读为统一的“严重程度”尺度。
2. 三个指标均呈现明显的县际差异（County-level variation）。中间 80% 的县分别落在：糖尿病 8.7%–14.2%，肥胖 31.4%–43.0%，缺乏体育活动 20.5%–34.3%。
3. 三个指标的均值（Mean）与中位数（Median）较为接近，但完整值域明显宽于中央分布。尾部县（Tail counties）已保留用于诊断检查，未被自动删除或当作异常数据。
4. 不同州的县级中位数存在差异，说明后续空间分析（Spatial analysis）具有必要性。但这些数值是各州内县级估计的等权中位数，不是人口加权的州级患病率（Population-weighted state prevalence）。

## 5. 解读边界（Interpretation limits）

- 本数据为模型生成的县级估计（Model-based county estimates），不是对每个县的直接调查测量。
- 空白值表示未发布（Unpublished），不表示 0。
- 本阶段的全国汇总对每个县等权处理（Equal county weight），未按人口加权。
- 尾部数值表用于诊断检查（Diagnostic review），不是县级健康排名（Health ranking）。
- 指标关联（Association）和空间分析将在后续阶段分开完成；本报告不作因果推断（Causal claim）。
