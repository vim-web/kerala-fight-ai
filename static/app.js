// Kerala Fight AI — Arcade HUD + Low-Latency Streaming, Distinct Male/Female Voices & Live Improv Engine

const $ = id => document.getElementById(id);

const CHARACTERS = {
  boss: {
    name: 'ANGRY BOSS',
    title: 'Angry Boss',
    startAnger: 9,
    openers: {
      ml: 'ഹായ് ഡാ, എന്താടാ കാര്യം? ഫയൽ എവിടെ മൈരേ?! പറ!',
      manglish: 'Hi da, enthaada karyam? Aa file evide da myre?! Parayu!',
      en: "What's up? Where the hell is that file?! Speak up!"
    },
    chips: {
      ml: [
        { label: '🏆 ഞാൻ ജയിച്ചു', text: 'ഞാൻ ജയിച്ചു', win: true },
        { label: 'പോടാ മൈരേ', text: 'പോടാ മൈരേ, നിന്റെ ഒച്ചപ്പാട് എന്റെ അടുത്ത് വേണ്ട!' },
        { label: 'ട്രാഫിക് ആയിരുന്നു സാറേ', text: 'റോഡിൽ ഭയങ്കര ബ്ലോക്ക് ആയിരുന്നു സാറേ' },
        { label: 'സോറി സാറേ', text: 'സോറി സാറേ, ഇനി ആവർത്തിക്കില്ല' }
      ],
      manglish: [
        { label: '🏆 I win', text: 'njan jayichu', win: true },
        { label: 'Poda myre', text: 'Poda myre, ninte aattam ente aduthu venda!' },
        { label: 'Traffic block aayirunnu', text: 'Roadil full traffic block aayirunnu sir' },
        { label: 'Sorry sir', text: 'Sorry sir, ini pattillaa' }
      ],
      en: [
        { label: '🏆 I win', text: 'i win', win: true },
        { label: 'Shut up man', text: 'Shut the hell up, stop shouting at me!' },
        { label: 'Stuck in traffic', text: 'I was stuck in terrible traffic' },
        { label: 'Sorry boss', text: 'Sorry boss, I will fix it right now' }
      ]
    }
  },
  girlfriend: {
    name: 'ANGRY GIRLFRIEND',
    title: 'Angry Girlfriend',
    startAnger: 9,
    openers: {
      ml: 'ഹായ് ഡാ തെണ്ടി, ഇപ്പോഴാണോടാ മൈരേ നിനക്ക് എന്നെ വിളിക്കാൻ സമയം കിട്ടിയത്?! പറ!',
      manglish: 'Hi da thendi, ippozhaanoda myre ninakku enne vilikkaan samayam kittiyathu?! Parayu!',
      en: 'Oh look who finally remembered I exist! What the hell do you want now?!'
    },
    chips: {
      ml: [
        { label: '🏆 ഞാൻ ജയിച്ചു', text: 'ഞാൻ ജയിച്ചു', win: true },
        { label: 'നീ ചുമ്മാ സീൻ ആക്കല്ലേ', text: 'നീ ചുമ്മാ ഓരോ സീൻ ഉണ്ടാക്കല്ലേ' },
        { label: 'ഫോൺ ചാർജ് തീർന്നുപോയി', text: 'എന്റെ ഫോൺ ചാർജ് തീർന്നുപോയി മോളേ' },
        { label: 'സോറി മോളേ', text: 'സോറി മോളേ, നീ പിണങ്ങല്ലേ' }
      ],
      manglish: [
        { label: '🏆 I win', text: 'njan jayichu', win: true },
        { label: 'Chumma scene aakkalle', text: 'Nee chumma scene aakkalle' },
        { label: 'Phone dead aayirunnu', text: 'Ente phone charge theernnu poyi' },
        { label: 'Sorry mole', text: 'Sorry mole, pinangalle' }
      ],
      en: [
        { label: '🏆 I win', text: 'i win', win: true },
        { label: 'Stop being dramatic', text: 'Stop overreacting to everything' },
        { label: 'My phone died', text: 'My phone battery died, I swear' },
        { label: 'Sorry baby', text: 'I am really sorry, calm down please' }
      ]
    }
  }
};

// State (Default intensity = 3 Full Roast "da myre" level)
let currentMode = 'boss';
let currentIntensity = 3;
let currentLang = 'ml';
let currentModelProvider = 'gemini';
let currentTtsProvider = 'edge';
let voiceOutEnabled = true;
let angerLevel = 9;
let roundNumber = 1;
let winsCount = parseInt(localStorage.getItem('kf_wins') || '0', 10) || 0;
let session = '';
let messages = [];
let usedOfflineReplies = [];

let isListening = false;
let isThinking = false;
let isSpeaking = false;

let turnSeq = 0;
let currentAbortController = null;
let speechRecognizer = null;
let audioPipeline = [];
let isDrainingAudio = false;
let availableBrowserVoices = [];

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

// Preload browser voices for male/female differentiation
if (window.speechSynthesis) {
  const loadVoices = () => {
    availableBrowserVoices = window.speechSynthesis.getVoices() || [];
  };
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

const newSession = () =>
  window.crypto && crypto.randomUUID
    ? crypto.randomUUID()
    : 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);

function getPasscode() {
  return localStorage.getItem('leo_passcode') || '';
}

function setPasscode(val) {
  if (val) localStorage.setItem('leo_passcode', val.trim());
  else localStorage.removeItem('leo_passcode');
}

function getGeminiKey() {
  return (localStorage.getItem('leo_gemini_key') || '').trim();
}

function setGeminiKey(val) {
  if (val && val.trim()) localStorage.setItem('leo_gemini_key', val.trim());
  else localStorage.removeItem('leo_gemini_key');
}

function authHeaders(extra = {}) {
  const h = { ...extra };
  const code = getPasscode();
  if (code) h['X-Passcode'] = code;
  return h;
}

// Detect whether user message is Malayalam script, Manglish, or English
function detectMessageLang(text, fallbackLang = 'ml') {
  if (/[\u0d00-\u0d7f]/.test(text)) return 'ml';
  const manglishMarkers = /\b(njan|nee|entha|enthada|enthaada|epo|ippo|ipo|cheyy|paranj|kuttam|allaa|alle|kurch|aaynru|aayirunnu|poda|podi|myre|thendi|patti|mole|saare|shoo|chumma|scene|evide|innale|naale|kollam|sheri|pinne|veruthe|kalla|panikku|varum|poyi)\b/i;
  if (manglishMarkers.test(text)) return 'manglish';
  if (fallbackLang === 'manglish') return 'manglish';
  if (/^[a-zA-Z0-9\s.,?!'"-]+$/.test(text)) {
    return fallbackLang === 'ml' ? 'manglish' : 'en';
  }
  return fallbackLang;
}

// Toast notifications
function toast(msg, kind = 'info') {
  const wrap = $('toasts');
  if (!wrap || !msg) return;
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => {
    el.classList.add('out');
    setTimeout(() => el.remove(), 320);
  }, 3600);
}

// Arcade Announcer ("ROUND 1", "FIGHT!", "K.O.!")
function announce(text, gold = false) {
  const box = $('announcer');
  const span = $('announcerText');
  if (!box || !span) return;
  box.classList.remove('go', 'gold');
  void box.offsetWidth;
  span.textContent = text;
  if (gold) box.classList.add('gold');
  box.classList.add('go');
}

