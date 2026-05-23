# 腾讯股票行情 API 参考文档

> 非官方接口，无官方文档，通过社区逆向工程发现。字段可能随时变更。

---

## 1. 实时行情 API

### 接口地址

```
https://qt.gtimg.cn/q={symbol}
```

### 参数说明

| 参数 | 格式 | 示例 | 说明 |
|------|------|------|------|
| `symbol` | `{exchange}{code}` | `sz300308` | exchange: `sh`=上海, `sz`=深圳 |

### 股票代码映射

```python
def tencent_symbol(code: str) -> str:
    """将 300308.SZ 格式转换为 sz300308 格式"""
    symbol, exchange = code.split(".", 1)
    prefix = "sh" if exchange == "SH" else "sz"
    return f"{prefix}{symbol}"
```

### 请求示例

```bash
# A股
curl "https://qt.gtimg.cn/q=sz300308"    # 中际旭创
curl "https://qt.gtimg.cn/q=sh600519"    # 贵州茅台

# 港股
curl "https://qt.gtimg.cn/q=hk00700"     # 腾讯

# 美股
curl "https://qt.gtimg.cn/q=usAAPL"      # 苹果
```

### 返回格式

GBK 编码，格式：`v_{symbol}="{fields}";`

字段以 `~` 分隔，共 88 个字段。

### 字段映射表

| 索引 | 字段名 | 示例值 | 说明 |
|------|--------|--------|------|
| 0 | market | 51 | 市场代码 |
| 1 | name | 中际旭创 | 股票名称 |
| 2 | code | 300308 | 股票代码 |
| 3 | **price** | 1037.98 | 最新价 |
| 4 | prev_close | 993.34 | 昨收价 |
| 5 | open | 1010.04 | 今开价 |
| 6 | volume | 209338 | 成交量（手） |
| 7 | buy_volume | 114398 | 外盘（主动买入量） |
| 8 | sell_volume | 94940 | 内盘（主动卖出量） |
| 9-28 | bid/ask | - | 买卖五档（价格+数量） |
| 29 | - | - | 保留字段 |
| 30 | **timestamp** | 20260522161406 | 行情时间（yyyyMMddHHmmss） |
| 31 | change | 44.64 | 涨跌额 |
| 32 | **pct_change** | 4.49 | 涨跌幅（%） |
| 33 | high | 1044.87 | 最高价 |
| 34 | low | 1006.18 | 最低价 |
| 35 | **trade_triplet** | 1037.98/209338/21509318912 | 最新价/成交量/成交额 |
| 36 | volume_hand | 209338 | 成交量（手） |
| 37 | **amount** | 2150932 | 成交额（万元） |
| 38 | **turnover_rate** | 1.89 | 换手率（%） |
| 39 | pe_dynamic | 77.32 | 动态市盈率 |
| 40 | - | - | 保留字段 |
| 41 | high_52w | 1044.87 | 52周最高价 |
| 42 | low_52w | 1006.18 | 52周最低价 |
| 43 | **amplitude** | 3.89 | 振幅（%） |
| 44 | **float_market_cap** | 11503.99 | 流通市值（亿元） |
| 45 | **market_cap** | 11558.95 | 总市值（亿元） |
| 46 | **pb** | 33.44 | 市净率 |
| 47 | high_limit | 1192.01 | 涨停价 |
| 48 | low_limit | 794.67 | 跌停价 |
| 49 | **volume_ratio** | 0.83 | 量比 |
| 50 | commission_ratio | 381 | 委比 |
| 51 | avg_price | 1027.49 | 均价 |
| 52 | **pe_ttm** | 50.39 | 滚动市盈率（TTM） |
| 53 | pe_static | 107.05 | 静态市盈率 |
| 54-55 | - | - | 保留字段 |
| 56 | turnover_ratio | 1.97 | 成交量/流通股本 |
| 57 | amount_wan | 2150931.8912 | 成交额（万元，精确） |
| 58 | float_shares | 166.0768 | 流通股本（亿股） |
| 59 | total_shares | 16 | 总股本（亿股） |
| 60 | stock_type |  A | 股票类型 |
| 61 | board | GP-A-CYB | 板块标识 |
| 62 | pb_ratio | 70.44 | 市净率（另一口径） |
| 63 | change_pct_5d | -1.13 | 5日涨跌幅（%） |
| 64 | change_pct_20d | 0.13 | 20日涨跌幅（%） |
| 65 | change_pct_60d | 42.01 | 60日涨跌幅（%） |
| 66 | change_pct_ytd | 28.64 | 年初至今涨跌幅（%） |
| 67 | change_pct_120d | 1099.87 | 120日涨跌幅（%） |
| 68-76 | - | - | 其他字段（待解析） |
| 77-87 | - | - | 保留字段 |

### 常用字段速查

```python
# 价格相关
price = fields[3]           # 最新价
prev_close = fields[4]      # 昨收价
open = fields[5]            # 今开价
high = fields[33]           # 最高价
low = fields[34]            # 最低价

# 成交相关
volume = fields[6]          # 成交量（手）
amount = fields[37]         # 成交额（万元）
turnover_rate = fields[38]  # 换手率（%）
volume_ratio = fields[49]   # 量比
amplitude = fields[43]      # 振幅（%）

# 估值相关
pe_ttm = fields[52]         # 滚动市盈率
pe_dynamic = fields[39]     # 动态市盈率
pb = fields[46]             # 市净率

# 市值相关
market_cap = fields[45]     # 总市值（亿元）
float_market_cap = fields[44]  # 流通市值（亿元）

# 涨跌幅
pct_change = fields[32]     # 当日涨跌幅（%）
change_pct_5d = fields[63]  # 5日涨跌幅（%）
change_pct_20d = fields[64] # 20日涨跌幅（%）
change_pct_60d = fields[65] # 60日涨跌幅（%）

# 时间
timestamp = fields[30]      # 行情时间（yyyyMMddHHmmss）
```

