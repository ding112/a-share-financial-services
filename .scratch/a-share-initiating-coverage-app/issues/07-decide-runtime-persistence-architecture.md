# 确定运行时与持久化架构

Type: grilling
Status: open
Blocked by: 01, 03, 06

## Question

独立应用仓库应如何划分 Web API、代码状态机、Worker、Agents SDK、DeepSeek Provider、数据库、产物存储和项目工作区；哪些状态必须持久化，如何保证阶段幂等、崩溃恢复、任务取消、资源隔离和能力源版本可追溯？
