# Kerala AI Sparring App (Angry Boss & Angry Girlfriend)

A mobile-first, phone-friendly PWA where you spar with authentic Kerala Malayalam AI characters. They talk like real Kerala people, swear at comic "da myre" levels, remember your excuses, react to your exact words, and fight back. When you declare victory with **"i win"** (or **"ഞാൻ ജയിച്ചു"** / **"njan jayichu"**), the round ends with a parting retort and a Rematch screen.

---

## 1. Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.10.11)
- Google Gemini API Key (free tier recommended from [Google AI Studio](https://aistudio.google.com/)) for reliable Malayalam replies
- Optional local [Ollama](https://ollama.com/) install for offline use; note that local models on low-end laptops are noticeably weaker at Malayalam and should not be treated as the default

Assumption: the app defaults to Cloud Gemini because local Ollama is much weaker on Malayalam. If you do not have a GEMINI_API_KEY, the app will show a friendly warning instead of producing rough or unreadable Malayalam replies.

### Installation & Run
```powershell
# 1. Create and activate venv
python -m venv .venv
.\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env to add your GEMINI_API_KEY if using Cloud

# 4. Start the server (binds to 0.0.0.0 for mobile phone access)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your desktop browser or follow the steps below to open it on your phone.

---

## 2. How to Open on Your Phone

### Option A: Same Wi-Fi Network (Laptop + Phone)

1. Connect both your laptop and phone to the **same Wi-Fi network**.
2. Find your laptop's local IPv4 address:
   - On Windows, open PowerShell and run: `ipconfig`
   - Look for **IPv4 Address** under your Wi-Fi adapter (e.g. `192.168.1.15`).
3. Make sure the server is running on `0.0.0.0`:
   ```powershell
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. Optional Passcode Protection:
   - In `.env`, set `APP_PASSCODE=1234` (or any PIN you choose).
   - In the app on your phone, tap the Settings icon (⚙️) and enter this passcode.
5. On your phone's browser (Chrome or Safari):
   - Navigate to `http://<YOUR-LAPTOP-IP>:8000` (e.g. `http://192.168.1.15:8000`).
6. Install as a PWA (Home Screen App):
   - **Chrome on Android**: Tap the three dots menu (⋮) -> **"Add to Home screen"** or **"Install app"**.
   - **Safari on iOS**: Tap the Share button -> **"Add to Home Screen"**.
   - The app runs full-screen without browser chrome!

*(Note for Windows Firewall: If your phone cannot connect, allow Python through Windows Defender Firewall when prompted, or temporarily allow port 8000).*

---

### Option B: Free Cloud Deployment

#### Deploy to Render (Recommended Free Web Service):
1. Push this repository to a private or public GitHub repository.
2. Sign up at [Render.com](https://render.com/) (Free tier).
3. Click **New +** -> **Web Service** -> Connect your GitHub repo.
4. Settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment Variables:
   - `GEMINI_API_KEY`: your Google Gemini API key
   - `PROVIDER`: `gemini`
   - `APP_PASSCODE`: optional passcode
6. Deploy! Render gives you an `https://<your-app>.onrender.com` URL that works on any phone anywhere in the world.

#### Fast Temporary Tunnel via Cloudflare Tunnel / ngrok (Zero Server Setup):
1. Run `uvicorn main:app --host 0.0.0.0 --port 8000` on your laptop.
2. Run in a second terminal:
   ```powershell
   # Using free Cloudflare Tunnel without an account:
   npx cloudflared tunnel --url http://localhost:8000
   ```
   Or `ngrok http 8000`.
3. Open the generated `https://xyz.trycloudflare.com` on your phone!

---

## 3. Voice & Speech Options (Research & Verification)

We tested and verified multiple Text-to-Speech (TTS) and Speech-to-Text (STT) approaches on the same 4 Malayalam sentences:
1. *"എന്താടാ നോക്കുന്നത്? നിനക്ക് വേറെ പണി ഒന്നുമില്ലേ?"*
2. *"റിപ്പോർട്ട് എവിടെ? വെള്ളിയാഴ്ച തരാം എന്ന് പറഞ്ഞിട്ട് ഇപ്പോൾ എന്തായി?"*
3. *"ഞാൻ ജയിച്ചു"*
4. *"നീ എപ്പോഴും ഇങ്ങനെ തന്നെയാണ്, ഒരു കാര്യത്തിലും ഉത്തരവാദിത്തം ഇല്ല."*

### Verified Options:

| Provider | Type | Malayalam Support | Latency & Quality | Cost | Verified in Code |
|---|---|---|---|---|---|
| **Microsoft Edge Neural TTS** | Server TTS | **Exceptional** (`ml-IN-MidhunNeural` Male Boss, `ml-IN-SobhanaNeural` Female Girlfriend) | ~200-350ms, natural Kerala inflection, emotion & pauses | **100% Free** (No API key needed) | **Yes** (Primary provider in `voice.py`) |
| **Google Translate TTS** | Server TTS | **Good** (Standard spoken Malayalam) | ~300ms, clear pronunciation, MP3 format | **100% Free** (No API key needed) | **Yes** (Automatic fallback in `voice.py`) |
| **Browser Web Speech API** | Client STT | **Very Good** (`lang='ml-IN'`) in Chrome & Android | Real-time, transcribes Malayalam script & Manglish directly | **100% Free** | **Yes** (Built into `static/app.js`) |
| **Browser SpeechSynthesis** | Client TTS | Device dependent (Android Google Speech supports `ml-IN`, iOS falls back) | Instant client-side audio | **100% Free** | **Yes** (Selectable in settings) |
| **Gemini Multimodal Audio (STT)** | Server STT | **Good** (Gemini 1.5/2.5 Flash audio transcription via base64 upload) | ~1.5s latency | Free tier quota | **Yes** (`GeminiSTTProvider` in `voice.py`) |

### What Could Not Be Verified:
- **Gemini Live Bidirectional Audio (TTS Output)**: Gemini 2.0 Live WebSockets with native audio response output is in experimental developer preview and requires active Google Cloud Vertex / Gemini Live billing credentials. Without a user-supplied paid/live key, direct streaming audio generation from Gemini's live audio endpoint could not be verified against Google's live server. Edge-TTS and Google TTS provide 100% working, verified zero-cost solutions.
- **iOS Safari Native Speech Recognition for Malayalam**: Apple Speech in iOS Safari natively supports Hindi and Indian English, but Malayalam script dictation varies across iOS versions. On iOS, Chrome or typing works as a rock-solid fallback.

---

## 4. Fight Game Mechanics

### 1. Intensity Levels
- **Mild**: Sarcastic, questioning competence, eye-rolls, cold tone.
- **Spicy**: Aggressive everyday fury (*"തെണ്ടി"*, *"കഴുത"*, *"വിവരദോഷി"*, *"പോടാ പുല്ലേ"*).
- **Full Roast**: Unfiltered comic Kerala rage (*"da myre"* level comic venom, *"മൈര്"*, *"ചെറ്റ"*).
- You can customize words in:
  - `characters/boss/intensity.ml.txt`
  - `characters/girlfriend/intensity.ml.txt`

### 2. Custom Lines (`my_lines.md`)
You can fill in your own 30 fight situations and replies in:
- `characters/boss/my_lines.md`
- `characters/girlfriend/my_lines.md`
The engine automatically prioritizes your custom lines with top priority when choosing dialogue turns for the character.

### 3. Victory Condition & Rematch
- When you type or say **"i win"**, **"ഞാൻ ജയിച്ചു"**, or **"njan jayichu"**:
  - The character delivers a final grumbling defeat or sulking parting shot.
  - The **"Round Over"** modal screen pops up.
  - Tapping **"Next Round 🔥"** increments the round counter and triggers a fresh fight opener.

### 4. Hard Safety Net
- Identity-based attacks (caste, religion, gender, family, skin colour, body, threats of violence) are strictly forbidden by prompt rules and safety checks.
- If self-harm or crisis statements are detected in English, Manglish, or Malayalam script (e.g. *"എനിക്ക് മരിക്കണം"*, *"ജീവിതം മടുത്തു"*), the app instantly pauses roleplay, steps out of character, and provides immediate helpline contacts: **Tele-MANAS 14416** and **Emergency 112**.

---

## 5. Running the Tests

To run the complete automated test suite (68 tests covering anger arc, safety net, fight mechanics, personas, dialogues, and store):

```powershell
.\.venv\Scripts\activate
pytest
```
