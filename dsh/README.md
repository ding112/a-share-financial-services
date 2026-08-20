# DSH 内嵌：FSI agent 全量 preset

本目录把 DeepSeek Harness（DSH）内嵌进当前仓库：把 `plugins/agent-plugins/` 下
**6 个 FSI agent** 各定义成一个 DSH agent preset（persona 内联现有 agent 系统
提示词正文、技能指向该 agent 的 bundled skills、带 bash/fs/edit 工具），用一条命令
全部装到 `~/.dsh/.agent-presets/`，然后在仓库根 `dsh --profile web` 启动，即可在
preset 选择器里选对应 agent，用 DeepSeek 模型跑研究/建模/投行材料，产物继续走仓库
既有的输出校验脚本。

> 起点是 `.scratch/dsh-mvp/spec-dsh-mvp.md` 的 MVP（1 个 preset：a-share-market-researcher），
> 本次按要求把其余 5 个 agent 补齐。范围仍为 web profile、不做服务化/HTTP API/
> 五阶段门禁/subagent。

## 目录结构

```
dsh/
├── presets/<slug>/                  # 6 个 agent preset 源
│   ├── preset.yml                   # preset 元数据（中文名 + order）
│   └── agent.cordis.yml             # agent-plane 组合模板（persona 占位符 + 工具行）
├── install-presets.sh               # 通用幂等安装：全部 / 单个
├── install-mvp.sh                   # 向后兼容包装 = install-presets.sh a-share-market-researcher
├── persona.py                       # persona 提取/渲染（install 与测试共用，单一事实源）
├── tests/
│   ├── test_install_presets.py      # 6 个 preset 的安装有效性测试（Seam 2，可进 CI）
│   └── test_install_mvp.py          # 钉住 a-share 包装契约的既有测试
└── README.md
```

## 前置条件

- Node.js + 全局安装 DSH：`npm install -g @deepseek-ai/dsh`（>= 0.1.0-rc.6）
- DeepSeek API 凭据：`export DEEPSEEK_API_KEY=sk-...`，或已有 `~/.dsh/.credentials.yaml`
- （跑研究时）`.venv`：`python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`

## 安装

```bash
cd <本仓库根>
bash dsh/install-presets.sh              # 安装全部 6 个
bash dsh/install-presets.sh a-share-screener   # 只装某一个
```

脚本幂等，可随时重跑。它会：校验凭据与仓库位置 → 把 `dsh/presets/<slug>/` 拷到
`~/.dsh/.agent-presets/<slug>/` → 用 `dsh/persona.py` 把
`plugins/agent-plugins/<slug>/agents/<slug>.md` 去掉 frontmatter 后的正文注入
`agent.cordis.yml` 的 `__PERSONA_TEXT__` 占位符。persona 只有一处源，不会与
agents/*.md 漂移。

> `dsh/install-mvp.sh` 保留为向后兼容包装，等价于 `bash dsh/install-presets.sh
> a-share-market-researcher`；新代码请直接用 `install-presets.sh`。

## 运行（Seam 1，发版前人工验收）

```bash
cd <本仓库根>          # 必须！customSkillDirs 用 process.cwd() 解析，相对路径都依赖它
dsh --profile web
```

preset 选择器应列出 6 个 FSI agent：

| preset 显示名 | agent | 技能数 |
|---|---|---|
| A股行业研究 | a-share-market-researcher | 6 |
| A股短线筛股 | a-share-screener | 5 |
| 财报评审 | earnings-reviewer | 6 |
| 行业研究 | market-researcher | 5 |
| 金融模型构建 | model-builder | 6 |
| 投行 Pitch | pitch-agent | 11 |

选中「A股行业研究」后贴验收 prompt（沿用 MVP，用 fixture 数据包跑通端到端）：

```text
用 ./fixtures/a-share-research-packs/robotics-reducer/ 作为输入数据包。
生成 A股机器人产业链-减速器 主题的中文研究 note，保存到
./out/A股机器人产业链-减速器/note/。先列出数据包覆盖、缺失字段、异常值和
待验证证据，再生成 note。不要联网抓数，只用 fixture 数据包。
```

跑完后校验产物（退出码 0 即通过）：

```bash
python3 scripts/validate_a_share_output_layout.py --theme "A股机器人产业链-减速器" --require-note
```

## 测试（Seam 2，CI 自动化门槛）

不需要 API key、模型调用或 web UI；用隔离的临时 `$HOME` 跑安装并断言产物契约：

```bash
python3 dsh/tests/test_install_presets.py   # 6 个 preset
python3 dsh/tests/test_install_mvp.py       # a-share 包装契约（既有测试）
```

6-agent 测试对每个 preset 断言：

1. `agent.cordis.yml` 存在且 YAML 可解析（`!!js` 表达式剥除后校验结构）；
2. persona 非空且与 `agents/<slug>.md` 去 frontmatter 后的正文逐字节一致；
3. `customSkillDirs` 指向 `plugins/agent-plugins/<slug>/skills`，且该目录 `SKILL.md`
   集合 == 预期（6/5/6/5/6/11）；
4. 15 个预期行齐全、delegation 组不出现；`preset.yml` 元数据正确；
5. 重复安装字节不变（幂等）；缺凭据时报错退出且不改动已装内容。

## 设计要点与取舍

- **web profile 而非 headless**：headless 不走 preset（写死 coding persona），
  必须用 web profile 才能让 preset 生效。
- **模型路由**：不额外配置，沿用 DSH 出厂默认 `deepseek-official / deepseek-v4-flash`。
- **只挂各自 agent 的技能**：每个 preset `includeDefaultRoots: false` + 单条
  `customSkillDirs`，避免捡到无关的项目/用户技能，也避免跨 preset 的 skill 目录冲突。
- **不装 delegation 组**：不做 subagent/workflow/ralph。
- **cwd 约束**：DSH 的 `sandbox-policy.workspaceRoot = process.cwd()`，必须在仓库根
  启动 `dsh --profile web`；agent 提示词里的 `./out/`、`scripts/`、`fixtures/`
  相对路径才解析得开。
- **确定性校验**：`persona.py` 是 persona 提取/渲染的单一事实源，install 与两个测试
  共用；`scripts/check.py` 的 `check_dsh_presets()` 守卫保证新增 agent 必须有对应
  preset、占位符与技能根不漂移。

## 校验（提交前）

```bash
python3 scripts/check.py     # 含 dsh preset 守卫；整体偏重，可能需要较久
```

## 后置（不在当前范围）

服务化/HTTP API、五阶段门禁、commands 桥、MCP 接入、subagent 映射、全量 vertical
skill frontmatter 清理、独立应用仓库——见 spec Out of Scope。
