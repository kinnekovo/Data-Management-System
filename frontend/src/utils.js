export function formatDate(value) {
  if (!value) return '未设置'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function toLocalInput(value) {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function fromLocalInput(value) {
  return value ? new Date(value).toISOString() : null
}

export const statusLabels = { draft: '草稿', published: '已发布', closed: '已关闭' }

export const questionTypeLabels = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  text: '文本题',
  number: '数字题',
}
