/* Dependency-free SVG charts: thin marks, hairline grid, hover tooltips, a legend only when there are
   two or more series. Same approach as the Smart Dukaan web edition, no Plotly. */
import { esc } from "./ui.js";

const registry = new Map();
let seq = 0;
const PRIMARY = () => getComputedStyle(document.documentElement).getPropertyValue("--primary").trim() || "#087F8C";
export const SERIES = () => [PRIMARY(), "#4C5FD5", "#C6862A", "#B9507A", "#5B7483", "#2F9E6B", "#E34948", "#6250D6"];
const compact = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + "M" : Math.abs(v) >= 1e3 ? Math.round(v / 1e3) + "K" : String(Math.round(v)));
const niceMax = (max) => { if (max <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(max))); const n = max / p; const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10; return step * p; };
const W = 720;

/** Line + area chart. series: [{label, values, color}], labels: x labels. */
export function lineAreaChart({ labels, series, height = 260, fmt = (v) => v.toLocaleString() }) {
  const id = `c${++seq}`; const H = height, padL = 48, padR = 12, padT = 12, padB = 28;
  const colors = SERIES(); const n = labels.length; const all = series.flatMap((s) => s.values);
  const max = niceMax(Math.max(...all, 1)); const x = (i) => padL + (n > 1 ? (i / (n - 1)) * (W - padL - padR) : (W - padL - padR) / 2);
  const y = (v) => padT + (1 - v / max) * (H - padT - padB);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const grid = ticks.map((v) => `<line class="grid-line" x1="${padL}" x2="${W - padR}" y1="${y(v)}" y2="${y(v)}"/><text x="${padL - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="#8CA0A8">${compact(v)}</text>`).join("");
  const every = Math.max(1, Math.ceil(n / 8));
  const xl = labels.map((l, i) => (i % every === 0 || i === n - 1) ? `<text x="${x(i)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#8CA0A8">${esc(l)}</text>` : "").join("");
  const paths = series.map((s, si) => {
    const c = s.color || colors[si]; if (!s.values.length) return "";
    const pts = s.values.map((v, i) => [x(i), y(v)]);
    const d = smooth(pts); const area = `${d} L ${pts[pts.length - 1][0]} ${y(0)} L ${pts[0][0]} ${y(0)} Z`;
    return `<path d="${area}" fill="${c}" opacity="0.10"/><path d="${d}" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");
  const dots = series.map((s, si) => s.values.map((v, i) => `<circle data-i="${i}" cx="${x(i)}" cy="${y(v)}" r="4" fill="${s.color || colors[si]}" stroke="#fff" stroke-width="2" opacity="0"/>`).join("")).join("");
  registry.set(id, { type: "line", labels, series: series.map((s, i) => ({ ...s, color: s.color || colors[i] })), x: (i) => x(i) / W, fmt });
  const legend = series.length > 1 ? `<div class="legend" style="margin-bottom:6px">${series.map((s, i) => `<span><i style="background:${s.color || colors[i]}"></i>${esc(s.label)}</span>`).join("")}</div>` : "";
  return `${legend}<div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="height:${H}px">${grid}${paths}<line class="cross" x1="0" x2="0" y1="${padT}" y2="${H - padB}" stroke="#CBD5DA" stroke-width="1" opacity="0"/>${dots}<g class="axis">${xl}</g></svg><div class="tip"></div></div>`;
}
function smooth(pts) {
  if (pts.length < 2) return pts.length ? `M ${pts[0][0]} ${pts[0][1]}` : "";
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) { const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2; const k = 0.18; d += ` C ${p1[0] + (p2[0] - p0[0]) * k} ${p1[1] + (p2[1] - p0[1]) * k}, ${p2[0] - (p3[0] - p1[0]) * k} ${p2[1] - (p3[1] - p1[1]) * k}, ${p2[0]} ${p2[1]}`; }
  return d;
}

/** Vertical columns. items: [{label, value}] */
export function columnChart({ items, height = 220, color, fmt = (v) => v.toLocaleString() }) {
  const id = `c${++seq}`; const H = height, padL = 48, padR = 8, padT = 10, padB = 26; const c = color || PRIMARY();
  const max = niceMax(Math.max(...items.map((i) => i.value), 1)); const n = items.length; const slot = (W - padL - padR) / Math.max(n, 1); const bw = Math.min(28, slot * 0.62);
  const y = (v) => padT + (1 - v / max) * (H - padT - padB);
  const grid = [0, 0.5, 1].map((f) => `<line class="grid-line" x1="${padL}" x2="${W - padR}" y1="${y(f * max)}" y2="${y(f * max)}"/><text x="${padL - 8}" y="${y(f * max) + 4}" text-anchor="end" font-size="11" fill="#8CA0A8">${compact(f * max)}</text>`).join("");
  const every = Math.max(1, Math.ceil(n / 10));
  const bars = items.map((it, i) => { const cx = padL + slot * i + slot / 2; const h = Math.max(0, y(0) - y(it.value)); return `<rect data-i="${i}" x="${cx - bw / 2}" y="${y(it.value)}" width="${bw}" height="${h}" rx="4" ry="4" fill="${c}"/>${i % every === 0 ? `<text x="${cx}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#8CA0A8">${esc(it.label)}</text>` : ""}`; }).join("");
  registry.set(id, { type: "col", items, fmt });
  return `<div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="height:${H}px">${grid}${bars}</svg><div class="tip"></div></div>`;
}

/** Grouped columns. items: [{label, values:[..]}], series: ["Completed","Cancelled"] */
export function groupedColumnChart({ items, series, height = 260, colors: cs, fmt = (v) => v.toLocaleString() }) {
  const id = `c${++seq}`; const H = height, padL = 48, padR = 8, padT = 10, padB = 26; const colors = cs || SERIES();
  const max = niceMax(Math.max(...items.flatMap((i) => i.values), 1)); const n = items.length; const slot = (W - padL - padR) / Math.max(n, 1);
  const k = series.length; const gw = Math.min(slot * 0.7, 18 * k + 4 * (k - 1)); const bw = (gw - 3 * (k - 1)) / k;
  const y = (v) => padT + (1 - v / max) * (H - padT - padB);
  const grid = [0, 0.5, 1].map((f) => `<line class="grid-line" x1="${padL}" x2="${W - padR}" y1="${y(f * max)}" y2="${y(f * max)}"/><text x="${padL - 8}" y="${y(f * max) + 4}" text-anchor="end" font-size="11" fill="#8CA0A8">${compact(f * max)}</text>`).join("");
  const every = Math.max(1, Math.ceil(n / 10));
  const bars = items.map((it, i) => { const cx = padL + slot * i + slot / 2; const x0 = cx - gw / 2; return it.values.map((v, j) => `<rect data-i="${i}" x="${x0 + j * (bw + 3)}" y="${y(v)}" width="${bw}" height="${Math.max(0, y(0) - y(v))}" rx="3" ry="3" fill="${colors[j]}"/>`).join("") + (i % every === 0 ? `<text x="${cx}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#8CA0A8">${esc(it.label)}</text>` : ""); }).join("");
  registry.set(id, { type: "group", items, series, colors, fmt });
  const legend = `<div class="legend" style="margin-bottom:6px">${series.map((s, i) => `<span><i style="background:${colors[i]}"></i>${esc(s)}</span>`).join("")}</div>`;
  return `${legend}<div class="chart" data-chart="${id}"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="height:${H}px">${grid}${bars}</svg><div class="tip"></div></div>`;
}

/** Horizontal bars with labels. items: [{label, value, sub}] */
export function hbarChart({ items, color, fmt = (v) => v.toLocaleString() }) {
  const c = color || PRIMARY(); const max = Math.max(...items.map((i) => i.value), 1);
  if (!items.length) return "";
  return `<div class="list">${items.map((it) => `<div class="row" style="padding:8px 2px"><div class="body"><div class="title" style="font-weight:500">${esc(it.label)}</div><div class="bar"><i style="width:${(it.value / max * 100).toFixed(0)}%;background:${c}"></i></div></div><div class="end"><div class="v num">${esc(fmt(it.value))}</div>${it.sub ? `<div class="s">${esc(it.sub)}</div>` : ""}</div></div>`).join("")}</div>`;
}

/** Donut with legend. items: [{label, value}] (top 6, rest folded into Other). */
export function donutChart({ items, fmt = (v) => v.toLocaleString(), otherLabel = "Other" }) {
  const colors = SERIES(); let list = items.slice().sort((a, b) => b.value - a.value);
  if (list.length > 6) { const other = list.slice(5).reduce((s, i) => s + i.value, 0); list = [...list.slice(0, 5), { label: otherLabel, value: other }]; }
  const total = list.reduce((s, i) => s + i.value, 0) || 1; const R = 46, r = 30, C = 2 * Math.PI * R; let off = 0;
  const arcs = list.map((it, i) => { const len = (it.value / total) * C; const seg = `<circle r="${R}" cx="60" cy="60" fill="none" stroke="${colors[i]}" stroke-width="${R - r}" stroke-dasharray="${Math.max(0, len - 1.5)} ${C - Math.max(0, len - 1.5)}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"><title>${esc(it.label)}: ${esc(fmt(it.value))} (${Math.round(it.value / total * 100)}%)</title></circle>`; off += len; return seg; }).join("");
  const legend = list.map((it, i) => `<div><span><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${colors[i]}"></i>${esc(it.label)}</span><b class="num">${esc(fmt(it.value))} <span class="faint">${Math.round(it.value / total * 100)}%</span></b></div>`).join("");
  return `<div class="donut-wrap"><svg viewBox="0 0 120 120">${arcs}</svg><div class="donut-legend">${legend}</div></div>`;
}

/** Attach hover tooltips to every chart rendered inside root. */
export function mountCharts(root) {
  root.querySelectorAll(".chart[data-chart]").forEach((el) => {
    const data = registry.get(el.dataset.chart); if (!data) return;
    const tip = el.querySelector(".tip"); const svg = el.querySelector("svg");
    const show = (i, px) => {
      if (data.type === "line") {
        const lines = data.series.map((s) => `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${s.color};margin-right:6px"></span>${esc(s.label)}: <b>${esc(data.fmt(s.values[i] ?? 0))}</b></div>`).join("");
        tip.innerHTML = `<div style="opacity:.75;margin-bottom:2px">${esc(data.labels[i])}</div>${lines}`;
        svg.querySelectorAll("circle[data-i]").forEach((c) => { c.setAttribute("opacity", c.dataset.i == i ? "1" : "0"); });
        const cross = svg.querySelector(".cross"); const xp = data.x(i) * W; cross.setAttribute("x1", xp); cross.setAttribute("x2", xp); cross.setAttribute("opacity", "1");
        tip.style.left = `${data.x(i) * el.clientWidth}px`; tip.style.top = "0px";
      } else if (data.type === "group") {
        const it = data.items[i]; tip.innerHTML = `<div style="opacity:.75">${esc(it.label)}</div>` + data.series.map((s, j) => `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${data.colors[j]};margin-right:6px"></span>${esc(s)}: <b>${esc(data.fmt(it.values[j]))}</b></div>`).join("");
        tip.style.left = `${px}px`; tip.style.top = "0px";
      } else {
        const it = data.items[i]; tip.innerHTML = `<div style="opacity:.75">${esc(it.label)}</div><b>${esc(data.fmt(it.value))}</b>`;
        tip.style.left = `${px}px`; tip.style.top = "0px";
      }
      tip.classList.add("show");
    };
    const hide = () => { tip.classList.remove("show"); svg.querySelectorAll("circle[data-i]").forEach((c) => c.setAttribute("opacity", "0")); const cr = svg.querySelector(".cross"); if (cr) cr.setAttribute("opacity", "0"); };
    const onMove = (e) => {
      const rect = svg.getBoundingClientRect(); let px = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left; let rel = px / rect.width;
      if (document.documentElement.dir === "rtl") { /* svg keeps ltr geometry; nothing to flip */ }
      if (data.type === "line") { const n = data.labels.length; const i = Math.max(0, Math.min(n - 1, Math.round(((rel * W) - 48) / (W - 60) * (n - 1)))); show(i, px); }
      else { const n = data.items.length; const i = Math.max(0, Math.min(n - 1, Math.floor(((rel * W) - 48) / (W - 56) * n))); show(i, px); }
    };
    svg.addEventListener("mousemove", onMove); svg.addEventListener("touchstart", onMove, { passive: true }); svg.addEventListener("touchmove", onMove, { passive: true });
    svg.addEventListener("mouseleave", hide); svg.addEventListener("touchend", hide);
  });
}