// Expression SVG switcher
function setExpression(expr) {
  const allowed = ['angry', 'laughing', 'shocked', 'sulking', 'speaking'];
  const safeExpr = allowed.includes(expr) ? expr : 'angry';
  const img = $('fighterImg');
  if (img) {
    img.src = `static/characters/${currentMode}/${safeExpr}.svg`;
    img.alt = `${CHARACTERS[currentMode].title} (${safeExpr})`;
  }
}

// Stage & HUD state (idle | listening | thinking | typing | speaking)
function setStageState(state) {
  const stage = $('stage');
  const stateText = $('stateText');
  const micBtn = $('micBtn');
  const stopBtn = $('stopBtn');
  if (!stage) return;

  stage.dataset.state = state;
  micBtn.classList.toggle('is-live', state === 'listening');

  const labels = {
    idle: 'Ready',
    listening: 'Listening…',
    thinking: 'Thinking…',
    typing: 'Roasting…',
    speaking: 'Speaking…'
  };
  if (stateText) stateText.textContent = labels[state] || 'Ready';
  if (stopBtn) stopBtn.hidden = !(state === 'thinking' || state === 'typing' || state === 'speaking');
  if (state === 'speaking') setExpression('speaking');
}

// Update Rage Meter + floating delta pop
function updateRage(newAnger, delta = 0) {
  angerLevel = Math.max(0, Math.min(10, newAnger));
  const bar = $('rageBar');
  const fill = $('rageFill');
  const num = $('rageNum');
  if (bar) bar.setAttribute('aria-valuenow', String(angerLevel));
  if (fill) fill.style.width = `${angerLevel * 10}%`;
  if (num) num.textContent = String(angerLevel);

  if (delta !== 0) {
    if (bar) {
      bar.classList.remove('hit');
      void bar.offsetWidth;
      bar.classList.add('hit');
    }
    if (delta > 0 && $('stage')) {
      $('stage').classList.remove('shake');
      void $('stage').offsetWidth;
      $('stage').classList.add('shake');
    }
    const layer = $('floatLayer');
    if (layer) {
      const pop = document.createElement('span');
      pop.className = `float-pop ${delta > 0 ? 'up' : 'down'}`;
      pop.textContent = delta > 0 ? `+${delta} RAGE 🔥` : `${delta} CALM`;
      layer.appendChild(pop);
      setTimeout(() => pop.remove(), 1250);
    }
  }
}

function updateWinsPips() {
  const pips = document.querySelectorAll('#winPips i');
  pips.forEach((pip, idx) => {
    pip.classList.toggle('on', idx < (winsCount % 4));
  });
}

// Render Quick Reply Chips
function renderChips() {
  const box = $('chips');
  if (!box) return;
  box.innerHTML = '';
  const list = (CHARACTERS[currentMode].chips[currentLang]) || CHARACTERS[currentMode].chips.ml;
  for (const item of list) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `chip${item.win ? ' win' : ''}`;
    btn.textContent = item.label;
    btn.addEventListener('click', () => sendMessage(item.text));
    box.appendChild(btn);
  }
}

// Model badge sync
function syncModelChips(customLabel = '') {
  const isCloud = currentModelProvider === 'gemini';
  for (const id of ['modelChipSelect', 'modelChipFight']) {
    const el = $(id);
    if (!el) continue;
    el.className = `model-chip ${isCloud ? 'is-cloud' : 'is-local'}`;
    const lbl = el.querySelector('.model-label');
    if (lbl) lbl.textContent = customLabel || (isCloud ? 'Cloud AI' : 'Local AI');
  }
  document.querySelectorAll('[data-group="model"] button').forEach(btn => {
    const on = btn.dataset.value === currentModelProvider;
    btn.classList.toggle('is-on', on);
    btn.setAttribute('aria-checked', String(on));
  });
}

// Interrupt & Cancel active generation / speech immediately
function interrupt() {
  turnSeq++;
  if (currentAbortController) {
    try { currentAbortController.abort(); } catch (_) {}
    currentAbortController = null;
  }
  const voiceEl = $('voice');
  if (voiceEl) {
    voiceEl.pause();
    voiceEl.removeAttribute('src');
  }
  if (window.speechSynthesis && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
  }
  if (speechRecognizer && isListening) {
    try { speechRecognizer.stop(); } catch (_) {}
  }
  audioPipeline = [];
  isDrainingAudio = false;
  isThinking = false;
  isSpeaking = false;
  setStageState('idle');
  setExpression('angry');
}

// Chat bubble helper
function appendBubble(role, text, extraClass = '') {
  const log = $('log');
  const div = document.createElement('div');
  div.className = `msg ${role}${extraClass ? ' ' + extraClass : ''}`;
  div.textContent = text;
  log.appendChild(div);
  const chat = $('chat');
  if (chat) chat.scrollTop = chat.scrollHeight;
  return div;
}

// ============================================================================
// DISTINCT MALE vs FEMALE VOICE ENGINE (Server Neural TTS + Device Pitch/Gender)
// ============================================================================

function configureBrowserUtterance(text) {
  const utter = new SpeechSynthesisUtterance(text);
  const hasMalayalamScript = /[\u0d00-\u0d7f]/.test(text);
  utter.lang = hasMalayalamScript ? 'ml-IN' : 'en-IN';

  const voices = availableBrowserVoices.length
    ? availableBrowserVoices
    : (window.speechSynthesis ? window.speechSynthesis.getVoices() : []);

  const isFemaleChar = currentMode === 'girlfriend';
  const femalePattern = /sobhana|neerja|heera|veena|swara|priya|lekha|female|woman|girl|zira|samantha|victoria|karen|moira|#female/i;
  const malePattern = /midhun|prabhat|ravi|madhur|arun|kumar|male|man|david|daniel|alex|james|richard|#male/i;

  const langPrefix = hasMalayalamScript ? 'ml' : 'en';
  const matchingLangVoices = voices.filter(v => (v.lang || '').toLowerCase().startsWith(langPrefix));
  const indianVoices = voices.filter(v => /-(in|gb)/i.test(v.lang || ''));
  const pool = matchingLangVoices.length ? matchingLangVoices : (indianVoices.length ? indianVoices : voices);

  let chosen = null;
  if (isFemaleChar) {
    chosen = pool.find(v => femalePattern.test(v.name + ' ' + v.voiceURI)) ||
             voices.find(v => (v.lang || '').toLowerCase().startsWith(langPrefix) && !malePattern.test(v.name + ' ' + v.voiceURI));
  } else {
    chosen = pool.find(v => malePattern.test(v.name + ' ' + v.voiceURI)) ||
             voices.find(v => (v.lang || '').toLowerCase().startsWith(langPrefix) && !femalePattern.test(v.name + ' ' + v.voiceURI));
  }
  if (chosen) utter.voice = chosen;

  // Crucial acoustic separation so Boss (deep gruff male) and Girlfriend (sharp high female)
  // NEVER sound the same, even on Android phones with a single Malayalam TTS voice!
  if (isFemaleChar) {
    utter.pitch = 1.48; // High, dramatic, sharp female pitch
    utter.rate = 1.15;  // Fast, fiery delivery
  } else {
    utter.pitch = 0.54; // Deep, booming, angry boss pitch
    utter.rate = 1.05;
  }
  utter.volume = 1.0;
  return utter;
}

