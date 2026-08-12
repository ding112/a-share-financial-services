# 上下文地图

## 上下文

- [A 股研究数据](./plugins/vertical-plugins/china-equity-trading/CONTEXT.md) — 定义 A 股公开数据如何进入研究数据包并支撑下游研究。
- [A 股首次覆盖](./plugins/vertical-plugins/equity-research/CONTEXT.md) — 定义单一 A 股公司的首次覆盖项目、阶段产物与研究员确认边界。

## 关系

- **A 股研究数据 → A 股研究 Agent**：A 股研究数据上下文产出带来源与降级语义的研究数据包，供 Agent 生成研究结果。
- **A 股研究数据 → A 股首次覆盖**：A 股研究数据提供带来源、时间和缺失语义的事实输入；首次覆盖将其转化为分阶段研究产物。
