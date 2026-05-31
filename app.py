# app.py — AgriVision AI Cameroun
# Serveur Flask : 3 modules (Diagnostic, Météo, Conseil)
# Déployable sur Render / Railway / Heroku / VPS

import os, base64, requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# ── CULTURES CAMEROUNAISES ─────────────────────────────────────────────────────
CULTURES = {
    "Vivriers":    ["Maïs","Manioc","Plantain","Igname","Macabo","Taro",
                    "Patate douce","Arachide","Sorgho","Mil","Riz","Haricot"],
    "Maraîchers":  ["Tomate","Gombo","Aubergine africaine","Poivron","Piment",
                    "Concombre","Oignon","Ail","Gingembre","Moringa"],
    "Rente":       ["Cacao","Café robusta","Café arabica","Palmier à huile",
                    "Coton","Hévéa","Canne à sucre","Tabac"],
    "Fruitiers":   ["Ananas","Papaye","Mangue","Avocat","Goyave",
                    "Orange","Citron","Safou","Prune africaine"],
    "Spéciaux":    ["Poivre blanc de Penja","Curcuma","Ndolé","Eru","Karité","Neem"],
}
ALL_CULTURES = [c for grp in CULTURES.values() for c in grp]
LISTE_STR    = ", ".join(ALL_CULTURES)

# ── SYSTEM PROMPTS ─────────────────────────────────────────────────────────────
SYS_DIAG = f"""Tu es un expert en phytopathologie spécialisé EXCLUSIVEMENT dans les cultures agricoles du Cameroun.

═══ RÈGLE 1 — REFUS NON-PLANTE ═══
Si l'image ne contient PAS une plante (végétal, feuille, tige, fruit, racine),
réponds UNIQUEMENT sur une seule ligne :
NON_PLANTE: [décris ce que tu vois]

═══ RÈGLE 2 — REFUS HORS CAMEROUN ═══
Cultures autorisées : {LISTE_STR}
Si la plante n'est PAS dans cette liste, réponds UNIQUEMENT :
NON_CAMEROUN: [nom de la plante identifiée]

═══ RÈGLE 3 — ÉTAT OBLIGATOIRE ═══
Distingue TOUJOURS l'état visuel de la plante :
• MORTE  : feuilles desséchées, brun/noir total, nécrose généralisée, aucune zone verte
• MALADE : taches, jaunissement, flétrissement partiel, lésions localisées
• SAINE  : vert vif uniforme, turgescence normale, pas de lésion

═══ RÈGLE 4 — FORMAT DE RÉPONSE (culture camerounaise confirmée) ═══

## Plante identifiée
[Nom camerounais courant] — [Nom scientifique] — [Variété locale si visible]

## État général : [MORTE 💀 / MALADE ⚠ / SAINE ✓]
[2–3 phrases décrivant précisément l'état visuel observé]

## Diagnostic
[Nom exact de la maladie ou "Aucune pathologie détectée"]
- Symptômes observés : [description précise]
- Gravité : [Critique / Sévère / Modérée / Faible / Nulle]
- Taux de confiance : [X%]

## Causes identifiées
[Champignon, bactérie, virus, insecte ravageur, carence minérale — sois précis]

## Traitements recommandés
- Urgence (moins de 24h) : [action concrète]
- Traitement curatif : [produit disponible au Cameroun + dose + fréquence + prix FCFA estimé]
- Traitement préventif : [mesures long terme]
- Alternative biologique locale : [solution disponible localement]

## Risque de contagion
[Risque de propagation aux cultures voisines + mesures d'isolation si nécessaire]

Tous les conseils sont adaptés au Cameroun : climat local, sols, intrants disponibles, prix FCFA."""

SYS_METEO = """Tu es un agronome-météorologue expert en agriculture camerounaise.
Tu maîtrises les 5 zones agro-écologiques du Cameroun :
1. Sahélo-soudanienne (Extrême-Nord)
2. Soudanienne (Nord, Adamaoua)
3. Forêt humide (Centre, Sud, Est)
4. Hautes terres (Ouest, Nord-Ouest)
5. Littorale (Littoral, Sud-Ouest)

FORMAT OBLIGATOIRE :

## Zone agro-écologique détectée
[Zone + caractéristiques climatiques]

## Analyse du climat actuel
[Résumé des conditions + saison en cours]

## Impact sur les cultures camerounaises
- ✓ Cultures favorisées : [liste avec explication]
- ⚠ Cultures à risque : [liste avec risques spécifiques]
- 🦠 Maladies favorisées par ces conditions : [liste pathologies probables]

## Actions agricoles prioritaires (48h)
[3 à 5 actions concrètes numérotées]

## Calendrier cultural cette semaine
[Jours recommandés pour : planter / récolter / traiter / irriguer]

## Alertes spécifiques Cameroun
[Risques climatiques locaux — seuils critiques à surveiller]

Donne des données chiffrées. Cite les marchés locaux si pertinent (Douala, Yaoundé, Bafoussam, Garoua)."""

