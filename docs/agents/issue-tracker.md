# Issue tracker：本地 Markdown

本仓库的 specs 和 issues 保存在 `.scratch/` 中。

## 约定

- 每项功能一个目录：`.scratch/<feature-slug>/`
- 规格文件：`.scratch/<feature-slug>/spec.md`
- 实现 issue：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- 每个 issue 单独一个文件，从 `01` 开始编号
- issue 状态在文件顶部附近使用 `Status:` 记录
- 阻塞关系使用 `Blocked by:` 记录
- 评论和讨论追加到文件底部的 `## Comments`

当技能要求发布规格或 issue 时，在对应功能目录创建文件；读取 ticket 时使用用户给出的路径或编号。

已有历史 `PRD.md` 保持原样，不要求迁移。
