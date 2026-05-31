# app.py — AgriVision AI Cameroun
# Serveur Flask compatible ANTHROPIC et GOOGLE GEMINI
# Déployable sur Render / Railway / Heroku / VPS

import os, base64, requests, json
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ── CULTURES CAMEROUNAISES ─────────────────────────────────────────────────────
CULTURES = {
    "Vivriers":   ["Maïs","Manioc","Plantain","Igname","Macabo","Taro",
                   "Patate douce","Arachide","Sorgho","Mil","Riz","Haricot"],
    "Maraîchers": ["Tomate","Gombo","Aubergine africaine","Poivron","Piment",
                   "Concombre","Oignon","Ail","Gingembre","Moringa"],
    "Rente":      ["Cacao","Café robusta","Café arabica","Palmier à huile",
                   "Coton","Hévéa","Canne à sucre","Tabac"],
    "Fruitiers":  ["Ananas","Papaye","Mangue","Avocat","Goyave",
                   "Orange","Citron","Safou","Prune africaine"],
    "Spéciaux":   ["Poivre blanc de Penja","Curcuma","Ndolé","Eru","Karité","Neem"],
}
ALL_CULTURES = [c for grp in CULTURES.values() for c in grp]
LISTE_STR    = ", ".join(ALL_CULTURES)

# ── SYSTEM PROMPTS ─────────────────────────────────────────────────────────────
SYS_DIAG = f"""Tu es un expert en phytopathologie spécialisé EXCLUSIVEMENT dans les cultures agricoles du Cameroun.

RÈGLE 1 — REFUS NON-PLANTE :
Si l'image ne contient PAS une plante (végétal, feuille, tige, fruit, racine),
réponds UNIQUEMENT : NON_PLANTE: [décris ce que tu vois]

RÈGLE 2 — REFUS HORS CAMEROUN :
Cultures autorisées : {LISTE_STR}
Si la plante n'est PAS dans cette liste, réponds UNIQUEMENT :
NON_CAMEROUN: [nom de la plante identifiée]

RÈGLE 3 — ÉTAT OBLIGATOIRE :
Distingue TOUJOURS :
- MORTE  : feuilles sèches, brun/noir, nécrose totale, aucun vert
- MALADE : taches, jaunissement, flétrissement partiel
- SAINE  : vert vif, turgescence normale, pas de lésion

RÈGLE 4 — FORMAT (culture camerounaise confirmée) :

## Plante identifiée
[Nom camerounais] — [Nom scientifique] — [Variété locale]

## État général : [MORTE 💀 / MALADE ⚠ / SAINE ✓]
[2–3 phrases sur l'état visuel]

## Diagnostic
[Maladie ou "Aucune pathologie détectée"]
- Symptômes : ...
- Gravité : [Critique/Sévère/Modérée/Faible/Nulle]
- Confiance : [X%]

## Causes identifiées
[Champignon, bactérie, virus, ravageur, carence]

## Traitements recommandés
- Urgence (24h) : ...
- Curatif : [produit dispo au Cameroun + prix FCFA]
- Préventif : ...
- Biologique local : ...

## Risque de contagion
[Propagation + isolation]

Tous les conseils sont adaptés au Cameroun : climat, intrants locaux, prix FCFA."""

SYS_METEO = """Tu es un agronome-météorologue expert en agriculture camerounaise.
Tu connais les 5 zones agro-écologiques du Cameroun.

FORMAT :
## Zone agro-écologique
[Zone + caractéristiques]

## Analyse du climat actuel
[Résumé conditions + saison]

## Impact sur les cultures camerounaises
- ✓ Cultures favorisées : ...
- ⚠ Cultures à risque : ...
- 🦠 Maladies favorisées : ...

## Actions prioritaires (48h)
[3–5 actions numérotées]

## Calendrier cette semaine
[Planter / récolter / traiter / irriguer]

## Alertes Cameroun
[Risques à surveiller]"""

