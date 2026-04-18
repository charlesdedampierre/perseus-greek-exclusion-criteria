import './CriteriaCard.css'

function Badge({ label, color }) {
  return <span className="badge" style={{ background: color }}>{label}</span>
}

function StdTag({ value }) {
  if (!value) return null
  return <span className="std-tag">{value}</span>
}

function Keywords({ keywords }) {
  if (!keywords || !keywords.trim()) return null
  const tags = keywords.split(', ').filter(Boolean)
  return (
    <div className="keywords-box">
      <div className="box-label">Matched Keywords</div>
      <div className="keyword-tags">
        {tags.map((k, i) => <span key={i} className="keyword-tag">{k}</span>)}
      </div>
    </div>
  )
}

export default function CriteriaCard({ data: d, catColors }) {
  const color = catColors[d.criterion_category] || '#475569'

  return (
    <div className="criteria-card" style={{ borderLeftColor: color }}>
      <div className="card-header">
        <div>
          <h3 className="card-title">{d.work_name}</h3>
          <div className="card-meta">
            <span>{d.author}</span>
            <span className="meta-sep" />
            <span>{d.impact_year}</span>
            <span className="meta-sep" />
            <span>{d.polity}</span>
          </div>
        </div>
      </div>

      <div className="card-body">
        <div className="badges-row">
          <Badge label={d.criterion_category?.replace(/_/g, ' ')} color={color} />
          <Badge label={d.criterion_label} color="var(--slate-600)" />
          {d.speaker && <Badge label={d.speaker} color="var(--amber-500)" />}
        </div>

        <div className="groups-row">
          <div className="group-box in-group">
            <div className="box-label">In-Group</div>
            <div className="group-value">
              {d.in_group}
              <StdTag value={d.in_group_std} />
            </div>
          </div>
          <div className="group-box out-group">
            <div className="box-label">Out-Group</div>
            <div className="group-value">
              {d.out_group}
              <StdTag value={d.out_group_std} />
            </div>
          </div>
        </div>

        <div className="resource-box">
          <div className="box-label">Resource</div>
          <div className="group-value">
            {d.resource}
            <StdTag value={d.resource_std} />
          </div>
        </div>

        <blockquote className="verbatim">
          "{d.verbatim}"
        </blockquote>

        <Keywords keywords={d.matched_keywords} />
      </div>
    </div>
  )
}
