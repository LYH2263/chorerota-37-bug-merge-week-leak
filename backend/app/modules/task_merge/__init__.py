"""task_merge：两个 clean 任务合并为新任务，按周迁移格子并生成迁移清单；支持显式拆回。

取舍拍板（模块级约定）：
- 源任务保留不动：未选中的周继续用旧任务格，新任务是额外的 clean 任务，权重=两源权重之和。
- 源任务在任意周存在 pending 对调 → 拒绝合并（不只选中周，避免确认对调时格子已迁走）。
- 拆回为全有或全无：任一已迁格无法还原（周被重新生成、格子被改派）→ 整体拒绝，
  保证迁移清单与看板始终同钉，不留半拆状态。
- 拆回成功后新任务置 archived（非 clean：不参与生成，也不可再作合并源/目标）。
"""

class MergeError(Exception):
    """reason 为稳定错误码；detail 附带上下文（冲突的对调、不可还原的周等）。"""
    def __init__(self, reason, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


def _task(c, tid):
    r = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    if not r:
        raise MergeError("task_missing", {"task_id": tid})
    return dict(r)


def _validate_sources(c, task_a, task_b):
    """脏任务不可作源；目标永远是新建 clean 任务，天然满足。"""
    if task_a == task_b:
        raise MergeError("same_task")
    a, b = _task(c, task_a), _task(c, task_b)
    for t in (a, b):
        if t["data_quality"] != "clean":
            raise MergeError("task_dirty", {"task_id": t["id"], "data_quality": t["data_quality"]})
    return a, b


def _pending_conflicts(c, task_ids):
    marks = ",".join("?" for _ in task_ids)
    return [dict(r) for r in c.execute(
        f"SELECT * FROM swap_requests WHERE status='pending' AND (a_task IN ({marks}) OR b_task IN ({marks}))",
        tuple(task_ids) + tuple(task_ids))]


def _weeks(c, week_ids):
    if not week_ids:
        raise MergeError("no_weeks")
    out = []
    for wid in week_ids:
        r = c.execute("SELECT * FROM weeks WHERE id=?", (wid,)).fetchone()
        if not r:
            raise MergeError("week_missing", {"week_id": wid})
        out.append(dict(r))
    return out


def _selected_cells(c, weeks, task_a, task_b):
    """选中周内挂在两源任务上的格子——预览、迁移、清单共用此唯一口径。"""
    marks = ",".join("?" for _ in weeks)
    return [dict(r) for r in c.execute(
        f"SELECT id, week_id, day, task_id, member_id FROM assignments "
        f"WHERE week_id IN ({marks}) AND task_id IN (?,?) ORDER BY week_id, day, id",
        tuple(w["id"] for w in weeks) + (task_a, task_b))]


def _per_week(weeks, task_a, task_b, cells):
    return [{
        "week_id": w["id"], "label": w["label"],
        "cells": sum(1 for x in cells if x["week_id"] == w["id"]),
        "task_a_cells": sum(1 for x in cells if x["week_id"] == w["id"] and x["task_id"] == task_a),
        "task_b_cells": sum(1 for x in cells if x["week_id"] == w["id"] and x["task_id"] == task_b),
    } for w in weeks]


def _reject_pending(c, task_ids):
    conflicts = _pending_conflicts(c, task_ids)
    if conflicts:
        raise MergeError("pending_swap_conflict", {"swap_ids": [s["id"] for s in conflicts]})


def preview_merge(c, task_a, task_b, title, week_ids):
    """合并预览：只读校验 + 统计将迁格数与目标标题，不写任何表。"""
    a, b = _validate_sources(c, task_a, task_b)
    _reject_pending(c, [task_a, task_b])
    weeks = _weeks(c, week_ids)
    cells = _selected_cells(c, weeks, task_a, task_b)
    return {
        "target_title": title.strip() if title and title.strip() else f'{a["title"]}+{b["title"]}',
        "new_weight": int(a["weight"] or 0) + int(b["weight"] or 0),
        "would_migrate": len(cells),
        "per_week": _per_week(weeks, task_a, task_b, cells),
        "cells": cells,
    }


def apply_merge(c, task_a, task_b, title, week_ids):
    """确认合并：建新任务，仅迁选中周格子；迁移清单与实际迁移格严格同集合。

    未选中周的旧任务格保持不动；源任务任意周存在 pending 对调则拒绝。
    """
    a, b = _validate_sources(c, task_a, task_b)
    _reject_pending(c, [task_a, task_b])
    weeks = _weeks(c, week_ids)
    listed = _selected_cells(c, weeks, task_a, task_b)
    title_s = title.strip() if title and title.strip() else f'{a["title"]}+{b["title"]}'
    new_weight = int(a["weight"] or 0) + int(b["weight"] or 0)
    cur = c.execute("INSERT INTO tasks(title,weight,data_quality) VALUES (?,?,?)",
                    (title_s, new_weight, "clean"))
    new_id = cur.lastrowid
    cur = c.execute(
        "INSERT INTO task_merges(task_a_id,task_b_id,new_task_id,title,status) VALUES (?,?,?,?,?)",
        (task_a, task_b, new_id, title_s, "confirmed"))
    merge_id = cur.lastrowid
    for cell in listed:
        c.execute(
            "INSERT INTO task_merge_cells(merge_id,week_id,assignment_id,day,member_id,old_task_id,new_task_id,status)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (merge_id, cell["week_id"], cell["id"], cell["day"], cell["member_id"], cell["task_id"], new_id, "migrated"))
        c.execute("UPDATE assignments SET task_id=? WHERE id=?", (new_id, cell["id"]))
    listed_ids = sorted(x["id"] for x in listed)
    return {"merge_id": merge_id, "new_task_id": new_id,
            "target_title": title_s, "migrated": len(listed),
            "per_week": _per_week(weeks, task_a, task_b, listed), "listed_ids": listed_ids}


def split_merge(c, merge_id):
    """显式拆回，全有或全无：看板挂新任务的格集合必须恰为清单 migrated 格集合。

    - 清单内格已缺失或不再挂新任务（周被重新生成、格子被改派）→ 拒绝；
    - 看板上存在清单外仍挂新任务的格（历史周泄漏等）→ 同样拒绝，
      否则新任务 archived 后这些格无清单可还原，看板与清单再度脱节。
    """
    m = c.execute("SELECT * FROM task_merges WHERE id=?", (merge_id,)).fetchone()
    if not m:
        raise MergeError("merge_missing", {"merge_id": merge_id})
    m = dict(m)
    if m["status"] != "confirmed":
        raise MergeError("not_confirmed", {"status": m["status"]})
    conflicts = _pending_conflicts(c, [m["new_task_id"]])
    if conflicts:
        raise MergeError("pending_swap_conflict", {"swap_ids": [s["id"] for s in conflicts]})
    cells = [dict(r) for r in c.execute(
        "SELECT * FROM task_merge_cells WHERE merge_id=? AND status='migrated'", (merge_id,))]
    blocked = []
    manifest_ids = set()
    for cell in cells:
        manifest_ids.add(cell["assignment_id"])
        a = c.execute("SELECT task_id FROM assignments WHERE id=?", (cell["assignment_id"],)).fetchone()
        if not a or a["task_id"] != m["new_task_id"]:
            blocked.append(cell["week_id"])
    extra = [dict(r) for r in c.execute(
        "SELECT id, week_id FROM assignments WHERE task_id=?", (m["new_task_id"],))
        if r["id"] not in manifest_ids]
    blocked.extend(x["week_id"] for x in extra)
    if blocked:
        raise MergeError("cells_not_restorable", {"week_ids": sorted(set(blocked))})
    for cell in cells:
        c.execute("UPDATE assignments SET task_id=? WHERE id=?", (cell["old_task_id"], cell["assignment_id"]))
        c.execute("UPDATE task_merge_cells SET status='restored' WHERE id=?", (cell["id"],))
    c.execute("UPDATE task_merges SET status='split' WHERE id=?", (merge_id,))
    c.execute("UPDATE tasks SET data_quality='archived' WHERE id=?", (m["new_task_id"],))
    return {"merge_id": merge_id, "restored": len(cells)}


def list_merges(c):
    """迁移单：合并记录 + 逐格清单。标题/成员/周名实时 join，与看板同源同钉。"""
    tasks = {r["id"]: r["title"] for r in c.execute("SELECT id,title FROM tasks")}
    members = {r["id"]: r["name"] for r in c.execute("SELECT id,name FROM members")}
    weeks = {r["id"]: r["label"] for r in c.execute("SELECT id,label FROM weeks")}
    out = []
    for m in c.execute("SELECT * FROM task_merges ORDER BY id DESC"):
        m = dict(m)
        cells = []
        for r in c.execute("SELECT * FROM task_merge_cells WHERE merge_id=? ORDER BY week_id, day, id", (m["id"],)):
            r = dict(r)
            cells.append({
                **r,
                "week_label": weeks.get(r["week_id"], "?"),
                "member_name": members.get(r["member_id"], "?"),
                "old_task_title": tasks.get(r["old_task_id"], "?"),
                "new_task_title": tasks.get(r["new_task_id"], "?"),
            })
        out.append({
            **m,
            "task_a_title": tasks.get(m["task_a_id"], "?"),
            "task_b_title": tasks.get(m["task_b_id"], "?"),
            "cells": cells,
        })
    return out
