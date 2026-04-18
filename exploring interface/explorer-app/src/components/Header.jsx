import './Header.css'

export default function Header({ totalCriteria, totalWorks }) {
  return (
    <header className="header">
      <div className="header-inner">
        <div>
          <h1 className="header-title">Exclusion Criteria Explorer</h1>
          <p className="header-subtitle">
            {totalCriteria} criteria extracted from {totalWorks} ancient Greek works
          </p>
        </div>
      </div>
    </header>
  )
}
