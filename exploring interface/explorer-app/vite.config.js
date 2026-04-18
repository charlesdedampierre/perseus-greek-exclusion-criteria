import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

const CSV_PATH = path.resolve(
  __dirname,
  '../../data/annotation/user_comments_sample60_v19.csv'
)

function csvEscape(val) {
  const s = String(val ?? '')
  if (s.includes(',') || s.includes('"') || s.includes('\n'))
    return `"${s.replace(/"/g, '""')}"`
  return s
}

function saveAnnotationsPlugin() {
  return {
    name: 'save-annotations',
    configureServer(server) {
      server.middlewares.use('/api/save_annotations', async (req, res) => {
        if (req.method === 'OPTIONS') {
          res.writeHead(200, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type' })
          res.end()
          return
        }
        if (req.method !== 'POST') {
          res.writeHead(405)
          res.end('Method not allowed')
          return
        }

        let body = ''
        for await (const chunk of req) body += chunk
        const { rows, accuracy_by_category } = JSON.parse(body)

        const headers = [
          'rule_uid', 'file_id',
          'work_name', 'author', 'impact_year', 'polity',
          'criteria',
          'sampled_for',
          'is_contemporary',
          'verbatim_type',
          'factuality',
          'criterion_label',
          'in_group', 'out_group',
          'resource', 'resource_std',
          'speaker', 'verbatim', 'matched_keywords',
          'rule_category', 'reasoning',
          'group_generality', 'generality_reasoning',
          'resource_materiality', 'materiality_reasoning',
          'resource_generality', 'resource_generality_reasoning',
          'resource_persistence', 'persistence_reasoning',
          'group_immutability', 'immutability_reasoning',
          'tautological', 'tautology_reasoning',
          'confidence',
          'extraction_method', 'extraction_cost_usd',
          'prompt_tokens', 'completion_tokens',
          'vote', 'comment'
        ]

        const csvLines = [headers.map(csvEscape).join(',')]
        for (const row of rows) {
          csvLines.push(headers.map(h => csvEscape(row[h])).join(','))
        }

        // Blank line then accuracy summary
        csvLines.push('')
        csvLines.push('# Accuracy by Category')
        csvLines.push(['category', 'up', 'down', 'pending', 'total', 'accuracy_pct'].map(csvEscape).join(','))
        for (const cat of accuracy_by_category) {
          csvLines.push([cat.category, cat.up, cat.down, cat.pending, cat.total, cat.accuracy_pct].map(csvEscape).join(','))
        }

        // Ensure directory exists
        const dir = path.dirname(CSV_PATH)
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })

        fs.writeFileSync(CSV_PATH, csvLines.join('\n'), 'utf-8')

        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ status: 'ok', path: CSV_PATH, rows: rows.length }))
      })
    }
  }
}

export default defineConfig({
  plugins: [react(), saveAnnotationsPlugin()],
})
