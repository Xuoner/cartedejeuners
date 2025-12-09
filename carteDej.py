# app.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import random
import uuid
import json
from html import escape

import requests
import base64
import pandas as pd
from io import StringIO

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = "Xuoner/cartedejeuners"  # change to your repo
CSV_PATH = "restaurants.csv"
API_URL_CSV = f"https://api.github.com/repos/{REPO}/contents/restaurants.csv"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

st.set_page_config(page_title="🍽️ Carte des Restos", layout="wide")



# -----------------------------
# Chargement / initialisation du CSV
# -----------------------------
# -----------------------------
# Load CSV from GitHub
# -----------------------------
def load_csv_github(api_url):
    resp = requests.get(api_url, headers=HEADERS)
    if resp.status_code == 200:
        content = resp.json()["content"]
        decoded = base64.b64decode(content).decode("utf-8")
        df = pd.read_csv(StringIO(decoded))
        return df
    else:
        st.warning("Impossible de charger le CSV depuis GitHub, création d'un CSV vide.")
        return pd.DataFrame(columns=["id", "nom", "lat", "lon", "type", "ratings"])

# -----------------------------
# Save CSV to GitHub
# -----------------------------
def save_csv_github(api_url, df, message="Update CSV"):
    # get current sha
    resp = requests.get(api_url, headers=HEADERS)
    sha = resp.json()["sha"] if resp.status_code == 200 else None

    csv_str = df.to_csv(index=False, encoding="utf-8")
    content_base64 = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")
    payload = {
        "message": message,
        "content": content_base64,
        "sha": sha,
    }
    put_resp = requests.put(api_url, headers=HEADERS, json=payload)
    if put_resp.status_code in [200, 201]:
        st.success("✅ CSV mis à jour sur GitHub")
    else:
        st.error(f"Erreur GitHub: {put_resp.status_code} {put_resp.text}")

df = load_csv_github(API_URL_CSV)

# S'assurer que les colonnes existent
for col in ["id", "nom", "lat", "lon", "type", "ratings"]:
    if col not in df.columns:
        df[col] = ""

# Remplacer NaN par ""
df = df.fillna("")

st.title("🍽️ Carte des Déjeuners")

# -----------------------------
# Sidebar : filtres & actions
# -----------------------------
st.sidebar.header("🔍 Filtres & Actions")

# Filtre par type
types_dispo = ["Tous"] + sorted([t for t in df["type"].unique() if t])
type_filtre = st.sidebar.selectbox("Type de cuisine", types_dispo)

if type_filtre != "Tous":
    df_affiche = df[df["type"] == type_filtre].copy()
else:
    df_affiche = df.copy()

# Bouton déjeuner aléatoire (prend les restos ayant au moins une note)
if st.sidebar.button("🎲 Choisis mon déjeuner !"):
    df_with_ratings = df_affiche[df_affiche["ratings"].str.len() > 2]  # "{}" length = 2
    if df_with_ratings.empty:
        st.sidebar.warning("Aucun restaurant noté pour le moment.")
    else:
        pick = df_with_ratings.sample(1).iloc[0]
        avg = None
        try:
            ratings = json.loads(pick["ratings"])
            if ratings:
                avg = sum(ratings.values()) / len(ratings)
        except Exception:
            ratings = {}
        st.sidebar.success(f"👉 **{pick['nom']}** ({pick['type']})")
        if avg:
            st.sidebar.write(f"⭐ Moyenne : {avg:.2f} / 5")

st.sidebar.markdown("---")

# -----------------------------
# Partie : noter un resto existant
# -----------------------------
st.sidebar.header("✏️ Noter un restaurant")

liste_restos = ["Aucun"] + df["nom"].tolist()
choix_resto = st.sidebar.selectbox("Choisir un restaurant à noter", liste_restos)

