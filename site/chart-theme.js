// Shared Plotly theme for the case-study pages. Charts render when they scroll into view,
// so Plotly's work doesn't slow down the first paint on phones.
(function () {
  const COLORS = {
    violet: '#8c7cff', violetDim: '#3b3470', cyan: '#56d9ff', green: '#74df9b',
    amber: '#f3c26b', rose: '#ff8fa3', grey: '#6e6e78', ink: '#f5f5f7', muted: '#a6a6b0',
  };
  const FONT = 'Manrope, Inter, system-ui, -apple-system, sans-serif';
  const axis = {
    gridcolor: 'rgba(255,255,255,.06)', zerolinecolor: 'rgba(255,255,255,.14)',
    linecolor: 'rgba(255,255,255,.14)', tickfont: { color: COLORS.muted }, automargin: true,
    title: { font: { color: COLORS.muted, size: 12 } },
  };

  function merge(base, extra) {
    const out = { ...base };
    for (const [k, v] of Object.entries(extra || {})) {
      out[k] = v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object'
        ? merge(base[k], v) : v;
    }
    return out;
  }

  function layout(el, extra) {
    const narrow = el.clientWidth < 520;
    return merge({
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: FONT, color: COLORS.muted, size: narrow ? 11 : 12.5 },
      margin: { l: 8, r: 12, t: 8, b: 8, pad: 4 },
      // fresh copies: Plotly writes into layout objects (e.g. axis type), so sharing one
      // object between axes or charts turns numeric axes into categories
      xaxis: structuredClone(axis), yaxis: structuredClone(axis),
      legend: { orientation: 'h', x: 0, y: -0.18, font: { color: COLORS.muted, size: narrow ? 11 : 12 } },
      hoverlabel: { bgcolor: '#11121a', bordercolor: COLORS.violet, font: { family: FONT, color: COLORS.ink } },
      bargap: 0.32, bargroupgap: 0.12,
    }, extra);
  }

  const specs = {};
  function define(name, build) { specs[name] = build; }

  function render(el) {
    const build = specs[el.dataset.chart];
    if (!build || !window.Plotly) return;
    const { data, layout: extra } = build(el, COLORS);
    window.Plotly.newPlot(el, data, layout(el, extra), { displayModeBar: false, responsive: true });
  }

  function start() {
    const charts = document.querySelectorAll('.chart[data-chart]');
    if (!window.Plotly) {
      charts.forEach(el => { el.innerHTML = '<div class="chart-fallback">chart could not load</div>'; });
      return;
    }
    const io = new IntersectionObserver(entries => entries.forEach(e => {
      if (e.isIntersecting) { io.unobserve(e.target); render(e.target); }
    }), { rootMargin: '200px' });
    charts.forEach(el => io.observe(el));
  }

  window.Charts = { define, COLORS, start };
  document.addEventListener('DOMContentLoaded', () => setTimeout(start, 0));
})();
