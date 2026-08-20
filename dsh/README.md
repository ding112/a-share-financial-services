# DSH 内嵌 MVP：A股行业研究 preset

本目录把 DeepSeek Harness（DSH）内嵌进当前仓库：定义 `a-share-market-researcher`
的 DSH agent preset（persona 内联现有 agent 系统提示词正文、技能指向现有
vertical skills、带 bash/fs/edit 工具），用一条命令装到 `~/.dsh/.agent-presets/`，
然后在仓库根 `dsh --profile web` 启动，选中「A股行业研究」即可用 DeepSeek 模型
跑 A 股行业研究，产物继续走仓库既有的输出校验脚本。

> 依据 `.scratch/dsh-mvp/spec-dsh-mvp.md` 实现（MVP 范围：1 个 preset、web
> profile、不做服务化/HTTP API/五阶段门禁/subagent）。

## 目录结构

```
dsh/
├── presets/a-share-market-researcher/
│   ├── preset.yml          # preset 元数据（name=A股行业研究, order=10）
│   └── agent.cordis.yml    # agent-plane 组合模板（persona 占位符 + 工具行）
├── install-mvp.sh          # 幂等安装：拷贝 preset 源 + 注入 persona
├── persona.py              # persona 提取/渲染（install 与测试共用，单一事实源）
├── tests/test_install_mvp.py  # Seam 2：安装有效性测试（可进 CI）
└── README.md
```

## 前置条件

- Node.js + 全局安装 DSH：`npm install -g @deepseek-ai/dsh`（>= 0.1.0-rc.6）
- DeepSeek API 凭据：`export DEEPSEEK_API_KEY=sk-...`，或已有 `~/.dsh/.credentials.yaml`
- （跑研究时）`.venv`：`python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`

  > 注意：API 凭据是安装的硬性前置（缺失直接报错退出）；`.venv` 只是提示——
  > 安装本身不需要它，只有端到端跑研究（Seam 1）才需要。

## 安装

```bash
cd <本仓库根>
bash dsh/install-mvp.sh
```

脚本幂等，可随时重跑。它会：校验凭据与仓库位置 → 把 `dsh/presets/` 拷到
`~/.dsh/.agent-presets/a-share-market-researcher/` → 用 `dsh/persona.py` 把
`plugins/agent-plugins/a-share-market-researcher/agents/a-share-market-researcher.md`
去掉 frontmatter 后的正文注入 `agent.cordis.yml` 的 `__PERSONA_TEXT__` 占位符。
persona 只有一处源，不会与 agents/*.md 漂移。

## 运行（Seam 1，发版前人工验收）

```bash
cd <本仓库根>          # 必须！customSkillDirs 用 process.cwd() 解析，相对路径都依赖它
dsh --profile web
```

在会话里选「A股行业研究」preset，然后贴验收 prompt：

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

不需要 API key、模型调用或 web UI；用隔离的临时 $HOME 跑安装并断言产物契约：

```bash
.venv/bin/python dsh/tests/test_install_mvp.py
```

断言内容（对应 spec Testing Decisions）：

1. `agent.cordis.yml` 存在且 YAML 可解析（`!!js` 表达式剥除后校验结构，运行时才由 DSH 求值）；
2. persona 非空且与 `agents/*.md` 去 frontmatter 后的正文逐字节一致；
3. `customSkillDirs` 指向 `plugins/agent-plugins/a-share-market-researcher/skills`，且 6 个 `SKILL.md` 都在；
4. 15 个预期行齐全、delegation 组不出现；preset.yml 元数据正确；
5. 缺凭据时报错退出且不改动已装内容；重复安装字节不变（幂等）。

## 设计要点与取舍

- **web profile 而非 headless**：headless 不走 preset（写死 coding persona），
  必须用 web profile 才能让「A股行业研究」preset 生效。
- **模型路由**：不额外配置，沿用 DSH 出厂默认 `deepseek-official / deepseek-v4-flash`
  （`dsh --profile web --dump-config` 里 `agent-default-model` 可核对）。
- **只挂 researcher 自己的技能**：`includeDefaultRoots: false` + 单条
  `customSkillDirs`，避免捡到无关的项目/用户技能。
- **不装 delegation 组**：MVP 不做 subagent/workflow/ralph。
- **cwd 约束**：DSH 的 `sandbox-policy.workspaceRoot = process.cwd()`，所以必须
  在仓库根启动 `dsh --profile web`；agent 提示词里的 `./out/`、`scripts/`、
  `fixtures/` 相对路径才解析得开。
- **Seam 3 已砍**：曾计划用 `dsh --profile web --dump-config` 做组合成型校验，
  但实测 dump 只含 host plane 树（preset 注册行，不含各 preset 内容），按 spec
  「跑不稳就砍」处理；CI 由 Seam 2 守，发版由 Seam 1 守。

## 后置（不在 MVP 内）

其余 5 个 FSI agent 的 preset、服务化/HTTP API、五阶段门禁、commands 桥、
MCP 接入、subagent 映射、全量 skill frontmatter 清理、独立应用仓库——见 spec
Out of Scope。
