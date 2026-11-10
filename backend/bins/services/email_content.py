"""Alert emails in English, French and Kinyarwanda (plain text + HTML).

render_alert(alert, user, lang) -> (subject, text, html)
render_test(user, lang)         -> (subject, text, html)
"""

from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

T = {
    "en": {
        "comp": {"organic": "organic", "inorganic": "inorganic"},
        "Comp": {"organic": "Organic", "inorganic": "Inorganic"},
        "severity": {"critical": "CRITICAL", "warning": "WARNING", "info": "INFO"},
        "subject": {
            "full": "[{bin}] {Comp} compartment is FULL ({level}%)",
            "warning": "[{bin}] {Comp} compartment is almost full ({level}%)",
            "gas_high": "[{bin}] Bad smell: gas at {gas} ppm",
            "device_offline": "[{bin}] Smart bin is OFFLINE",
            "low_confidence": "[{bin}] The AI camera is often uncertain",
            "test": "Test email from Edge-AI Smart Dustbin",
        },
        "message": {
            "full": "The {comp} compartment of {bin} is full ({level}%).",
            "warning": "The {comp} compartment of {bin} is almost full ({level}%).",
            "gas_high": "The gas level in {bin} is high ({gas} ppm): organic waste is decomposing.",
            "device_offline": "{bin} has not sent any data since {since}.",
            "low_confidence": "The AI camera of {bin} was uncertain on {ratio} of the last {count} items.",
        },
        "action": {
            "full": "Please empty it as soon as possible, then press “{Comp} emptied” in the Control Panel.",
            "warning": "Plan a collection soon so it does not overflow.",
            "gas_high": "Empty and wash the organic compartment within 24 hours, even if it is not full.",
            "device_offline": "Check the power supply and the Wi-Fi of the bin.",
            "low_confidence": "Clean the camera lens, check the LED light, and retrain the AI model with the uncertain photos.",
        },
        "hello": "Hello {name},",
        "details": "Details",
        "bin": "Bin", "location": "Location", "time": "Time",
        "organic_level": "Organic level", "inorganic_level": "Inorganic level", "gas": "Gas",
        "open": "Open the dashboard",
        "test_body": "This is a test. Email alerts from your smart dustbin are working, in English.",
        "footer": "You receive this email because email alerts are turned on in Settings → Email notifications.",
    },
    "fr": {
        "comp": {"organic": "organique", "inorganic": "inorganique"},
        "Comp": {"organic": "Organique", "inorganic": "Inorganique"},
        "severity": {"critical": "CRITIQUE", "warning": "ATTENTION", "info": "INFO"},
        "subject": {
            "full": "[{bin}] Compartiment {comp} PLEIN ({level} %)",
            "warning": "[{bin}] Compartiment {comp} presque plein ({level} %)",
            "gas_high": "[{bin}] Mauvaise odeur : gaz à {gas} ppm",
            "device_offline": "[{bin}] La poubelle est HORS LIGNE",
            "low_confidence": "[{bin}] La caméra IA hésite souvent",
            "test": "E-mail de test de la poubelle intelligente Edge-AI",
        },
        "message": {
            "full": "Le compartiment {comp} de {bin} est plein ({level} %).",
            "warning": "Le compartiment {comp} de {bin} est presque plein ({level} %).",
            "gas_high": "Le niveau de gaz de {bin} est élevé ({gas} ppm) : les déchets organiques se décomposent.",
            "device_offline": "{bin} n'envoie plus de données depuis le {since}.",
            "low_confidence": "La caméra IA de {bin} a hésité sur {ratio} des {count} derniers objets.",
        },
        "action": {
            "full": "Videz-le dès que possible, puis appuyez sur « {Comp} vidé » dans le Panneau de contrôle.",
            "warning": "Prévoyez une collecte bientôt pour éviter le débordement.",
            "gas_high": "Videz et lavez le compartiment organique sous 24 heures, même s'il n'est pas plein.",
            "device_offline": "Vérifiez l'alimentation électrique et le Wi-Fi de la poubelle.",
            "low_confidence": "Nettoyez l'objectif, vérifiez l'éclairage LED et réentraînez le modèle d'IA avec les photos incertaines.",
        },
        "hello": "Bonjour {name},",
        "details": "Détails",
        "bin": "Poubelle", "location": "Emplacement", "time": "Heure",
        "organic_level": "Niveau organique", "inorganic_level": "Niveau inorganique", "gas": "Gaz",
        "open": "Ouvrir le tableau de bord",
        "test_body": "Ceci est un test. Les alertes par e-mail de votre poubelle intelligente fonctionnent, en français.",
        "footer": "Vous recevez cet e-mail car les alertes sont activées dans Paramètres → Notifications par e-mail.",
    },
    "rw": {
        "comp": {"organic": "ibibora", "inorganic": "ibitabora"},
        "Comp": {"organic": "Ibibora", "inorganic": "Ibitabora"},
        "severity": {"critical": "BIKOMEYE", "warning": "IBURIRA", "info": "AMAKURU"},
        "subject": {
            "full": "[{bin}] Igice cy'{comp} CYUZUYE ({level}%)",
            "warning": "[{bin}] Igice cy'{comp} kiri hafi kuzura ({level}%)",
            "gas_high": "[{bin}] Impumuro mbi: gaze iri kuri {gas} ppm",
            "device_offline": "[{bin}] Ikimoteri NTIKIRI ku murongo",
            "low_confidence": "[{bin}] Kamera ya AI ikunze gushidikanya",
            "test": "Ubutumwa bw'igerageza buvuye ku kimoteri cy'ubwenge Edge-AI",
        },
        "message": {
            "full": "Igice cy'{comp} cya {bin} cyuzuye ({level}%).",
            "warning": "Igice cy'{comp} cya {bin} kiri hafi kuzura ({level}%).",
            "gas_high": "Gaze iri muri {bin} iri hejuru ({gas} ppm): imyanda ibora iri kubora.",
            "device_offline": "{bin} nticyohereje amakuru kuva {since}.",
            "low_confidence": "Kamera ya AI ya {bin} yashidikanyije kuri {ratio} by'ibintu {count} biheruka.",
        },
        "action": {
            "full": "Kuramo imyanda vuba bishoboka, hanyuma ukande “{Comp}: byakuwemo” mu Igenzura.",
            "warning": "Teganya gukuramo imyanda vuba kugira ngo kitarenga.",
            "gas_high": "Kuramo imyanda kandi usukure igice cy'ibibora mu masaha 24, n'iyo cyaba kitaruzura.",
            "device_offline": "Reba amashanyarazi na Wi-Fi by'ikimoteri.",
            "low_confidence": "Sukura lensi ya kamera, reba urumuri rwa LED, wongere utoze moderi ya AI ukoresheje amafoto ashidikanywaho.",
        },
        "hello": "Muraho {name},",
        "details": "Ibisobanuro",
        "bin": "Ikimoteri", "location": "Aho giherereye", "time": "Igihe",
        "organic_level": "Urugero rw'ibibora", "inorganic_level": "Urugero rw'ibitabora", "gas": "Gaze",
        "open": "Fungura ikibaho",
        "test_body": "Iri ni igerageza. Integuza zoherezwa kuri email n'ikimoteri cyawe zirakora, mu Kinyarwanda.",
        "footer": "Wakiriye iyi email kubera ko integuza kuri email zifunguye mu Igenamiterere → Integuza kuri email.",
    },
}

