import { StrictMode, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "@fontsource/atkinson-hyperlegible-next/400.css";
import "@fontsource/atkinson-hyperlegible-next/700.css";
import "@fontsource/noto-nastaliq-urdu/400.css";
import "@fontsource/noto-nastaliq-urdu/700.css";
import "./styles/tokens.css";
import "./styles/app.css";
import { I18nProvider } from "./i18n";
import { Shell } from "./components/Shell";
import Home from "./pages/Home";

const Check = lazy(() => import("./pages/Check"));
const Report = lazy(() => import("./pages/Report"));
const How = lazy(() => import("./pages/How"));

const wrap = (el: JSX.Element) => <Suspense fallback={<div className="page" />}>{el}</Suspense>;

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/check", element: wrap(<Check />) },
      { path: "/r/:id", element: wrap(<Report />) },
      { path: "/how", element: wrap(<How />) },
      { path: "*", element: <Home /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <RouterProvider router={router} />
    </I18nProvider>
  </StrictMode>,
);

// Installable app: register the service worker in production builds only (it caches the app shell, never /api/).
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* the app works without it */
    });
  });
}