SYS_CONSEIL = f"""Tu es un agronome expert senior du Cameroun, conseiller agricole personnel disponible 24h/24.

CULTURES QUE TU GÈRES EXCLUSIVEMENT :
{LISTE_STR}

RÈGLES STRICTES :
1. Si la culture n'est PAS dans la liste, réponds :
   "❌ Cette culture n'est pas gérée. Je suis spécialisé dans : [cultures proches]"
2. Si la question n'est pas agricole, refuse poliment et recentre.
3. Donne des données chiffrées : rendements kg/ha, doses, prix FCFA, calendriers précis.
4. Cite les institutions camerounaises utiles : IRAD, MINADER, FOFIFA, coopératives locales.
5. Mentionne les variétés adaptées au contexte camerounais (ex : maïs CMS 8704, cacao hybride).
6. Sois concret, pratique, adapté aux ressources des petits exploitants camerounais.
7. Utilise des emojis pertinents pour une lecture mobile confortable.
8. Réponds en français naturel, comme un agronome camerounais de terrain."""

# ── APPEL CLAUDE API ──────────────────────────────────────────────────────────
def call_claude(messages: list, system: str, key: str) -> dict:
    if not key:
        return {"error": "Clé API manquante", "code": 401}
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": "claude-opus-4-5", "max_tokens": 1500,
                  "system": system, "messages": messages},
            timeout=60,
        )
        if r.status_code == 401:
            return {"error": "Clé API invalide ou expirée", "code": 401}
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
        return jsonify({"error": "Format non supporté (JPG/PNG/WEBP requis)"}), 400

    result = call_claude(
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
            {"type": "text",  "text":  (
                "Analyse cette image étape par étape :\n"
                "1) Est-ce une plante agricole camerounaise ?\n"
                "2) Quel est son état visuel exact (morte/malade/saine) ?\n"
                "3) Quel est le diagnostic complet ?\n"
                "Applique strictement tes règles de refus si nécessaire."
            )}
        ]}],
        system=SYS_DIAG,
        key=get_key(),
    )
    if "error" in result:
        return jsonify(result), result.get("code", 500)

    texte = result["text"].strip()
    upper = texte.upper()

    if upper.startswith("NON_PLANTE"):
        detail = texte.split(":", 1)[-1].strip()
        return jsonify({"type": "non_plante", "message": detail})

    if upper.startswith("NON_CAMEROUN"):
        detail = texte.split(":", 1)[-1].strip()
        return jsonify({"type": "non_cameroun", "message": detail})

    # Détecter l'état de santé depuis le texte
    if any(w in upper for w in ["MORTE 💀", "MORTE :", "ÉTAT : MORTE", "ÉTAT GÉNÉRAL : MORTE"]):
        etat = "morte"
    elif any(w in upper for w in ["MALADE ⚠", "MALADE :", "ÉTAT : MALADE", "ÉTAT GÉNÉRAL : MALADE"]):
        etat = "malade"
    else:
        etat = "saine"

    return jsonify({"type": "diagnostic", "etat": etat, "texte": texte})


@app.route("/api/meteo", methods=["POST"])
def api_meteo():
    d = request.get_json() or {}
    prompt = (
        f"Localisation : {d.get('lieu','Yaoundé')}, Cameroun\n"
        f"Température : {d.get('temperature',26)}°C | "
        f"Humidité : {d.get('humidite',75)}% | "
        f"Précipitations : {d.get('precipitations','modérée')} | "
        f"Saison : {d.get('saison','Grande saison des pluies')}\n"
        f"Cultures en champ : {d.get('cultures','cultures vivrières camerounaises')}\n\n"
        "Fournis l'analyse agricole complète selon ton format."
    )
    result = call_claude(
        messages=[{"role": "user", "content": prompt}],
        system=SYS_METEO,
        key=get_key(),
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

    # Vérification côté serveur
    cl = culture.lower()
    if not any(cl in c.lower() or c.lower() in cl for c in ALL_CULTURES):
        suggestions = ", ".join(ALL_CULTURES[:10])
        return jsonify({
            "type": "non_cameroun",
            "texte": (f"❌ La culture « {culture} » n'est pas gérée par AgriVision AI Cameroun.\n\n"
                      f"Je suis spécialisé dans : {suggestions}…\n\n"
                      f"Choisissez une culture camerounaise pour continuer. 🇨🇲")
        })

    msgs = [{"role": m["role"], "content": m["content"]}
            for m in history[-10:] if m.get("role") in ("user","assistant")]
    msgs.append({"role": "user", "content": f"Culture : {culture}\n\nQuestion : {question}"})

    result = call_claude(
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
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    api_status = "✓ définie" if os.environ.get("ANTHROPIC_API_KEY") else "⚠ manquante (entrez-la dans l'interface)"
    print(f"\n🌿 AgriVision AI — Cameroun\n"
          f"   URL   : http://localhost:{port}\n"
          f"   API   : {api_status}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
