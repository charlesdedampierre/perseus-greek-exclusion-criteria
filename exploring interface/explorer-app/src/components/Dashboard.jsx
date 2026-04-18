import { useMemo } from 'react'
import './Dashboard.css'

function countBy(arr, key) {
  const counts = {}
  arr.forEach(d => {
    const val = d[key] || 'Unknown'
    counts[val] = (counts[val] || 0) + 1
  })
  return Object.entries(counts).sort((a, b) => b[1] - a[1])
}

export default function Dashboard({ filtered, catColors, onCategoryClick }) {
  const catCounts = useMemo(() => countBy(filtered, 'criterion_category'), [filtered])
  const maxCount = catCounts.length > 0 ? catCounts[0][1] : 1

  if (filtered.length === 0) return null

  return (
    <div className="dashboard">
      <h2 className="dashboard-title">Category Distribution</h2>
      <div className="bar-chart">
        {catCounts.map(([cat, count]) => (
          <div
            className="bar-row"
            key={cat}
            onClick={() => onCategoryClick(cat)}
          >
            <span className="bar-label">{cat.replace(/_/g, ' ')}</span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{
                  width: `${(count / maxCount) * 100}%`,
                  background: catColors[cat] || '#475569'
                }}
              >
                <span className="bar-count">{count}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
