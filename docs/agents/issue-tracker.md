# Issue tracker：本地 Markdown

本仓库的 PRD 和 issues 保存在 `.scratch/` 中。

## 约定

- 每项功能一个目录：`.scratch/<feature-slug>/`
- PRD 文件：`.scratch/<feature-slug>/PRD.md`
- 实现 issue：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- issue 状态在文件顶部附近使用 `Status:` 记录
- 评论和讨论追加到文件底部的 `## Comments`

当技能要求“发布到 issue tracker”时，在对应功能目录下创建文件。
当技能要求“读取 ticket”时，读取用户指定的路径或 issue 编号。