### 代码示例

```python
import requests

def fetch_tencent_quote(symbol: str) -> dict:
    """获取腾讯实时行情"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers, timeout=10)
    response.encoding = "gbk"
    
    # 解析返回数据
    quote = response.text.split('"', 2)[1]
    fields = quote.split("~")
    
    return {
        "name": fields[1],
        "price": float(fields[3]),
        "pct_change": float(fields[32]),
        "volume_ratio": float(fields[49]),
        "amplitude": float(fields[43]),
        "pe_ttm": float(fields[52]),
        "pb": float(fields[46]),
        "market_cap": float(fields[45]),  # 亿元
        "timestamp": fields[30],
    }

# 使用示例
quote = fetch_tencent_quote("sz300308")
print(f"{quote['name']}: {quote['price']} ({quote['pct_change']}%)")
```

---

## 2. 历史 K 线 API

### 接口地址

```
https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
```

### 参数说明

| 参数 | 格式 | 示例 | 说明 |
|------|------|------|------|
| `param` | `{symbol},{period},{start},{end},{count},{adjust}` | `sz300308,day,,,60,qfq` | 逗号分隔参数 |

### 参数详解

| 参数 | 可选值 | 说明 |
|------|--------|------|
| `symbol` | `sz300308`, `sh600519` | 股票代码 |
| `period` | `day`, `week`, `month` | K线周期 |
| `start` | `2026-01-01` | 开始日期（可空） |
| `end` | `2026-05-23` | 结束日期（可空） |
| `count` | `60`, `120` | 返回条数 |
| `adjust` | `qfq`, `hfq`, `` | 复权类型：前复权/后复权/不复权 |

### 请求示例

```bash
# 获取前复权日K线（最近60天）
curl "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz300308,day,,,60,qfq"

# 获取指定日期范围
curl "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz300308,day,2026-01-01,2026-05-23,,qfq"
```

### 返回格式

JSON 格式，UTF-8 编码。

```json
{
  "code": 0,
  "msg": "",
  "data": {
    "sz300308": {
      "qfqday": [
        ["2026-05-22", "1010.040", "1037.980", "1044.870", "1006.180", "209338.000"]
      ],
      "prec": "1049.870"
    }
  }
}
```

### K线字段说明

`qfqday` 数组中每个元素：

| 索引 | 字段 | 说明 |
|------|------|------|
| 0 | date | 日期（yyyy-MM-dd） |
| 1 | open | 开盘价 |
| 2 | close | 收盘价 |
| 3 | high | 最高价 |
| 4 | low | 最低价 |
| 5 | volume | 成交量（手） |

### 代码示例

```python
import requests

def fetch_kline(symbol: str, count: int = 60) -> list[dict]:
    """获取历史K线数据"""
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{symbol},day,,,{count},qfq"}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers, params=params, timeout=10)
    data = response.json()
    
    kline = data["data"][symbol]["qfqday"]
    return [
        {
            "date": item[0],
            "open": float(item[1]),
            "close": float(item[2]),
            "high": float(item[3]),
            "low": float(item[4]),
            "volume": float(item[5]),
        }
        for item in kline
    ]

def calculate_returns(kline: list[dict]) -> dict:
    """计算涨跌幅"""
    if len(kline) < 60:
        return {}
    
    latest = kline[-1]["close"]
    return {
        "5d": (latest - kline[-5]["close"]) / kline[-5]["close"] * 100,
        "20d": (latest - kline[-20]["close"]) / kline[-20]["close"] * 100,
        "60d": (latest - kline[-60]["close"]) / kline[-60]["close"] * 100,
    }

# 使用示例
kline = fetch_kline("sz300308", 60)
returns = calculate_returns(kline)
print(f"5日涨幅: {returns['5d']:.2f}%")
```

---

## 3. 使用注意事项

### 请求限制

- 无官方文档，具体限制未知
- 建议请求间隔 ≥ 100ms
- 避免短时间内大量请求

### 编码问题

- 实时行情 API 返回 GBK 编码
- K 线 API 返回 UTF-8 编码

### 错误处理

```python
try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"请求失败: {e}")
```

### 数据验证

```python
# 验证返回数据格式
if len(fields) < 58:
    raise ValueError(f"字段数量不足: {len(fields)}")

# 验证数值字段
try:
    price = float(fields[3])
except ValueError:
    price = None  # 停牌或其他异常
```

---

## 4. 与其他数据源对比

| 数据源 | 实时行情 | 历史K线 | 免费额度 | 稳定性 |
|--------|---------|---------|---------|--------|
| **腾讯 API** | ✓ | ✓ | 无限制 | 中（非官方） |
| AKShare | ✓ | ✓ | 无限制 | 中（依赖底层接口） |
| Tushare Pro | ✓ | ✓ | 有限制 | 高（有官方支持） |
| 东方财富 Choice | ✓ | ✓ | 付费 | 高 |
| Wind | ✓ | ✓ | 付费 | 最高 |

---

## 5. 相关资源

- [腾讯财经](https://finance.qq.com) — 数据来源网站
- [AKShare 文档](https://akshare.akfamily.xyz/) — 封装了腾讯 API
- [Tushare 文档](https://tushare.pro/document/1) — 另一个数据接口

---

> **免责声明：** 本文档基于社区逆向工程整理，非官方文档。接口可能随时变更或关闭，请谨慎使用。
