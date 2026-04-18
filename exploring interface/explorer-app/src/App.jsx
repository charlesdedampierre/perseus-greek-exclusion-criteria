import { useState, useEffect, useMemo } from 'react'
import Papa from 'papaparse'
import Header from './components/Header'
import Filters from './components/Filters'
import Stats from './components/Stats'
import Dashboard from './components/Dashboard'
import CriteriaCard from './components/CriteriaCard'
import AnnotationTab from './components/AnnotationTab'
import './App.css'

const CAT_COLORS = {
  MORAL_CONDUCT: '#e11d48',
  BIRTH_LINEAGE: '#7c3aed',
  ACHIEVEMENTS: '#d97706',
  CITIZENSHIP: '#2563eb',
  PROPERTY_WEALTH: '#059669',
  AGE: '#0d9488',
  GENDER: '#db2777',
  FREEDOM_STATUS: '#ea580c',
  OCCUPATION: '#475569',
  PHYSICAL_STATUS: '#78350f',
  LEGAL_STANDING: '#0891b2',
}

// The CSV is already the annotation sample — every row is meant to be reviewed.
function computeStratifiedSample(data) {
  return data.map((_, i) => i)
}

function App() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('explore')
  const [filters, setFilters] = useState({
    category: '', author: '', polity: '', search: ''
  })

  useEffect(() => {
    Papa.parse(`/data/sample60_v19.csv?t=${Date.now()}`, {
      download: true,
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        setData(results.data)
        setLoading(false)
      }
    })
  }, [])

  const sampleIndices = useMemo(() => computeStratifiedSample(data), [data])

  const filtered = useMemo(() => {
    return data.filter(d => {
      if (filters.category && d.criterion_category !== filters.category) return false
      if (filters.author && d.author !== filters.author) return false
      if (filters.polity && d.polity !== filters.polity) return false
      if (filters.search) {
        const s = filters.search.toLowerCase()
        const searchable = `${d.verbatim} ${d.criterion_label} ${d.in_group} ${d.out_group}`.toLowerCase()
        if (!searchable.includes(s)) return false
      }
      return true
    })
  }, [data, filters])

  const categories = useMemo(() =>
    [...new Set(data.map(d => d.criterion_category).filter(Boolean))].sort(),
    [data]
  )
  const authors = useMemo(() =>
    [...new Set(data.map(d => d.author).filter(Boolean))].sort(),
    [data]
  )
  const polities = useMemo(() =>
    [...new Set(data.map(d => d.polity).filter(Boolean))].sort(),
    [data]
  )

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>Loading criteria data...</p>
      </div>
    )
  }

  return (
    <div className="app">
      <Header totalCriteria={data.length} totalWorks={new Set(data.map(d => d.work_name)).size} />

      <div className="container">
        <div className="tabs">
          <button
            className={`tab ${tab === 'explore' ? 'active' : ''}`}
            onClick={() => setTab('explore')}
          >
            All Criteria
            <span className="tab-count">{data.length}</span>
          </button>
          <button
            className={`tab ${tab === 'annotate' ? 'active' : ''}`}
            onClick={() => setTab('annotate')}
          >
            Annotation Sample
            <span className="tab-count">{sampleIndices.length}</span>
          </button>
        </div>

        {tab === 'explore' && (
          <>
            <Filters
              filters={filters}
              setFilters={setFilters}
              categories={categories}
              authors={authors}
              polities={polities}
            />
            <Stats filtered={filtered} total={data.length} />
            <Dashboard filtered={filtered} catColors={CAT_COLORS} onCategoryClick={(cat) => setFilters(f => ({ ...f, category: cat }))} />
            <div className="cards-list">
              {filtered.length === 0 ? (
                <div className="no-results">No criteria match your filters.</div>
              ) : (
                filtered.map((d, i) => (
                  <CriteriaCard key={i} data={d} catColors={CAT_COLORS} />
                ))
              )}
            </div>
          </>
        )}

        {tab === 'annotate' && (
          <AnnotationTab
            data={data}
            sampleIndices={sampleIndices}
            catColors={CAT_COLORS}
          />
        )}
      </div>
    </div>
  )
}

export default App
