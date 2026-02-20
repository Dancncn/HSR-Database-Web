function el(id) {
  return document.getElementById(id);
}

function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtNum(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  if (Number.isNaN(n)) return esc(value);
  if (Math.abs(n - Math.round(n)) < 0.0000001) return String(Math.round(n));
  return n.toFixed(digits).replace(/\.?0+$/, "");
}

const ENUM_I18N = {
  damage_type: {
    Physical: { CHS: "物理", EN: "Physical", JP: "物理", KR: "물리" },
    Fire: { CHS: "火", EN: "Fire", JP: "炎", KR: "화염" },
    Ice: { CHS: "冰", EN: "Ice", JP: "氷", KR: "얼음" },
    Thunder: { CHS: "雷", EN: "Thunder", JP: "雷", KR: "번개" },
    Wind: { CHS: "风", EN: "Wind", JP: "風", KR: "바람" },
    Quantum: { CHS: "量子", EN: "Quantum", JP: "量子", KR: "양자" },
    Imaginary: { CHS: "虚数", EN: "Imaginary", JP: "虚数", KR: "허수" },
  },
  avatar_base_type: {
    Warrior: { CHS: "毁灭", EN: "Destruction", JP: "壊滅", KR: "파멸" },
    Knight: { CHS: "存护", EN: "Preservation", JP: "存護", KR: "보존" },
    Rogue: { CHS: "巡猎", EN: "Hunt", JP: "巡狩", KR: "수렵" },
    Mage: { CHS: "智识", EN: "Erudition", JP: "知恵", KR: "지식" },
    Shaman: { CHS: "同谐", EN: "Harmony", JP: "調和", KR: "화합" },
    Warlock: { CHS: "虚无", EN: "Nihility", JP: "虚無", KR: "공허" },
    Priest: { CHS: "丰饶", EN: "Abundance", JP: "豊穣", KR: "풍요" },
    Memory: { CHS: "记忆", EN: "Remembrance", JP: "記憶", KR: "기억" },
  },
  rarity: {
    CombatPowerAvatarRarityType4: { CHS: "4星", EN: "4-Star", JP: "星4", KR: "4성" },
    CombatPowerAvatarRarityType5: { CHS: "5星", EN: "5-Star", JP: "星5", KR: "5성" },
    SuperRare: { CHS: "五星", EN: "Super Rare", JP: "星5", KR: "5성" },
    VeryRare: { CHS: "四星", EN: "Very Rare", JP: "星4", KR: "4성" },
    Rare: { CHS: "三星", EN: "Rare", JP: "星3", KR: "3성" },
  },
  item_type: {
    Equipment: { CHS: "光锥", EN: "Light Cone", JP: "光円錐", KR: "광추" },
    Relic: { CHS: "遗器", EN: "Relic", JP: "遺物", KR: "유물" },
    Material: { CHS: "材料", EN: "Material", JP: "素材", KR: "재료" },
    Virtual: { CHS: "虚拟道具", EN: "Virtual", JP: "仮想アイテム", KR: "가상 아이템" },
    Usable: { CHS: "消耗品", EN: "Usable", JP: "消耗品", KR: "소모품" },
  },
  monster_rank: {
    Minion: { CHS: "杂兵", EN: "Minion", JP: "雑兵", KR: "잡몹" },
    MinionLv2: { CHS: "强化杂兵", EN: "Enhanced Minion", JP: "強化雑兵", KR: "강화 잡몹" },
    Elite: { CHS: "精英", EN: "Elite", JP: "精鋭", KR: "정예" },
    LittleBoss: { CHS: "首领", EN: "Boss", JP: "ボス", KR: "보스" },
    BigBoss: { CHS: "周本首领", EN: "Weekly Boss", JP: "週ボス", KR: "주간 보스" },
  },
  attack_type: {
    Normal: { CHS: "普攻", EN: "Normal", JP: "通常", KR: "일반" },
    Skill: { CHS: "战技", EN: "Skill", JP: "戦闘スキル", KR: "스킬" },
    Ultra: { CHS: "终结技", EN: "Ultimate", JP: "必殺技", KR: "필살기" },
    MazeNormal: { CHS: "秘技普攻", EN: "Technique Normal", JP: "秘技通常", KR: "비술 일반" },
    MazeSkill: { CHS: "秘技", EN: "Technique", JP: "秘技", KR: "비술" },
  },
};

function tEnum(type, value, lang = "CHS") {
  if (value === null || value === undefined || value === "") return "-";
  const raw = String(value);
  const group = ENUM_I18N[type];
  if (!group) return raw;
  const item = group[raw];
  if (!item) return raw;
  return item[lang] || item.CHS || raw;
}

const UI_I18N = {
  CHS: {
    title: "星铁资源查询",
    search: "查询",
    detail: "查看详情",
    refs: "查看引用",
    loading: "加载中...",
    no_results: "没有结果。",
    pager_first: "首页",
    pager_prev: "上一页",
    pager_next: "下一页",
    pager_last: "末页",
    pager_jump: "跳至",
    pager_page: "页",
    pager_go: "跳转",
    item_all_rarity: "全部稀有度",
    item_all_main: "全部主类型",
    item_all_sub: "全部子类型",
    monster_all_rank: "全部阶级",
    monster_all_weak: "全部弱点",
    mission_source: "来源",
    narration: "旁白",
    term_loading: "正在查询解释...",
    term_none: "暂无可用解释。",
    term_close: "关闭",
    term_fallback: "当前无该语言解释，已回退到中文",
    stats_build: "构建时间",
    stats_dialogue: "对话",
    stats_refs: "引用",
    stats_main: "主线",
    stats_avatar: "角色",
    stats_item: "物品",
    stats_monster: "怪物",
    stats_fail: "加载统计失败",
  },
  EN: {
    title: "HSR Resource Explorer",
    search: "Search",
    detail: "Details",
    refs: "References",
    loading: "Loading...",
    no_results: "No results.",
    pager_first: "First",
    pager_prev: "Prev",
    pager_next: "Next",
    pager_last: "Last",
    pager_jump: "Jump",
    pager_page: "page",
    pager_go: "Go",
    item_all_rarity: "All Rarities",
    item_all_main: "All Main Types",
    item_all_sub: "All Sub Types",
    monster_all_rank: "All Ranks",
    monster_all_weak: "All Weaknesses",
    mission_source: "Source",
    narration: "Narration",
    term_loading: "Loading explanation...",
    term_none: "No explanation found.",
    term_close: "Close",
    term_fallback: "No explanation in selected language, fallback to CHS",
    stats_build: "Build",
    stats_dialogue: "Dialogue",
    stats_refs: "Refs",
    stats_main: "Main",
    stats_avatar: "Avatar",
    stats_item: "Item",
    stats_monster: "Monster",
    stats_fail: "Failed to load stats",
  },
  JP: {
    title: "星鉄リソース検索",
    search: "検索",
    detail: "詳細",
    refs: "参照",
    loading: "読み込み中...",
    no_results: "結果なし。",
    pager_first: "先頭",
    pager_prev: "前へ",
    pager_next: "次へ",
    pager_last: "末尾",
    pager_jump: "移動",
    pager_page: "ページ",
    pager_go: "移動",
    item_all_rarity: "全レア度",
    item_all_main: "全メインタイプ",
    item_all_sub: "全サブタイプ",
    monster_all_rank: "全ランク",
    monster_all_weak: "全弱点",
    mission_source: "ソース",
    narration: "ナレーション",
    term_loading: "解説を検索中...",
    term_none: "解説が見つかりません。",
    term_close: "閉じる",
    term_fallback: "この言語の解説がないため中国語を表示",
    stats_build: "ビルド",
    stats_dialogue: "セリフ",
    stats_refs: "参照",
    stats_main: "任務",
    stats_avatar: "キャラ",
    stats_item: "アイテム",
    stats_monster: "敵",
    stats_fail: "統計の読み込み失敗",
  },
  KR: {
    title: "스타레일 리소스 검색",
    search: "검색",
    detail: "상세",
    refs: "참조",
    loading: "로딩 중...",
    no_results: "결과 없음",
    pager_first: "처음",
    pager_prev: "이전",
    pager_next: "다음",
    pager_last: "마지막",
    pager_jump: "이동",
    pager_page: "페이지",
    pager_go: "이동",
    item_all_rarity: "전체 희귀도",
    item_all_main: "전체 메인 타입",
    item_all_sub: "전체 서브 타입",
    monster_all_rank: "전체 등급",
    monster_all_weak: "전체 약점",
    mission_source: "출처",
    narration: "나레이션",
    term_loading: "설명을 불러오는 중...",
    term_none: "설명을 찾을 수 없습니다.",
    term_close: "닫기",
    term_fallback: "선택한 언어 설명이 없어 중국어로 표시",
    stats_build: "빌드",
    stats_dialogue: "대사",
    stats_refs: "참조",
    stats_main: "임무",
    stats_avatar: "캐릭터",
    stats_item: "아이템",
    stats_monster: "적",
    stats_fail: "통계 로드 실패",
  },
};

