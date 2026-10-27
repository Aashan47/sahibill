import type { ReactNode } from "react";
import type { Stamp as StampKind } from "../api";
import { useI18n } from "../i18n";

/** The inked verdict stamp. `land` plays the one motion moment, when a result first arrives. */
export function Stamp({ status, size = "lg", land = false }: { status: StampKind; size?: "lg" | "sm"; land?: boolean }) {
  const { t, lang } = useI18n();
  return (
    <span
      className={`stamp stamp--${status} stamp--${size}${land ? " stamp--land" : ""}`}
      lang={lang}
      role="img"
      aria-label={t.stamp[status]}
    >
      {t.stamp[status]}
    </span>
  );
}

export function Chip({ status }: { status: StampKind }) {
  const { t } = useI18n();
  return <span className={`chip chip--${status}`}>{t.stamp[status]}</span>;
}

/** A section headed the way the bill heads its own sections: a solid bar, English with Urdu beside it. */
export function Section({ title, titleUr, children, id }: { title: string; titleUr?: string; children: ReactNode; id?: string }) {
  const { lang } = useI18n();
  return (
    <section className="block" aria-labelledby={id}>
      <h2 className="bar" id={id}>
        <span>{title}</span>
        {lang === "en" && titleUr ? (
          <span className="bar__ur" lang="ur" aria-hidden="true">
            {titleUr}
          </span>
        ) : null}
      </h2>
      <div className="panel">{children}</div>
    </section>
  );
}
