/* Light / dark theme handling, shared across the portfolio.

   The reader's choice is remembered in localStorage. If they have never
   chosen, the page follows their operating system setting. A small script in
   the page head (see the inline snippet in each HTML file) applies the saved
   choice before first paint to avoid a flash; this file wires up the button
   and lets charts react. */

(function () {
  const root = document.documentElement;

  function current() {
    const set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function label() {
    const btn = document.getElementById("theme-btn");
    if (btn) btn.textContent = current() === "dark" ? "Light" : "Dark";
  }

  window.toggleTheme = function () {
    const next = current() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
    label();
    document.dispatchEvent(new CustomEvent("themechange", { detail: next }));
  };

  // Keep pages that are open while the OS theme changes in step, unless the
  // reader has made an explicit choice.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (!root.getAttribute("data-theme")) {
      label();
      document.dispatchEvent(new CustomEvent("themechange", { detail: current() }));
    }
  });

  document.addEventListener("DOMContentLoaded", label);
})();