COLORS = {"critical": "#b91c1c", "warning": "#b45309", "info": "#1d4ed8"}


def _topic(alert):
    """Map an alert kind to a text topic + its compartment."""
    if alert.kind.endswith("_full"):
        return "full", alert.kind.split("_")[0]
    if alert.kind.endswith("_warning"):
        return "warning", alert.kind.split("_")[0]
    return alert.kind, None


def _fmt(dt):
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M")


def _layout(lang, title, color, severity, hello, paragraphs, rows, footer):
    tx = T[lang]
    url = settings.SITE_URL
    text = "\n\n".join([hello, *paragraphs])
    if rows:
        text += "\n\n" + tx["details"] + ":\n" + "\n".join(f"  {k}: {v}" for k, v in rows)
    text += f"\n\n{tx['open']}: {url}\n\n--\n{footer}\n"

    rows_html = "".join(
        f'<tr><td style="padding:6px 12px 6px 0;color:#64748b">{escape(k)}</td>'
        f'<td style="padding:6px 0;font-weight:600">{escape(v)}</td></tr>' for k, v in rows)
    paras_html = "".join(f'<p style="margin:0 0 12px">{escape(p)}</p>' for p in paragraphs)
    html = f"""<!doctype html><html lang="{lang}"><body style="margin:0;background:#f4f7fb;font-family:Segoe UI,Arial,sans-serif;color:#0f172a">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e9f0">
<tr><td style="background:{color};color:#fff;padding:16px 24px;font-size:13px;letter-spacing:.06em;font-weight:700">{escape(severity)} · EDGE-AI SMART DUSTBIN</td></tr>
<tr><td style="padding:24px">
<h1 style="font-size:20px;margin:0 0 16px">{escape(title)}</h1>
<p style="margin:0 0 12px">{escape(hello)}</p>{paras_html}
{f'<table role="presentation" style="margin:8px 0 20px;font-size:14px">{rows_html}</table>' if rows else ''}
<a href="{escape(url)}" style="display:inline-block;background:#1d4ed8;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600">{escape(tx['open'])}</a>
</td></tr>
<tr><td style="padding:16px 24px;background:#f8fafc;color:#64748b;font-size:12px">{escape(footer)}</td></tr>
</table></td></tr></table></body></html>"""
    return text, html


