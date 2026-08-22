const JAM = 12;
const ACCENT = '#d97757', MUTED = 'rgba(242,240,237,.46)', LINE = 'rgba(255,255,255,.09)';

const HL = { bgcolor: '#20201f', bordercolor: LINE, font: { color: '#f2f0ed' } };

const LAYOUT = {
  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
  font: { family: 'Source Serif 4, Georgia, serif', color: MUTED, size: 11 },
  margin: { l: 44, r: 12, t: 8, b: 36 },
  xaxis: { gridcolor: LINE, zerolinecolor: LINE, linecolor: LINE, automargin: true },
  yaxis: { gridcolor: LINE, zerolinecolor: LINE, linecolor: LINE, automargin: true },
  showlegend: false, hoverlabel: HL,
};
const CFG = { displayModeBar: false, responsive: true };

const $ = id => document.getElementById(id);
const dm = d => `${d.slice(8, 10)}.${d.slice(5, 7)}`;   // 2026-08-06 -> 06.08
const CAT = { xaxis: { type: 'category' } };
const fmt = n => n == null ? '—' : Math.round(n).toLocaleString('ru-RU');
const draw = (id, traces, extra = {}) =>
  Plotly.newPlot($(id), traces, { ...LAYOUT, ...extra, xaxis: { ...LAYOUT.xaxis, ...extra.xaxis }, yaxis: { ...LAYOUT.yaxis, ...extra.yaxis } }, CFG);

/** Ключи вида "tech.engines.Unity" -> {Unity: 45}, отсортированные по убыванию. */
function pick(m, prefix, { sort = true, limit = 0 } = {}) {
  let e = Object.entries(m).filter(([k]) => k.startsWith(prefix + '.'))
    .map(([k, v]) => [k.slice(prefix.length + 1), v]);
  if (sort) e.sort((a, b) => b[1] - a[1]);
  else e.sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }));
  return limit ? e.slice(0, limit) : e;
}

// unit — слово в подсказке; <extra></extra> убирает плашку с названием серии
const bars = (e, { h = false, unit = '' } = {}) => h
  ? [{ type: 'bar', orientation: 'h', y: e.map(x => x[0]).reverse(), x: e.map(x => x[1]).reverse(),
       marker: { color: ACCENT }, hovertemplate: `%{y} · %{x} ${unit}<extra></extra>` }]
  : [{ type: 'bar', x: e.map(x => x[0]), y: e.map(x => x[1]),
       marker: { color: ACCENT }, hovertemplate: `%{x} · %{y} ${unit}<extra></extra>` }];

let STATE = { games: [], mine: localStorage.getItem('my_game') || '', trend: null,
              topN: 10, topLb: 10, topWorks: 10, sort: { key: null, dir: -1 } };

const cut = (arr, n) => n ? arr.slice(0, n) : arr;
const val = (g, k) => g.metrics[k] ?? null;

/** Приглушённая палитра для множества линий: наша работа всегда акцентом. */
const lineColor = i => `hsl(${(18 + i * 137.5) % 360} 42% 62%)`;

// ts от сервера в UTC, а сутки джема — московские; сдвигаем перед тем, как резать дату
const mskDate = ts => new Date(new Date(ts).getTime() + 3 * 3600e3).toISOString().slice(0, 10);

/** Ряд метрики -> {дата по МСК: последнее значение за день}. */
const byDay = pts => {
  const m = new Map();
  pts.forEach(p => m.set(mskDate(p.ts), p.value));
  return m;
};

async function load() {
  const [info, latest, games, trend, dl] = await Promise.all([
    fetch(`/api/jam/${JAM}/info`).then(r => r.json()),
    fetch(`/api/jam/${JAM}/latest`).then(r => r.json()),
    fetch('/api/games').then(r => r.json()),
    fetch('/api/games/series?key=jam_points').then(r => r.json()),
    fetch(`/api/jam/${JAM}/downloads_daily`).then(r => r.json()),
  ]);
  // очков на голос = очки джема, делённые на число голосовавших за работу
  games.forEach(g => {
    if (g.metrics.jam_voters) g.metrics.avg_points = g.metrics.jam_points / g.metrics.jam_voters;
  });
  STATE.games = games;
  STATE.trend = trend;
  STATE.dl = dl;
  render(info, latest, games);
}