const UI_LABELS = {
  CHS: {
    "hero.title": "星铁资源查询台",
    "hero.subtitle": "分页结构：角色信息 / 对话文本搜索 / 主线任务搜索 / 物品搜索 / 怪物信息",
    "ui.lang.label": "界面语言",
    "tab.avatar": "角色信息",
    "tab.dialogue": "对话文本搜索",
    "tab.mission": "主线任务搜索",
    "tab.item": "物品搜索",
    "tab.monster": "怪物信息",
    "avatar.search.title": "角色检索",
    "avatar.result.title": "角色搜索结果",
    "avatar.detail.title": "角色详情",
    "dialogue.search.title": "对话检索",
    "dialogue.result.title": "对话搜索结果",
    "dialogue.refs.title": "对话引用明细",
    "mission.search.title": "主线任务检索",
    "mission.result.title": "主线任务结果",
    "mission.detail.title": "任务细化信息",
    "item.search.title": "物品检索",
    "item.result.title": "物品搜索结果",
    "item.detail.title": "物品详情",
    "monster.search.title": "怪物检索",
    "monster.result.title": "怪物搜索结果",
    "monster.detail.title": "怪物详情",
    "dialogue.order.asc": "按ID正序",
    "dialogue.order.desc": "按ID倒序",
    "avatar.search.placeholder": "输入角色名关键词",
    "dialogue.search.placeholder": "输入台词或说话人关键词",
    "mission.search.placeholder": "输入主线任务关键词",
    "item.search.placeholder": "输入物品或光锥关键词",
    "monster.search.placeholder": "输入怪物名、介绍或ID",
    "lang.chs": "中文",
    "lang.en": "English",
    "lang.jp": "日本語",
    "lang.kr": "한국어",
  },
  EN: {
    "hero.title": "HSR Resource Console",
    "hero.subtitle": "Sections: Avatars / Dialogue Search / Main Missions / Items / Monsters",
    "ui.lang.label": "UI Language",
    "tab.avatar": "Avatar Info",
    "tab.dialogue": "Dialogue Search",
    "tab.mission": "Main Mission Search",
    "tab.item": "Item Search",
    "tab.monster": "Monster Info",
    "avatar.search.title": "Avatar Search",
    "avatar.result.title": "Avatar Results",
    "avatar.detail.title": "Avatar Detail",
    "dialogue.search.title": "Dialogue Search",
    "dialogue.result.title": "Dialogue Results",
    "dialogue.refs.title": "Reference Details",
    "mission.search.title": "Mission Search",
    "mission.result.title": "Mission Results",
    "mission.detail.title": "Mission Detail",
    "item.search.title": "Item Search",
    "item.result.title": "Item Results",
    "item.detail.title": "Item Detail",
    "monster.search.title": "Monster Search",
    "monster.result.title": "Monster Results",
    "monster.detail.title": "Monster Detail",
    "dialogue.order.asc": "ID Asc",
    "dialogue.order.desc": "ID Desc",
    "avatar.search.placeholder": "Search avatar name",
    "dialogue.search.placeholder": "Search dialogue or speaker",
    "mission.search.placeholder": "Search mission keyword",
    "item.search.placeholder": "Search item or light cone",
    "monster.search.placeholder": "Search monster name, intro, or ID",
    "lang.chs": "中文",
    "lang.en": "English",
    "lang.jp": "日本語",
    "lang.kr": "한국어",
  },
  JP: {
    "hero.title": "星鉄リソース検索コンソール",
    "hero.subtitle": "ページ: キャラ情報 / セリフ検索 / 開拓任務 / アイテム / 敵情報",
    "ui.lang.label": "UI言語",
    "tab.avatar": "キャラ情報",
    "tab.dialogue": "セリフ検索",
    "tab.mission": "開拓任務検索",
    "tab.item": "アイテム検索",
    "tab.monster": "敵情報",
    "avatar.search.title": "キャラ検索",
    "avatar.result.title": "キャラ検索結果",
    "avatar.detail.title": "キャラ詳細",
    "dialogue.search.title": "セリフ検索",
    "dialogue.result.title": "セリフ結果",
    "dialogue.refs.title": "参照詳細",
    "mission.search.title": "任務検索",
    "mission.result.title": "任務結果",
    "mission.detail.title": "任務詳細",
    "item.search.title": "アイテム検索",
    "item.result.title": "アイテム結果",
    "item.detail.title": "アイテム詳細",
    "monster.search.title": "敵検索",
    "monster.result.title": "敵結果",
    "monster.detail.title": "敵詳細",
    "dialogue.order.asc": "ID昇順",
    "dialogue.order.desc": "ID降順",
    "avatar.search.placeholder": "キャラ名で検索",
    "dialogue.search.placeholder": "セリフ・話者を検索",
    "mission.search.placeholder": "任務キーワードを入力",
    "item.search.placeholder": "アイテム・光円錐を入力",
    "monster.search.placeholder": "敵名・紹介・IDを入力",
    "lang.chs": "中文",
    "lang.en": "English",
    "lang.jp": "日本語",
    "lang.kr": "한국어",
  },
  KR: {
    "hero.title": "스타레일 리소스 콘솔",
    "hero.subtitle": "페이지: 캐릭터 / 대사 검색 / 메인 임무 / 아이템 / 적 정보",
    "ui.lang.label": "UI 언어",
    "tab.avatar": "캐릭터 정보",
    "tab.dialogue": "대사 검색",
    "tab.mission": "메인 임무 검색",
    "tab.item": "아이템 검색",
    "tab.monster": "적 정보",
    "avatar.search.title": "캐릭터 검색",
    "avatar.result.title": "캐릭터 결과",
    "avatar.detail.title": "캐릭터 상세",
    "dialogue.search.title": "대사 검색",
    "dialogue.result.title": "대사 결과",
    "dialogue.refs.title": "참조 상세",
    "mission.search.title": "임무 검색",
    "mission.result.title": "임무 결과",
    "mission.detail.title": "임무 상세",
    "item.search.title": "아이템 검색",
    "item.result.title": "아이템 결과",
    "item.detail.title": "아이템 상세",
    "monster.search.title": "적 검색",
    "monster.result.title": "적 결과",
    "monster.detail.title": "적 상세",
    "dialogue.order.asc": "ID 오름차순",
    "dialogue.order.desc": "ID 내림차순",
    "avatar.search.placeholder": "캐릭터 이름 검색",
    "dialogue.search.placeholder": "대사/화자 검색",
    "mission.search.placeholder": "임무 키워드 입력",
    "item.search.placeholder": "아이템/광추 검색",
    "monster.search.placeholder": "적 이름, 소개, ID 검색",
    "lang.chs": "中文",
    "lang.en": "English",
    "lang.jp": "日本語",
    "lang.kr": "한국어",
  },
};

