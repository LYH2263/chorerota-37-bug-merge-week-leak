<template>
  <div>
    <h1 class="brand">迁移单</h1>
    <p class="muted">任务合并的逐格迁移清单，与看板同源同钉 · confirmed 的合并可显式拆回（全有或全无）</p>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-if="!rows.length" class="muted">暂无合并记录，去「任务」页发起合并</p>
    <article v-for="m in rows" :key="m.id" class="week-card" style="margin-bottom:12px;min-height:0">
      <header style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap">
        <span>
          #{{ m.id }} 「{{ m.task_a_title }}」+「{{ m.task_b_title }}」 → <strong>{{ m.title }}</strong>
          <span class="muted"> · {{ m.cells.length }} 格</span>
        </span>
        <span>
          <span class="chip" :class="{ coral: m.status==='confirmed' }">{{ m.status }}</span>
          <button v-if="m.status==='confirmed'" class="ghost" style="margin-left:8px" @click="split(m.id)">拆回</button>
        </span>
      </header>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr v-for="cell in m.cells" :key="cell.id" style="border-bottom:1px dashed var(--line)">
          <td style="padding:6px 4px">{{ cell.week_label }}</td>
          <td>Day {{ cell.day }}</td>
          <td>{{ cell.member_name }}</td>
          <td>{{ cell.old_task_title }} → {{ cell.new_task_title }}</td>
          <td style="text-align:right"><span class="chip">{{ cell.status }}</span></td>
        </tr>
        <tr v-if="!m.cells.length"><td class="muted" style="padding:6px 4px">无迁移格（合并时勾选周无相关格子）</td></tr>
      </table>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api, errText } from '../api'
const rows = ref([])
const err = ref('')
async function load() { rows.value = await api('/merges') }
async function split(id) {
  err.value = ''
  try { await api('/merges/' + id + '/split', { method: 'POST', body: '{}' }); await load() }
  catch (e) { err.value = errText(e) }
}
onMounted(load)
</script>
