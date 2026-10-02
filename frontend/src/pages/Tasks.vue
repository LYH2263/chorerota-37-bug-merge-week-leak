<template>
  <div>
    <h1 class="brand">任务</h1>
    <form @submit.prevent="add">
      <input v-model="title" placeholder="任务名" />
      <button type="submit">添加</button>
    </form>
    <ul class="list">
      <li v-for="t in rows" :key="t.id">
        <strong>{{ t.title }}</strong>
        <span class="muted"> · 权重 {{ t.weight }} · {{ t.data_quality }}</span>
      </li>
    </ul>

    <section class="week-card" style="margin-top:16px">
      <h2 class="brand" style="font-size:1.05rem;margin-top:0">合并任务</h2>
      <p class="muted">两个 clean 任务合为新任务，仅迁移勾选周的格子；未勾选的周保持旧任务格不动</p>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 12px">
        <select v-model.number="merge.task_a">
          <option :value="0" disabled>源任务 A</option>
          <option v-for="t in cleanTasks" :key="t.id" :value="t.id" :disabled="t.id===merge.task_b">
            {{ t.title }}
          </option>
        </select>
        <select v-model.number="merge.task_b">
          <option :value="0" disabled>源任务 B</option>
          <option v-for="t in cleanTasks" :key="t.id" :value="t.id" :disabled="t.id===merge.task_a">
            {{ t.title }}
          </option>
        </select>
      </div>
      <input v-model="merge.title" placeholder="新任务名（留空则 A+B）" />
      <div style="display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 10px">
        <label v-for="w in weeks" :key="w.id" style="display:flex;align-items:center;gap:4px">
          <input type="checkbox" :value="w.id" v-model="merge.week_ids" style="width:auto;margin:0" />
          <span>{{ w.label }}</span>
        </label>
      </div>
      <button class="ghost" @click="preview">预览</button>
      <button v-if="prev" style="margin-left:8px" @click="confirm">确认合并</button>
      <p v-if="err" class="err">{{ err }}</p>
      <div v-if="prev" class="week-card" style="margin-top:10px;min-height:0">
        <p style="margin:4px 0">
          目标标题 <strong>{{ prev.target_title }}</strong> · 将迁格数 <strong>{{ prev.would_migrate }}</strong>
        </p>
        <p v-for="w in prev.per_week" :key="w.week_id" class="muted" style="margin:2px 0">
          {{ w.label }}：{{ w.cells }} 格（A {{ w.task_a_cells }} + B {{ w.task_b_cells }}）
        </p>
        <p class="muted" style="margin:4px 0 0">预览不改 assignments，确认后才落库</p>
      </div>
      <p v-if="done" class="muted" style="margin-bottom:0">
        {{ done }} · 看板任务名已同步，明细见 <router-link to="/migrations">迁移单</router-link>
      </p>
    </section>
  </div>
</template>
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api, errText } from '../api'
const rows = ref([])
const weeks = ref([])
const title = ref('')
const merge = ref({ task_a: 0, task_b: 0, title: '', week_ids: [] })
const prev = ref(null)
const done = ref('')
const err = ref('')
const cleanTasks = computed(() => rows.value.filter(t => t.data_quality === 'clean'))
async function load() {
  rows.value = await api('/tasks')
  weeks.value = await api('/weeks')
}
async function add() {
  if (!title.value.trim()) return
  await api('/tasks', { method: 'POST', body: JSON.stringify({ title: title.value }) })
  title.value = ''; await load()
}
async function preview() {
  err.value = ''; prev.value = null; done.value = ''
  try {
    prev.value = await api('/tasks/merge/preview', { method: 'POST', body: JSON.stringify(merge.value) })
  } catch (e) { err.value = errText(e) }
}
async function confirm() {
  err.value = ''
  try {
    const r = await api('/tasks/merge/confirm', { method: 'POST', body: JSON.stringify(merge.value) })
    done.value = `已合并为「${r.target_title}」，迁移 ${r.migrated} 格`
    prev.value = null
    merge.value = { task_a: 0, task_b: 0, title: '', week_ids: [] }
    await load()
  } catch (e) { err.value = errText(e) }
}
watch(merge, () => { prev.value = null }, { deep: true })  // 输入变了旧预览作废
onMounted(load)
</script>