function render(info, m, games) {
  $('sub').textContent = `${games.length} работ · данные на ${new Date(info.date_up).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' }) + ' МСК'}`;
  countdown(info.voting_end);

  // скачивания считаем сами по работам: в API это события, их в разы больше
  const dl = games.map(g => g.metrics.downloads).filter(v => v != null);
  kpis([
    ['Работы', m['overview.builds_approved']],
    ['Проголосовавшие', m['activity.voters_total']],
    ['Очки', m['vote.points_total']],
    ['Скачивания', dl.reduce((a, b) => a + b, 0)],
  ]);

  const vd = pick(m, 'activity.votes_by_day', { sort: false });
  const votes = vd.filter(([k]) => k.endsWith('.votes'));
  const voters = vd.filter(([k]) => k.endsWith('.voters'));
  draw('ch-votes', [
    { type: 'bar', x: votes.map(x => dm(x[0].split('.')[0])), y: votes.map(x => x[1]), name: 'голоса',
      marker: { color: ACCENT }, hovertemplate: '%{x} · %{y} голосов<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: voters.map(x => dm(x[0].split('.')[0])), y: voters.map(x => x[1]),
      name: 'голосующие', line: { color: '#f2f0ed', width: 1.5 },
      hovertemplate: '%{x} · %{y} человек<extra></extra>' },
  ], CAT);
  drawDownloads();

  draw('ch-engines', bars(pick(m, 'tech.engines', { limit: 8 }), { h: true, unit: 'работ' }), { margin: { l: 110, r: 12, t: 8, b: 30 } });
  draw('ch-genres', bars(pick(m, 'tech.genres', { limit: 8 }), { h: true, unit: 'работ' }), { margin: { l: 130, r: 12, t: 8, b: 30 } });
  draw('ch-geo', bars(pick(m, 'geo.top', { limit: 10 }), { h: true, unit: 'человек' }), { margin: { l: 120, r: 12, t: 8, b: 30 } });
  // порядок ведёр задаём явно: по имени ключа он выходит неверным
  const BUCKETS = [['lt_100mb', '<100 МБ'], ['100_300mb', '100–300 МБ'], ['300mb_1gb', '300 МБ – 1 ГБ'], ['gt_1gb', '>1 ГБ']];
  const bk = Object.fromEntries(pick(m, 'builds.buckets', { sort: false }));
  draw('ch-buckets', bars(BUCKETS.filter(([k]) => bk[k] != null).map(([k, l]) => [l, bk[k]]), { unit: 'работ' }),
    { xaxis: { tickangle: -25 }, bargap: .3 });
  draw('ch-teams', bars(pick(m, 'teams.size_histogram', { sort: false }).map(([k, v]) => [k + ' чел.', v]), { unit: 'команд' }));
  draw('ch-uploads', bars(pick(m, 'timeline.uploads_by_day', { sort: false }).map(([k, v]) => [dm(k), v]), { unit: 'билдов' }), CAT);

  fillGames(games);
}

function kpis(items) {
  $('kpis').innerHTML = items.map(([lbl, v, hint]) =>
    `<div class="kpi"><div class="val">${fmt(v)}</div><div class="lbl">${lbl}</div>` +
    (hint ? `<div class="delta">${hint}</div>` : '') + '</div>').join('');
}

function countdown(end) {
  if (!end) return;
  const target = new Date(end.replace(' ', 'T') + '+03:00');
  const tick = () => {
    const ms = target - new Date();
    if (ms <= 0) { $('cd').textContent = 'завершено'; return; }
    const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24,
          mi = Math.floor(ms / 6e4) % 60, s = Math.floor(ms / 1e3) % 60;
    $('cd').textContent = `${d} д ${h} ч ${mi} м ${String(s).padStart(2, '0')} с`;
  };
  tick(); setInterval(tick, 1000);
}

function fillGames(games) {
  const sel = $('mine');
  sel.innerHTML = '<option value="">— не выбрана —</option>' +
    games.map(g => `<option value="${g.game_id}">${g.title}</option>`).join('');
  sel.value = STATE.mine;
  sel.onchange = () => { STATE.mine = sel.value; localStorage.setItem('my_game', sel.value); paintGames(); };
  paintGames();
}