if choix_resto != "Aucun":
    # trouver la ligne correspondante (si plusieurs même nom, prend la première)
    resto_row = df[df["nom"] == choix_resto].iloc[0]
    st.sidebar.write(f"**{resto_row['nom']}** — {resto_row['type']}")
    user_name = st.sidebar.text_input("Ton prénom (ou nom)", key="user_name")
    note_user = st.sidebar.slider("Ta note (étoiles)", 1, 5, 4, key="note_user")
    if st.sidebar.button("Enregistrer ma note"):
        if not user_name.strip():
            st.sidebar.error("Indique ton prénom pour enregistrer ta note.")
        else:
            idx = df[df["id"] == resto_row["id"]].index[0]
            try:
                ratings = json.loads(df.at[idx, "ratings"]) if df.at[idx, "ratings"] else {}
            except Exception:
                ratings = {}
            ratings[user_name.strip()] = int(note_user)
            df.at[idx, "ratings"] = json.dumps(ratings, ensure_ascii=False)
            save_csv_github(API_URL_CSV, df, message="Ajout/modification de restaurant")
            st.sidebar.success("Note enregistrée !")
            st.rerun()

st.sidebar.markdown("---")

# -----------------------------
# Carte : style plus épuré + emojis comme "stickers"
# -----------------------------
centre = [48.872706818553965, 2.3357471708821524]
m = folium.Map(location=centre, zoom_start=18, tiles="CartoDB positron")  # style épuré

# Ajouter le point "RSM 🏢" par défaut
work_lat, work_lon = 48.87199, 2.33562

work_popup = folium.Popup(
    "<b>RSM 🏢</b><br><small>Bureau</small>",
    max_width=120
)

work_icon_html = """
<div style="text-align:center;">
  <div style="
      display:inline-block;
      padding:2px 4px;
      border-radius:10px;
      background:rgba(255,255,255,0.9);
      box-shadow:0 1px 3px rgba(0,0,0,0.25);
  ">
      <div style="font-size:16px; line-height:16px;">🏢</div>
      <div style="font-size:12px; color:#555; margin-top:2px;">RSM</div>
  </div>
</div>
"""



work_icon = folium.DivIcon(html=work_icon_html)

folium.Marker(
    location=[work_lat, work_lon],
    popup=work_popup,
    tooltip="Locaux RSM 🏢",
    icon=work_icon
).add_to(m)


# fonction qui retourne un emoji selon le type
def get_emoji(type_cuisine: str) -> str:
    if not isinstance(type_cuisine, str) or type_cuisine.strip() == "":
        return "⭐"

    t = type_cuisine.lower()

    if "jap" in t: return "🍣"
    if "ital" in t or "pâtes" in t: return "🍝"
    if "pizz" in t: return "🍕"
    if "burger" in t: return "🍔"
    if "mex" in t: return "🌮"
    if "ind" in t: return "🇮🇳"
    if "healthy" in t or "salad" in t or "vege" in t: return "🥗"
    if "asiat" in t or "chin" in t or "thai" in t: return "🍜"
    if "bar" in t or "pub" in t: return "🍺"
    if "café" in t or "cafe" in t: return "☕"
    if "leban" in t or "liban" in t: return "🥙"
    if "fast food" in t or "kfc" in t or "mcdo" in t: return "🍟"

    return "🍽️"


# fonction pour afficher des étoiles HTML (nombre entier 1..5)
def stars_html(n: int) -> str:
    n = max(1, min(5, int(n)))
    full = "★" * n
    empty = "☆" * (5 - n)
    return f"<span style='color:#f4c542;font-size:14px'>{full}{empty}</span>"

