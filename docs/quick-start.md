# Quick Start（本地使用）

## 1) 安装本地 marketplace

```bash
claude plugin marketplace add /Users/ding/workspace/mengzai/financial-services
```

## 2) 安装插件

```bash
claude plugin install a-share-screener@claude-for-financial-services
claude plugin install a-share-market-researcher@claude-for-financial-services
```

## 3) 使用命令

短线筛选（`a-share-screener`）：

```text
a-share-screener:a-share-screener(
  基于“机器人+减速器”生成A股短线研究清单，并保存到 ./out/机器人减速器短线研究清单.md
)
```

行业/主题研究（`a-share-market-researcher`）：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。生成结果保存到 ./out/机器人产业链行业研究.md
)
```

## 4) 成功标志

看到类似 `Backgrounded agent` 或 agent 开始返回结果，即表示调用成功。

## 5) 来源契约 smoke test

在本地调用 `a-share-market-researcher` 时，使用一个有明确来源要求的 prompt
检查来源契约是否生效：

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  要求：先列出本次研究用到的来源类型、来源名称、数据时间、报告期或口径、
  验证状态和缺失行为；如果只有概念标签或新闻线索，放入待验证名单，不要进入
  核心 idea shortlist。生成结果保存到 ./out/机器人产业链来源契约测试.md
)
```

成功标志：

- 输出包含 `来源类型`、`来源名称`、`数据时间`、`报告期或口径`、
  `验证状态` 和 `缺失行为`。
- 核心 idea 不使用单独的概念标签作为入选依据。
- 缺失行情、估值或业务暴露证据时，输出写 `来源缺失` 或 `待验证`。

## 6) 数据包契约 smoke test

如果你已经准备了本地研究数据包，可以让 `a-share-market-researcher` 先解析
数据包，再开始写行业研究。推荐目录名是 `research-pack/`，必需文件是
`source_manifest.json` 和 `peer_universe.csv`。

```text
a-share-market-researcher:a-share-market-researcher(
  Primer: A股机器人产业链, angle: 减速器供给缺口。
  使用 ./research-pack/机器人产业链/ 作为输入数据包。
  先解析 source_manifest.json 和 peer_universe.csv；如果存在
  market_snapshot.csv、financial_summary.csv、company_exposure.md 或
  events_and_risks.md，也一并读取。请先列出数据包字段来源、数据时间、
  报告期或口径、验证状态和缺失行为，再生成结果到
  ./out/机器人产业链行业研究.md
)
```

成功标志：

- 输出先说明 `source_manifest.json` 和 `peer_universe.csv` 是否存在。
- 缺少可选文件时，对应字段写 `来源缺失`、`待验证` 或 `口径不可比`。
- 没有 `snapshot_time` 的行情或估值字段不用于排序。