const KEY_ALIAS = {
  "action.search": "search",
  "action.viewDetail": "detail",
  "action.viewRefs": "refs",
  "stats.loading": "loading",
  "item.filter.rarity.all": "item_all_rarity",
  "item.filter.main.all": "item_all_main",
  "item.filter.sub.all": "item_all_sub",
  "monster.filter.rank.all": "monster_all_rank",
  "monster.filter.weakness.all": "monster_all_weak",
};

const state = {
  uiLang: "CHS",
  currentPage: "avatar",
  avatar: { q: "", lang: "CHS", page: 1, page_size: 20 },
  dialogue: { q: "", lang: "CHS", order: "asc", page: 1, page_size: 20 },
  dialogueRefs: { talkSentenceId: null, page: 1, page_size: 20 },
  mission: { q: "", lang: "CHS", sub_preview_limit: 8, page: 1, page_size: 20 },
  item: { q: "", lang: "CHS", rarity: "", item_main_type: "", item_sub_type: "", page: 1, page_size: 20 },
  monster: { q: "", lang: "CHS", rank: "", weakness: "", page: 1, page_size: 20 },
  selected: { avatarId: null, missionId: null, itemId: null, monsterId: null },
};

function t(key) {
  const pack = UI_I18N[state.uiLang] || UI_I18N.CHS;
  if (pack[key]) return pack[key];
  const alias = KEY_ALIAS[key];
  if (alias && pack[alias]) return pack[alias];
  const labels = UI_LABELS[state.uiLang] || UI_LABELS.CHS;
  if (labels[key]) return labels[key];
  const fallbackPack = UI_I18N.CHS || {};
  if (fallbackPack[key]) return fallbackPack[key];
  if (alias && fallbackPack[alias]) return fallbackPack[alias];
  const fallbackLabels = UI_LABELS.CHS || {};
  return fallbackLabels[key] || key;
}

function normalizeUiLang(raw) {
  const token = String(raw || "").toLowerCase();
  if (token.startsWith("zh")) return "CHS";
  if (token.startsWith("ja") || token.startsWith("jp")) return "JP";
  if (token.startsWith("ko") || token.startsWith("kr")) return "KR";
  if (token.startsWith("en")) return "EN";
  if (UI_I18N[token.toUpperCase()]) return token.toUpperCase();
  return "CHS";
}

function detectInitialUiLang() {
  const saved = localStorage.getItem("hsrdb-ui-lang");
  if (saved && UI_I18N[saved]) return saved;
  const langs = [];
  if (Array.isArray(navigator.languages)) langs.push(...navigator.languages);
  if (navigator.language) langs.push(navigator.language);
  for (const raw of langs) {
    const mapped = normalizeUiLang(raw);
    if (mapped) return mapped;
  }
  return "CHS";
}

function applyUiLanguage(lang, persist = true) {
  state.uiLang = normalizeUiLang(lang);
  if (persist) localStorage.setItem("hsrdb-ui-lang", state.uiLang);
  const uiSel = el("ui-lang");
  if (uiSel) uiSel.value = state.uiLang;
  document.title = t("title");
  document.documentElement.lang =
    state.uiLang === "EN" ? "en" : state.uiLang === "JP" ? "ja" : state.uiLang === "KR" ? "ko" : "zh-CN";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (!key) return;
    node.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    const key = node.dataset.i18nPlaceholder;
    if (!key) return;
    node.setAttribute("placeholder", t(key));
  });
  const closeBtn = el("term-popover-close");
  if (closeBtn) closeBtn.textContent = t("term_close");
}

