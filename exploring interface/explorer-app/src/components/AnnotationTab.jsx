import { useState, useMemo, useCallback } from 'react'
import './AnnotationTab.css'

function StdTag({ value }) {
  if (!value) return null
  return <span className="std-tag">{value}</span>
}

export default function AnnotationTab({ data, sampleIndices, catColors }) {
  const [votes, setVotes] = useState({})
  const [comments, setComments] = useState({})
  const [detailsOpen, setDetailsOpen] = useState({})

  const vote = useCallback((idx, direction) => {
    setVotes(v => ({ ...v, [idx]: v[idx] === direction ? null : direction }))
  }, [])

  const setComment = useCallback((idx, text) => {
    setComments(c => ({ ...c, [idx]: text }))
  }, [])

  const toggleDetails = useCallback((idx) => {
    setDetailsOpen(d => ({ ...d, [idx]: !d[idx] }))
  }, [])

  const annotatedCount = useMemo(() => {
    const done = new Set()
    sampleIndices.forEach(idx => {
      if (votes[idx] || comments[idx]) done.add(idx)
    })
    return done.size
  }, [sampleIndices, votes, comments])

  const progressPct = sampleIndices.length > 0
    ? (annotatedCount / sampleIndices.length) * 100 : 0

  // Count by ALL criteria on each rule. Multi-criterion rules contribute to
  // every bucket they belong to, so totals can exceed 5 per criterion and a
  // single down-vote will count against every criterion of that rule.
  const catStats = useMemo(() => {
    const stats = {}
    sampleIndices.forEach(idx => {
      const raw = (data[idx]?.criteria || '').trim()
      const buckets = raw ? raw.split('|').map(s => s.trim()).filter(Boolean) : ['(none)']
      const vote = votes[idx]
      buckets.forEach(cat => {
        if (!stats[cat]) stats[cat] = { up: 0, down: 0, pending: 0, total: 0 }
        stats[cat].total++
        if (vote === 'up') stats[cat].up++
        else if (vote === 'down') stats[cat].down++
        else stats[cat].pending++
      })
    })
    return Object.entries(stats).sort((a, b) => b[1].total - a[1].total)
  }, [sampleIndices, data, votes])

  const [exportStatus, setExportStatus] = useState(null)

  const exportAnnotations = async () => {
    // Build rows with all metadata + vote/comment
    const rows = sampleIndices.map(idx => {
      const d = data[idx]
      return {
        work_name: d.work_name,
        author: d.author,
        impact_year: d.impact_year,
        polity: d.polity,
        criterion_label: d.criterion_label,
        in_group: d.in_group,
        out_group: d.out_group,
        resource: d.resource,
        resource_std: d.resource_std,
        speaker: d.speaker,
        verbatim: d.verbatim,
        matched_keywords: d.matched_keywords,
        extraction_method: d.extraction_method,
        extraction_cost_usd: d.extraction_cost_usd,
        prompt_tokens: d.prompt_tokens,
        completion_tokens: d.completion_tokens,
        rule_uid: d.rule_uid,
        file_id: d.file_id,
        criteria: d.criteria,
        sampled_for: d.sampled_for,
        is_contemporary: d.is_contemporary,
        verbatim_type: d.verbatim_type,
        factuality: d.factuality,
        rule_category: d.rule_category,
        reasoning: d.reasoning,
        group_generality: d.group_generality,
        generality_reasoning: d.generality_reasoning,
        resource_materiality: d.resource_materiality,
        materiality_reasoning: d.materiality_reasoning,
        resource_generality: d.resource_generality,
        resource_generality_reasoning: d.resource_generality_reasoning,
        resource_persistence: d.resource_persistence,
        persistence_reasoning: d.persistence_reasoning,
        group_immutability: d.group_immutability,
        immutability_reasoning: d.immutability_reasoning,
        tautological: d.tautological,
        tautology_reasoning: d.tautology_reasoning,
        confidence: d.confidence,
        vote: votes[idx] || '',
        comment: comments[idx] || '',
      }
    })

    // Accuracy per category
    const accuracy_by_category = catStats.map(([cat, s]) => ({
      category: cat,
      up: s.up,
      down: s.down,
      pending: s.pending,
      total: s.total,
      accuracy_pct: (s.up + s.down) > 0
        ? ((s.up / (s.up + s.down)) * 100).toFixed(1)
        : 'N/A',
    }))

    setExportStatus('saving')
    try {
      const res = await fetch('/api/save_annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows, accuracy_by_category }),
      })
      if (res.ok) {
        const result = await res.json()
        setExportStatus(`Saved ${result.rows} rows to data/annotation/user_comments_sample60_v19.csv`)
      } else {
        setExportStatus('Error saving file')
      }
    } catch (e) {
      setExportStatus(`Error: ${e.message}`)
    }
    setTimeout(() => setExportStatus(null), 4000)
  }

  return (
    <div className="annotation-tab">
      {/* Progress bar */}
      <div className="annotation-progress">
        <span className="progress-text">
          {annotatedCount} / {sampleIndices.length} annotated
        </span>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {/* Export */}
      <div className="export-section">
        <button className="export-btn" onClick={exportAnnotations} disabled={exportStatus === 'saving'}>
          {exportStatus === 'saving' ? 'Saving...' : 'Export Annotations'}
        </button>
        {exportStatus && exportStatus !== 'saving' && (
          <span className="export-status">{exportStatus}</span>
        )}
      </div>

      {/* Dashboard */}
      <div className="annotation-dashboard">
        <h2>Annotation Results by Criterion</h2>
        {catStats.map(([cat, s]) => (
          <div className="ann-row" key={cat}>
            <span className="ann-cat-name">{cat.replace(/_/g, ' ')} ({s.total})</span>
            <div className="ann-bar">
              <div className="ann-bar-up" style={{ width: `${(s.up / s.total) * 100}%` }} />
              <div className="ann-bar-down" style={{ width: `${(s.down / s.total) * 100}%` }} />
              <div className="ann-bar-pending" style={{ width: `${(s.pending / s.total) * 100}%` }} />
            </div>
            <div className="ann-counts">
              <span className="count-up">{s.up}</span>
              <span className="count-down">{s.down}</span>
              <span className="count-pending">{s.pending}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Sample cards */}
      <div className="sample-cards">
        {sampleIndices.map(idx => {
          const d = data[idx]
          if (!d) return null
          const color = catColors[d.criterion_category] || '#475569'
          const isDone = votes[idx] || comments[idx]

          return (
            <div className="criteria-card" style={{ borderLeftColor: color }} key={idx}>
              <div className="card-header">
                <div>
                  <h3 className="card-title">{d.work_name}</h3>
                  <div className="card-meta">
                    <span>{d.author}</span>
                    <span className="meta-sep" />
                    <span>{d.impact_year}</span>
                    <span className="meta-sep" />
                    <span>{d.polity}</span>
                    <span className={`ann-status ${isDone ? 'status-done' : 'status-pending'}`}>
                      {isDone ? 'done' : 'pending'}
                    </span>
                  </div>
                </div>
              </div>
              <div className="card-body">
                {/* Key-value table of every LLM field + computed criteria */}
                <table className="kv-table">
                  <tbody>
                    <tr><th>Rule name</th><td>{d.criterion_label}</td></tr>
                    <tr><th>Group</th><td>{d.in_group}</td></tr>
                    <tr>
                      <th>Criteria</th>
                      <td>
                        {d.criteria && d.criteria.split('|').filter(Boolean).map(c => (
                          <span key={c} className="badge badge-criterion" style={{ background: '#0f172a' }}>{c}</span>
                        ))}
                      </td>
                    </tr>
                    <tr>
                      <th>Directionality</th>
                      <td>
                        {d.speaker && (
                          <span className="badge" style={{ background: d.speaker === 'MORE' ? '#2c6e91' : '#c0392b' }}>
                            {d.speaker}
                          </span>
                        )}
                      </td>
                    </tr>
                    <tr><th>Resource</th><td>{d.resource}</td></tr>
                    <tr><th>Proof</th><td className="verbatim-cell">"{d.verbatim}"</td></tr>
                    <tr><th>Reasoning</th><td>{d.reasoning}</td></tr>
                    {detailsOpen[idx] && (
                      <>
                        <tr>
                          <th>Group generality</th>
                          <td>
                            {d.group_generality && <strong>{d.group_generality}/5</strong>}
                            {d.group_generality && d.generality_reasoning && ' — '}
                            {d.generality_reasoning}
                          </td>
                        </tr>
                        <tr>
                          <th>Resource materiality</th>
                          <td>
                            {d.resource_materiality && <strong>{d.resource_materiality}/5</strong>}
                            {d.resource_materiality && d.materiality_reasoning && ' — '}
                            {d.materiality_reasoning}
                          </td>
                        </tr>
                        <tr>
                          <th>Resource generality</th>
                          <td>
                            {d.resource_generality && <strong>{d.resource_generality}/5</strong>}
                            {d.resource_generality && d.resource_generality_reasoning && ' — '}
                            {d.resource_generality_reasoning}
                          </td>
                        </tr>
                        <tr>
                          <th>Resource persistence</th>
                          <td>
                            {d.resource_persistence && <strong>{d.resource_persistence}/5</strong>}
                            {d.resource_persistence && d.persistence_reasoning && ' — '}
                            {d.persistence_reasoning}
                          </td>
                        </tr>
                        <tr>
                          <th>Group immutability</th>
                          <td>
                            {d.group_immutability && <strong>{d.group_immutability}/5</strong>}
                            {d.group_immutability && d.immutability_reasoning && ' — '}
                            {d.immutability_reasoning}
                          </td>
                        </tr>
                        <tr>
                          <th>Tautological?</th>
                          <td>
                            {d.tautological === '1' || d.tautological === 1 ? (
                              <span className="badge" style={{ background: '#991b1b' }}>Tautological</span>
                            ) : d.tautological === '0' || d.tautological === 0 ? (
                              <span className="badge" style={{ background: '#065f46' }}>Non-tautological</span>
                            ) : (
                              <span style={{ color: 'var(--slate-400)' }}>—</span>
                            )}
                            {d.tautology_reasoning && ` — ${d.tautology_reasoning}`}
                          </td>
                        </tr>
                        <tr><th>Confidence</th><td>{d.confidence && <strong>{d.confidence}/10</strong>}</td></tr>
                        <tr>
                          <th>Contemporary?</th>
                          <td>
                            {d.is_contemporary === '1' || d.is_contemporary === 1 ? (
                              <span className="badge" style={{ background: '#059669' }}>Contemporary</span>
                            ) : d.is_contemporary === '0' || d.is_contemporary === 0 ? (
                              <span className="badge" style={{ background: '#b45309' }}>Historical / Mythical</span>
                            ) : (
                              <span style={{ color: 'var(--slate-400)' }}>—</span>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <th>Verbatim type</th>
                          <td>
                            {d.verbatim_type === 'fact' && (
                              <span className="badge" style={{ background: '#1d4ed8' }}>Fact</span>
                            )}
                            {d.verbatim_type === 'opinion' && (
                              <span className="badge" style={{ background: '#9333ea' }}>Opinion</span>
                            )}
                            {d.verbatim_type === 'mixed' && (
                              <span className="badge" style={{ background: '#475569' }}>Mixed</span>
                            )}
                            {!d.verbatim_type && <span style={{ color: 'var(--slate-400)' }}>—</span>}
                          </td>
                        </tr>
                        <tr>
                          <th>Factuality</th>
                          <td>
                            {d.factuality ? (
                              <span className="badge" style={{
                                background: ({
                                  '1': '#991b1b', '2': '#b45309', '3': '#475569',
                                  '4': '#065f46', '5': '#064e3b'
                                })[String(d.factuality)] || '#475569'
                              }}>
                                {d.factuality}/5 — {({
                                  '1': 'Mythic / speculative',
                                  '2': 'Indirect inference',
                                  '3': 'Contemporary documentation',
                                  '4': 'Legal oration',
                                  '5': 'Original legal text'
                                })[String(d.factuality)] || ''}
                              </span>
                            ) : (
                              <span style={{ color: 'var(--slate-400)' }}>—</span>
                            )}
                          </td>
                        </tr>
                      </>
                    )}
                  </tbody>
                </table>

                <button
                  type="button"
                  className="details-toggle"
                  onClick={() => toggleDetails(idx)}
                >
                  {detailsOpen[idx] ? 'Hide details' : 'Show details'}
                </button>

                {/* Voting */}
                <div className="vote-section">
                  <span className="vote-label">Valid?</span>
                  <button
                    className={`vote-btn ${votes[idx] === 'up' ? 'vote-selected-up' : ''}`}
                    onClick={() => vote(idx, 'up')}
                  >
                    &#128077;
                  </button>
                  <button
                    className={`vote-btn ${votes[idx] === 'down' ? 'vote-selected-down' : ''}`}
                    onClick={() => vote(idx, 'down')}
                  >
                    &#128078;
                  </button>
                </div>

                {/* Comment */}
                <div className="comment-section">
                  <label className="box-label">Annotation</label>
                  <textarea
                    className="comment-input"
                    placeholder="Optional comment..."
                    value={comments[idx] || ''}
                    onChange={e => setComment(idx, e.target.value)}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