def render_alert(alert, user, lang="en"):
    tx = T.get(lang, T["en"])
    lang = lang if lang in T else "en"
    bin = alert.bin
    topic, comp = _topic(alert)
    p = dict(alert.params or {})
    values = {
        "bin": bin.name,
        "comp": tx["comp"].get(comp or p.get("compartment"), ""),
        "Comp": tx["Comp"].get(comp or p.get("compartment"), ""),
        "level": p.get("level", ""),
        "gas": p.get("gas", ""),
        "count": p.get("count", ""),
        "ratio": f"{round(p['ratio'] * 100)}%" if "ratio" in p else "",
        "since": _fmt(bin.last_seen) if bin.last_seen else "",
    }
    subject = tx["subject"].get(topic, alert.message).format(**values)
    message = tx["message"].get(topic, alert.message).format(**values)
    action = tx["action"].get(topic, "").format(**values)

    latest = bin.readings.first()
    rows = [(tx["bin"], bin.name)]
    if bin.location:
        rows.append((tx["location"], bin.location))
    rows.append((tx["time"], _fmt(alert.created_at)))
    if latest:
        if latest.organic_level is not None:
            rows.append((tx["organic_level"], f"{latest.organic_level:.0f}%"))
        if latest.inorganic_level is not None:
            rows.append((tx["inorganic_level"], f"{latest.inorganic_level:.0f}%"))
        if latest.gas_ppm is not None:
            rows.append((tx["gas"], f"{latest.gas_ppm:.0f} ppm"))

    name = user.get_full_name() or user.username
    text, html = _layout(lang, subject.split("] ", 1)[-1], COLORS[alert.severity], tx["severity"][alert.severity],
                         tx["hello"].format(name=name), [message, action], rows, tx["footer"])
    return subject, text, html


def render_test(user, lang="en"):
    lang = lang if lang in T else "en"
    tx = T[lang]
    name = user.get_full_name() or user.username
    text, html = _layout(lang, tx["subject"]["test"], COLORS["info"], tx["severity"]["info"],
                         tx["hello"].format(name=name), [tx["test_body"]], [], tx["footer"])
    return tx["subject"]["test"], text, html
