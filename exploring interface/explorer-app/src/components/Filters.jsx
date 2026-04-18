import './Filters.css'

export default function Filters({ filters, setFilters, categories, authors, polities }) {
  const update = (key, value) => setFilters(f => ({ ...f, [key]: value }))
  const clear = () => setFilters({ category: '', author: '', polity: '', search: '' })

  return (
    <div className="filters">
      <div className="filter-group">
        <label>Category</label>
        <select value={filters.category} onChange={e => update('category', e.target.value)}>
          <option value="">All categories</option>
          {categories.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
        </select>
      </div>
      <div className="filter-group">
        <label>Author</label>
        <select value={filters.author} onChange={e => update('author', e.target.value)}>
          <option value="">All authors</option>
          {authors.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      <div className="filter-group">
        <label>Polity</label>
        <select value={filters.polity} onChange={e => update('polity', e.target.value)}>
          <option value="">All polities</option>
          {polities.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div className="filter-group filter-search">
        <label>Search</label>
        <input
          type="text"
          placeholder="Search verbatims, labels..."
          value={filters.search}
          onChange={e => update('search', e.target.value)}
        />
      </div>
      <button className="clear-btn" onClick={clear}>Clear</button>
    </div>
  )
}