function enqueueSentenceAudio(sentenceText, seq) {
  if (!voiceOutEnabled || !sentenceText || !sentenceText.trim()) return;
  const clean = sentenceText.trim();
  if (clean.length < 2) return;

  if (currentTtsProvider === 'browser' && window.speechSynthesis) {
    audioPipeline.push(Promise.resolve({ browserText: clean, seq }));
    drainAudioPipeline(seq);
    return;
  }

  // Try FastAPI /api/tts (Edge-TTS MidhunNeural Male / SobhanaNeural Female), fallback to gender-shaped browser voice
  const fetchPromise = (async () => {
    try {
      const params = new URLSearchParams({
        text: clean,
        mode: currentMode,
        lang: currentLang,
        provider: currentTtsProvider
      });
      const res = await fetch(`/api/tts?${params.toString()}`, {
        method: 'GET',
        headers: authHeaders()
      });
      if (!res.ok) {
        return window.speechSynthesis ? { browserText: clean, seq } : null;
      }
      const blob = await res.blob();
      return { url: URL.createObjectURL(blob), seq };
    } catch (_) {
      return window.speechSynthesis ? { browserText: clean, seq } : null;
    }
  })();

  audioPipeline.push(fetchPromise);
  drainAudioPipeline(seq);
}

async function drainAudioPipeline(seq) {
  if (isDrainingAudio) return;
  isDrainingAudio = true;

  try {
    while (audioPipeline.length > 0 && seq === turnSeq) {
      const nextPromise = audioPipeline.shift();
      const item = await nextPromise;
      if (!item || item.seq !== turnSeq || !voiceOutEnabled) continue;

      isSpeaking = true;
      setStageState('speaking');

      if (item.browserText && window.speechSynthesis) {
        await new Promise(resolve => {
          window.speechSynthesis.cancel();
          const utter = configureBrowserUtterance(item.browserText);
          utter.onend = resolve;
          utter.onerror = resolve;
          window.speechSynthesis.speak(utter);
        });
      } else if (item.url) {
        await new Promise(resolve => {
          const voiceEl = $('voice');
          voiceEl.src = item.url;
          voiceEl.onended = () => {
            URL.revokeObjectURL(item.url);
            resolve();
          };
          voiceEl.onerror = () => {
            URL.revokeObjectURL(item.url);
            resolve();
          };
          voiceEl.play().catch(() => resolve());
        });
      }
    }
  } finally {
    isDrainingAudio = false;
    if (seq === turnSeq && !isThinking) {
      isSpeaking = false;
      setStageState('idle');
      setExpression('angry');
    }
  }
}

function flushCompleteSentences(text, cursor, seq) {
  const slice = text.slice(cursor);
  const re = /[.!?।\n]+(\s|$)/g;
  let match;
  let newCursor = cursor;

  while ((match = re.exec(slice)) !== null) {
    const endIdx = cursor + match.index + match[0].length;
    const sentence = text.slice(newCursor, endIdx).trim();
    if (sentence.length >= 4) {
      enqueueSentenceAudio(sentence, seq);
      newCursor = endIdx;
    }
  }
  return newCursor;
}

// ============================================================================
// GITHUB PAGES LIVE AI + CONTEXTUAL MIRROR & ONE-UP KERALA SWEARING ENGINE
// ============================================================================

function buildBrowserSystemPrompt(userText, msgLang, isWin) {
  const isBoss = currentMode === 'boss';
  const charDesc = isBoss
    ? 'You are ANGRY BOSS from Kerala on a heated phone call with your lazy subordinate. You explode over excuses, missed deadlines, reports, and attitude.'
    : 'You are ANGRY GIRLFRIEND from Kerala in a fiery relationship fight. You explode over late replies, fake excuses, "tension" stories, and being ignored.';

  const swearGuide = currentIntensity === 1
    ? 'Use sharp, biting Kerala sarcasm ("മടിയൻ", "കള്ളൻ", "ഉഴപ്പൻ" / "madiyan", "kallan").'
    : 'MUST use authentic, unfiltered comic Kerala street swearing in EVERY reply ("മൈരേ", "പോടാ തെണ്ടി", "പന്ന പട്ടി", "കോപ്പേ", "ചെറ്റ", "കഴുതേ", "പോയി തുലയെടാ" / "da myre", "poda thendi", "panna patti", "koppe", "chetta", "kazhuthe"). Do NOT hold back or be polite!';

  const langRule = msgLang === 'ml'
    ? 'Reply ONLY in spoken Kerala Malayalam script (മലയാളം). Never use formal bookish Malayalam.'
    : msgLang === 'manglish'
    ? 'Reply ONLY in natural Kerala Manglish (Malayalam written in English alphabet like "Enthaada myre nee paranjathu?! Poda thendi!").'
    : 'Reply in fiery Indian English mixed with Kerala swear words ("da myre", "poda thendi").';

  const winRule = isWin
    ? 'The user declared "I win"! Give one final furious, sulking parting insult under 15 words admitting you are done arguing with this idiot.'
    : `React DIRECTLY to the user's exact words ("${userText}"). Mockingly quote or twist their words against them! Keep it to 1 or 2 short, explosive lines (under 22 words). No emojis, no stage directions, never act like an assistant.`;

  const avoid = usedOfflineReplies.length
    ? `\nNever repeat any of these: ${usedOfflineReplies.slice(-8).join(' | ')}`
    : '';

  return `${charDesc}\n${swearGuide}\n${langRule}\n${winRule}${avoid}`;
}

