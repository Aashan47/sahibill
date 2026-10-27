const $ = (s) => document.querySelector(s);
const MARKS = {
  problem_found: '<path d="M9 9 C16 15 24 24 31 32"/><path d="M31 8 C24 16 16 24 9 31"/>',
  cannot_be_determined: '<path d="M13 13 C13 6 27 5 27 13 C27 19 20 19 20 25"/><path d="M20 32 L20.5 32.5"/>',
  looks_right: '<path d="M8 21 C12 24 15 28 17 31 C21 22 26 14 33 8"/>',
};
const SAMPLE_NAMES = {"sample-detection.jpg": "Detection bill", "sample-months.jpg": "Months in one bill",
                      "sample-protected.jpg": "Protected status", "sample-snapshot.jpg": "Meter snapshot"};

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k === "lang") e.lang = v; else e.setAttribute(k, v);
  }
  if (text !== undefined) e.textContent = text;
  return e;
}

function show(id) {
  for (const s of ["ask", "working", "result"]) $("#" + s).hidden = s !== id;
  window.scrollTo({ top: 0 });
}

async function loadSamples() {
  const list = await (await fetch("/api/samples")).json();
  const box = $("#sample-list");
  for (const s of list) {
    const b = el("button", { class: "sample", type: "button" });
    const img = el("img", { src: s.url, alt: "Synthetic sample bill: " + (SAMPLE_NAMES[s.name] || s.name), loading: "lazy" });
    b.append(img, el("span", {}, SAMPLE_NAMES[s.name] || "Sample"));
    b.addEventListener("click", () => run(fetch(`/api/check/sample/${encodeURIComponent(s.name)}`, { method: "POST" }), s.url, "Synthetic sample bill"));
    box.append(b);
  }
}

async function run(request, imgUrl, caption) {
  show("working");
  let data;
  try {
    const r = await request;
    data = await r.json();
    if (!r.ok && !data.error) data = { ok: false, error: "The check did not complete. Try again." };
  } catch (e) {
    data = { ok: false, error: "The server could not be reached. Check the connection and try again." };
  }
  render(data, imgUrl, caption);
}

function reqList(ul, items) {
  ul.replaceChildren();
  for (const r of items || []) {
    const li = el("li");
    li.append(el("p", { class: "req-en" }, r.en));
    if (r.ur) li.append(el("p", { class: "ur req-ur", lang: "ur" }, r.ur));
    if (r.clause) li.append(el("p", { class: "req-clause" }, r.clause));
    ul.append(li);
  }
  ul.closest("section").hidden = !(items && items.length);
}

function render(d, imgUrl, caption) {
  show("result");
  $("#bill-img").src = imgUrl;
  $("#bill-cap").textContent = caption + (d.rotated ? `. The photo was turned ${d.rotated} degrees and read again.` : "");
  const slip = $("#slip");
  const lines = $("#lines");
  lines.replaceChildren();
  document.querySelectorAll(".error").forEach((e) => e.remove());
  if (!d.ok) {
    $("#headline").textContent = "This bill could not be checked.";
    $("#headline-ur").textContent = "اس بل کی جانچ نہیں ہو سکی۔";
    $("#tally").textContent = "";
    const err = el("p", { class: "error" }, d.error);
    slip.after(err);
    for (const id of ["#ask-utility", "#retake", "#questions", "#limits"]) $(id).hidden = true;
    return;
  }
  const v = d.verdict;
  $("#headline").textContent = v.headline;
  $("#headline-ur").textContent = v.headline_ur;
  const c = v.counts;
  $("#tally").textContent = `${c.problem} problem${c.problem === 1 ? "" : "s"}, ${c.cannot_be_determined} open, ${c.looks_right} look right. Each line names the rule it comes from.`;
  v.cards.forEach((card, i) => {
    const li = el("li", { class: "line " + card.status });
    li.style.animationDelay = `${Math.min(i, 14) * 70}ms`;
    const svg = `<svg class="mark-sym" viewBox="0 0 40 40" role="img" aria-label="${card.status_text}">${MARKS[card.status]}</svg>`;
    const left = el("div"); left.innerHTML = svg;
    const body = el("div");
    const head = el("div", { class: "line-head" });
    head.append(el("span", { class: "line-title" }, card.title), el("span", { class: "line-status" }, card.status_text));
    body.append(head, el("p", { class: "ur line-ur", lang: "ur" }, card.title_ur + " : " + card.status_ur));
    for (const t of card.lines) body.append(el("p", { class: "line-text" }, t));
    if (card.status === "problem_found") for (const t of card.lines_ur || []) body.append(el("p", { class: "ur line-ur", lang: "ur" }, t));
    if (card.clauses.length) body.append(el("p", { class: "line-clause" }, card.clauses.join("; ")));
    li.append(left, body);
    lines.append(li);
  });
  slip.classList.remove("printing"); void slip.offsetWidth; slip.classList.add("printing");
  const comp = d.complaint;
  window.__letter = comp;
  $("#complaint").hidden = !(comp && comp.problem_count);
  setLetter("en");
  const ns = d.next_steps || {};
  reqList($("#utility-list"), ns.utility);
  reqList($("#retake-list"), ns.retake);
  reqList($("#question-list"), ns.user);
  reqList($("#limit-list"), ns.limit);
  const tb = $("#read-table tbody");
  tb.replaceChildren();
  for (const f of d.reading || []) {
    if (f.value === null && !f.held) continue;
    const tr = el("tr");
    tr.append(el("td", {}, f.label));
    const td = el("td", {}, f.held ? "Held: " + f.held : String(f.value));
    if (f.held) td.className = "held";
    tr.append(td);
    tb.append(tr);
  }
}

$("#photo").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("photo", file);
  run(fetch("/api/check", { method: "POST", body: fd }), URL.createObjectURL(file), "Your bill");
  e.target.value = "";
});
function setLetter(lang) {
  const comp = window.__letter;
  if (!comp) return;
  const box = $("#letter");
  box.textContent = comp[lang];
  box.className = "letter" + (lang === "ur" ? " ur" : "");
  if (lang === "ur") box.lang = "ur"; else box.removeAttribute("lang");
  document.querySelectorAll(".letter-tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.lang === lang)));
}
document.querySelectorAll(".letter-tabs button").forEach((b) => b.addEventListener("click", () => setLetter(b.dataset.lang)));
$("#copy-letter").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($("#letter").textContent); $("#copy-letter").textContent = "Copied"; }
  catch (e) { $("#copy-letter").textContent = "Select the text and copy it"; }
  setTimeout(() => { $("#copy-letter").textContent = "Copy the letter"; }, 2000);
});
$("#again").addEventListener("click", () => show("ask"));
loadSamples();