function paintGames() {
  const games = STATE.games, mine = Number(STATE.mine);

  // все топы работают по очкам джема; наша работа показывается всегда
  const shown = cut([...games].sort((a, b) => (val(b, 'jam_points') || 0) - (val(a, 'jam_points') || 0)),
                    STATE.topWorks);

  scatter('ch-votes-avgpts', shown, mine, {
    xKey: 'jam_voters', xTitle: 'голосов', xUnit: 'голос.',
    yKey: 'avg_points', sizeKey: 'jam_points', sizeMul: .04, yTitle: 'средние очки',
    label: g => `${val(g, 'avg_points').toFixed(1)} очк. на голос · ${fmt(val(g, 'jam_points'))} очк. всего`,
  });
  scatter('ch-reviews-rating', shown, mine, {
    xKey: 'ratings_count', xTitle: 'отзывов', xUnit: 'отзывов',
    yKey: 'rating_avg', sizeKey: 'downloads', sizeMul: .04, yTitle: 'оценка',
    label: g => `${val(g, 'rating_avg')}/10 · ${fmt(val(g, 'downloads'))} скач.`,
  });
  scatter('ch-scatter', shown, mine, {
    xKey: 'downloads', xTitle: 'скачивания', xUnit: 'скач.',
    yKey: 'rating_avg', sizeKey: 'ratings_count', sizeMul: .6, yTitle: 'оценка',
    label: g => `${val(g, 'rating_avg')}/10 · ${fmt(val(g, 'ratings_count'))} отзывов`,
  });
  scatter('ch-avgpts', shown, mine, {
    xKey: 'downloads', xTitle: 'скачивания', xUnit: 'скач.',
    yKey: 'avg_points', sizeKey: 'jam_voters', sizeMul: .35, yTitle: 'средние очки',
    label: g => `${val(g, 'avg_points').toFixed(1)} очк. на голос · ${fmt(val(g, 'jam_voters'))} голос.`,
  });

  const hasLb = games.some(g => val(g, 'jam_points') != null);
  $('sec-lb').hidden = !hasLb;
  if (hasLb) { drawLb(); drawTrend(); }

  const cols = [
    ['game_id', 'ID', true], ['title', 'Работа', false], ['genre', 'Жанр', false],
    ...(hasLb ? [['jam_points', 'Очки', true], ['jam_voters', 'Голосов', true],
                 ['avg_points', 'Ср. очки', true]] : []),
    ['downloads', 'Скач.', true],
    ['rating_avg', 'Оценка', true], ['ratings_count', 'Отзывов', true], ['build_bytes', 'Размер', true],
  ];
  const sKey = STATE.sort.key || (hasLb ? 'jam_points' : 'downloads');
  const dir = STATE.sort.key ? STATE.sort.dir : -1;
  const raw = (g, k) => g.metrics[k] ?? g[k] ?? null;
  const sorted = [...games].sort((a, b) => {
    const x = raw(a, sKey), y = raw(b, sKey);
    if (typeof x === 'string' || typeof y === 'string')
      return dir * String(x ?? '').localeCompare(String(y ?? ''), 'ru');
    return dir * ((x ?? -Infinity) - (y ?? -Infinity));
  });
  const cell = (g, k) => {
    if (k === 'build_bytes') { const v = val(g, k); return v ? (v / 1024 ** 2 > 1024 ? (v / 1024 ** 3).toFixed(1) + ' ГБ' : Math.round(v / 1024 ** 2) + ' МБ') : '—'; }
    if (k === 'avg_points') { const v = val(g, k); return v == null ? '—' : v.toFixed(1); }
    if (['downloads', 'rating_avg', 'ratings_count', 'jam_points', 'jam_voters'].includes(k)) {
      const v = val(g, k); return v == null ? '—' : (k === 'rating_avg' ? v : fmt(v));
    }
    if (k === 'title') return `<a href="https://dustore.ru/g/${g.game_id}" target="_blank" rel="noopener" style="color:inherit">${g[k]}</a>`;
    return g[k] ?? '—';
  };
  const arrow = k => k === sKey ? (dir < 0 ? ' ↓' : ' ↑') : '';
  $('tbl').innerHTML =
    `<thead><tr>${cols.map(([k, l, n]) =>
      `<th class="${n ? 'num' : ''}${k === sKey ? ' on' : ''}" data-k="${k}">${l}${arrow(k)}</th>`).join('')}</tr></thead>` +
    `<tbody>${sorted.map(g => `<tr class="${g.game_id === mine ? 'mine' : ''}">` +
      cols.map(([k, , n]) => `<td class="${n ? 'num' : ''}">${cell(g, k)}</td>`).join('') + '</tr>').join('')}</tbody>`;

  $('tbl').querySelectorAll('th').forEach(th => th.onclick = () => sortBy(th.dataset.k));
}

function sortBy(k) {
  const s = STATE.sort;
  // повторный клик по той же колонке переворачивает порядок
  s.dir = s.key === k ? -s.dir : (['title', 'studio', 'genre'].includes(k) ? 1 : -1);
  s.key = k;
  paintGames();
}

/** Диаграмма «метрика × метрика»: серые точки и наша работа акцентом. */
function scatter(id, list, mine, { xKey, xTitle, xUnit, yKey, sizeKey, sizeMul, yTitle, label }) {
  const ok = list.filter(g => val(g, yKey) != null && val(g, xKey) != null);
  const trace = (gs, color, ring) => ({
    type: 'scatter', mode: 'markers', hoverinfo: 'text',
    x: gs.map(g => val(g, xKey)), y: gs.map(g => val(g, yKey)),
    text: gs.map(g => `${g.title}<br>${fmt(val(g, xKey))} ${xUnit} · ${label(g)}`),
    marker: { color, opacity: .85, line: { width: ring ? 2 : 0, color: '#151515' },
              size: gs.map(g => Math.min(26, 7 + (val(g, sizeKey) || 0) * sizeMul)) },
  });
  const traces = [trace(ok.filter(g => g.game_id !== mine), 'rgba(242,240,237,.45)')];
  const me = ok.find(g => g.game_id === mine);
  if (me) traces.push(trace([me], ACCENT, true));
  draw(id, traces, {
    xaxis: { title: { text: xTitle, font: { size: 10 } } },
    yaxis: { title: { text: yTitle, font: { size: 10 } }, range: [0, 10.5] },
  });
}

