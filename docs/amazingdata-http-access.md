# AmazingData 授权终端 HTTP 接入

本文记录 AmazingData 授权终端（银河「星耀数智」）HTTP 服务的接入方式、
配置、凭证边界、单会话限制与排错。AmazingData 是用户提供的授权终端
连接器，在 SKILL 契约中定位为来源等级 `licensed_terminal`（S2.5）。

> 2026-08-20 全量 sweep 后 55 工具 OK=54、ERR=0（仅 `mcp_logout` 主动跳过），
> F0-F5 各模块接口均可用，F6 与业绩/分红接口为 EMPTY 待复验。接入与状态
> 以此为准；接口逐个的实测状态见
> `docs/amazingdata-skill-function-mapping.md` 与
> `references/ad-http-interface-catalog.md`。

## 服务形态

- 协议：REST，`POST /api/{tool}`，JSON body，JSON response。
- 服务端（PC 端）持有单一登录会话，客户端无需凭证，只依赖 base URL。
- 客户端是仓库自带的 `scripts/ad_http_client.py`（纯标准库，厚客户端）。
- 接口清单、参数与字段形状见
  `plugins/vertical-plugins/china-equity-trading/skills/a-share-data-sources/references/ad-http-interface-catalog.md`。

## 配置

客户端 base URL 解析顺序：

1. `--base` 参数
2. `AD_HTTP_BASE` 环境变量
3. `AD_HTTP_HOST` + `AD_HTTP_PORT` 环境变量
4. `http://127.0.0.1:8000`（默认）

```dotenv
# 可选本地 .env（gitignored），与服务端凭证无关
AD_HTTP_BASE=http://<pc-ip>:8000
```

```bash
# 快速冒烟：health / code_list / calendar / kline / income
python scripts/ad_http_client.py --quick

# 单接口调用（各模块示例）
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_kline '{"code_list":["000001.SZ","600519.SH"],"begin_date":20240102,"end_date":20240131,"period":"day","limit":5}'
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_snapshot '{"code_list":["000001.SZ","600519.SH"]}'
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_backward_factor '{"code_list":["000001.SZ","600519.SH"]}'
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_calendar '{"market":"SH"}'
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_balance_sheet '{"code_list":["000001.SZ"],"begin_date":20230101,"end_date":20231231}'
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_index_constituent '{"index_code":"000300.SH","date":20260815}'
AD_HTTP_BASE=http://<pc-ip>:8000 python scripts/ad_http_client.py \
  --tool mcp_kzz '{}'
```

全量扫描（记录失败请求）：
```bash
# 每次失败会把 url / request_body / status / 完整 response 写入 failures.json
AD_HTTP_BASE=http://<pc-ip>:8000 AD_CAPTURE_DIR=.scratch/ad_capture \
  python -u .scratch/sweep_ad_all.py
```

## 凭证边界

- 登录凭证 `AD_USERNAME / AD_PASSWORD / AD_HOST / AD_PORT` 只存在于
  PC 端服务 `.env`，永不出现在客户端代码、HTTP 请求或响应中。
- 客户端只持有 reachable 的 base URL，不接触凭证；本仓库 `.gitignore`
  已忽略 `.env`。
- 账号并发登录会被银河侧停服；验证或批量调用期间勿在别处同时登录。

## 免责声明

- AmazingData 是用户提供的授权终端连接器，定位 `licensed_terminal`
  （S2.5），可升级行情、复权、估值、财务三表、事件风险等 S3 字段。
- 它不能替代公告原文、巨潮定期报告或交易所披露作为 `official_disclosure`。
- 资金流、龙虎榜、大宗交易只说明交易行为，不说明基本面，不得升级为业务
  暴露证据。
- `licensed_terminal` 来源与 `public_market_data` 一样，仍必须保留访问时间、
  行情时间戳、报告期或口径、复权基准日与缺失行为。

## 已知缺口与修复路径

- **状态**：2026-08-20 全量 sweep 55 工具 OK=54、ERR=0、SKIP=1（仅
  `mcp_logout` 主动跳过）。F0-F5 模块接口全部可用；无 HTTP 500，关键缺口
  `mcp_balance_sheet`（EV 计算必需）已解除。
- **待复验（EMPTY，非故障）**：业绩快报/预告（`mcp_profit_express` /
  `mcp_profit_notice`）、分红（`mcp_dividend`）、股东与股本
  （`mcp_share_holder` / `mcp_holder_num` / `mcp_equity_structure`）等返回
  空结果，需换报告期/代码复验后定是否进契约。逐个接口状态见
  `docs/amazingdata-skill-function-mapping.md`。

## 排错

| 现象 | 判定 | 处理 |
|---|---|---|
| 返回 EMPTY / count 0 | 参数、日期、代码或报告期不在覆盖范围 | 换日期范围（建议 ≤1 年）、换代码或换报告期复验。 |
| 登录失败 / 连接超时 / 未登录 | `AD_*` 四项凭证或账号状态；登录中途失效会大量报 `未登录` | 检查 PC 端 `.env` 四项、端口可达、账号未过期、无并发登录；必要时重启服务使其自动登录（`mcp_get_login_status` 查状态）。 |
| 代码无数据 | 代码未带市场后缀 | 确认格式如 `000001.SZ`、`600519.SH`。 |
| HTTP 500 Internal Server Error | 服务端问题（SDK 崩溃或参数 bug），客户端零改动 | PC 端查 `ad_mcp/http_server.py` 服务日志定位；若复现，用 `AD_CAPTURE_DIR` 的 `failures.json` 把请求/响应交给服务端。 |
