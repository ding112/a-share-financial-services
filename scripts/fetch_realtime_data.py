#!/usr/bin/env python3
"""获取A股实时行情数据用于量化筛选"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

STOCK_LIST = [
    ("688017", "绿的谐波"),
    ("002472", "双环传动"),
    ("002527", "新时达"),
    ("300124", "汇川技术"),
    ("300024", "机器人"),
    ("002896", "中大力德"),
    ("002031", "巨轮智能"),
]

def get_stock_realtime_data(code, name):
    """获取单只股票的实时行情和历史数据"""
    try:
        # 获取实时行情
        realtime = ak.stock_zh_a_spot_em()
        stock_data = realtime[realtime['代码'] == code]

        if stock_data.empty:
            return None

        current_price = stock_data['最新价'].values[0]
        change_pct = stock_data['涨跌幅'].values[0]
        volume_ratio = stock_data['量比'].values[0] if '量比' in stock_data.columns else None

        # 获取历史行情用于计算均线和成交额
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')

        hist = ak.stock_zh_a_hist(symbol=code, period="daily",
                                  start_date=start_date, end_date=end_date, adjust="qfq")

        if hist.empty:
            return {
                'code': code, 'name': name,
                'price': current_price, 'change_pct': change_pct,
                'volume_ratio': volume_ratio,
                'error': '无法获取历史数据'
            }

        # 计算近5日日均成交额
        hist['成交额'] = hist['成交额'].astype(float)
        avg_amount_5d = hist['成交额'].tail(5).mean() / 1e8  # 转换为亿

        # 计算近5日平均换手率
        avg_turnover_5d = hist['换手率'].tail(5).mean()

        # 计算均线
        hist['收盘'] = hist['收盘'].astype(float)
        ma5 = hist['收盘'].tail(5).mean()
        ma10 = hist['收盘'].tail(10).mean()
        ma20 = hist['收盘'].tail(20).mean()

        # 计算近5日涨幅
        if len(hist) >= 5:
            price_5d_ago = hist['收盘'].iloc[-6] if len(hist) > 5 else hist['收盘'].iloc[0]
            gain_5d = (current_price - price_5d_ago) / price_5d_ago * 100
        else:
            gain_5d = None

        # 近20日最大单日跌幅及当日成交额放大倍数
        recent_20 = hist.tail(20)
        recent_20['涨跌幅'] = recent_20['涨跌幅'].astype(float)
        max_drop_idx = recent_20['涨跌幅'].idxmin()
        max_drop = recent_20.loc[max_drop_idx, '涨跌幅']
        max_drop_amount = recent_20.loc[max_drop_idx, '成交额']
        avg_amount_20d = recent_20['成交额'].mean()
        amount_ratio = max_drop_amount / avg_amount_20d if avg_amount_20d > 0 else None

        return {
            'code': code,
            'name': name,
            'price': current_price,
            'change_pct': change_pct,
            'avg_amount_5d': round(avg_amount_5d, 2),
            'avg_turnover_5d': round(avg_turnover_5d, 2),
            'volume_ratio': volume_ratio,
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'gain_5d': round(gain_5d, 2) if gain_5d else None,
            'max_drop_20d': round(max_drop, 2),
            'drop_amount_ratio': round(amount_ratio, 2) if amount_ratio else None,
        }

    except Exception as e:
        return {'code': code, 'name': name, 'error': str(e)}

def main():
    results = []
    for code, name in STOCK_LIST:
        print(f"获取 {code} {name} 数据...")
        data = get_stock_realtime_data(code, name)
        if data:
            results.append(data)

    # 生成 Markdown 报告
    md = f"""# "机器人+减速器"主题 A 股实时行情数据

**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 量化筛选数据

| 序号 | 代码 | 简称 | 当前价 | 涨跌幅 | 5日均成交额(亿) | 5日均换手率 | 量比 | MA5 | MA10 | MA20 | 5日涨幅 | 20日最大跌幅 | 跌幅日成交额倍数 |
|------|------|------|--------|--------|----------------|------------|------|-----|------|------|---------|-------------|----------------|
"""

    for i, r in enumerate(results, 1):
        if 'error' in r:
            md += f"| {i} | {r['code']} | {r['name']} | - | - | - | - | - | - | - | - | - | - | - |\n"
        else:
            md += f"| {i} | {r['code']} | {r['name']} | {r['price']} | {r['change_pct']}% | {r['avg_amount_5d']} | {r['avg_turnover_5d']}% | {r['volume_ratio']} | {r['ma5']} | {r['ma10']} | {r['ma20']} | {r['gain_5d']}% | {r['max_drop_20d']}% | {r['drop_amount_ratio']} |\n"

    md += """
---

## 量化筛选规则判定

根据以下规则对候选股票进行初步筛选：

1. **流动性门槛**：近 5 日日均成交额 >= 5000 万元（0.5亿）；近 5 日平均换手率 >= 1%
2. **强度筛选**：近 5 日涨幅 >= 0%（正收益优先）
3. **量价状态**：5 日均线 >= 10 日均线 >= 20 日均线（多头排列优先）
4. **排除项**：近 20 日内出现放量大阴线（单日跌幅 > 5%，成交额放大 2 倍以上）

### 初筛结果

"""

    for r in results:
        if 'error' in r:
            md += f"- **{r['name']}**：数据获取失败，需人工核实\n"
            continue

        issues = []
        if r['avg_amount_5d'] < 0.5:
            issues.append("流动性不足（5日均成交额<0.5亿）")
        if r['avg_turnover_5d'] < 1:
            issues.append("换手率偏低（<1%）")
        if r['gain_5d'] is not None and r['gain_5d'] < 0:
            issues.append("近5日下跌")
        if r['ma5'] < r['ma10'] or r['ma10'] < r['ma20']:
            issues.append("均线空头排列")
        if r['max_drop_20d'] < -5 and r['drop_amount_ratio'] and r['drop_amount_ratio'] > 2:
            issues.append("20日内存在放量大阴线")

        if issues:
            md += f"- **{r['name']}**（{r['code']}）：{'；'.join(issues)}\n"
        else:
            md += f"- **{r['name']}**（{r['code']}）：通过初筛 ✓\n"

    md += """
---

**数据来源**：AKShare（东方财富）
**免责声明**：本数据仅供参考，不构成投资建议。
"""

    return md

if __name__ == "__main__":
    report = main()
    print(report)

    # 保存到文件
    with open("./out/realtime-data-机器人减速器.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n报告已保存到 ./out/realtime-data-机器人减速器.md")