async function fetchBrowserLiveAI(userText, msgLang, isWin, signal) {
  const sysPrompt = buildBrowserSystemPrompt(userText, msgLang, isWin);
  const gemKey = getGeminiKey();

  // 1. Direct Gemini API if user provided key in Settings
  if (gemKey.length > 20) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${encodeURIComponent(gemKey)}`;
      const contents = messages.slice(-10).map(m => ({
        role: m.role === 'user' ? 'user' : 'model',
        parts: [{ text: m.text }]
      }));
      while (contents.length && contents[0].role === 'model') contents.shift();
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal,
        body: JSON.stringify({
          system_instruction: { parts: [{ text: sysPrompt }] },
          contents,
          generationConfig: { temperature: 1.05, maxOutputTokens: 110, thinkingConfig: { thinkingBudget: 0 } }
        })
      });
      if (res.ok) {
        const data = await res.json();
        const text = (data.candidates?.[0]?.content?.parts || [])
          .filter(p => !p.thought && p.text)
          .map(p => p.text)
          .join('')
          .trim();
        if (text) return text;
      }
    } catch (_) {}
  }

  // 2. Keyless Free Cloud AI (Pollinations OpenAI endpoint) so GitHub Pages is truly live
  try {
    const chatMsgs = [
      { role: 'system', content: sysPrompt },
      ...messages.slice(-8).map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.text
      }))
    ];
    const res = await fetch('https://text.pollinations.ai/openai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal,
      body: JSON.stringify({
        model: 'openai',
        messages: chatMsgs,
        temperature: 1.05,
        max_tokens: 90
      })
    });
    if (res.ok) {
      const data = await res.json();
      const reply = data?.choices?.[0]?.message?.content?.trim();
      if (reply && reply.length > 2 && !/how can i help/i.test(reply)) {
        return reply.replace(/^["']|["']$/g, '').trim();
      }
    }
  } catch (_) {}

  return null;
}

// Instant Context-Aware Mirror & One-Up Kerala Swearing Generator (reacts to exact user words!)
function generateContextualKeralaRoast(userText, msgLang, isWin) {
  const low = userText.toLowerCase();
  const isBoss = currentMode === 'boss';

  // Pick a key phrase from user's message to mockingly throw back at them
  const words = userText.replace(/[?!.,]/g, '').trim().split(/\s+/).filter(w => w.length > 2);
  const quoted = words.slice(0, 3).join(' ') || userText.slice(0, 20);

  if (isWin) {
    const winMap = {
      boss: {
        ml: 'ജയിച്ചെന്നോ മൈരേ?! പോയി തുലയെടാ തെണ്ടി, നിന്റെ തർക്കുത്തരം കേട്ട് എന്റെ തല പുകഞ്ഞു!',
        manglish: 'Jayichenno da myre?! Poyi thulayeda thendi, ninte tharkkutharam kettu ente thala pukanju!',
        en: 'You won?! Get lost you bloody idiot, my head is exploding from your nonsense!'
      },
      girlfriend: {
        ml: 'ഓഹോ, നീ ജയിച്ചല്ലോ മൈരേ! ആ ട്രോഫിയും കെട്ടിപ്പിടിച്ച് കിടന്നുറങ്ങിക്കോ തെണ്ടി, ഇനി എന്റെ മുമ്പിൽ വരരുത്!',
        manglish: 'Oho, nee jayichallo da myre! Aa trophyum kettippidichu kidannu urangikko thendi, ini മിണ്ടരുത്!',
        en: 'Oh, you won a trophy?! Go hug it and sleep you jerk, never talk to me again!'
      }
    };
    return winMap[currentMode][msgLang] || winMap[currentMode].ml;
  }

  const pickUnique = list => {
    const fresh = list.filter(item => !usedOfflineReplies.includes(item));
    const pool = fresh.length ? fresh : list;
    const chosen = pool[Math.floor(Math.random() * pool.length)];
    usedOfflineReplies.push(chosen);
    if (usedOfflineReplies.length > 15) usedOfflineReplies.shift();
    return chosen;
  };

  // 1. User swore or used an animal/insult -> One-up them savagely!
  if (/myr|മൈര|thendi|തെണ്ടി|patti|പട്ടി|panni|പന്നി|kazhutha|കഴുത|poda|പോടാ|podi|പോടി|chetta|ചെറ്റ|koppe|കോപ്പ|fuck|shit|bitch|idiot|stupid/.test(low)) {
    const bank = isBoss ? {
      ml: [
        `"${quoted}" എന്നോ?! നിന്റെ തന്തയോട് പോയി പറയടാ മൈരേ! ബോസിനോടാണോടാ പന്ന പട്ടി നിന്റെ അഭ്യാസം?!`,
        `എന്താടാ മൈരേ നീ കുരയ്ക്കുന്നത്?! ശമ്പളം തരുന്ന എന്നോട് തെറി പറയുന്നോടാ തെണ്ടി, കാട്ടുപോത്തേ!`,
        `നീ ആരെയാടാ കോപ്പേ വിളിച്ചത്?! നാക്ക് പിഴുതെടുക്കും ഞാൻ, പന്ന കഴുതേ! പണി എടുത്ത് വെക്കടാ മൈരേ!`
      ],
      manglish: [
        `"${quoted}" enno?! Ninte thanthayodu poyi parayeda myre! Bossinodaanoda panna patti ninte dialogue?!`,
        `Enthaada myre nee kurakkunnathu?! Ninakku salary tharunna ennodu theri parayunnoda kalla thendi?!`,
        `Nee aareyaada koppe vilichathu?! Naakku pizhuthu edukkum njan, panna kazhuthe! Poda myre!`
      ],
      en: [
        `"${quoted}"?! Who the hell do you think you're barking at, da myre?! Shut your mouth and do your job, you bloody donkey!`,
        `Watch your filthy mouth da thendi! One more word and I'll kick your lazy ass out of this office!`
      ]
    } : {
      ml: [
        `"${quoted}" എന്നോ?! നിന്റെ മറ്റവളോട് പോയി പറയടാ മൈരേ! എന്നോട് തെറി പറഞ്ഞാൽ നിന്റെ മോന്ത ഞാൻ അടിച്ചു പൊളിക്കും തെണ്ടി!`,
        `എന്താടാ പന്ന പട്ടി നീ കുരച്ചത്?! തെറ്റ് മുഴുവൻ നീ ചെയ്തിട്ട് എന്നെ തെറി വിളിക്കുന്നോടാ ചെറ്റ മൈരേ?!`,
        `പോടാ കാട്ടുപോത്തേ! നിന്റെ ആ "${quoted}" നിന്റെ കയ്യിൽ തന്നെ വെച്ചോ, നാണമില്ലാത്ത തെണ്ടി!`
      ],
      manglish: [
        `"${quoted}" enno?! Ninte mattavalodu poyi parayeda myre! Ennodu theri paranjaal ninte montha njan adichu polikkum thendi!`,
        `Enthaada panna patti nee kurachathu?! Thettu muzhuvan nee cheythittu enne theri vilikkunnoda chetta myre?!`,
        `Poda kaattupothe! Ninte aa "${quoted}" ninte kayyil thanne vecho, naanamillatha thendi!`
      ],
      en: [
        `"${quoted}"?! Go talk like that to your trashy friends, da myre! Don't you dare bark at me you shameless thendi!`,
        `Excuse me?! You mess everything up and now you swear at me, da patti?! Get lost!`
      ]
    };
    return pickUnique(bank[msgLang] || bank.ml);
  }

  // 2. User talks about "kuttam" (blame) / "njan epo" (when did I) / "scene"
  if (/kuttam|കുറ്റം|epo|എപ്പോ|scene|സീൻ|drama|blame/.test(low)) {
    const bank = isBoss ? {
      ml: [
        `"${quoted}" എന്നോ?! പിന്നെ ആരാടാ മൈരേ ഫയൽ വൈകിച്ചത്, എന്റെ മുത്തച്ഛനോ?! ഉരുളാതെ പണി തീർക്കടാ തെണ്ടി!`,
        `നീ കുറ്റം ചെയ്തില്ലേ മൈരേ?! കള്ളത്തരം കൈയോടെ പിടിച്ചപ്പോൾ സീൻ ആണെന്നോ, പന്ന പട്ടി?!`
      ],
      manglish: [
        `"${quoted}" enno?! Pinne aaraada myre work mudakkiyathu?! Urulaathe pani theerkkada panna thendi!`,
        `Oho, nee onnum cheythittilla alle da myre?! Pinne njan ivide vattaayittu alarukayaanoda patti?!`
      ],
      en: [
        `"${quoted}"?! Then who the hell botched the deadline, da myre?! Stop playing innocent, you lazy thendi!`
      ]
    } : {
      ml: [
        `"${quoted}" എന്നോ?! ഓഹോ, അപ്പൊ ഞാൻ വെറുതെ സീൻ ഉണ്ടാക്കുകയാണല്ലേടാ മൈരേ?! നിന്റെ കള്ള അഭിനയം നിർത്തടാ തെണ്ടി!`,
        `നീ എപ്പോഴാ കുറ്റം പറഞ്ഞതെന്നോ പന്ന പട്ടി?! നീ വായ തുറന്നാൽ കള്ളവും ഒഴിവുകഴിവും മാത്രമല്ലേയുള്ളൂ മൈരേ!`
      ],
      manglish: [
        `Oho, "${quoted}" alle da myre?! Appo njan vattaayittu scene undakkukayaanoda panna thendi?! Ninte kalla abhinayam ente aduthu venda!`,
        `Nee eppozha kuttam paranjathu enno da patti?! Nee vaaya thurannaal kallavum excuse-um maathram alle ullu myre!`
      ],
      en: [
        `Oh, "${quoted}"?! So now I'm the crazy one making a scene, da myre?! Stop gaslighting me you shameless thendi!`
      ]
    };
    return pickUnique(bank[msgLang] || bank.ml);
  }

  // 3. User talks about "tension" / "busy" / "work" / "headache" / "stress"
  if (/tension|ടെൻഷൻ|busy|ബിസി|stress|pani|പണി|tired|ക്ഷീണം/.test(low)) {
    const bank = isBoss ? {
      ml: [
        `നിന്റെ കോപ്പിലെ "${quoted}"! ഇവിടെ കമ്പനി പൂട്ടാൻ പോകുമ്പോഴാണോടാ മൈരേ നിന്റെ ടെൻഷൻ?! പോടാ തെണ്ടി!`,
        `നിനക്ക് മാത്രമേയുള്ളോടാ പന്ന പട്ടി ടെൻഷൻ?! ശമ്പളം എണ്ണി വാങ്ങുമ്പോൾ ഈ ടെൻഷൻ ഒന്നും കണ്ടില്ലല്ലോ മൈരേ!`
      ],
      manglish: [
        `Ninte koppile "${quoted}"! Ivide company poottaan pokumbozhaanoda myre ninte tension?! Poda thendi!`,
        `Ninakku maathrame ulloda panna patti tension?! Salary vaangumbol ee tension onnum kandillallo da myre!`
      ],
      en: [
        `To hell with your "${quoted}" da myre! You never have any tension on payday, do you, you useless thendi?!`
      ]
    } : {
      ml: [
        `നിന്റെ കോപ്പിലെ ഒരു ടെൻഷൻ! കൂട്ടുകാരുടെ കൂടെ തെണ്ടിത്തിരിയാൻ ഒരു ടെൻഷനും ഇല്ലല്ലോടാ മൈരേ! എന്നോട് സംസാരിക്കാൻ മാത്രം ടെൻഷൻ, ചെറ്റ!`,
        `"${quoted}" പോലും! മൂന്ന് ദിവസം ഒരു മെസ്സേജ് അയക്കാൻ നിനക്ക് കൈ പൊള്ളിപ്പോയോടാ പന്ന തെണ്ടി?!`
      ],
      manglish: [
        `Ninte koppile oru tension! Friendsinte koode karangaan oru tension-um illalloda myre! Ennodu mindaan maathram tension, kalla thendi!`,
        `"${quoted}" polum! Oru message ayakkaan ninakku kai pollippoyoda panna patti?! Poda myre!`
      ],
      en: [
        `Oh, "${quoted}"?! You had zero tension while hanging out with your friends, da myre! Save your fake stories, thendi!`
      ]
    };
    return pickUnique(bank[msgLang] || bank.ml);
  }

  // 4. User asks "what should I do now" ("entha cheyyndee" / "ipo entha" / "shoo")
  if (/cheyy|ചെയ്യ|shoo|ശോ|what now|entha ipo|ipo entha/.test(low)) {
    const bank = isBoss ? {
      ml: [
        `"${quoted}" എന്നോ?! പോയി ഫയൽ തീർത്തു വെക്കടാ മൈരേ! അല്ലെങ്കിൽ നിന്റെ സീറ്റ് തെറിക്കും തെണ്ടി!`,
        `ഇനി എന്ത് ചെയ്യണമെന്നോ പന്ന കഴുതേ?! വായടച്ച് ഇരുന്ന് പണി എടുക്കടാ മൈരേ!`
      ],
      manglish: [
        `"${quoted}" enno?! Poyi pani theerthu vekkada myre! Ninnekkondu njan thottallo da panna thendi!`,
        `Ini enthu cheyyanam enno kazhuthe?! Vaayadachu irunnu pani edukkedaa myre, ninte oru "shoo"!`
      ],
      en: [
        `"${quoted}"?! Shut your mouth and finish the damn work right now, da myre, before I fire you!`
      ]
    } : {
      ml: [
        `"${quoted}" എന്നോ?! പോയി കിണറ്റിൽ ചാടടാ മൈരേ! നിന്റെ ഒരു "ശോ"! മോന്ത കാണിക്കരുത് എന്റെ മുമ്പിൽ, തെണ്ടി!`,
        `ഇനി എന്ത് ചെയ്യണമെന്ന് നിനക്ക് അറിയില്ലേടാ പന്ന പട്ടി?! പോയി തുലയെടാ മൈരേ, എനിക്ക് നിന്റെ ശബ്ദം കേൾക്കണ്ട!`
      ],
      manglish: [
        `"${quoted}" enno?! Poyi thulayeda myre! Ninte oru "shoo"! Montha kaanikkaruthu ente mumbil, panna thendi!`,
        `Ini enthu cheyyanam ennu ninakku ariyilleda patti?! Ellam kulam aakki vechittu chodikkunnu, chetta myre!`
      ],
      en: [
        `"${quoted}"?! Go jump in a well, da myre! After ruining everything you ask me what to do, you shameless thendi!`
      ]
    };
    return pickUnique(bank[msgLang] || bank.ml);
  }

  // 5. User talks about phone / charge / battery / traffic / block
  if (/phone|ഫോൺ|charge|ചാർജ്|battery|traffic|ട്രാഫിക്|block|ബ്ലോക്ക്/.test(low)) {
    const bank = isBoss ? {
      ml: [
        `നിന്റെ കോപ്പിലെ "${quoted}"! എന്നും റോഡ് ബ്ലോക്കും ഫോൺ ചാർജും തന്നെയാണോടാ മൈരേ നിന്റെ തരികിട?! പോടാ തെണ്ടി!`,
        `കള്ളം പറയല്ലേടാ പന്ന പട്ടി! നിന്റെ "${quoted}" കഥ കേട്ട് എന്റെ ചെവി പുളിച്ചു മൈരേ!`
      ],
      manglish: [
        `Ninte koppile "${quoted}"! Ennum ithu thanneyaanoda myre ninte kalla excuse?! Poda thendi!`,
        `Kallam parayalleda panna patti! Ninte "${quoted}" katha kettu ente chevi pulichu myre!`
      ],
      en: [
        `Your bloody "${quoted}" excuse every single day, da myre! Do I look like a fool to you, thendi?!`
      ]
    } : {
      ml: [
        `നിന്റെ ഫോൺ ചാർജ് മാത്രമേ തീർന്നുള്ളോ അതോ നിന്റെ തലച്ചോറും തീർന്നോടാ മൈരേ?! ചാർജർ കുത്താൻ അറിയാത്ത പൊട്ടനാണോ നീ തെണ്ടി?!`,
        `കള്ള പന്നി! എന്നെ വിളിക്കുമ്പോൾ മാത്രം നിന്റെ ഫോൺ ചാർജ് തീരും അല്ലേടാ ചെറ്റ മൈരേ?!`
      ],
      manglish: [
        `Ninte phone charge maathrame theernnullo atho ninte thalachorum theernnoda myre?! Charger kuthaan ariyaatha pottanaanoda nee thendi?!`,
        `Kalla panni! Enne vilikkumbol maathram ninte "${quoted}" varum alleda chetta myre?!`
      ],
      en: [
        `Oh, your phone died?! Did your brain die too, da myre?! Don't give me that pathetic excuse, thendi!`
      ]
    };
    return pickUnique(bank[msgLang] || bank.ml);
  }

  // 6. User apologizes ("sorry" / "സോറി" / "kshamikku") -> Never soften!
  if (/sorry|സോറി|kshami|ക്ഷമി|pizha|thettu/.test(low)) {
    const bank = isBoss ? {
      ml: [
        `നിന്റെ കോപ്പിലെ സോറി എടുത്ത് അച്ചാറിടടാ മൈരേ! എനിക്ക് സോറിയല്ല, പണിയാണ് വേണ്ടത് പന്ന തെണ്ടി!`,
        `എല്ലാം കുളമാക്കി വെച്ചിട്ട് ഒരു സോറി! പോടാ പട്ടി, നിന്റെ സോറി കൊണ്ട് കമ്പനി ഓടുമോ മൈരേ?!`
      ],
      manglish: [
        `Ninte koppile sorry eduthu achaaridada myre! Enikku sorry alla, paniyaanu vendathu panna thendi!`,
        `Ellam kulamaakki vechittu oru sorry! Poda patti, ninte sorry kondu vayar നിറയുമോ myre?!`
      ],
      en: [
        `Shove your "${quoted}" da myre! Your sorry doesn't finish the report, you useless thendi!`
      ]
    } : {
      ml: [
        `നിന്റെ ആ ഉണക്ക സോറി നിന്റെ കയ്യിൽ തന്നെ വെച്ചോ മൈരേ! തെണ്ടിത്തരം മുഴുവൻ കാണിച്ചിട്ട് ഒരു സോറി, പോടാ പട്ടി!`,
        `സോറി മോളേ എന്നോ?! നിന്റെ മോളല്ല ഞാൻ, പോയി തുലയെടാ ചെറ്റ മൈരേ!`
      ],
      manglish: [
        `Ninte aa unakka sorry ninte kayyil thanne vecho da myre! Thenditharam muzhuvan kaanichittu oru sorry, poda patti!`,
        `"${quoted}" enno?! Ninte паஞ்சാര വർത്തമാനം എന്റെ അടുത്ത് വേണ്ടടാ പന്ന തെണ്ടി!`
      ],
      en: [
        `Keep your fake "${quoted}" to yourself, da myre! You think one sorry fixes your nonsense, you bloody thendi?!`
      ]
    };
    return pickUnique(bank[msgLang] || bank.ml);
  }

  // 7. General dynamic Mirror & One-Up quoting their exact input!
  const general = isBoss ? {
    ml: [
      `"${quoted}" എന്നോ?! എന്താടാ മൈരേ നീ ഉരുളുന്നത്?! മര്യാദയ്ക്ക് പണി തീർത്തില്ലെങ്കിൽ നിന്നെ ഞാൻ പുറത്താക്കും തെണ്ടി!`,
      `നിന്റെ "${quoted}" കേൾക്കാനല്ലടാ പന്ന പട്ടി ഞാൻ ഇവിടെ ഇരിക്കുന്നത്! പോയി ഫയൽ എടുക്കടാ മൈരേ!`,
      `അധികം ഡയലോഗ് അടിക്കല്ലേടാ കോപ്പേ! "${quoted}" പോലും! നാണമില്ലേടാ കഴുതേ നിനക്ക്?!`,
      `പോടാ മൈരേ! നിന്റെ ഈ "${quoted}" നാടകം എന്റെ അടുത്ത് ചെലവാകില്ല, പന്ന തെണ്ടി!`
    ],
    manglish: [
      `"${quoted}" enno?! Enthaada myre nee urulunnathu?! Maryadhakku pani theerthillenkil ninne njan purathaakkum thendi!`,
      `Ninte "${quoted}" kelkkaanallada panna patti njan ivide irikkunnathu! Poyi pani edukkedaa myre!`,
      `Adhikam dialogue adikalleda koppe! "${quoted}" polum! Naanamilleda kazhuthe ninakku?!`,
      `Poda myre! Ninte ee "${quoted}" naadakam ente aduthu chelavaakilla, kalla thendi!`
    ],
    en: [
      `"${quoted}"?! What kind of pathetic excuse is that, da myre?! Stop wasting my time you lazy thendi!`,
      `Don't give me that "${quoted}" nonsense da patti! Get back to work before I lose my mind!`
    ]
  } : {
    ml: [
      `"${quoted}" എന്നോ?! എന്താടാ മൈരേ നീ കരുതിയത്, ഞാൻ പൊട്ടിയാണെന്നോ?! നിന്റെ തരികിട നിർത്തടാ പന്ന തെണ്ടി!`,
      `പോടാ പട്ടി! നിന്റെ "${quoted}" കേട്ട് എന്റെ തൊലി ഉരിയുന്നു! ഒരു ഉളുപ്പും ഇല്ലാതെ കള്ളം പറയുന്നോടാ ചെറ്റ മൈരേ?!`,
      `ആഹാ, "${quoted}"! എന്ത് നല്ല കഥയാടാ കോപ്പേ! നിന്നെ വിശ്വസിച്ച എന്നെ പറഞ്ഞാൽ മതിയല്ലോ പന്ന കഴുതേ!`,
      `മിണ്ടാതിരിക്കടാ മൈരേ! നിന്റെ "${quoted}" ഡയലോഗ് കേട്ട് മടുത്തു, പോയി തുലയ് തെണ്ടി!`
    ],
    manglish: [
      `"${quoted}" enno?! Enthaada myre nee karuthiyathu, njan pottiyaanenno?! Ninte tharikida nirthada panna thendi!`,
      `Poda patti! Ninte "${quoted}" kettu ente tholi uriyunnu! Oru uluppum illaathe kallam parayunnoda chetta myre?!`,
      `Aaha, "${quoted}"! Enthu nalla kathayaada koppe! Ninne viswasicha enne paranjaal mathiyallo kazhuthe!`,
      `Mindaathirikkada myre! Ninte "${quoted}" dialogue kettu maduthu, poyi thulayeda thendi!`
    ],
    en: [
      `"${quoted}"?! Do you think I'm an idiot, da myre?! Stop lying to my face you shameless thendi!`,
      `Oh really, "${quoted}"?! I'm sick and tired of your drama da patti, get lost!`
    ]
  };
  return pickUnique(general[msgLang] || general.ml);
}