/** Свой ряд скачиваний: прирост за день по счётчикам работ. */
function drawDownloads() {
  const rows = STATE.dl || [];
  draw('ch-dl', bars(rows.map(r => [dm(r.date), r.delta]), { unit: 'скачиваний' }), CAT);
}

/** Горизонтальные бары: очки топ-N работ. */
function drawLb() {
  const mine = Number(STATE.mine), n = STATE.topLb;
  const ranked = STATE.games.filter(g => val(g, 'jam_points') != null)
    .sort((a, b) => val(b, 'jam_points') - val(a, 'jam_points'));
  const top = cut(ranked, n).reverse();
  $('lb-title').textContent = `Очки по работам, ${n ? 'топ-' + n : 'все'}`;
  draw('ch-lb', [{
    type: 'bar', orientation: 'h',
    y: top.map(g => g.title.length > 26 ? g.title.slice(0, 25) + '…' : g.title),
    x: top.map(g => val(g, 'jam_points')),
    text: top.map(g => `${fmt(val(g, 'jam_points'))} очк. · ${fmt(val(g, 'jam_voters'))} гол.`),
    textposition: 'auto', insidetextanchor: 'end', cliponaxis: false,
    textfont: { color: '#151515', size: 10 }, outsidetextfont: { color: '#f2f0ed', size: 10 },
    hovertemplate: '%{y}<br>%{text}<extra></extra>',
    hoverlabel: HL,
    marker: { color: ACCENT, line: { color: '#f2f0ed', width: top.map(g => g.game_id === mine ? 2 : 0) } },
  }], { margin: { l: 180, r: 60, t: 8, b: 30 }, bargap: .35 });
}

/** Линии очков по дням для топ-N работ. */
function drawTrend() {
  const series = STATE.trend || {};
  const mine = Number(STATE.mine);
  const ranked = Object.entries(series)
    .map(([gid, pts]) => ({ gid: Number(gid), day: byDay(pts) }))
    .map(s => ({ ...s, last: [...s.day.values()].pop() ?? 0 }))
    .sort((a, b) => b.last - a.last);
  const shown = cut(ranked, STATE.topN);

  const days = [...new Set(shown.flatMap(s => [...s.day.keys()]))].sort();
  const title = gid => (STATE.games.find(g => g.game_id === gid) || {}).title || `#${gid}`;

  const traces = shown.map((s, i) => {
    let carry = null;
    return {
      type: 'scatter', mode: days.length > 1 ? 'lines' : 'lines+markers',
      x: days.map(dm), y: days.map(d => (carry = s.day.get(d) ?? carry)),
      name: title(s.gid),
      // имя внутри подсказки, пустой <extra> убирает второй бокс с заливкой
      hovertemplate: `<b>${title(s.gid)}</b><br>%{y} очк. · %{x}<extra></extra>`,
      line: { color: s.gid === mine ? ACCENT : lineColor(i), width: s.gid === mine ? 3 : 1.6 },
      hoverlabel: HL,
    };
  });

  draw('ch-trend', traces, {
    showlegend: true, xaxis: { type: 'category' },
    legend: { orientation: 'h', y: -0.18, font: { size: 10 } },
    margin: { l: 44, r: 12, t: 8, b: 60 },
  });
}

const TOPS = [5, 10, 20, 50, 0];  // 0 — все

/** Рисует переключатель топ-N и вешает обработчик. */
function mkSeg(id, current, apply) {
  const el = $(id);
  el.innerHTML = TOPS.map(n =>
    `<button data-n="${n}" class="${n === current ? 'on' : ''}">${n ? 'топ-' + n : 'все'}</button>`).join('');
  el.onclick = e => {
    const b = e.target.closest('button');
    if (!b) return;
    [...el.children].forEach(x => x.classList.toggle('on', x === b));
    apply(Number(b.dataset.n));
  };
}

mkSeg('seg-top', STATE.topN, n => { STATE.topN = n; drawTrend(); });
mkSeg('seg-lb', STATE.topLb, n => { STATE.topLb = n; drawLb(); });
mkSeg('seg-works', STATE.topWorks, n => { STATE.topWorks = n; paintGames(); });

load();