function normalizeHexColor(raw) {
  const token = (raw || "").trim().replaceAll('"', "").replaceAll("'", "");
  const short = token.match(/^#([0-9a-fA-F]{6})$/);
  if (short) return token;
  const long = token.match(/^#([0-9a-fA-F]{8})$/);
  if (long) {
    const hex = long[1];
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    const a = (parseInt(hex.slice(6, 8), 16) / 255).toFixed(3);
    return `rgba(${r},${g},${b},${a})`;
  }
  return "";
}

function stripHtmlToText(rawHtml) {
  const text = String(rawHtml || "").replace(/<[^>]+>/g, "").trim();
  return text
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'");
}

function formatGameText(raw) {
  if (raw === null || raw === undefined) return "";
  let safe = esc(String(raw));
  safe = safe.replace(/\{RUBY_B#([^}]+)\}([\s\S]*?)\{RUBY_E#\}/gi, (_, rubyText, baseText) => `<ruby class="game-ruby">${baseText}<rt>${rubyText}</rt></ruby>`);
  safe = safe.replace(/\{RUBY_B#[^}]+\}/gi, "").replace(/\{RUBY_E#\}/gi, "");
  safe = safe.replace(/\{NICKNAME\}/g, "开拓者");
  safe = safe.replace(/\r\n/g, "\n").replace(/\n/g, "<br>").replace(/\\n/g, "<br>");
  safe = safe.replace(/&lt;unbreak&gt;/gi, '<span class="game-unbreak">').replace(/&lt;\/unbreak&gt;/gi, "</span>");
  safe = safe.replace(/&lt;u&gt;/gi, "<u>").replace(/&lt;\/u&gt;/gi, "</u>");
  safe = safe.replace(/<u>([\s\S]*?)<\/u>/gi, (_, innerHtml) => {
    const term = stripHtmlToText(innerHtml);
    if (!term) return innerHtml;
    return `<button type="button" class="term-link" data-term="${esc(term)}">${innerHtml}</button>`;
  });
  safe = safe.replace(/&lt;i&gt;/gi, "<i>").replace(/&lt;\/i&gt;/gi, "</i>");
  safe = safe.replace(/&lt;b&gt;/gi, "<strong>").replace(/&lt;\/b&gt;/gi, "</strong>");
  safe = safe.replace(/&lt;color=([^&]+?)&gt;/gi, (_, token) => {
    const color = normalizeHexColor(token);
    return color ? `<span class="game-color" style="color:${color};">` : '<span class="game-color">';
  });
  safe = safe.replace(/&lt;\/color&gt;/gi, "</span>");
  safe = safe.replace(/&lt;\/?size[^&]*&gt;/gi, "").replace(/&lt;\/?align[^&]*&gt;/gi, "");
  return safe;
}

const CONFIGURED_API_BASE = (() => {
  const raw = (window.PUBLIC_API_BASE || "").trim();
  if (!raw) return "/api";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
})();

function buildApiPath(path) {
  const p = path.startsWith("/api/") ? path.slice(4) : path;
  const suffix = p.startsWith("/") ? p : `/${p}`;
  return `${CONFIGURED_API_BASE}${suffix}`;
}

async function api(path, params = {}) {
  const u = new URL(buildApiPath(path), window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") u.searchParams.set(k, v);
  });
  const r = await fetch(u);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

function bindEnter(input, handler) {
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handler();
  });
}

function card(meta, line, extra = "") {
  return `<div class="item"><div class="meta">${meta}</div><div class="line">${line}</div>${extra}</div>`;
}

function stateCard(text, warn = false) {
  return `<div class="item"><div class="line ${warn ? "warn" : ""}">${esc(text)}</div></div>`;
}

function setLoading(target, text = null) {
  target.innerHTML = stateCard(text || t("loading"));
}

function setEmpty(target, text = null) {
  target.innerHTML = stateCard(text || t("no_results"));
}

function setError(target, err) {
  target.innerHTML = stateCard(err.message || String(err), true);
}

const termExplainState = {
  requestId: 0,
};

function currentDataLang() {
  if (state.currentPage === "avatar") return state.avatar.lang || "CHS";
  if (state.currentPage === "dialogue") return state.dialogue.lang || "CHS";
  if (state.currentPage === "mission") return state.mission.lang || "CHS";
  if (state.currentPage === "item") return state.item.lang || "CHS";
  if (state.currentPage === "monster") return state.monster.lang || "CHS";
  return "CHS";
}

function ensureTermPopover() {
  let pop = el("term-popover");
  if (pop) return pop;
  pop = document.createElement("div");
  pop.id = "term-popover";
  pop.className = "term-popover hidden";
  pop.innerHTML = `
    <div class="term-popover-head">
      <strong id="term-popover-title"></strong>
      <button type="button" id="term-popover-close" class="term-popover-close">${esc(t("term_close"))}</button>
    </div>
    <div id="term-popover-body" class="term-popover-body"></div>
  `;
  document.body.appendChild(pop);
  const closeBtn = el("term-popover-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => closeTermPopover());
  }
  return pop;
}

function closeTermPopover() {
  const pop = el("term-popover");
  if (!pop) return;
  pop.classList.add("hidden");
}

function positionTermPopover(anchorEl) {
  const pop = el("term-popover");
  if (!pop || !anchorEl) return;
  const rect = anchorEl.getBoundingClientRect();
  const margin = 12;
  const maxLeft = Math.max(margin, window.innerWidth - pop.offsetWidth - margin);
  const left = Math.min(maxLeft, Math.max(margin, rect.left));
  const top = rect.bottom + 8;
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
}

async function openTermPopover(term, anchorEl) {
  const cleanTerm = String(term || "").trim();
  if (!cleanTerm) return;

  const pop = ensureTermPopover();
  const title = el("term-popover-title");
  const body = el("term-popover-body");
  if (!title || !body) return;

  title.textContent = cleanTerm;
  body.innerHTML = `<div class="item"><div class="line">${esc(t("term_loading"))}</div></div>`;
  pop.classList.remove("hidden");
  positionTermPopover(anchorEl);

  const requestId = ++termExplainState.requestId;
  try {
    const lang = currentDataLang();
    const data = await api("/api/term/explain", { term: cleanTerm, lang, limit: 5, module: state.currentPage });
    if (requestId !== termExplainState.requestId) return;
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) {
      body.innerHTML = `<div class="item"><div class="line">${esc(t("term_none"))}</div></div>`;
      positionTermPopover(anchorEl);
      return;
    }

    const fallbackNotice =
      data.used_lang && data.lang && data.used_lang !== data.lang
        ? `<div class="subtle term-fallback">${esc(t("term_fallback"))}</div>`
        : "";
    body.innerHTML = `
      ${fallbackNotice}
      ${items
        .map(
          (it, idx) => `
          <div class="item">
            <div class="meta">${idx === 0 ? "Top 1" : `候选 ${idx + 1}`}</div>
            <div class="line">${formatGameText(it.text || "")}</div>
          </div>
        `
        )
        .join("")}
    `;
    positionTermPopover(anchorEl);
  } catch (err) {
    if (requestId !== termExplainState.requestId) return;
    body.innerHTML = `<div class="item"><div class="line warn">${esc(err.message || String(err))}</div></div>`;
    positionTermPopover(anchorEl);
  }
}

function renderPager(container, payload, onPageChange) {
  const total = Number(payload.total || 0);
  const page = Math.max(1, Number(payload.page || 1));
  const totalPages = Math.max(1, Number(payload.total_pages || 1));
  const infoText =
    state.uiLang === "EN"
      ? `Page ${page}/${totalPages}, ${total} total`
      : state.uiLang === "JP"
        ? `${page}/${totalPages} ページ, 合計 ${total}`
        : state.uiLang === "KR"
          ? `${page}/${totalPages} 페이지, 총 ${total}`
          : `第 ${page}/${totalPages} 页，共 ${total} 条`;

  container.innerHTML = `
    <button class="secondary" data-role="first" ${page <= 1 ? "disabled" : ""}>${esc(t("pager_first"))}</button>
    <button class="secondary" data-role="prev" ${page <= 1 ? "disabled" : ""}>${esc(t("pager_prev"))}</button>
    <button class="secondary" data-role="next" ${page >= totalPages ? "disabled" : ""}>${esc(t("pager_next"))}</button>
    <button class="secondary" data-role="last" ${page >= totalPages ? "disabled" : ""}>${esc(t("pager_last"))}</button>
    <span class="info">${esc(infoText)}</span>
    <span class="jump">
      ${esc(t("pager_jump"))}
      <input class="page-input" data-role="page-input" type="number" min="1" max="${totalPages}" value="${page}">
      ${esc(t("pager_page"))}
      <button class="secondary" data-role="go">${esc(t("pager_go"))}</button>
    </span>
  `;

  const first = container.querySelector("button[data-role='first']");
  const prev = container.querySelector("button[data-role='prev']");
  const next = container.querySelector("button[data-role='next']");
  const last = container.querySelector("button[data-role='last']");
  const go = container.querySelector("button[data-role='go']");
  const pageInput = container.querySelector("input[data-role='page-input']");

  const goPage = (rawPage) => {
    const n = Math.floor(Number(rawPage));
    if (Number.isNaN(n)) return;
    const safe = Math.max(1, Math.min(totalPages, n));
    if (safe !== page) onPageChange(safe);
  };

  if (first) first.onclick = () => goPage(1);
  if (prev) prev.onclick = () => onPageChange(page - 1);
  if (next) next.onclick = () => onPageChange(page + 1);
  if (last) last.onclick = () => goPage(totalPages);
  if (go) go.onclick = () => goPage(pageInput ? pageInput.value : page);
  if (pageInput) {
    pageInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") goPage(pageInput.value);
    });
  }
}

function renderLevelTable(rows) {
  if (!rows.length) return "无";
  const body = rows
    .map(
      (r) => `<tr><td>Lv${esc(r.level)}</td><td>P${esc(r.promotion)}</td><td>${fmtNum(r.hp)}</td><td>${fmtNum(r.attack)}</td><td>${fmtNum(r.defence)}</td><td>${fmtNum(r.speed)}</td></tr>`
    )
    .join("");
  return `<table class="metric-table"><thead><tr><th>等级</th><th>晋阶</th><th>HP</th><th>ATK</th><th>DEF</th><th>SPD</th></tr></thead><tbody>${body}</tbody></table>`;
}

function formatParamValues(values) {
  if (!Array.isArray(values) || !values.length) return "-";
  return values.map((v) => fmtNum(v, 4)).join(", ");
}

function switchPage(pageName) {
  state.currentPage = pageName;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.page === pageName);
  });
  document.querySelectorAll(".page-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `page-${pageName}`);
  });
}

