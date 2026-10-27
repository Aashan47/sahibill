import { NavLink, Link, Outlet } from "react-router-dom";
import { useI18n } from "../i18n";

/** The brand mark: a round rubber stamp with a tick, in the bill's print colour. */
export function BrandMark() {
  return (
    <svg className="brand__mark" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="17" fill="none" stroke="var(--print)" strokeWidth="3" />
      <circle cx="20" cy="20" r="12.5" fill="none" stroke="var(--print)" strokeWidth="1.2" />
      <path d="M13.5 20.5l4.5 4.5 8.5-9.5" fill="none" stroke="var(--print)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Shell() {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="shell">
      <a className="visually-hidden" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar__in">
          <Link to="/" className="brand" aria-label="SahiBill home">
            <BrandMark />
            <span>
              SahiBill <span className="brand__ur" lang="ur">صحیح بل</span>
            </span>
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/check">{t.nav.check}</NavLink>
            <NavLink to="/how">{t.nav.how}</NavLink>
          </nav>
          <div className="lang" role="group" aria-label={t.langLabel}>
            <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
              EN
            </button>
            <button type="button" className="ur" lang="ur" aria-pressed={lang === "ur"} onClick={() => setLang("ur")}>
              اردو
            </button>
          </div>
        </div>
      </header>
      <main id="main">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="footer__in">
          <span>{t.footer.built}</span>
          <span>{t.footer.privacy}</span>
          <span>{t.footer.rules}</span>
        </div>
      </footer>
    </div>
  );
}
