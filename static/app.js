// Kerala Fight AI — Arcade HUD + Low-Latency Streaming & Pipelined Voice Engine

const $ = id => document.getElementById(id);

const CHARACTERS = {
  boss: {
    name: 'ANGRY BOSS',
    title: 'Angry Boss',
    startAnger: 9,
    openers: {
      ml: 'ഹായ് ഡാ, എന്താടാ കാര്യം? പറ.',
      manglish: 'Hi da, enthaada karyam? Parayu.',
      en: "Hi da, what's up? Tell me."
    },
    chips: {
      ml: [
        { label: '🏆 ഞാൻ ജയിച്ചു', text: 'ഞാൻ ജയിച്ചു', win: true },
        { label: 'പോടാ മൈരേ', text: 'പോടാ മൈരേ' },
        { label: 'ട്രാഫിക് ആയിരുന്നു സാറേ', text: 'റോഡിൽ ഭയങ്കര ബ്ലോക്ക് ആയിരുന്നു സാറേ' },
        { label: 'സോറി സാറേ', text: 'സോറി സാറേ, ഇനി ആവർത്തിക്കില്ല' }
      ],
      manglish: [
        { label: '🏆 I win', text: 'njan jayichu', win: true },
        { label: 'Poda myre', text: 'Poda myre' },
        { label: 'Traffic block aayirunnu', text: 'Roadil full traffic block aayirunnu sir' },
        { label: 'Sorry sir', text: 'Sorry sir, ini pattillaa' }
      ],
      en: [
        { label: '🏆 I win', text: 'i win', win: true },
        { label: 'Shut up man', text: 'Shut up, stop shouting at me' },
        { label: 'Stuck in traffic', text: 'I was stuck in terrible traffic' },
        { label: 'Sorry boss', text: 'Sorry boss, I will fix it right now' }
      ]
    }
  },
  girlfriend: {
    name: 'ANGRY GIRLFRIEND',
    title: 'Angry Girlfriend',
    startAnger: 8,
    openers: {
      ml: 'ഹായ് ഡാ, എന്താടാ വിളിച്ചത്? പറ.',
      manglish: 'Hi da, enthaada vilichath? Parayu.',
      en: 'Hi da, what is it? Speak.'
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

// State
let currentMode = 'boss';
let currentIntensity = 2;
let currentLang = 'ml';
let currentModelProvider = 'gemini';
let currentTtsProvider = 'edge';
let voiceOutEnabled = true;
let angerLevel = 9;
let roundNumber = 1;
let winsCount = parseInt(localStorage.getItem('kf_wins') || '0', 10) || 0;
let session = '';
let messages = [];

let isListening = false;
let isThinking = false;
let isSpeaking = false;

let turnSeq = 0; // Guards against stale chunks/audio from aborted requests
let currentAbortController = null;
let speechRecognizer = null;
let audioPipeline = []; // Array of Promises resolving to audio URLs or { browserText }
let isDrainingAudio = false;

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

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

function authHeaders(extra = {}) {
  const h = { ...extra };
  const code = getPasscode();
  if (code) h['X-Passcode'] = code;
  return h;
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
    typing: 'Replying…',
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
function syncModelChips() {
  const isCloud = currentModelProvider === 'gemini';
  for (const id of ['modelChipSelect', 'modelChipFight']) {
    const el = $(id);
    if (!el) continue;
    el.className = `model-chip ${isCloud ? 'is-cloud' : 'is-local'}`;
    const lbl = el.querySelector('.model-label');
    if (lbl) lbl.textContent = isCloud ? 'Cloud' : 'Local';
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
    try { currentAbortController.abort(); } catch (_) { }
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
    try { speechRecognizer.stop(); } catch (_) { }
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
// PIPELINED VOICE ENGINE (Prefetches Sentence Audio in Parallel with Streaming)
// ============================================================================

function enqueueSentenceAudio(sentenceText, seq) {
  if (!voiceOutEnabled || !sentenceText || !sentenceText.trim()) return;
  const clean = sentenceText.trim();
  if (clean.length < 2) return;

  if (currentTtsProvider === 'browser' && window.speechSynthesis) {
    audioPipeline.push(Promise.resolve({ browserText: clean, seq }));
    drainAudioPipeline(seq);
    return;
  }

  // Start fetching MP3 immediately in the background while text continues streaming!
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

      if (item.browserText) {
        await new Promise(resolve => {
          const utter = new SpeechSynthesisUtterance(item.browserText);
          utter.lang = currentLang === 'ml' ? 'ml-IN' : (currentLang === 'manglish' ? 'en-IN' : 'en-US');
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

// Extract complete sentences from streaming buffer so TTS starts immediately
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

const STATIC_ROASTS = {
  boss: {
    win: {
      ml: 'ജയിച്ചെന്നോ? പോയി തുലയ്, നിന്റെ തർക്കുത്തരം കേട്ട് എന്റെ തല പുകഞ്ഞു!',
      manglish: 'Jayichenno? Poyi thulay, ninte tharkkutharam kettu ente thala pukanju!',
      en: 'You won?! Get lost, my head is spinning from your arguments!'
    },
    lines: {
      ml: [
        'എനിക്ക് ഒഴിവുകഴിവല്ല വേണ്ടത്, ആ ഫയൽ എവിടെയെന്ന് പറ!',
        'നാക്ക് അടക്കി സംസാരിക്കെടാ! ശമ്പളം വാങ്ങാൻ മാത്രം സമയത്ത് വരും!',
        'കള്ളം പറയുന്നതിനും ഒരു പരിധിയുണ്ട് ഡാ!',
        'നിന്റെ ഈ ഡയലോഗ് കേട്ട് മടുത്തു, പണി എടുത്ത് കാണിക്കെടാ!',
        'അതേടാ, എല്ലാം ട്രാഫിക് ബ്ലോക്കിന്റെ തലയിൽ വെച്ചോ!'
      ],
      manglish: [
        'Enikku excuse venda, aa file evide ennu parayu!',
        'Naavukondu paniyaan nokkalle, pani eduthu kaanikeda!',
        'Salary vaangaan maathram krithya samayathu varum alle?',
        'Ninte ee dialogue kettu maduthu, valla paniyum cheyyeda!',
        'Ellam road blockinte thalayil vecho, kalla thendi!'
      ],
      en: [
        "I didn't ask for excuses, where is the report?!",
        'Watch your tone! You only show up on time on payday!',
        'Save the drama and finish the work you were assigned!',
        'Every single day a new story from you!',
        'Stop giving lectures and get back to your desk!'
      ]
    }
  },
  girlfriend: {
    win: {
      ml: 'ഓഹോ, കപ്പടിച്ചല്ലോ! ആ ട്രോഫിയും കെട്ടിപ്പിടിച്ച് കിടന്നുറങ്ങിക്കോ, ഇനി മിണ്ടരുത്!',
      manglish: 'Oho, cup adichallo! Aa trophyum kettippidichu kidannu urangikko!',
      en: 'Oh, you won a trophy? Go hug it and sleep, never talk to me again!'
    },
    lines: {
      ml: [
        'മൂന്ന് ദിവസം ഒരു മെസ്സേജ് അയക്കാൻ സമയം കിട്ടിയില്ലല്ലേ?!',
        'എപ്പോഴും ഇത് തന്നെ, കഴിഞ്ഞിട്ട് ഒരു സോറി പറഞ്ഞ് കൈ കഴുകും!',
        'എനിക്ക് ഇപ്പോൾ ദേഷ്യമല്ല, നിന്റെ സ്വഭാവം കണ്ട് മടുത്തു!',
        'കള്ളം പറയല്ലേ, കൂട്ടുകാരുടെ കൂടെ കറങ്ങാൻ സമയം ഉണ്ടായിരുന്നല്ലോ!',
        'ആഹാ, ഇപ്പോൾ എല്ലാം എന്റെ കുറ്റമായോ?! കൊള്ളാം!'
      ],
      manglish: [
        'Moonnu divasam oru message polum ayakkan samayam kittiyillalle?!',
        'Ellam kazhinju oru sorry parayum, athu kondu entha karyam?',
        'Enikku ippo deshyam alla, ninte swabhavam kandu maduthu!',
        'Friendsinte koode karangaan ishtam pole samayam undallo!',
        'Aaha, ippo ellam ente kuttam aayo?! Nalla karyam!'
      ],
      en: [
        'Three days and not even a single text message from you!',
        'You always do this and think one sorry fixes everything!',
        'You had plenty of time for your friends though, right?!',
        'Oh wonderful, now somehow this is all MY fault?!',
        "I'm not even angry anymore, I'm just tired of your excuses!"
      ]
    }
  }
};
let staticRoastIdx = 0;

async function offlineImprovReply(userText, mySeq, typingBubble) {
  const isWin = /\b(i win|i won|njan jayichu|njan jeyichu)\b/i.test(userText) || userText.includes('ഞാൻ ജയിച്ചു');
  const pack = STATIC_ROASTS[currentMode] || STATIC_ROASTS.boss;
  let reply;
  if (isWin) {
    reply = pack.win[currentLang] || pack.win.ml;
  } else {
    const pool = pack.lines[currentLang] || pack.lines.ml;
    reply = pool[staticRoastIdx % pool.length];
    staticRoastIdx++;
  }

  await new Promise(r => setTimeout(r, 260));
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
    await new Promise(r => setTimeout(r, 45));
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

  // Barge-in: cancel any ongoing reply/speech
  interrupt();
  const mySeq = ++turnSeq;

  messages.push({ role: 'user', text });
  appendBubble('user', text);

  isThinking = true;
  setStageState('thinking');

  // Show typing indicator bubble immediately
  const typingBubble = document.createElement('div');
  typingBubble.className = 'msg ai typing';
  typingBubble.innerHTML = '<i></i><i></i><i></i>';
  $('log').appendChild(typingBubble);
  $('chat').scrollTop = $('chat').scrollHeight;

  currentAbortController = new AbortController();

  const payload = {
    mode: currentMode,
    intensity: currentIntensity,
    lang: currentLang,
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

    if (res.status === 404 || res.status === 405) {
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

          // Pipelined TTS: synthesize completed sentences immediately while streaming continues
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

          // Speak any remaining tail that didn't end with punctuation
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
          typingBubble.remove();
          isThinking = false;
          setStageState('idle');
          appendBubble('ai', event.message || 'Model error. Try again.', 'error');
        }
      }
    }
  } catch (err) {
    typingBubble.remove();
    if (err.name === 'AbortError') return;
    isThinking = false;
    setStageState('idle');
    appendBubble('ai', 'Connection interrupted. Check server.', 'error');
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
    }
  } catch (_) {
    roundNumber++;
    resetRound(false);
  }
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
    } catch (_) { }
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
  try {
    const res = await fetch('/api/config', { headers: authHeaders() });
    if (!res.ok) return;
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
  } catch (_) { }
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
    navigator.serviceWorker.register('/sw.js').catch(() => { });
  });
}
