export async function api(path, opts = {}) {
  const r = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  })
  if (!r.ok) {
    let detail = r.statusText
    try { const j = await r.json(); detail = j.detail || JSON.stringify(j) } catch {}
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (r.status === 204) return null
  return r.json()
}

const REASONS = {
  task_missing: '任务不存在',
  task_dirty: '脏任务不可作源或目标',
  same_task: '两个源任务相同',
  no_weeks: '未选择要迁移的周',
  week_missing: '所选周不存在',
  pending_swap_conflict: '源任务存在 pending 对调，拒绝合并/拆回',
  merge_missing: '迁移单不存在',
  not_confirmed: '该合并已拆回',
  cells_not_restorable: '有迁移格已无法还原（周可能被重新生成），拆回整体拒绝',
}

// 后端错误为 {reason, ...detail} 时给出中文说明，其余原样展示
export function errText(e) {
  try {
    const j = JSON.parse(e.message)
    if (j && j.reason) {
      const extra = j.week_ids ? `（周 ${j.week_ids.join(',')}）`
        : j.swap_ids ? `（对调 #${j.swap_ids.join(',#')}）` : ''
      return (REASONS[j.reason] || j.reason) + extra
    }
  } catch {}
  return e.message
}
