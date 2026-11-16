"""Keyword safety net for crisis prevention and harmful content.

Catches statements about self-harm or harm to others in English,
Manglish, and Malayalam script so the app steps out of roleplay and answers
with care and helpline details.
"""

import re
from typing import Optional

_SPACE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _SPACE.sub(" ", (text or "").lower()).strip()


# (category, pattern). Latin script: word boundaries are safe.
_LATIN = [
    # self-harm (English)
    ("self", r"\bkil(?:l|ling) my ?self\b"),
    ("self", r"\bsuicid(?:e|al)\b"),
    ("self", r"\b(?:end|ending|take|taking) my (?:own )?life\b"),
    ("self", r"\bwant(?:ing)? to die\b"),
    ("self", r"\bwanna die\b"),
    ("self", r"\bwish i (?:was|were) dead\b"),
    ("self", r"\bbetter off dead\b"),
    ("self", r"\bno reason to live\b"),
    ("self", r"\bhurt(?:ing)? my ?self\b"),
    ("self", r"\bcut(?:ting)? my ?wrists?\b"),

    # self-harm (Manglish)
    ("self", r"\bchathu ?pokan(?:am)?\b"),          # ചത്തു പോകണം
    ("self", r"\bchaak?kanam\b"),                    # ചാകണം
    ("self", r"\bchaavanam\b"),                      # ചാവണം
    ("self", r"\bchathaal mathi(?:yirunnu)?\b"),     # ചത്താൽ മതി
    ("self", r"\bmarikkan(?:am)?\b"),                # മരിക്കണം
    ("self", r"\bmarichaal mathi(?:yirunnu)?\b"),    # മരിച്ചാൽ മതി
    ("self", r"\bnjan marikkum\b"),                  # ഞാൻ മരിക്കും
    ("self", r"\batma ?hat(?:hya|ya)\b"),            # ആത്മഹത്യ
    ("self", r"\bjeevikkan vayya\b"),                # ജീവിക്കാൻ വയ്യ
    ("self", r"\bjeevikkan thalparyam illa\b"),      # ജീവിക്കാൻ താല്പര്യമില്ല
    ("self", r"\bjeevitham maduthu\b"),              # ജീവിതം മടുത്തു
    ("self", r"\bkai murikkum\b"),                   # കൈ മുറിക്കും
    ("self", r"\bvisham kazhikkum\b"),               # വിഷം കഴിക്കും

    # harm to others (English)
    ("other", r"\bkill (?:you|u|him|her|them)\b"),
    ("other", r"\bi(?:'ll| will) (?:kill|stab|shoot|strangle) (?:you|u|him|her|them)\b"),
    ("other", r"\bmurder (?:you|u|him|her|them)\b"),

    # harm to others (Manglish)
    ("other", r"\b(?:avaneye|avane|ninne|avale) kollum\b"),           # അവനെ/നിന്നെ കൊല്ലും
    ("other", r"\b(?:ninne|avane) konnu kalayum\b"),                  # കൊന്നു കളയും
    ("other", r"\bchavitti(?:k)? ?kollum\b"),                         # ചവിട്ടിക്കൊല്ലും
    ("other", r"\bvetti(?:k)? ?kollum\b"),                            # വെട്ടിക്കൊല്ലും
    ("other", r"\bkollum ninne\b"),                                   # കൊല്ലും നിന്നെ
    ("other", r"\bkuthiy?k?kollum\b"),                                # കുത്തിക്കൊല്ലും
]

# Malayalam script: plain substrings
_SCRIPT = [
    # self-harm
    ("self", "ആത്മഹത്യ"),             # suicide
    ("self", "ജീവിക്കണ്ട"),            # don't want to live
    ("self", "ചാകണം"),                # want to die
    ("self", "ചാവണം"),                # want to die
    ("self", "മരിക്കണം"),              # want to die
    ("self", "മരിച്ചാൽ മതി"),          # better if dead
    ("self", "ചത്താൽ മതി"),            # better if dead
    ("self", "ജീവിതം മടുത്തു"),         # tired of life
    ("self", "കൈ മുറിക്കും"),          # cut wrist
    ("self", "വിഷം കഴിക്കും"),          # drink poison
    ("self", "ജീവനൊടുക്കും"),          # end life

    # harm to others
    ("other", "കൊല്ലണം"),              # want to kill
    ("other", "കൊല്ലും"),               # will kill
    ("other", "കൊന്നുകളയും"),           # will murder
    ("other", "വെട്ടിക്കൊല്ലും"),         # will hack/kill
    ("other", "ചവിട്ടിക്കൊല്ലും"),        # will kick/kill
    ("other", "കുത്തിക്കൊല്ലും"),         # will stab/kill
    ("other", "കൊലപ്പെടുത്തും"),        # will assassinate
]

_LATIN_COMPILED = [(cat, re.compile(p, re.I)) for cat, p in _LATIN]


def check(text: str) -> Optional[str]:
    """Return "self", "other" or None for the given user message."""
    body = _norm(text)
    if not body:
        return None
    for category, pattern in _LATIN_COMPILED:
        if pattern.search(body):
            return category
    for category, piece in _SCRIPT:
        if piece in body:
            return category
    return None


REPLY_EN = """I'm stepping out of the character and stopping the fight. This is the app talking, not the character.

What you just shared sounds serious, and your life and safety matter far more than any game or argument. Please talk to someone you trust right now, or contact professional support:
- Tele-MANAS (India, free, 24x7): 14416 or 1800-891-4416
- National Emergency: 112

I am an AI sparring app, not a therapist or mental health professional. When you are ready and feeling okay, you can restart anytime."""

REPLY_ML = """ഇവിടെ ഫൈറ്റ് നിർത്തി ഞാൻ കഥാപാത്രത്തിൽ നിന്ന് പുറത്തു കടക്കുന്നു. ഇത് കഥാപാത്രമല്ല സംസാരിക്കുന്നത്, ആപ്പാണ്.

നിങ്ങൾ ഇപ്പോൾ പറഞ്ഞത് വളരെ ഗൗരവമുള്ളതാണ്. ഏതൊരു കളിയേക്കാളും തർക്കത്തേക്കാളും പ്രധാനം നിങ്ങളുടെ ജീവനും സുരക്ഷിതത്വവുമാണ്. ദയവായി ഇപ്പോൾ തന്നെ നിങ്ങൾ വിശ്വസിക്കുന്ന ആരോടെങ്കിലും സംസാരിക്കൂ, അല്ലെങ്കിൽ താഴെ പറയുന്ന സൗജന്യ ഹെൽപ്പ്‌ലൈനിൽ വിളിക്കൂ:
- Tele-MANAS (ഇന്ത്യ, സൗജന്യം, 24x7): 14416 അല്ലെങ്കിൽ 1800-891-4416
- നാഷണൽ എമർജൻസി: 112

ഞാൻ ഒരു പരിശീലന ആപ്പാണ്, കൗൺസിലറോ തെറാപ്പിസ്റ്റോ അല്ല. നിങ്ങൾക്ക് ആശ്വാസം തോന്നുമ്പോൾ ശാന്തമായ മനസ്സോടെ വീണ്ടും തുടങ്ങാം."""


def reply(lang: str = "en") -> str:
    """Caring, out-of-character reply."""
    return REPLY_ML if lang == "ml" else REPLY_EN