async function loadStats() {
  const stats = el("stats");
  try {
    const data = await api("/api/stats");
    const tbc = data.table_counts || {};
    stats.innerHTML = `<strong>${esc(t("stats_build"))}</strong> ${esc(data.build_at || "-")} | ${esc(t("stats_dialogue"))} ${esc(tbc.talk_sentence || 0)} | ${esc(t("stats_refs"))} ${esc(tbc.story_reference || 0)} | ${esc(t("stats_main"))} ${esc(tbc.main_mission || 0)} | ${esc(t("stats_avatar"))} ${esc(tbc.avatar || 0)} | ${esc(t("stats_item"))} ${esc(tbc.item || 0)} | ${esc(t("stats_monster"))} ${esc(data.monster_count || 0)}`;
  } catch (err) {
    stats.innerHTML = `<span class="warn">${esc(t("stats_fail"))}: ${esc(err.message)}</span>`;
  }
}

async function searchAvatar(page = 1) {
  state.avatar.page = page;
  state.avatar.q = el("avatar-q").value.trim();
  state.avatar.lang = el("avatar-lang").value;

  const list = el("avatar-list");
  const pager = el("avatar-pager");
  setLoading(list);

  try {
    const data = await api("/api/search/avatar", state.avatar);
    if (!data.items.length) {
      setEmpty(list);
      pager.innerHTML = "";
      return;
    }

    list.innerHTML = data.items
      .map((it) =>
        card(
          `Avatar ${it.avatar_id} | ${esc(tEnum("rarity", it.rarity, state.avatar.lang))}`,
          `<strong>${formatGameText(it.name || "(no name)")}</strong><br>${formatGameText(it.full_name || "")}<br>${esc(tEnum("damage_type", it.damage_type, state.avatar.lang))} / ${esc(tEnum("avatar_base_type", it.avatar_base_type, state.avatar.lang))}`,
          `<div class="actions"><button class="link-btn avatar-detail" data-id="${it.avatar_id}">${esc(t("detail"))}</button></div>`
        )
      )
      .join("");

    renderPager(pager, data, (nextPage) => searchAvatar(nextPage));
  } catch (err) {
    setError(list, err);
    pager.innerHTML = "";
  }
}

async function loadAvatarDetail(avatarId) {
  state.selected.avatarId = avatarId;
  const detail = el("avatar-detail");
  setLoading(detail);
  try {
    const data = await api(`/api/avatar/${avatarId}`, { lang: state.avatar.lang, skill_level_limit: 10, level_max: 80 });
    if (data.error) {
      setEmpty(detail);
      return;
    }

    const a = data.avatar || {};
    const promotions = data.promotions || [];
    const checkpoints = data.level_checkpoints || [];
    const levelStats = data.level_stats || [];
    const skills = data.skills || [];
    const ranks = data.ranks || [];
    const stories = data.personal_stories || [];

    const promotionText = promotions.length
      ? promotions.map((p) => `P${esc(p.promotion)} Lv${esc(p.max_level)} | HP ${fmtNum(p.hp_base)} + ${fmtNum(p.hp_add)}*L | ATK ${fmtNum(p.attack_base)} + ${fmtNum(p.attack_add)}*L | DEF ${fmtNum(p.defence_base)} + ${fmtNum(p.defence_add)}*L | SPD ${fmtNum(p.speed_base)}`).join("<br>")
      : "无";

    const skillBlocks = skills.length
      ? skills
          .map((s) => {
            const lvRows = (s.levels || []).map((lv) => `<tr><td>Lv${esc(lv.level)}</td><td class="mono">${esc(formatParamValues(lv.param_values))}</td><td>${formatGameText(lv.description || lv.description_raw || "-")}</td></tr>`).join("");
            return card(`${esc(s.skill_id)} | ${esc(s.tag || "-")} | 显示 ${esc(s.shown_levels)}/${esc(s.available_levels)} 级`, `<strong>${formatGameText(s.name || "(no name)")}</strong><br><span class="subtle">${esc(s.skill_effect || "-")} | ${esc(s.attack_type || "-")} | ${esc(s.stance_damage_type || "-")}</span>`, lvRows ? `<div class="actions"><table class="metric-table"><thead><tr><th>等级</th><th>参数</th><th>描述</th></tr></thead><tbody>${lvRows}</tbody></table></div>` : `<div class="subtle">无等级数据</div>`);
          })
          .join("")
      : stateCard("无技能数据");

    const rankBlocks = ranks.length
      ? ranks.map((r) => card(`E${esc(r.rank)} (${esc(r.rank_id)})`, `<strong>${formatGameText(r.name || `星魂 ${r.rank || ""}`)}</strong><br>${formatGameText(r.description || "无可解析描述")}<br><span class="subtle">参数: ${esc(formatParamValues(r.param_values))}</span>`)).join("")
      : stateCard("无星魂数据");

    const storyBlocks = stories.length
      ? stories.map((s) => card(`${esc(s.title || `故事 ${s.story_id}`)} | StoryID ${esc(s.story_id)} | Unlock ${esc(s.unlock ?? "-")}`, `${formatGameText(s.content || "暂无故事正文")}`)).join("")
      : stateCard("无个人故事数据");

    detail.innerHTML = `${card(`Avatar ${a.avatar_id}`, `<strong>${formatGameText(a.name || "")}</strong><br>${formatGameText(a.full_name || "")}<br>${esc(tEnum("damage_type", a.damage_type, state.avatar.lang))} / ${esc(tEnum("avatar_base_type", a.avatar_base_type, state.avatar.lang))} | 稀有度 ${esc(tEnum("rarity", a.rarity, state.avatar.lang))}`)}${card("晋阶基础参数", promotionText)}${card("80级基础属性（每10级）", renderLevelTable(checkpoints))}${card("80级完整属性曲线", `<details><summary class="subtle">展开 Lv1-Lv80 全部属性</summary>${renderLevelTable(levelStats)}</details>`)}${card("技能（1-10级具体展示）", skillBlocks)}${card("星魂（E1-E6）", rankBlocks)}${card("个人故事", storyBlocks)}`;
  } catch (err) {
    setError(detail, err);
  }
}
async function searchDialogue(page = 1) {
  state.dialogue.page = page;
  state.dialogue.q = el("dialogue-q").value.trim();
  state.dialogue.lang = el("dialogue-lang").value;
  state.dialogue.order = el("dialogue-order").value || "asc";

  const list = el("dialogue-list");
  const pager = el("dialogue-pager");
  setLoading(list);

  try {
    const data = await api("/api/search/dialogue", state.dialogue);
    if (!data.items.length) {
      setEmpty(list);
      pager.innerHTML = "";
      return;
    }

    list.innerHTML = data.items
      .map((it) =>
        card(
          `TalkSentenceID ${it.talk_sentence_id}`,
          `<strong>${formatGameText(it.speaker || t("narration"))}</strong>: ${formatGameText(it.text || "")}`,
          `<div class="actions"><button class="link-btn dialogue-ref" data-id="${it.talk_sentence_id}">${esc(t("refs"))}</button></div>`
        )
      )
      .join("");

    renderPager(pager, data, (nextPage) => searchDialogue(nextPage));
  } catch (err) {
    setError(list, err);
    pager.innerHTML = "";
  }
}

