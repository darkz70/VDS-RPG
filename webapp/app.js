/* VDS RPG : Между Мирами — клиент мини-аппа (совместим со старым WebView) */

try { history.replaceState(null, "", location.pathname + location.search); } catch (e0) {}

var tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
if (tg) {
  tg.expand();
  if (tg.ready) tg.ready();
  try { if (tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (e) {}
}
var INIT_DATA = tg ? tg.initData : "tg_id=1&first_name=Dev";

var STATE = null;     // state игрока
var META = null;      // константы
var IS_ADMIN = false; // админ-флаг
var MAINT = false;    // техперерыв
var TAB = "menu";     // текущий экран: menu|map|chars|shop|brew|profile|admin|battle
var MAP_CHAPTER = 1;  // выбранная глава на карте
var BATTLE = null;    // сессия боя
var BATTLE_TARGET = 0;
var STANCE = {};      // char_id -> "attack"|"defend"

function charFaceFor(c) {
  if (!c) return "🦸";
  if (c.face) return c.face;
  var key = c.key || "";
  var cat = (META && META.characters) || [];
  for (var i = 0; i < cat.length; i++) { if (cat[i].key === key) return cat[i].face || "🦸"; }
  return "🦸";
}

var IC_DARK = '<img class="ic" src="/app/img/darkness.png" alt="">';
var IC_EGEZ = '<img class="ic" src="/app/img/egez.png" alt="">';

function $(sel) { return document.querySelector(sel); }
var screen = $("#screen");

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
}
function fmt(n) { return Number(n || 0).toLocaleString("ru-RU"); }
function toast(msg) {
  var t = $("#toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._h);
  t._h = setTimeout(function () { t.classList.add("hidden"); }, 2600);
}
function api(path, body) {
  body = body || {};
  var payload = { initData: INIT_DATA };
  for (var k in body) payload[k] = body[k];
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(function (r) { return r.json(); });
}

/* ── Чипы ── */
function renderChip() {
  if (!STATE) return;
  $("#tb-name").textContent = STATE.name || "";
  var lv = $("#tb-level");
  lv.textContent = "⭐ " + (STATE.level || 1);
  lv.className = "tb-chip star";
  var d = $("#tb-dark");
  d.innerHTML = IC_DARK + " " + fmt(STATE.darkness);
  d.className = "tb-chip dark";
  var e = $("#tb-egez");
  e.innerHTML = IC_EGEZ + " " + fmt(STATE.egez);
  e.className = "tb-chip egez";
}

/* ── Оверлей меню (3 точки / жест) ── */
function openMenu() { $("#menu_overlay").classList.remove("hidden"); }
function closeMenu(ev) {
  ev = ev || event;
  if (ev && ev.stopPropagation) ev.stopPropagation();
  var o = $("#menu_overlay");
  if (o) o.classList.add("hidden");
}
$("#menu_overlay").addEventListener("click", function (e) {
  if (e.target === this) this.classList.add("hidden");
});
function tryFullscreen() {
  try { if (tg && tg.requestFullscreen) tg.requestFullscreen(); } catch (e) {}
  try { if (tg && tg.lockOrientation) tg.lockOrientation("landscape"); } catch (e) {}
}
function goMenu()   { TAB = "menu";    render(); }
function goChars()  { TAB = "chars";   render(); }
function goShop()   { TAB = "shop";    render(); }
function goInv()    { TAB = "brew";    render(); }
function goProfile(){ TAB = "profile"; render(); }
function goAdmin()  { TAB = "admin";   render(); }
function goBattle() { TAB = "map";     render(); }

/* ── Главное меню ── */
async function renderMap() {
  var r = await api("/api/campaign", { chapter: MAP_CHAPTER });
  if (r.ok) {
    var next = r.next;
    var team = STATE.team || [];
    var hero = null;
    (STATE.characters || []).forEach(function (c) { if (c.id === team[0]) hero = c; });
    screen.innerHTML =
      '<div class="bsm">' +
        '<div class="col">' +
          '<button class="sq" onclick="TAB=\'chars\';render()">🎭<span>Персы</span></button>' +
          '<button class="sq" onclick="TAB=\'shop\';render()">🛒<span>Магазин</span></button>' +
          '<button class="sq" onclick="TAB=\'brew\';render()">🎒<span>Инвентарь</span></button>' +
        '</div>' +
        '<div class="center">' +
          '<div class="hero-face">' + esc(charFaceFor(hero)) + '</div>' +
          '<div class="hero-name">' + esc(hero ? hero.name : STATE.name) + '</div>' +
          '<div class="team-info">👥 Отряд ' + team.length + '/' + (STATE.team_size || 1) + ' · ⭐ ур. ' + (STATE.level || 1) + '</div>' +
          '<button class="btn small" onclick="TAB=\'chars\';render()">⚙️ Управление отрядом</button>' +
          '<button class="btn small" onclick="TAB=\'chars\';render()">🎯 Выбрать отряд</button>' +
          '<button class="btn small" onclick="randomTeam()">🎲 Случайный отряд</button>' +
        '</div>' +
        '<div class="col">' +
          '<button class="sq" onclick="TAB=\'profile\';render()">👤<span>Профиль</span></button>' +
          '<button class="sq" disabled>📰<span>Новости</span></button>' +
          '<button class="sq" disabled>👥<span>Друзья</span></button>' +
          (IS_ADMIN ? '<button class="sq" onclick="TAB=\'admin\';render()">🛠<span>Админка</span></button>' : '') +
        '</div>' +
        '<div class="bottom">' +
          '<button class="btn small on">🗺 Кампания</button>' +
          '<button class="btn small" disabled>🏆 Ранкед · скоро</button>' +
          '<button class="btn btn-play" onclick="TAB=\'map\';render()">▶ ИГРАТЬ</button>' +
        '</div>' +
      '</div>';
  } else {
    screen.innerHTML = '<div class="panel"><h3>⚠️ ' + esc(r.error || "ошибка") + '</h3></div>';
  }
}
function randomTeam() {
  var owned = (STATE.characters || []).map(function (c) { return c.id; });
  if (!owned.length) { toast("Нет персонажей"); return; }
  owned = owned.slice().sort(function () { return Math.random() - 0.5; }).slice(0, STATE.team_size || 1);
  api("/api/character/team", { char_ids: owned }).then(function (r) {
    if (r.ok) { toast("Отряд обновлён"); refresh(); } else toast(r.error);
  });
}

/* ── Карта глав ── */
async function renderMapGrid() {
  var r = await api("/api/campaign");
  if (!r.ok) { toast(r.error); return; }
  var chapters = r.chapters || [];
  if (!chapters.length) { screen.innerHTML = '<div class="panel"><p class="muted">Нет данных по главам</p></div>'; return; }
  var cur = chapters.filter(function (c) { return c.chapter === MAP_CHAPTER; })[0] || chapters[0];
  var chBtns = "";
  chapters.forEach(function (c) {
    chBtns += '<button class="btn small' + (c.chapter === cur.chapter ? "" : "") + '" onclick="MAP_CHAPTER=' + c.chapter + ';renderMapGrid()"' + (c.unlocked ? "" : " disabled") + '>Глава ' + c.chapter + '</button>';
  });
  var locs = "";
  (cur.locations || []).forEach(function (l) {
    var cls = l.clears > 0 ? "done" : (l.locked ? "lock" : "next");
    locs += '<div class="loc ' + cls + '" onclick="' + (l.locked ? "toast('Локация закрыта')" : "startBattle(" + cur.chapter + "," + l.n + ")") + '"><div class="num">' + l.n + '</div>' + esc(l.theme || "") + (l.is_boss ? " 👹" : "") + '</div>';
  });
  screen.innerHTML = '<div class="panel"><h3>🗺 Глава ' + cur.chapter + ' — ' + esc(cur.name || "") + '</h3>' +
    '<div class="chapters">' + chBtns + '</div><div class="locgrid">' + locs + '</div></div>';
}

/* ── Бой ── */
async function startBattle(chapter, loc) {
  var r = await api("/api/battle/start", { chapter: chapter, loc: loc });
  if (!r.ok) { toast(r.error); return; }
  BATTLE = r.battle || r;
  BATTLE_TARGET = 0;
  STANCE = {};
  (BATTLE.fighters || []).forEach(function (f) { STANCE[f.char_id] = "attack"; });
  if (r.state) { STATE = r.state; renderChip(); }
  TAB = "battle";
  render();
}
function hpBar(hp, max) {
  var p = max > 0 ? Math.max(0, Math.round(100 * hp / max)) : 0;
  return '<div class="hpb"><i style="width:' + p + '%"></i></div>';
}
function renderBattle() {
  if (!BATTLE || BATTLE.over) { TAB = "map"; render(); return; }
  var s = BATTLE;
  var you = '<div class="side">';
  (s.fighters || []).forEach(function (u) {
    var dead = u.hp <= 0;
    you += '<div class="unit' + (dead ? " dead" : "") + '">' +
      '<b>' + esc(u.name) + '</b> <span class="muted">' + u.hp + '/' + u.max_hp + '</span>' + hpBar(u.hp, u.max_hp) +
      '<div class="stances">' +
        '<button class="btn' + (STANCE[u.char_id] !== "defend" ? " on" : "") + '" onclick="setStance(\'' + u.char_id + '\',\'attack\')">⚔️</button>' +
        '<button class="btn' + (STANCE[u.char_id] === "defend" ? " on" : "") + '" onclick="setStance(\'' + u.char_id + '\',\'defend\')">🛡</button>' +
      '</div></div>';
  });
  you += '</div>';
  var foes = '<div class="side">';
  (s.enemies || []).forEach(function (u, i) {
    var dead = u.hp <= 0;
    foes += '<div class="unit' + (dead ? " dead" : "") + (i === BATTLE_TARGET ? " sel" : "") + '" onclick="BATTLE_TARGET=' + i + ';renderBattle()">' +
      '<b>' + esc(u.name) + '</b> <span class="muted">' + u.hp + '/' + u.max_hp + '</span>' + hpBar(u.hp, u.max_hp) + '</div>';
  });
  foes += '</div>';
  var log = "";
  (s.log || []).forEach(function (l) { log += '<div>' + esc(l) + '</div>'; });
  screen.innerHTML =
    '<div class="panel"><h3>⚔️ Глава ' + s.chapter + ' · локация ' + s.loc + ' — раунд ' + s.round + '</h3>' +
      '<div class="arena">' + you + foes + '</div>' +
      '<div class="battle-controls"><button class="btn" onclick="battleTurn()">⚔️ Сделать ход</button><button class="btn small" onclick="TAB=\'map\';BATTLE=null;render()">↩ Назад</button></div>' +
      '<div class="log">' + log + '</div></div>';
}
function setStance(cid, st) { STANCE[cid] = st; renderBattle(); }
function battleEnd(r) {
  var win = BATTLE.win;
  if (r.state) { STATE = r.state; renderChip(); }
  var w = r.rewards || {};
  var parts = [];
  if (w.exp) parts.push("+" + fmt(w.exp) + " опыта");
  if (w.egez) parts.push("+" + fmt(w.egez) + " Э Gez");
  if (w.darkness) parts.push("+" + fmt(w.darkness) + " Тьмы");
  if (w.scroll) parts.push("📜 Свиток босса");
  var log = "";
  (BATTLE.log || []).forEach(function (l) { log += "<div>" + esc(l) + "</div>"; });
  BATTLE = null;
  screen.innerHTML =
    '<div class="panel" style="text-align:center">' +
    '<h3>' + (win ? "🏆 Победа!" : "💀 Поражение") + '</h3>' +
    '<p class="muted">' + (parts.length ? parts.join(" · ") : (win ? "" : "Отряд пал. Усильте героев и попробуйте снова.")) + '</p>' +
    (r.levelups && r.levelups.length
      ? '<p style="color:var(--good);font-weight:700">⭐ Новый уровень: ' + esc(r.levelups.join(", ")) + '</p>' : "") +
    '<div class="log" style="text-align:left">' + log + '</div>' +
    '<button class="btn btn-play" style="margin-top:12px" onclick="TAB=\'map\';render()">🗺 К карте</button>' +
    '<button class="btn" style="margin-top:8px" onclick="TAB=\'menu\';render()">🏠 В меню</button></div>';
}

async function battleTurn() {
  var actions = [];
  (BATTLE.fighters || []).forEach(function (u) {
    if (u.hp > 0) actions.push({ char_id: u.char_id, type: STANCE[u.char_id] || "attack", target: BATTLE_TARGET });
  });
  var r = await api("/api/battle/turn", { actions: actions });
  if (!r.ok) { toast(r.error); return; }
  BATTLE = r.battle || r;
  if (BATTLE.over) { battleEnd(r); return; }
  renderBattle();
}

/* ── Персонажи ── */
function renderChars() {
  var chars = STATE.characters || [];
  var team = STATE.team || [];
  var cards = chars.map(function (c) {
    var inte = team.indexOf(c.id) >= 0;
    var st = c.stats || {};
    return '<div class="card"><div class="face">' + (c.face || "🦸") + '</div><h4>' + esc(c.name) + (inte ? '<span class="tag inteam">в отряде</span>' : "") + '</h4>' +
      '<div class="row"><span>⭐ ур. ' + c.level + '</span><span>' + esc((c.affinities || []).join(", ") || "") + '</span></div>' +
      '<div class="row"><span>❤️ ' + st.hp + '</span><span>⚔️ ' + st.str + ' · 🛡 ' + st.def + '</span></div>' +
      '<div class="row"><span>💨 ' + st.agi + ' · 🔮 ' + st.will + '</span></div>' +
      '<div style="display:flex;gap:6px;justify-content:center">' +
      '<button class="btn" onclick="toggleTeam(\'' + c.id + '\')">' + (inte ? "Убрать" : "В отряд") + '</button>' +
      '<button class="btn" onclick="charGear(\'' + c.id + '\')">🎒 Экипировка</button></div></div>';
  }).join("");
  screen.innerHTML = '<div class="panel"><h3>🎭 Персонажи · отряд ' + team.length + '/' + (STATE.team_size || 1) + '</h3><div class="grid">' + cards + '</div></div>';
}
function charGear(cid) {
  var c = null;
  (STATE.characters || []).forEach(function (x) { if (x.id === cid) c = x; });
  if (!c) return;
  var slotNames = (META && META.slot_names) || {};
  var gear = c.gear || {};
  var worn = "";
  ["weapon","armor","gloves","amulet","off_weapon","off_armor"].forEach(function (slot) {
    var it = gear[slot];
    worn += '<div class="row"><span>' + esc(slotNames[slot] || slot) + '</span><span>' +
      (it ? esc(it.name) + ' <button class="btn small" onclick="unequipItem(\'' + cid + '\',\'' + slot + '\')">✖</button>' : '<span class="muted">пусто</span>') + '</span></div>';
  });
  (c.artifacts || []).forEach(function (it, idx) {
    worn += '<div class="row"><span>Артефакт ' + (idx + 1) + '</span><span>' +
      (it ? esc(it.name) + ' <button class="btn small" onclick="unequipItem(\'' + cid + '\',\'artifact\',' + idx + ')">✖</button>' : '<span class="muted">пусто</span>') + '</span></div>';
  });
  (c.bonus || []).forEach(function (it, idx) {
    worn += '<div class="row"><span>Бонус ' + (idx + 1) + '</span><span>' +
      (it ? esc(it.name) + ' <button class="btn small" onclick="unequipItem(\'' + cid + '\',\'bonus\',' + idx + ')">✖</button>' : '<span class="muted">пусто</span>') + '</span></div>';
  });
  var inv = ((STATE.items) || []).map(function (it) {
    return '<div class="row"><span>' + esc(it.name) + ' <span class="tag">' + esc(slotNames[it.slot] || it.slot) + '</span></span>' +
      '<button class="btn small" onclick="equipItem(\'' + cid + '\',\'' + it.id + '\')">➕ Надеть</button></div>';
  }).join("");
  openModal('<h3 style="margin-bottom:6px">🎒 ' + esc(c.name) + '</h3>' +
    '<p class="muted" style="margin-bottom:8px">Надето:</p>' + worn +
    '<p class="muted" style="margin:10px 0 4px">Инвентарь:</p>' +
    (inv || '<p class="muted">Пусто — предметы выпадают в бою и из колод</p>') +
    '<button class="btn" style="margin-top:12px" onclick="closeModal()">Готово</button>');
}
async function equipItem(cid, iid) {
  var r = await api("/api/equip", { char_id: cid, item_id: iid });
  if (!r.ok) { toast(r.error); return; }
  toast("Надето");
  await refresh();
  charGear(cid);
}
async function unequipItem(cid, slot, idx) {
  var r = await api("/api/unequip", { char_id: cid, slot: slot, index: idx });
  if (!r.ok) { toast(r.error); return; }
  toast("Снято");
  await refresh();
  charGear(cid);
}

async function toggleTeam(id) {
  var team = (STATE.team || []).slice();
  var i = team.indexOf(id);
  if (i >= 0) {
    if (team.length <= 1) { toast("В отряде должен оставаться хотя бы один герой"); return; }
    team.splice(i, 1);
    toast("Герой убран из отряда");
  } else {
    if (team.length >= (STATE.team_size || 1)) {
      team.shift();
      toast("Отряд полон — заменён первый герой");
    } else {
      toast("Герой добавлен в отряд");
    }
    team.push(id);
  }
  var r = await api("/api/character/team", { char_ids: team });
  if (r.ok) { STATE.team = r.team || team; renderChars(); refresh(); }
  else toast(r.error);
}

/* ── Магазин ── */
async function renderShop() {
  var cost = (META && META.pack_cost) || 100;
  var free = STATE && !STATE.gacha_free_used;
  screen.innerHTML = '<div class="panel"><h3>🛒 Магазин</h3>' +
    '<div class="row"><span class="k">Колода героя</span><b>' + IC_EGEZ + " " + fmt(cost) + ' Э Gez</b></div>' +
    '<button class="btn btn-play" onclick="buyPack()" style="margin-top:10px">🎴 ×1 — ' + fmt(cost) + '</button>' +
    '<div class="row" style="margin-top:14px"><span class="k">×10 колод</span><b>' + IC_EGEZ + " " + fmt(cost * 10) + ' Э Gez</b></div>' +
    '<button class="btn btn-play" onclick="buyPacksTimes(10)">🎁 ×10 — ' + fmt(cost * 10) + '</button>' +
    (free
      ? '<div class="row" style="margin-top:14px"><span class="k">🎁 Бесплатная колода</span><b>одна навсегда</b></div>' +
        '<button class="btn" style="margin-top:10px;background:linear-gradient(180deg,#15803d,#166534);border-color:#4ade80" onclick="buyPacksTimes(1,{free:true})">🎁 Открыть бесплатно</button>'
      : "") +
    '</div>';
}
function showPackRes(chars) {
  if (!chars.length) return;
  if (chars.length === 1) {
    var c = chars[0];
    openModal('<div class="card" style="margin:0">' +
      '<div class="face">' + (c.face || "🎴") + '</div>' +
      '<h3>' + esc(c.name) + '</h3>' +
      '<p class="muted">' + esc(c.aff || "") + " · " + esc(c.rarity || "") + ' редкость</p>' +
      '<div class="row"><span>⭐ ур. ' + (c.level || 1) + '</span><span>' + esc(c.rarity_name || "") + '</span></div>' +
      '<button class="btn btn-play" onclick="closeModal()">Забрать</button></div>');
  } else {
    var cards = chars.map(function (c) {
      return '<div class="card" style="margin:0;padding:10px"><div class="face">' + (c.face || "🎴") + '</div><h4>' + esc(c.name) + '</h4><p class="muted" style="font-size:11px">' + esc(c.rarity || "") + '</p></div>';
    }).join("");
    openModal('<h3 style="margin-bottom:10px">🎉 Выпали:</h3><div class="grid">' + cards + '</div><button class="btn btn-play" style="margin-top:10px" onclick="closeModal()">Забрать</button>');
  }
}
async function buyPack() {
  var r = await api("/api/gacha/open");
  if (r.ok) { showPackRes([r.character]); STATE = r.state || STATE; renderChip(); renderShop(); }
  else toast(r.error);
}
async function buyPacksTimes(times, opts) {
  opts = opts || {};
  var body = { times: times };
  if (opts.free) body.free = true;
  var r = await api("/api/gacha/open", body);
  if (r.ok) {
    var chars = r.characters || [];
    if (!chars.length && r.character) chars = [r.character];
    showPackRes(chars);
    STATE = r.state || STATE;
    renderChip();
    renderShop();
  } else toast(r.error);
}

/* ── Инвентарь/зелья ── */
async function renderBrewing() {
  var r = await api("/api/brewing");
  var html = '<div class="panel"><h3>🎒 Инвентарь</h3>';
  if (r.ok) {
    (r.potions || []).forEach(function (p) {
      var cnt = (STATE.potions && STATE.potions[p.id]) || 0;
      html += '<div class="row"><span>' + esc(p.name) + ' ×' + cnt + '</span>' +
        '<span><button class="btn small" onclick="brew(\'' + p.id + '\')">⚗️ Сварить</button> ' +
        (cnt > 0 ? '<button class="btn small" onclick="usePotion(\'' + p.id + '\')">🧪 Использовать</button>' : "") + '</span></div>';
    });
    (r.brews || []).forEach(function (b) {
      var ready = (b.time_left || 0) <= 0;
      html += '<div class="row"><span>' + esc(b.potion_name || b.potion_id) + '</span><span>' +
        (ready ? '<button class="btn small" onclick="claimBrew(' + b.id + ')">✅ Забрать</button>' : '⏳ ' + Math.ceil((b.time_left || 0) / 60) + ' мин') + '</span></div>';
    });
    html += '<p class="muted" style="margin-top:8px">Материалы: ' + IC_DARK + ' ' + fmt((STATE.materials && STATE.materials.dust) || 0) + ' пыли</p>';
  } else html += '<p class="muted">' + esc(r.error || "") + '</p>';
  screen.innerHTML = html + '</div>';
}
async function brew(pid) { var r = await api("/api/brew/start", { potion_id: pid }); toast(r.ok ? "Варка началась" : r.error); refresh(); }
async function claimBrew(bid) { var r = await api("/api/brew/claim", { brew_id: bid }); toast(r.ok ? "Готово!" : r.error); refresh(); }
async function usePotion(pid) { var r = await api("/api/potion/use", { potion_id: pid }); toast(r.ok ? "Использовано" : r.error); refresh(); }

/* ── Профиль ── */
function renderProfile() {
  var html = '<div class="panel"><h3>👤 ' + esc(STATE.name || "") + '</h3>' +
    '<div class="row"><span>Уровень</span><b>⭐ ' + (STATE.level || 1) + '</b></div>' +
    '<div class="row"><span>Опыт</span><b>' + fmt(STATE.xp) + ' / ' + fmt(STATE.xp_need || 0) + '</b></div>' +
    '<div class="row"><span>Глава</span><b>' + (STATE.chapter || 1) + '</b></div>' +
    '<div class="row"><span>Свитки боссов</span><b>' + fmt(STATE.boss_scroll_claimed || 0) + '</b></div>' +
    '<div class="row"><span>' + IC_DARK + ' Тьма</span><b>' + fmt(STATE.darkness) + '</b></div>' +
    '<div class="row"><span>' + IC_EGEZ + ' Э Gez</span><b>' + fmt(STATE.egez) + '</b></div>' +
    '<div class="row"><span>Персонажей</span><b>' + (STATE.characters || []).length + '</b></div>' +
    '<p class="muted" style="margin-top:10px">Бонус опыта: ' + (STATE.exp_boost || 50) + '%</p></div>';
  html += '<div class="panel"><h3>🎟 Промокод</h3><div style="display:flex;gap:8px"><input id="promo-code" placeholder="КОД" style="flex:1;padding:10px;border-radius:10px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit"><button class="btn" onclick="redeemPromo()">Получить</button></div></div>';
  screen.innerHTML = html;
}
async function redeemPromo() {
  var code = ($("#promo-code") ? $("#promo-code").value : "").trim().toUpperCase();
  if (!code) { toast("Введите код"); return; }
  var r = await api("/api/promo", { code: code });
  if (r.ok) { toast("🎁 Награда получена!"); STATE = r.state || STATE; renderChip(); renderProfile(); }
  else toast(r.error);
}

/* ── Админка ── */
var ADMIN_LIST = [];
async function renderAdmin() {
  if (!IS_ADMIN) { screen.innerHTML = '<div class="panel"><h3>⛔ нет доступа</h3></div>'; return; }
  var r = await api("/api/admin/players");
  ADMIN_LIST = (r.ok && r.players) ? r.players : [];
  var opts = ADMIN_LIST.map(function (p) {
    return '<div class="dd-item" onclick="pickAdminPlayer(' + p.tg_id + ')">' + esc(p.name || p.tg_id) + ' <span class="muted">⭐' + p.level + '</span></div>';
  }).join("");
  var charOpts = ((META && META.characters) || []).map(function (c) {
    return '<div class="dd-item" onclick="pickAdminChar(\'' + c.key + '\', \'' + esc(c.name) + '\')">' + esc(c.name) + '</div>';
  }).join("");
  screen.innerHTML =
    '<div class="panel"><h3>🛠 Админка</h3>' +
      '<div style="display:flex;gap:10px;margin-bottom:10px">' +
        '<button class="btn small" onclick="toggleMaintenance()">' + (MAINT ? "Выключить техперерыв ✅" : "Включить техперерыв 🔧") + '</button>' +
      '</div>' +
      '<div class="row"><span>Игрок</span><span class="dd"><b id="adm-pick" onclick="ddT(\'adm-pick-list\')">— выбрать —</b><div class="dd-list hidden" id="adm-pick-list">' + opts + '</div></span></div>' +
      '<div id="adm-detail" style="margin-top:10px"><p class="muted">Выберите игрока</p></div>' +
    '</div>' +
    '<div class="panel"><h3>🎟 Промокоды</h3>' +
      '<div class="row"><span>Код</span><input id="pc-code" placeholder="КОД" style="width:120px;padding:8px;border-radius:8px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit"></div>' +
      '<div class="row"><span>Тьма</span><input id="pc-dark" type="number" value="0" style="width:90px;padding:8px;border-radius:8px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit"></div>' +
      '<div class="row"><span>Э Gez</span><input id="pc-egez" type="number" value="0" style="width:90px;padding:8px;border-radius:8px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit"></div>' +
      '<div class="row"><span>Свитки</span><input id="pc-scroll" type="number" value="0" style="width:90px;padding:8px;border-radius:8px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit"></div>' +
      '<div class="row"><span>Персонаж</span><span class="dd"><b id="pc-char-btn" onclick="ddT(\'pc-char-list\')">—</b><div class="dd-list hidden" id="pc-char-list">' + charOpts + '</div></span></div>' +
      '<div class="row"><span>Активаций</span><input id="pc-uses" type="number" value="1" style="width:90px;padding:8px;border-radius:8px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit"></div>' +
      '<input type="hidden" id="pc-char" value="">' +
      '<div style="display:flex;gap:10px;margin-top:10px"><button class="btn" onclick="createPromo()">Создать промокод</button><button class="btn small" onclick="delPromo()">Удалить промокод</button></div>' +
    '</div>' +
    '<div class="panel"><h3>📢 Рассылка</h3>' +
      '<textarea id="bc-text" rows="3" style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--line2);background:rgba(0,0,0,.3);color:var(--text);font:inherit" placeholder="Текст сообщения"></textarea>' +
      '<button class="btn" style="margin-top:8px" onclick="doBroadcast()">Отправить</button>' +
    '</div>';
}
function ddT(id) { var l = document.getElementById(id); if (l) l.classList.toggle("hidden"); }
function pickAdminChar(key, name) {
  document.getElementById("pc-char").value = key;
  document.getElementById("pc-char-btn").textContent = name;
  document.getElementById("pc-char-list").classList.add("hidden");
}
function pickAdminPlayer(tgId) {
  document.getElementById("adm-pick").textContent = "…";
  for (var i = 0; i < ADMIN_LIST.length; i++) {
    if (ADMIN_LIST[i].tg_id === tgId) {
      var p = ADMIN_LIST[i];
      document.getElementById("adm-pick").textContent = (p.name || p.tg_id);
      document.getElementById("adm-pick-list").classList.add("hidden");
      renderAdminDetail(p);
      return;
    }
  }
}
function renderAdminDetail(p) {
  document.getElementById("adm-detail").innerHTML =
    '<div class="row"><span>Ник</span><b>' + esc(p.name || "") + '</b></div>' +
    '<div class="row"><span>TG ID</span><b>' + p.tg_id + '</b></div>' +
    '<div class="row"><span>Уровень</span><b>⭐ ' + p.level + '</b></div>' +
    '<div class="row"><span>Тьма</span><b>' + fmt(p.darkness || 0) + '</b></div>' +
    '<div class="row"><span>Э Gez</span><b>' + fmt(p.egez || 0) + '</b></div>' +
    '<div class="row"><span>Свитки</span><b>' + fmt(p.scrolls || 0) + '</b></div>' +
    '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-top:10px">' +
      '<button class="btn small" onclick="adminGiveField(' + p.tg_id + ',\'darkness\')">' + IC_DARK + ' Тьма</button>' +
      '<button class="btn small" onclick="adminGiveField(' + p.tg_id + ',\'egez\')">' + IC_EGEZ + ' Э Gez</button>' +
      '<button class="btn small" onclick="adminGiveField(' + p.tg_id + ',\'scrolls\')">📜 Свитки</button>' +
      '<button class="btn small" onclick="adminGiveField(' + p.tg_id + ',\'exp\')">⭐ Опыт</button>' +
      '<button class="btn small" onclick="adminGiveChar(' + p.tg_id + ')">🎴 Персонаж</button>' +
      '<button class="btn small" onclick="adminReset(' + p.tg_id + ')" style="color:var(--bad)">♻️ Сбросить</button>' +
    '</div>';
}
async function adminGive(tgId, field, val) {
  var body = { tg_id: tgId };
  body[field] = val;
  var r = await api("/api/admin/give", body);
  toast(r.ok ? "Выдано" : r.error);
  if (r.ok) renderAdmin();
}
function openModal(html) { $("#modal-box").innerHTML = html; $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); }
function adminGiveField(tgId, field) {
  var labels = { darkness: "Тьму", egez: "Э Gez", scrolls: "Свитков", exp: "опыта" };
  openModal(
    '<h3 style="margin-bottom:8px">Выдать: ' + (labels[field] || field) + '</h3>' +
    '<input id="ag-val" type="number" value="0" min="0">' +
    '<div style="display:flex;gap:8px;margin-top:12px">' +
      '<button class="btn" onclick="adminDoGive(' + tgId + ',\'' + field + '\')">Выдать</button>' +
      '<button class="btn small" onclick="closeModal()">Отмена</button>' +
    '</div>');
}
async function adminDoGive(tgId, field) {
  var v = parseInt($("#ag-val").value || "0", 10) || 0;
  closeModal();
  adminGive(tgId, field, v);
}
function adminGiveChar(tgId) {
  var opts = ((META && META.characters) || []).map(function (c) {
    return '<div class="dd-item" onclick="adminPickGiveChar(' + tgId + ',\'' + c.key + '\',\'' + esc(c.name) + '\')">' + esc(c.name) + '</div>';
  }).join("");
  openModal('<h3 style="margin-bottom:8px">Выдать персонажа</h3><div class="dd-list" style="position:static;max-height:260px;overflow-y:auto">' + opts + '</div>' +
    '<button class="btn small" style="margin-top:10px" onclick="closeModal()">Отмена</button>');
}
async function adminPickGiveChar(tgId, key, name) {
  closeModal();
  var r = await api("/api/admin/give", { tg_id: tgId, character: key });
  toast(r.ok ? "Выдано: " + name : r.error);
  if (r.ok) renderAdmin();
}
async function adminReset(tgId) {
  if (!confirm("Полностью сбросить прогресс игрока?")) return;
  var r = await api("/api/admin/reset", { tg_id: tgId });
  toast(r.ok ? "Сброшено" : r.error);
  if (r.ok) renderAdmin();
}
async function toggleMaintenance() {
  var r = await api("/api/admin/maintenance");
  if (r.ok) { MAINT = !!r.maintenance; toast("Обновлено"); renderAdmin(); } else toast(r.error);
}
async function createPromo() {
  var code = (document.getElementById("pc-code").value || "").trim().toUpperCase();
  if (!code) { toast("Введите код"); return; }
  var r = await api("/api/admin/promo/create", {
    code: code,
    darkness: parseInt(document.getElementById("pc-dark").value || "0", 10) || 0,
    egez: parseInt(document.getElementById("pc-egez").value || "0", 10) || 0,
    scrolls: parseInt(document.getElementById("pc-scroll").value || "0", 10) || 0,
    character: document.getElementById("pc-char").value || "",
    max_uses: parseInt(document.getElementById("pc-uses").value || "1", 10) || 1,
  });
  toast(r.ok ? "Промокод '" + code + "' создан" : r.error);
}
async function delPromo() {
  var code = (document.getElementById("pc-code").value || "").trim().toUpperCase();
  if (!code) { toast("Введите код"); return; }
  var r = await api("/api/admin/promo/delete", { code: code });
  toast(r.ok ? "Промокод удалён" : r.error);
}
async function doBroadcast() {
  var text = (document.getElementById("bc-text").value || "").trim();
  if (!text) { toast("Введите текст"); return; }
  if (!confirm("Отправить всем игрокам?")) return;
  var r = await api("/api/admin/broadcast", { text: text });
  toast(r.ok ? "Отправлено " + (r.sent || 0) : r.error);
}

/* ── Экраны сервиса ── */
function renderMaintenance() {
  screen.innerHTML = '<div class="center-screen"><div class="panel reg-panel"><h3>🔧 Тех перерыв</h3><p class="muted">Игра временно недоступна. Загляните позже!</p></div></div>';
}
function showRegister() {
  screen.innerHTML = '<div class="center-screen"><div class="panel reg-panel"><h3>⚔️ Придумай ник</h3><p class="muted">Его увидят другие игроки. Выбирается один раз.</p>' +
    '<input id="reg-name" maxlength="16" placeholder="Ник"><button class="btn btn-play" style="width:100%" onclick="doRegister()">Создать</button></div></div>';
}
async function doRegister() {
  var name = ($("#reg-name") ? $("#reg-name").value : "").trim();
  var r = await api("/api/register", { name: name });
  if (r.ok) { STATE = r.state; toast("Добро пожаловать, " + name + "!"); renderChip(); TAB = "menu"; render(); }
  else toast(r.error);
}

/* ── Движок вкладок ── */
function goBack() { TAB = "menu"; render(); }
if (tg && tg.BackButton) {
  try { tg.BackButton.onClick(function () { goBack(); }); } catch (e) {}
}
function setTgBack() {
  if (!tg || !tg.BackButton) return;
  try {
    if (TAB === "menu") tg.BackButton.hide(); else tg.BackButton.show();
  } catch (e) {}
}
function adaptScreen() {
  var h = window.innerHeight || 800;
  document.body.classList.toggle("tiny", h < 480);
  document.body.classList.toggle("small", h >= 480 && h < 620);
}
window.addEventListener("resize", adaptScreen);
window.addEventListener("orientationchange", function () { setTimeout(adaptScreen, 200); });

function render() {
  if (!STATE) return;
  adaptScreen();
  tryFullscreen();
  setTgBack();
  if (MAINT && !IS_ADMIN) { renderMaintenance(); return; }
  if (!STATE.registered) { showRegister(); return; }
  if (TAB === "menu") renderMap();
  else if (TAB === "map") renderMapGrid();
  else if (TAB === "battle") renderBattle();
  else if (TAB === "chars") renderChars();
  else if (TAB === "shop") renderShop();
  else if (TAB === "brew") renderBrewing();
  else if (TAB === "profile") renderProfile();
  else if (TAB === "admin") renderAdmin();
}
function refresh() {
  api("/api/state").then(function (r) {
    if (r.ok) { STATE = r.state; renderChip(); render(); }
  });
}

/* ── Отладка ошибок на экране ── */
window.addEventListener("error", function (e) {
  var s = $("#screen");
  if (s) {
    s.innerHTML = '<div class="panel"><h3>⚠️ Ошибка: ' + esc((e && e.message) || "JS error") + '</h3>' +
      '<p class="muted">' + esc((e && e.filename) || "") + ':' + esc((e && e.lineno) || "") + '</p>' +
      '<button class="btn" style="margin-top:10px" onclick="location.reload()">🔄 Обновить</button></div>';
  }
});

/* ── Старт ── */
(function boot() {
  adaptScreen();
  tryFullscreen();
  var timeout = setTimeout(function () {
    if (!STATE) screen.innerHTML = '<div class="panel" style="margin-top:30px;text-align:center"><h3>⚠️ Долгая загрузка</h3><p class="muted">Сервер не ответил. Обновите страницу.</p><button class="btn" onclick="location.reload()">🔄 Обновить</button></div>';
  }, 10000);
  Promise.all([
    fetch("/api/meta").then(function (r) { return r.json(); }),
    api("/api/auth"),
  ]).then(function (res) {
    clearTimeout(timeout);
    META = res[0];
    var a = res[1];
    if (a.ok) {
      STATE = a.state;
      MAINT = !!a.maintenance;
      IS_ADMIN = !!a.admin;
      renderChip();
      if (IS_ADMIN) { var b = $("#m-admin"); if (b) b.classList.remove("hidden"); }
      render();
    } else {
      screen.innerHTML = '<div class="panel"><h3>⛔ Не удалось авторизоваться</h3><p class="muted">' + esc(a.error || "") + '. Откройте мини-апп кнопкой из бота.</p></div>';
    }
  }).catch(function (e) {
    clearTimeout(timeout);
    screen.innerHTML = '<div class="panel"><h3>⚠️ Нет связи с сервером</h3><p class="muted">' + esc(e.message) + '</p><button class="btn" onclick="location.reload()">🔄 Обновить</button></div>';
  });
})();
