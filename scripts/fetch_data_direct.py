#!/usr/bin/env python3
"""直接通过东方财富 API 获取A股实时行情数据"""

import requests
import json
from datetime import datetime

STOCK_LIST = [
    ("688017", "绿的谐波"),
    ("002472", "双环传动"),
    ("002527", "新时达"),
    ("300124", "汇川技术"),
    ("300024", "机器人"),
    ("002896", "中大力德"),
    ("002031", "巨轮智能"),
]

def get_eastmoney_realtime(code):
    """通过东方财富 API 获取实时行情"""
    # 判断市场前缀
    if code.startswith('6'):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"

    url = f"https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170",
        "invt": 2,
        "fltt": 2,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get('data'):
            d = data['data']
            # 东方财富 API 返回的字段已经是实际值，不需要除以100
            return {
                'price': d.get('f43', '-') if d.get('f43') else '-',
                'change_pct': d.get('f170', '-') if d.get('f170') else '-',
                'volume_ratio': d.get('f50', '-') if d.get('f50') else '-',
                'amount': d.get('f47', 0),  # 成交量
                'turnover': d.get('f168', '-') if d.get('f168') else '-',  # 换手率
                'high': d.get('f44', '-') if d.get('f44') else '-',
                'low': d.get('f45', '-') if d.get('f45') else '-',
                'open': d.get('f46', '-') if d.get('f46') else '-',
                'prev_close': d.get('f60', '-') if d.get('f60') else '-',
                'pe': d.get('f167', '-') if d.get('f167') else '-',
                'market_cap': d.get('f116', 0),
                'circulating_cap': d.get('f117', 0),
            }
    except Exception as e:
        print(f"获取 {code} 实时行情失败: {e}")
    return None

def get_eastmoney_kline(code, days=30):
    """通过东方财富 API 获取历史 K 线"""
    if code.startswith('6'):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"

    url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": 101,  # 日线
        "fqt": 1,  # 前复权
        "end": "20500101",
        "lmt": days,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get('data') and data['data'].get('klines'):
            klines = []
            for line in data['data']['klines']:
                parts = line.split(',')
                klines.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5]),
                    'amount': float(parts[6]),
                    'turnover': float(parts[10]) if len(parts) > 10 else 0,
                })
            return klines
    except Exception as e:
        print(f"获取 {code} K线失败: {e}")
    return None

def calculate_metrics(klines, current_price):
    """计算量化指标"""
    if not klines or len(klines) < 5:
        return None

    closes = [k['close'] for k in klines]
    amounts = [k['amount'] for k in klines]
    turnovers = [k['turnover'] for k in klines]

    # 近5日日均成交额（亿）
    avg_amount_5d = sum(amounts[-5:]) / 5 / 1e8

    # 近5日平均换手率
    avg_turnover_5d = sum(turnovers[-5:]) / 5

    # 均线
    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None

    # 近5日涨幅
    if len(closes) >= 6:
        gain_5d = (current_price - closes[-6]) / closes[-6] * 100
    else:
        gain_5d = None

    # 近20日最大单日跌幅及成交额放大倍数
    recent_20 = klines[-20:] if len(klines) >= 20 else klines
    max_drop = 0
    max_drop_amount_ratio = None
    avg_amount_20d = sum(k['amount'] for k in recent_20) / len(recent_20)

    for k in recent_20:
        if k['open'] > 0:
            drop = (k['close'] - k['open']) / k['open'] * 100
            if drop < max_drop:
                max_drop = drop
                if avg_amount_20d > 0:
                    max_drop_amount_ratio = k['amount'] / avg_amount_20d

    return {
        'avg_amount_5d': round(avg_amount_5d, 2),
        'avg_turnover_5d': round(avg_turnover_5d, 2),
        'ma5': round(ma5, 2) if ma5 else None,
        'ma10': round(ma10, 2) if ma10 else None,
        'ma20': round(ma20, 2) if ma20 else None,
        'gain_5d': round(gain_5d, 2) if gain_5d else None,
        'max_drop_20d': round(max_drop, 2),
        'drop_amount_ratio': round(max_drop_amount_ratio, 2) if max_drop_amount_ratio else None,
    }

def main():
    results = []

    for code, name in STOCK_LIST:
        print(f"获取 {code} {name} 数据...")

        # 获取实时行情
        realtime = get_eastmoney_realtime(code)
        if not realtime:
            results.append({'code': code, 'name': name, 'error': '无法获取实时行情'})
            continue

        # 获取历史 K 线
        klines = get_eastmoney_kline(code, days=30)
        if not klines:
            results.append({'code': code, 'name': name, 'error': '无法获取历史K线'})
            continue

        # 计算指标
        metrics = calculate_metrics(klines, realtime['price'])
        if not metrics:
            results.append({'code': code, 'name': name, 'error': '数据不足无法计算'})
            continue

        results.append({
            'code': code,
            'name': name,
            'price': realtime['price'],
            'change_pct': realtime['change_pct'],
            'volume_ratio': realtime['volume_ratio'],
            **metrics
        })

    # 生成 Markdown 报告
    md = f"""# "机器人+减速器"主题 A 股实时行情数据

**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**：东方财富

---

## 量化筛选数据

| 序号 | 代码 | 简称 | 当前价 | 涨跌幅 | 5日均成交额(亿) | 5日均换手率 | 量比 | MA5 | MA10 | MA20 | 5日涨幅 | 20日最大跌幅 | 跌幅日成交额倍数 |
|------|------|------|--------|--------|----------------|------------|------|-----|------|------|---------|-------------|----------------|
"""

    for i, r in enumerate(results, 1):
        if 'error' in r:
            md += f"| {i} | {r['code']} | {r['name']} | 获取失败 | - | - | - | - | - | - | - | - | - | - |\n"
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
            md += f"- **{r['name']}**：{r['error']}\n"
            continue

        issues = []
        passed = True

        # 流动性检查
        if r['avg_amount_5d'] < 0.5:
            issues.append("流动性不足（5日均成交额<0.5亿）")
            passed = False
        if r['avg_turnover_5d'] < 1:
            issues.append("换手率偏低（<1%）")
            passed = False

        # 强度检查
        if r['gain_5d'] is not None and r['gain_5d'] < 0:
            issues.append("近5日下跌")
            passed = False

        # 均线检查
        if r['ma5'] and r['ma10'] and r['ma20']:
            if r['ma5'] < r['ma10'] or r['ma10'] < r['ma20']:
                issues.append("均线空头排列")
                passed = False

        # 排除放量大阴线
        if r['max_drop_20d'] < -5 and r['drop_amount_ratio'] and r['drop_amount_ratio'] > 2:
            issues.append("20日内存在放量大阴线")
            passed = False

        if passed:
            md += f"- **{r['name']}**（{r['code']}）：通过初筛 ✓\n"
        else:
            md += f"- **{r['name']}**（{r['code']}）：{'；'.join(issues)}\n"

    md += """
---

**免责声明**：本数据仅供参考，不构成投资建议。数据来源于东方财富，可能存在延迟。
"""

    return md

if __name__ == "__main__":
    report = main()
    print(report)

    # 保存到文件
    with open("./out/realtime-data-机器人减速器.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n报告已保存到 ./out/realtime-data-机器人减速器.md")