async function loadDialogueRefs(talkSentenceId, page = 1) {
  state.dialogueRefs.talkSentenceId = talkSentenceId;
  state.dialogueRefs.page = page;

  const refs = el("dialogue-refs");
  const pager = el("dialogue-refs-pager");
  setLoading(refs);

  try {
    const data = await api(`/api/dialogue/${talkSentenceId}/refs`, {
      page: state.dialogueRefs.page,
      page_size: state.dialogueRefs.page_size,
    });

    if (!data.items.length) {
      setEmpty(refs);
      pager.innerHTML = "";
      return;
    }

    refs.innerHTML = data.items
      .map((it) =>
        card(
          `${esc(it.source_group)} | ${esc(it.task_type || "-")} | timeline ${esc(it.timeline_name || "-")}`,
          `${esc(it.source_path)}<br><code>${esc(it.json_path)}</code>`
        )
      )
      .join("");

    renderPager(pager, data, (nextPage) => loadDialogueRefs(talkSentenceId, nextPage));
  } catch (err) {
    setError(refs, err);
    pager.innerHTML = "";
  }
}

async function searchMission(page = 1) {
  state.mission.page = page;
  state.mission.q = el("mission-q").value.trim();
  state.mission.lang = el("mission-lang").value;

  const list = el("mission-list");
  const pager = el("mission-pager");
  setLoading(list);

  try {
    const data = await api("/api/search/mission", state.mission);
    if (!data.items.length) {
      setEmpty(list);
      pager.innerHTML = "";
      return;
    }

    list.innerHTML = data.items
      .map((it) => {
        const subs = Array.isArray(it.sub_missions_preview) ? it.sub_missions_preview : [];
        const subPreview = subs.length
          ? subs.map((s) => `${esc(s.sub_mission_id)}: ${formatGameText(s.target || "")}<br><span class="subtle">${formatGameText(s.description || "")}</span>`).join("<br>")
          : `<span class="subtle">暂无子任务</span>`;
        const subMeta = `<span class="badge">子任务 ${esc(it.sub_mission_count || 0)} 个</span>${it.sub_missions_more ? `<span class="subtle">另有 ${esc(it.sub_missions_more)} 个未展开</span>` : ""}`;
        return card(
          `MainMission ${it.main_mission_id} | ${esc(it.mission_type || "-")} | Chapter ${esc(it.chapter_id || "-")}`,
          `${formatGameText(it.name || "(no name)")}<br><div class="actions">${subMeta}</div><div class="sub-preview">${subPreview}</div>`,
          `<div class="actions"><button class="link-btn mission-detail" data-id="${it.main_mission_id}">${esc(t("detail"))}</button></div>`
        );
      })
      .join("");

    renderPager(pager, data, (nextPage) => searchMission(nextPage));
  } catch (err) {
    setError(list, err);
    pager.innerHTML = "";
  }
}

async function loadMissionDetail(mainMissionId) {
  state.selected.missionId = mainMissionId;
  const detail = el("mission-detail");
  setLoading(detail);

  try {
    const data = await api(`/api/mission/${mainMissionId}`, {
      lang: state.mission.lang,
      ref_limit: 200,
      dialogue_limit: 300,
    });
    if (data.error) {
      setEmpty(detail);
      return;
    }

    const m = data.main_mission || {};
    const subs = data.sub_missions || [];
    const dialogues = data.dialogues || [];
    const refs = data.story_refs || [];

    const subsHtml = subs.length ? subs.map((s) => `${esc(s.sub_mission_id)}: ${formatGameText(s.target || "")}<br><span class="subtle">${formatGameText(s.description || "")}</span>`).join("<br>") : "无";

    const dialogueHtml = dialogues.length
      ? dialogues
          .map((d) => {
            const speaker = d.speaker || t("narration");
            const pathHint = d.source_path ? `<br><span class="subtle">${esc(t("mission_source"))}: ${esc(d.source_path)}</span>` : "";
            return `<div class="item"><div class="meta">Talk ${esc(d.talk_sentence_id)} | Voice ${esc(d.voice_id || "-")}</div><div class="line"><strong>${formatGameText(speaker)}</strong>: ${formatGameText(d.text || "")}${pathHint}</div></div>`;
          })
          .join("")
      : stateCard("无可解析剧情对话。");

    const refsHtml = refs.length
      ? `<details><summary class="subtle">查看引用路径（${refs.length}）</summary>${refs
          .slice(0, 120)
          .map((r) => `<div class="item"><div class="meta">${esc(r.source_group || "-")} | ${esc(r.task_type || "-")}</div><div class="line">${esc(r.source_path)}<br><code>${esc(r.json_path)}</code></div></div>`)
          .join("")}</details>`
      : "无引用路径数据";

    detail.innerHTML = `${card(`MainMission ${m.main_mission_id} | ${esc(m.mission_type || "-")}`, `${formatGameText(m.name || "")}<br>World ${esc(m.world_id)} | Chapter ${esc(m.chapter_id)} | Pack ${esc(m.mission_pack)}`)}${card("子任务", subsHtml)}${card("剧情对话（按顺序）", dialogueHtml)}${card("引用路径", refsHtml)}`;
  } catch (err) {
    setError(detail, err);
  }
}

async function loadItemFacets() {
  try {
    const prev = { rarity: el("item-rarity").value, main: el("item-main-type").value, sub: el("item-sub-type").value };
    const data = await api("/api/item/facets");
    const raritySel = el("item-rarity");
    const mainSel = el("item-main-type");
    const subSel = el("item-sub-type");

    raritySel.innerHTML = `<option value="">${esc(t("item_all_rarity"))}</option>${(data.rarity || []).map((v) => `<option value="${esc(v)}">${esc(tEnum("rarity", v, state.item.lang))}</option>`).join("")}`;
    mainSel.innerHTML = `<option value="">${esc(t("item_all_main"))}</option>${(data.item_main_type || []).map((v) => `<option value="${esc(v)}">${esc(tEnum("item_type", v, state.item.lang))}</option>`).join("")}`;
    subSel.innerHTML = `<option value="">${esc(t("item_all_sub"))}</option>${(data.item_sub_type || []).map((v) => `<option value="${esc(v)}">${esc(tEnum("item_type", v, state.item.lang))}</option>`).join("")}`;

    if (prev.rarity) raritySel.value = prev.rarity;
    if (prev.main) mainSel.value = prev.main;
    if (prev.sub) subSel.value = prev.sub;
  } catch (err) {
    console.error(err);
  }
}