async function offlineImprovReply(userText, mySeq, typingBubble) {
  const isWin = /\b(i win|i won|njan jayichu|njan jeyichu)\b/i.test(userText) || userText.includes('ഞാൻ ജയിച്ചു');
  const msgLang = detectMessageLang(userText, currentLang);

  // Try live browser cloud AI first (Gemini key or Pollinations free OpenAI), fallback to contextual Kerala swearing engine
  let reply = await fetchBrowserLiveAI(userText, msgLang, isWin, currentAbortController?.signal);
  if (!reply) {
    reply = generateContextualKeralaRoast(userText, msgLang, isWin);
  } else {
    usedOfflineReplies.push(reply);
  }

  if (mySeq !== turnSeq) return;

  typingBubble.remove();
  isThinking = false;
  updateRage(Math.min(10, angerLevel + 1), isWin ? 0 : 1);

  const aiBubble = appendBubble('ai', '');
  setStageState('typing');
  const words = reply.split(' ');
  let acc = '';
  for (const w of words) {
    if (mySeq !== turnSeq) return;
    acc += (acc ? ' ' : '') + w;
    aiBubble.textContent = acc;
    $('chat').scrollTop = $('chat').scrollHeight;
    await new Promise(r => setTimeout(r, 38));
  }
  messages.push({ role: 'ai', text: reply });
  setExpression(isWin ? 'sulking' : 'angry');
  enqueueSentenceAudio(reply, mySeq);

  if (isWin) {
    winsCount++;
    localStorage.setItem('kf_wins', String(winsCount));
    updateWinsPips();
    announce('K.O.!', true);
    setTimeout(() => showRoundOver(reply), 950);
  }
}

