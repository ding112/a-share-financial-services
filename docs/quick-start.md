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
