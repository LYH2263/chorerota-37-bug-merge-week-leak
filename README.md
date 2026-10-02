# Chorerota · 家庭值日轮转

底座：成员+任务 → round-robin 生成周表 → 申请对调 → 确认改表。

迭代：任务合并迁移。任务页选两个 clean 任务合并为新任务，按勾选周迁移格子并生成迁移清单（未勾选的周保持旧格）；预览只读给出将迁格数与目标标题，确认后看板任务名与迁移单逐格同钉。源任务有 pending 对调或脏任务作源/目标均拒。迁移单页可显式拆回——全有或全无：任一已迁格无法还原（如周被重新生成）则整体拒绝。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5100 |
| API | 10100 |

```bash
docker compose up --build
pytest backend/app/tests
```

种子含 clean/dirty。0-1 空桩：`streak_badge` / `skip_week` / `chore_photo`。
模块：`task_merge`（合并预览/确认/拆回/迁移单）。