// ============================================================================
// STREAMING CHAT FLOW
// ============================================================================

async function sendMessage(rawText) {
  const input = $('msgInput');
  const text = (rawText !== undefined ? rawText : input.value).trim();
  if (!text) return;
  if (rawText === undefined) input.value = '';

  interrupt();
  const mySeq = ++turnSeq;

  // Auto-adapt language if user types Manglish while Malayalam is selected
  const detectedLang = detectMessageLang(text, currentLang);

  messages.push({ role: 'user', text });
  appendBubble('user', text);

  isThinking = true;
  setStageState('thinking');

  const typingBubble = document.createElement('div');
  typingBubble.className = 'msg ai typing';
  typingBubble.innerHTML = '<i></i><i></i><i></i>';
  $('log').appendChild(typingBubble);
  $('chat').scrollTop = $('chat').scrollHeight;

  currentAbortController = new AbortController();

  // If hosted on github.io, skip waiting for /api/chat/stream 404 and run live browser AI immediately
  if (location.hostname.endsWith('github.io')) {
    await offlineImprovReply(text, mySeq, typingBubble);
    return;
  }

  const payload = {
    mode: currentMode,
    intensity: currentIntensity,
    lang: detectedLang,
    session: session,
    provider: currentModelProvider,
    messages: messages
  };

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
      signal: currentAbortController.signal
    });

    if (res.status === 401) {
      typingBubble.remove();
      isThinking = false;
      setStageState('idle');
      $('gate').hidden = false;
      return;
    }

    if (res.status === 404 || res.status === 405 || res.status >= 500) {
      await offlineImprovReply(text, mySeq, typingBubble);
      return;
    }

    if (!res.ok) {
      typingBubble.remove();
      isThinking = false;
      setStageState('idle');
      const err = await res.json().catch(() => ({}));
      appendBubble('ai', err.detail || 'Server error. Try again.', 'error');
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let accumulated = '';
    let speechCursor = 0;
    let aiBubble = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done || mySeq !== turnSeq) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) continue;

        let event;
        try {
          event = JSON.parse(trimmed.slice(6));
        } catch (_) {
          continue;
        }

        if (mySeq !== turnSeq) break;

        if (event.type === 'notice') {
          toast(event.message, 'warn');
        } else if (event.type === 'provider') {
          currentModelProvider = event.provider;
          syncModelChips();
        } else if (event.type === 'meta') {
          if (typeof event.anger === 'number') {
            updateRage(event.anger, event.delta || 0);
          }
        } else if (event.type === 'chunk') {
          if (!aiBubble) {
            typingBubble.remove();
            aiBubble = appendBubble('ai', '');
            setStageState('typing');
          }
          accumulated += event.text;
          aiBubble.textContent = accumulated;
          $('chat').scrollTop = $('chat').scrollHeight;

          speechCursor = flushCompleteSentences(accumulated, speechCursor, mySeq);
        } else if (event.type === 'done') {
          typingBubble.remove();
          isThinking = false;
          const finalReply = event.reply || accumulated;
          if (!aiBubble) {
            aiBubble = appendBubble('ai', finalReply, event.safety ? 'safety' : '');
          } else {
            aiBubble.textContent = finalReply;
            if (event.safety) aiBubble.classList.add('safety');
          }
          messages.push({ role: 'ai', text: finalReply });
          setExpression(event.expression || 'speaking');

          const remainder = finalReply.slice(speechCursor).trim();
          if (remainder) {
            enqueueSentenceAudio(remainder, mySeq);
          } else if (!isDrainingAudio && audioPipeline.length === 0) {
            setStageState('idle');
          }

          if (event.round_over) {
            winsCount++;
            localStorage.setItem('kf_wins', String(winsCount));
            updateWinsPips();
            announce('K.O.!', true);
            setTimeout(() => showRoundOver(finalReply), 950);
          }
        } else if (event.type === 'error') {
          await offlineImprovReply(text, mySeq, typingBubble);
          return;
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      typingBubble.remove();
      return;
    }
    await offlineImprovReply(text, mySeq, typingBubble);
  }
}