# Construire les marqueurs
for _, row in df_affiche.iterrows():
    emoji = get_emoji(row["type"])
    # couleur du marker selon avis moyen (si pas de notes: orange)
    avg = None
    try:
        ratings = json.loads(row["ratings"]) if row["ratings"] else {}
        if ratings:
            avg = sum(ratings.values()) / len(ratings)
    except Exception:
        ratings = {}
    if avg is None:
        couleur = "orange"
    elif avg >= 4.0:
        couleur = "green"
    elif avg >= 2.5:
        couleur = "blue"
    else:
        couleur = "red"

    # Construire le HTML du popup : nom, type, commentaire, moyenne, liste des notes individuelles
    safe_nom = escape(str(row["nom"]))
    safe_type = escape(str(row["type"]))
    popup_html = f"<div style='min-width:180px'>"
    popup_html += f"<b>{safe_nom} {emoji}</b><br><small>{safe_type}</small><br>"
    if ratings:
        avg_display = sum(ratings.values()) / len(ratings)
        popup_html += f"<b>Moyenne :</b> {avg_display:.2f} / 5 {stars_html(round(avg_display))}<br>"
        popup_html += "<b>Notes (par personne) :</b><br><ul style='margin:6px 0 0 14px;padding:0;'>"
        # trier par nom
        for user, val in sorted(ratings.items(), key=lambda x: x[0].lower()):
            popup_html += f"<li>{escape(user)} — {int(val)} / 5 {stars_html(int(val))}</li>"
        popup_html += "</ul>"
    else:
        popup_html += "<i>Aucune note pour le moment</i><br>"
    popup_html += "</div>"

    # compute star label (integer)
    star_label = ""
    if avg is not None:
        star_label = f"{round(avg)}/5 <span style='color:#f4c542;'>★</span>"

    # truncate the name if too long
    display_name = safe_nom if len(safe_nom) <= 15 else safe_nom[:15] + "…"

    # determine name color based on average rating
    if avg is None:
        name_color = "#555"  # default gray
    elif avg >= 4.0:
        name_color = "green"
    elif avg >= 2.5:
        name_color = "blue"
    else:
        name_color = "red"

    # then use name_color in the icon HTML
    icon_html = f"""
    <div style="text-align:center;">
    <div style="
        display:inline-flex;
        flex-direction:column;
        align-items:center;
        padding:2px 4px;
        border-radius:10px;
        background:rgba(255,255,255,0.9);
        box-shadow:0 1px 3px rgba(0,0,0,0.25);
        gap:2px;
        white-space:nowrap;
    ">
        <div style="font-size:20px; line-height:20px;">{emoji}</div>
        <div style="font-size:10px; color:{name_color}; line-height:12px;">{display_name}</div>
        <div style="font-size:12px; color:#555; line-height:14px;">{star_label}</div>
    </div>
    </div>
    """





    icon = folium.DivIcon(html=icon_html)

    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=folium.Popup(popup_html, max_width=300),
        icon=icon
    ).add_to(m)

# Afficher la carte et récupérer les clics (plein width)
map_output = st_folium(m, height=700, width="100%")

# -----------------------------
# Ajout d'un restaurant en cliquant sur la carte (formulaire dans la sidebar)
# -----------------------------
if map_output and map_output.get("last_clicked"):
    lat = map_output["last_clicked"]["lat"]
    lon = map_output["last_clicked"]["lng"]

    st.sidebar.header("➕ Ajouter un restaurant")
    st.sidebar.success(f"Position sélectionnée : {lat:.5f}, {lon:.5f}")

    nom = st.sidebar.text_input("Nom du restaurant", key="new_nom")
    liste_genres = [
        "Japonais",
        "Italien",
        "Pizza",
        "Burger",
        "Mexicain",
        "Indien",
        "Healthy",
        "Pâtes",
        "Chinois",
        "Asiatique",
        "Bar / Pub",
        "Café",
        "Autre"
    ]

    # Instead of a selectbox, use text_input
    type_ = st.sidebar.text_input(
        "Type de cuisine (ex : Japonais, Pizza, etc.)",
        key="new_type"
    )
    # Optionnel : première note par la personne qui ajoute
    add_your_note = st.sidebar.checkbox("Je veux ajouter ma note maintenant", value=False, key="add_note_cb")
    user_note = 4
    user_name_new = ""
    if add_your_note:
        user_name_new = st.sidebar.text_input("Ton prénom (pour la note)", key="new_user_name")
        user_note = st.sidebar.slider("Ta note (étoiles)", 1, 5, 4, key="new_user_note")

    if st.sidebar.button("Ajouter à la carte", key="add_button"):
        if not nom.strip():
            st.sidebar.error("Indique le nom du restaurant.")
        else:
            new_id = str(uuid.uuid4())
            ratings_dict = {}
            if add_your_note and user_name_new.strip():
                ratings_dict[user_name_new.strip()] = int(user_note)
            new_row = {
                "id": new_id,
                "nom": nom.strip(),
                "lat": lat,
                "lon": lon,
                "type": type_.strip(),
                "ratings": json.dumps(ratings_dict, ensure_ascii=False)
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_csv_github(API_URL_CSV, df, message="Ajout/modification de restaurant")
            st.sidebar.success(f"{nom} ajouté !")
            st.rerun()