async function searchItem(page = 1) {
  state.item.page = page;
  state.item.q = el("item-q").value.trim();
  state.item.lang = el("item-lang").value;
  state.item.rarity = el("item-rarity").value;
  state.item.item_main_type = el("item-main-type").value;
  state.item.item_sub_type = el("item-sub-type").value;

  const list = el("item-list");
  const pager = el("item-pager");
  setLoading(list);

  try {
    const data = await api("/api/search/item", state.item);
    if (!data.items.length) {
      setEmpty(list);
      pager.innerHTML = "";
      return;
    }

    list.innerHTML = data.items
      .map((it) => {
        const bgLine = it.bg_description ? `<br><span class="subtle">${formatGameText(it.bg_description)}</span>` : "";
        const lc = it.light_cone;
        const lcLine = lc ? `<br><span class="badge">光锥 ${esc(lc.avatar_base_type || "-")}</span> <strong>${formatGameText(lc.skill_name || "")}</strong>: ${formatGameText(lc.skill_desc || "")}` : "";
        return card(`Item ${it.item_id} | ${esc(tEnum("rarity", it.rarity, state.item.lang))} | ${esc(tEnum("item_type", it.item_main_type, state.item.lang))}/${esc(tEnum("item_type", it.item_sub_type, state.item.lang))}`, `<strong>${formatGameText(it.name || "(no name)")}</strong><br>${formatGameText(it.description || "")}${bgLine}${lcLine}<br>${formatGameText(it.purpose || "")}`, `<div class="actions"><button class="link-btn item-detail" data-id="${it.item_id}">${esc(t("detail"))}</button></div>`);
      })
      .join("");

    renderPager(pager, data, (nextPage) => searchItem(nextPage));
  } catch (err) {
    setError(list, err);
    pager.innerHTML = "";
  }
}

async function loadItemDetail(itemId) {
  state.selected.itemId = itemId;
  const detail = el("item-detail");
  setLoading(detail);

  try {
    const data = await api(`/api/item/${itemId}`, { lang: state.item.lang });
    if (data.error) {
      setEmpty(detail);
      return;
    }

    const it = data.item;
    const lc = data.light_cone;
    const lcLevels = lc && Array.isArray(lc.levels)
      ? lc.levels.map((lv) => `<tr><td>S${esc(lv.level)}</td><td class="mono">${esc(formatParamValues(lv.param_values))}</td><td>${formatGameText(lv.skill_desc || "-")}</td></tr>`).join("")
      : "";

    detail.innerHTML = `${card(`Item ${it.item_id} | ${esc(tEnum("rarity", it.rarity, state.item.lang))}`, `<strong>${formatGameText(it.name || "")}</strong><br>${formatGameText(it.description || "")}<br>背景文本: ${formatGameText(it.bg_description || "-")}<br>用途: ${formatGameText(it.purpose || "-")}`)}${card("分类", `主类型: ${esc(tEnum("item_type", it.item_main_type, state.item.lang))}<br>子类型: ${esc(tEnum("item_type", it.item_sub_type, state.item.lang))}<br>来源文件: ${esc(it.source_file || "-")}`)}${lc ? card("光锥效果文本", `命途: ${esc(tEnum("avatar_base_type", lc.avatar_base_type, state.item.lang))} | SkillID ${esc(lc.skill_id || "-")} | 叠影上限 ${esc(lc.max_rank || "-")}`, lcLevels ? `<div class="actions"><table class="metric-table"><thead><tr><th>叠影</th><th>参数</th><th>效果文本</th></tr></thead><tbody>${lcLevels}</tbody></table></div>` : `<div class="subtle">无光锥技能文本</div>`) : ""}${card("显示字段", `PileLimit: ${esc(it.pile_limit || "-")}<br>Icon: <code>${esc(it.icon_path || "-")}</code><br>Figure: <code>${esc(it.figure_icon_path || "-")}</code>`)}`;
  } catch (err) {
    setError(detail, err);
  }
}
async function loadMonsterFacets() {
  try {
    const prevRank = el("monster-rank").value;
    const prevWeak = el("monster-weakness").value;
    const data = await api("/api/monster/facets");
    const rankSel = el("monster-rank");
    const weakSel = el("monster-weakness");

    rankSel.innerHTML = `<option value="">${esc(t("monster_all_rank"))}</option>${(data.rank || []).map((v) => `<option value="${esc(v)}">${esc(tEnum("monster_rank", v, state.uiLang))}</option>`).join("")}`;
    weakSel.innerHTML = `<option value="">${esc(t("monster_all_weak"))}</option>${(data.weakness || []).map((v) => `<option value="${esc(v)}">${esc(tEnum("damage_type", v, state.uiLang))}</option>`).join("")}`;

    if (prevRank) rankSel.value = prevRank;
    if (prevWeak) weakSel.value = prevWeak;
  } catch (err) {
    console.error(err);
  }
}

async function searchMonster(page = 1) {
  state.monster.page = page;
  state.monster.q = el("monster-q").value.trim();
  state.monster.lang = el("monster-lang").value;
  state.monster.rank = el("monster-rank").value;
  state.monster.weakness = el("monster-weakness").value;

  const list = el("monster-list");
  const pager = el("monster-pager");
  setLoading(list);

  try {
    const data = await api("/api/search/monster", state.monster);
    if (!data.items.length) {
      setEmpty(list);
      pager.innerHTML = "";
      return;
    }

    list.innerHTML = data.items
      .map((it) => {
        const weakText = (it.stance_weak_list || []).map((w) => tEnum("damage_type", w, state.uiLang)).join(" / ");
        return card(
          `Monster ${it.monster_id} | ${esc(tEnum("monster_rank", it.rank, state.uiLang))} | Template ${esc(it.monster_template_id || "-")}`,
          `<strong>${formatGameText(it.name || `Monster ${it.monster_id}`)}</strong><br>${formatGameText(it.introduction || "暂无介绍")}<br><span class="subtle">弱点: ${esc(weakText || "-")} | 韧性: ${esc(tEnum("damage_type", it.stance_type, state.uiLang))}</span>`,
          `<div class="actions"><button class="link-btn monster-detail" data-id="${it.monster_id}">${esc(t("detail"))}</button></div>`
        );
      })
      .join("");

    renderPager(pager, data, (nextPage) => searchMonster(nextPage));
  } catch (err) {
    setError(list, err);
    pager.innerHTML = "";
  }
}