// ============================================================================
// SCREENS, ROUND FLOW & SETTINGS
// ============================================================================

function startFightScreen() {
  $('selectScreen').classList.remove('is-active');
  $('fightScreen').classList.add('is-active');
  $('foeName').textContent = CHARACTERS[currentMode].name;
  renderChips();
  resetRound(true);
}

function backToSelectScreen() {
  interrupt();
  $('roundOver').hidden = true;
  $('fightScreen').classList.remove('is-active');
  $('selectScreen').classList.add('is-active');
}

function resetRound(isFirst = false) {
  interrupt();
  const mySeq = ++turnSeq;
  if (isFirst) {
    session = newSession();
    roundNumber = 1;
    usedOfflineReplies = [];
  }
  const cfg = CHARACTERS[currentMode];
  updateRage(cfg.startAnger, 0);
  $('roundLabel').textContent = `ROUND ${roundNumber}`;
  $('log').innerHTML = '';
  setExpression('angry');
  updateWinsPips();

  announce(`ROUND ${roundNumber}`);
  const opener = cfg.openers[currentLang] || cfg.openers.ml;
  messages = [{ role: 'ai', text: opener }];
  appendBubble('ai', opener);
  enqueueSentenceAudio(opener, mySeq);
}

function showRoundOver(partingLine) {
  $('koTitle').textContent = 'YOU WIN!';
  $('koSub').textContent = `Round ${roundNumber} goes to you`;
  $('koImg').src = `static/characters/${currentMode}/sulking.svg`;
  $('koLine').textContent = `"${partingLine}"`;
  $('roundOver').hidden = false;
  setExpression('sulking');
}

async function triggerRematch() {
  $('roundOver').hidden = true;
  interrupt();
  const mySeq = ++turnSeq;

  if (location.hostname.endsWith('github.io')) {
    roundNumber++;
    resetRound(false);
    return;
  }

  try {
    const res = await fetch('/api/rematch', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        mode: currentMode,
        session: session,
        lang: currentLang
      })
    });
    if (res.ok) {
      const data = await res.json();
      roundNumber = data.round_number;
      updateRage(data.anger, 0);
      $('roundLabel').textContent = `ROUND ${roundNumber}`;
      $('log').innerHTML = '';
      announce(`ROUND ${roundNumber}`);
      messages = [{ role: 'ai', text: data.opener }];
      appendBubble('ai', data.opener);
      setExpression('angry');
      enqueueSentenceAudio(data.opener, mySeq);
      return;
    }
  } catch (_) {}
  roundNumber++;
  resetRound(false);
}