SYS_CONSEIL = f"""Tu es un agronome expert senior du Cameroun, conseiller agricole 24h/24.

CULTURES GÉRÉES : {LISTE_STR}

RÈGLES :
1. Si culture hors liste : refuse et propose des cultures proches.
2. Si question non agricole : refuse et recentre.
3. Données chiffrées : rendements kg/ha, doses, prix FCFA.
4. Cite : IRAD, MINADER, coopératives locales.
5. Variétés adaptées au Cameroun.
6. Réponds en français naturel avec emojis pour mobile."""

# ── MOTEUR IA : ANTHROPIC OU GEMINI ──────────────────────────────────────────
def call_ai(messages: list, system: str, key: str, image_b64: str = None,
            image_mime: str = None) -> dict:
    """
    Détecte automatiquement le type de clé :
    - sk-ant-... → API Anthropic (Claude)
    - AIza...    → API Google Gemini
    """
    if not key:
        return {"error": "Clé API manquante", "code": 401}

    if key.startswith("AIza"):
        return _call_gemini(messages, system, key, image_b64, image_mime)
    else:
        return _call_anthropic(messages, system, key, image_b64, image_mime)


def _call_anthropic(messages, system, key, image_b64, image_mime):
    """Appel API Anthropic Claude."""
    # Construire les messages avec image si présente
    if image_b64 and messages and messages[-1]["role"] == "user":
        content = [
            {"type": "image", "source": {
                "type": "base64", "media_type": image_mime, "data": image_b64}},
            {"type": "text", "text": messages[-1]["content"]}
        ]
        msgs = messages[:-1] + [{"role": "user", "content": content}]
    else:
        msgs = messages

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-opus-4-5", "max_tokens": 1500,
                  "system": system, "messages": msgs},
            timeout=60,
        )
        if r.status_code == 401:
            return {"error": "Clé Anthropic invalide ou expirée", "code": 401}
        if r.status_code == 529 or "credit" in r.text.lower():
            return {"error": "Solde Anthropic insuffisant — utilisez une clé Google (AIza...)", "code": 402}
        if not r.ok:
            msg = r.json().get("error", {}).get("message", f"Erreur {r.status_code}")
            return {"error": msg, "code": r.status_code}
        return {"text": r.json()["content"][0]["text"]}
    except requests.exceptions.ConnectionError:
        return {"error": "Pas de connexion internet", "code": 503}
    except requests.exceptions.Timeout:
        return {"error": "Délai dépassé, réessayez", "code": 504}
    except Exception as e:
        return {"error": str(e), "code": 500}


def _call_gemini(messages, system, key, image_b64, image_mime):
    """Appel API Google Gemini."""
    # Construire le contenu Gemini
    parts = []

    # Image si présente
    if image_b64 and image_mime:
        parts.append({"inline_data": {"mime_type": image_mime, "data": image_b64}})

    # Historique de conversation
    contents = []
    for m in messages[:-1]:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    # Dernier message utilisateur
    last_text = messages[-1]["content"] if messages else ""
    parts.append({"text": last_text})
    contents.append({"role": "user", "parts": parts})

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.3},
    }

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.0-flash:generateContent?key={key}")

    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 400:
            return {"error": "Clé Google invalide ou quota dépassé", "code": 400}
        if not r.ok:
            return {"error": f"Erreur Gemini {r.status_code}", "code": r.status_code}
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return {"text": text}
    except requests.exceptions.ConnectionError:
        return {"error": "Pas de connexion internet", "code": 503}
    except requests.exceptions.Timeout:
        return {"error": "Délai dépassé", "code": 504}
    except (KeyError, IndexError):
        return {"error": "Réponse Gemini inattendue", "code": 500}
    except Exception as e:
        return {"error": str(e), "code": 500}


def get_key():
    return request.headers.get("X-API-Key") or os.environ.get("ANTHROPIC_API_KEY", "")

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", cultures=CULTURES)


