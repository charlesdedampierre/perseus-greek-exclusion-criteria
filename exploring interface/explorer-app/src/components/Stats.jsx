import './Stats.css'

export default function Stats({ filtered, total }) {
  const works = new Set(filtered.map(d => d.work_name)).size
  const authors = new Set(filtered.map(d => d.author)).size

  return (
    <div className="stats">
      <span className="stat">
        Showing <strong>{filtered.length}</strong> of {total}
      </span>
      <span className="stat">
        Works: <strong>{works}</strong>
      </span>
      <span className="stat">
        Authors: <strong>{authors}</strong>
      </span>
    </div>
  )
}