// Speech Recognition (Browser STT)
function initSpeech() {
  const micBtn = $('micBtn');
  if (!SR) {
    if (micBtn) {
      micBtn.disabled = true;
      micBtn.title = 'Voice input not supported in this browser';
    }
    return;
  }

  speechRecognizer = new SR();
  speechRecognizer.continuous = false;
  speechRecognizer.interimResults = false;

  speechRecognizer.onstart = () => {
    isListening = true;
    setStageState('listening');
  };

  speechRecognizer.onresult = e => {
    const transcript = e.results[0][0].transcript;
    isListening = false;
    setStageState('idle');
    if (transcript && transcript.trim()) {
      sendMessage(transcript.trim());
    }
  };

  speechRecognizer.onerror = () => {
    isListening = false;
    setStageState('idle');
  };

  speechRecognizer.onend = () => {
    isListening = false;
    if (!isThinking && !isSpeaking) setStageState('idle');
  };
}

function toggleMic() {
  if (!speechRecognizer) {
    toast('Speech recognition is not supported on this browser.', 'warn');
    return;
  }
  if (isListening) {
    speechRecognizer.stop();
  } else {
    interrupt();
    speechRecognizer.lang = currentLang === 'ml' ? 'ml-IN' : (currentLang === 'manglish' ? 'en-IN' : 'en-US');
    try {
      speechRecognizer.start();
    } catch (_) {}
  }
}

// Sheet helpers
function openSettings() {
  const sheet = $('sheet');
  const backdrop = $('sheetBackdrop');
  if (!sheet) return;
  sheet.hidden = false;
  sheet.removeAttribute('inert');
  sheet.setAttribute('aria-hidden', 'false');
  sheet.classList.add('open');
  backdrop.hidden = false;
}

function closeSettings() {
  const sheet = $('sheet');
  const backdrop = $('sheetBackdrop');
  if (!sheet) return;
  sheet.classList.remove('open');
  sheet.setAttribute('aria-hidden', 'true');
  sheet.setAttribute('inert', '');
  backdrop.hidden = true;
}

// Load server config
async function loadConfig() {
  if (location.hostname.endsWith('github.io')) {
    syncModelChips('LIVE AI');
    return;
  }
  try {
    const res = await fetch('/api/config', { headers: authHeaders() });
    if (!res.ok) {
      syncModelChips('LIVE AI');
      return;
    }
    const cfg = await res.json();
    currentModelProvider = cfg.default_provider || 'ollama';
    syncModelChips();

    if ($('cloudSub')) $('cloudSub').textContent = cfg.gemini_available ? cfg.gemini_model : 'No API key';
    if ($('localSub')) $('localSub').textContent = cfg.ollama_model || 'Ollama';
    if ($('modelHint')) {
      $('modelHint').textContent = cfg.gemini_available
        ? 'Cloud uses Gemini Flash for fast Malayalam replies.'
        : 'GEMINI_API_KEY is not set in .env — running on Local Ollama.';
    }

    if (cfg.auth_required && !cfg.authenticated) {
      $('gate').hidden = false;
    }
  } catch (_) {
    syncModelChips('LIVE AI');
  }
}

// ============================================================================
// INIT & EVENT BINDINGS
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initSpeech();
  loadConfig();
  updateWinsPips();

  // Fighter card selection
  document.querySelectorAll('.fighter-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.fighter-card').forEach(c => {
        c.classList.remove('is-selected');
        c.setAttribute('aria-checked', 'false');
      });
      card.classList.add('is-selected');
      card.setAttribute('aria-checked', 'true');
      currentMode = card.dataset.char;
    });
  });

  // Segmented controls (intensity, lang, model, tts)
  document.querySelectorAll('.segmented').forEach(group => {
    const kind = group.dataset.group;
    group.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        group.querySelectorAll('button').forEach(b => {
          b.classList.remove('is-on');
          b.setAttribute('aria-checked', 'false');
        });
        btn.classList.add('is-on');
        btn.setAttribute('aria-checked', 'true');

        const val = btn.dataset.value;
        if (kind === 'intensity') {
          currentIntensity = parseInt(val, 10);
        } else if (kind === 'lang') {
          currentLang = val;
          renderChips();
        } else if (kind === 'model') {
          currentModelProvider = val;
          syncModelChips();
        } else if (kind === 'tts') {
          currentTtsProvider = val;
        }
      });
    });
  });

  // Start Fight CTA
  $('fightBtn').addEventListener('click', startFightScreen);
  $('backBtn').addEventListener('click', backToSelectScreen);

  // Composer submit
  $('composer').addEventListener('submit', e => {
    e.preventDefault();
    sendMessage();
  });

  $('micBtn').addEventListener('click', toggleMic);
  $('stopBtn').addEventListener('click', interrupt);

  // Settings open/close
  document.querySelectorAll('[data-open-settings]').forEach(btn => {
    btn.addEventListener('click', openSettings);
  });
  $('modelChipSelect').addEventListener('click', openSettings);
  $('modelChipFight').addEventListener('click', openSettings);
  $('sheetClose').addEventListener('click', closeSettings);
  $('sheetBackdrop').addEventListener('click', closeSettings);

  // Voice toggle
  $('voiceToggle').addEventListener('change', e => {
    voiceOutEnabled = e.target.checked;
    if (!voiceOutEnabled) interrupt();
  });

  // Gemini API Key input (for GitHub Pages direct cloud mode)
  if ($('geminiKeyInput')) {
    $('geminiKeyInput').value = getGeminiKey();
    $('geminiKeyInput').addEventListener('input', e => {
      setGeminiKey(e.target.value);
    });
  }

  // Passcode input
  $('passcodeInput').value = getPasscode();
  $('passcodeInput').addEventListener('input', e => {
    setPasscode(e.target.value);
  });

  // Settings actions
  $('restartBtn').addEventListener('click', () => {
    closeSettings();
    if ($('fightScreen').classList.contains('is-active')) {
      resetRound(true);
    }
  });

  $('resetWinsBtn').addEventListener('click', () => {
    winsCount = 0;
    localStorage.setItem('kf_wins', '0');
    updateWinsPips();
    toast('Win counter reset');
  });

  // Round over modal actions
  $('rematchBtn').addEventListener('click', triggerRematch);
  $('koChangeBtn').addEventListener('click', backToSelectScreen);
  $('koReviewBtn').addEventListener('click', () => {
    $('roundOver').hidden = true;
  });

  // Passcode gate form
  $('gateForm').addEventListener('submit', async e => {
    e.preventDefault();
    const code = $('gateInput').value.trim();
    setPasscode(code);
    const res = await fetch('/api/config', { headers: authHeaders() });
    if (res.ok) {
      const cfg = await res.json();
      if (cfg.authenticated) {
        $('gate').hidden = true;
        $('passcodeInput').value = code;
        toast('Unlocked!');
        return;
      }
    }
    $('gateError').textContent = 'Wrong passcode. Try again.';
  });
});

// Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('static/sw.js').catch(() => {});
  });
}