async function loadMonsterDetail(monsterId) {
  state.selected.monsterId = monsterId;
  const detail = el("monster-detail");
  setLoading(detail);

  try {
    const data = await api(`/api/monster/${monsterId}`, { lang: state.monster.lang });
    if (data.error) {
      setEmpty(detail);
      return;
    }

    const m = data.monster || {};
    const skills = data.skills || [];
    const abilities = data.abilities || [];

    const weakText = (m.stance_weak_list || []).map((w) => tEnum("damage_type", w, state.uiLang)).join(" / ");
    const ratioText = `ATK x${fmtNum(m.attack_modify_ratio, 4)} | DEF x${fmtNum(m.defence_modify_ratio, 4)} | HP x${fmtNum(m.hp_modify_ratio, 4)} | SPD x${fmtNum(m.speed_modify_ratio, 4)} | Stance x${fmtNum(m.stance_modify_ratio, 4)}`;

    const baseStats = m.base_stats || {};
    const scaledStats = m.scaled_stats || {};

    const resistText = (m.damage_type_resistance || []).length
      ? m.damage_type_resistance.map((r) => `<span class="badge">${esc(tEnum("damage_type", r.damage_type, state.uiLang))} ${esc(`${fmtNum(Number(r.value || 0) * 100, 2)}%`)}</span>`).join("")
      : "无";

    const skillRows = skills
      .map((s) => {
        const desc = formatGameText(s.description || s.description_raw || "-");
        const params = esc(formatParamValues(s.param_values));
        const tag = s.skill_tag ? formatGameText(s.skill_tag) : "-";
        const ov = s.has_override_params ? `<span class="badge">覆盖参数</span>` : "";
        return `<div class="item"><div class="meta">Skill ${esc(s.skill_id)} | ${esc(tEnum("damage_type", s.damage_type, state.uiLang))} | ${esc(tEnum("attack_type", s.attack_type, state.uiLang))}</div><div class="line"><strong>${formatGameText(s.name || `Skill ${s.skill_id}`)}</strong><br><span class="subtle">${tag}</span><br>${desc}<br><span class="mono">${params}</span>${ov}</div></div>`;
      })
      .join("");

    const abilityText = abilities.length
      ? abilities.map((a) => `<div class="item"><div class="meta">${esc(a.key)}</div><div class="line">${formatGameText(a.text || a.key)}</div></div>`).join("")
      : stateCard("无能力关键词");

    detail.innerHTML = `${card(`Monster ${m.monster_id} | ${esc(tEnum("monster_rank", m.rank, state.uiLang))}`, `<strong>${formatGameText(m.name || `Monster ${m.monster_id}`)}</strong><br>${formatGameText(m.introduction || "暂无介绍")}<br><span class="subtle">弱点: ${esc(weakText || "-")} | 韧性: ${esc(tEnum("damage_type", m.stance_type, state.uiLang))}</span>`)}${card("基础属性", `HP ${fmtNum(baseStats.hp_base)} | ATK ${fmtNum(baseStats.attack_base)} | DEF ${fmtNum(baseStats.defence_base)} | SPD ${fmtNum(baseStats.speed_base)} | Stance ${fmtNum(baseStats.stance_base)}`)}${card("当前系数下属性", `HP ${fmtNum(scaledStats.hp)} | ATK ${fmtNum(scaledStats.attack)} | DEF ${fmtNum(scaledStats.defence)} | SPD ${fmtNum(scaledStats.speed)} | Stance ${fmtNum(scaledStats.stance)}`)}${card("系数", ratioText)}${card("属性抗性", resistText)}${card("技能", skillRows || stateCard("无技能信息"))}${card("能力关键词", abilityText)}${card("资源路径", `Config: <code>${esc(m.json_config || "-")}</code><br>AI: <code>${esc(m.ai_path || "-")}</code><br>Icon: <code>${esc(m.icon_path || "-")}</code><br>Image: <code>${esc(m.image_path || "-")}</code>`)}`;
  } catch (err) {
    setError(detail, err);
  }
}

function attachTabs() {
  el("tabs").addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.classList.contains("tab")) return;
    const page = target.dataset.page;
    if (!page) return;
    switchPage(page);
  });
}

function attachEvents() {
  el("ui-lang").addEventListener("change", async () => {
    applyUiLanguage(el("ui-lang").value, true);
    await loadItemFacets();
    await loadMonsterFacets();
    await loadStats();
    await searchAvatar(state.avatar.page || 1);
    await searchDialogue(state.dialogue.page || 1);
    await searchMission(state.mission.page || 1);
    await searchItem(state.item.page || 1);
    await searchMonster(state.monster.page || 1);
    if (state.selected.avatarId) await loadAvatarDetail(state.selected.avatarId);
    if (state.dialogueRefs.talkSentenceId) await loadDialogueRefs(state.dialogueRefs.talkSentenceId, state.dialogueRefs.page || 1);
    if (state.selected.missionId) await loadMissionDetail(state.selected.missionId);
    if (state.selected.itemId) await loadItemDetail(state.selected.itemId);
    if (state.selected.monsterId) await loadMonsterDetail(state.selected.monsterId);
  });

  document.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const termBtn = target.closest(".term-link");
    if (termBtn) {
      e.preventDefault();
      const term = termBtn.dataset.term || termBtn.textContent || "";
      openTermPopover(term, termBtn);
      return;
    }
    const pop = el("term-popover");
    if (!pop || pop.classList.contains("hidden")) return;
    if (!pop.contains(target)) {
      closeTermPopover();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeTermPopover();
    }
  });

  el("avatar-search").addEventListener("click", () => searchAvatar(1));
  el("avatar-lang").addEventListener("change", () => searchAvatar(1));
  bindEnter(el("avatar-q"), () => searchAvatar(1));
  el("avatar-list").addEventListener("click", (e) => {
    const tbtn = e.target;
    if (!(tbtn instanceof HTMLElement) || !tbtn.classList.contains("avatar-detail")) return;
    const id = Number(tbtn.dataset.id);
    if (!Number.isNaN(id)) loadAvatarDetail(id);
  });

  el("dialogue-search").addEventListener("click", () => searchDialogue(1));
  el("dialogue-lang").addEventListener("change", () => searchDialogue(1));
  bindEnter(el("dialogue-q"), () => searchDialogue(1));
  el("dialogue-list").addEventListener("click", (e) => {
    const tbtn = e.target;
    if (!(tbtn instanceof HTMLElement) || !tbtn.classList.contains("dialogue-ref")) return;
    const id = Number(tbtn.dataset.id);
    if (!Number.isNaN(id)) loadDialogueRefs(id, 1);
  });

  el("mission-search").addEventListener("click", () => searchMission(1));
  el("mission-lang").addEventListener("change", () => searchMission(1));
  bindEnter(el("mission-q"), () => searchMission(1));
  el("mission-list").addEventListener("click", (e) => {
    const tbtn = e.target;
    if (!(tbtn instanceof HTMLElement) || !tbtn.classList.contains("mission-detail")) return;
    const id = Number(tbtn.dataset.id);
    if (!Number.isNaN(id)) loadMissionDetail(id);
  });

  el("item-search").addEventListener("click", () => searchItem(1));
  el("item-lang").addEventListener("change", async () => {
    state.item.lang = el("item-lang").value;
    await loadItemFacets();
    await searchItem(1);
  });
  bindEnter(el("item-q"), () => searchItem(1));
  el("item-list").addEventListener("click", (e) => {
    const tbtn = e.target;
    if (!(tbtn instanceof HTMLElement) || !tbtn.classList.contains("item-detail")) return;
    const id = Number(tbtn.dataset.id);
    if (!Number.isNaN(id)) loadItemDetail(id);
  });

  el("monster-search").addEventListener("click", () => searchMonster(1));
  el("monster-lang").addEventListener("change", () => searchMonster(1));
  el("monster-rank").addEventListener("change", () => searchMonster(1));
  el("monster-weakness").addEventListener("change", () => searchMonster(1));
  bindEnter(el("monster-q"), () => searchMonster(1));
  el("monster-list").addEventListener("click", (e) => {
    const tbtn = e.target;
    if (!(tbtn instanceof HTMLElement) || !tbtn.classList.contains("monster-detail")) return;
    const id = Number(tbtn.dataset.id);
    if (!Number.isNaN(id)) loadMonsterDetail(id);
  });
}

async function init() {
  const initialUiLang = detectInitialUiLang();
  applyUiLanguage(initialUiLang, false);

  ["avatar-lang", "dialogue-lang", "mission-lang", "item-lang", "monster-lang"].forEach((id) => {
    const sel = el(id);
    if (sel) sel.value = initialUiLang;
  });

  attachTabs();
  attachEvents();
  switchPage("avatar");

  await loadStats();
  await loadItemFacets();
  await loadMonsterFacets();
  await searchAvatar(1);
  await searchDialogue(1);
  await searchMission(1);
  await searchItem(1);
  await searchMonster(1);
}

init();