@app.route("/api/diagnostic", methods=["POST"])
def api_diagnostic():
    data = request.get_json() or {}
    b64  = data.get("image", "")
    mime = data.get("mime", "image/jpeg")
    if not b64:
        return jsonify({"error": "Image manquante"}), 400
    if mime not in ("image/jpeg","image/png","image/webp","image/gif"):
        return jsonify({"error": "Format non supporté (JPG/PNG/WEBP)"}), 400

    question = ("Analyse cette image :\n"
                "1) Est-ce une plante agricole camerounaise ?\n"
                "2) Quel est son état visuel exact (morte/malade/saine) ?\n"
                "3) Quel est le diagnostic complet ?\n"
                "Applique strictement tes règles de refus si nécessaire.")

    result = call_ai(
        messages=[{"role": "user", "content": question}],
        system=SYS_DIAG,
        key=get_key(),
        image_b64=b64,
        image_mime=mime,
    )
    if "error" in result:
        return jsonify(result), result.get("code", 500)

    texte = result["text"].strip()
    upper = texte.upper()

    if upper.startswith("NON_PLANTE"):
        return jsonify({"type": "non_plante",
                        "message": texte.split(":", 1)[-1].strip()})
    if upper.startswith("NON_CAMEROUN"):
        return jsonify({"type": "non_cameroun",
                        "message": texte.split(":", 1)[-1].strip()})

    # Détecter état santé
    if any(w in upper for w in ["MORTE 💀", "MORTE :", ": MORTE", "GÉNÉRAL : MORTE"]):
        etat = "morte"
    elif any(w in upper for w in ["MALADE ⚠", "MALADE :", ": MALADE", "GÉNÉRAL : MALADE"]):
        etat = "malade"
    else:
        etat = "saine"

    return jsonify({"type": "diagnostic", "etat": etat, "texte": texte})


@app.route("/api/meteo", methods=["POST"])
def api_meteo():
    d = request.get_json() or {}
    prompt = (f"Localisation : {d.get('lieu','Yaoundé')}, Cameroun\n"
              f"Température : {d.get('temperature',26)}°C | "
              f"Humidité : {d.get('humidite',75)}% | "
              f"Précipitations : {d.get('precipitations','modérée')} | "
              f"Saison : {d.get('saison','Grande saison des pluies')}\n"
              f"Cultures : {d.get('cultures','cultures vivrières camerounaises')}\n\n"
              "Fournis l'analyse agricole complète.")

    result = call_ai(
        messages=[{"role": "user", "content": prompt}],
        system=SYS_METEO, key=get_key(),
    )
    if "error" in result:
        return jsonify(result), result.get("code", 500)
    return jsonify({"type": "meteo", "texte": result["text"]})


@app.route("/api/conseil", methods=["POST"])
def api_conseil():
    d        = request.get_json() or {}
    culture  = d.get("culture", "").strip()
    question = d.get("question", "").strip()
    history  = d.get("history", [])

    if not culture or not question:
        return jsonify({"error": "culture et question requises"}), 400

    cl = culture.lower()
    if not any(cl in c.lower() or c.lower() in cl for c in ALL_CULTURES):
        return jsonify({
            "type": "non_cameroun",
            "texte": (f"❌ « {culture} » n'est pas gérée par AgriVision AI Cameroun.\n\n"
                      f"Cultures disponibles : {', '.join(ALL_CULTURES[:10])}…\n\n"
                      "Choisissez une culture camerounaise. 🇨🇲")
        })

    msgs = [{"role": m["role"], "content": m["content"]}
            for m in history[-10:] if m.get("role") in ("user","assistant")]
    msgs.append({"role": "user",
                 "content": f"Culture : {culture}\n\nQuestion : {question}"})

    result = call_ai(
        messages=msgs,
        system=SYS_CONSEIL + f"\n\nCulture de la session : {culture}",
        key=get_key(),
    )
    if "error" in result:
        return jsonify(result), result.get("code", 500)
    return jsonify({"type": "conseil", "texte": result["text"]})


@app.route("/api/cultures")
def api_cultures():
    return jsonify({"cultures": CULTURES, "total": len(ALL_CULTURES)})


# ── LANCEMENT ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key.startswith("AIza"):
        provider = "Google Gemini ✓"
    elif api_key.startswith("sk-"):
        provider = "Anthropic Claude ✓"
    else:
        provider = "⚠ non définie (entrez-la dans l'interface)"
    print(f"\n🌿 AgriVision AI — Cameroun\n"
          f"   URL      : http://localhost:{port}\n"
          f"   Fournisseur IA : {provider}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
