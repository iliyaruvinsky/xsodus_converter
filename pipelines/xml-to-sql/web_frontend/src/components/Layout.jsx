import './Layout.css'

const APP_VERSION = '0.2.1'

function Layout({ children }) {
  return (
    <div className="layout">
      <div className="layout-content">{children}</div>
      <footer className="app-footer">
        <span>Created by Iliya Ruvinsky and Codex</span>
        <span className="app-version">v{APP_VERSION}</span>
      </footer>
    </div>
  )
}

export default Layout

