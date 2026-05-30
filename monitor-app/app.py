#!/usr/bin/env python3
"""
ATMAN Monitor — SaaS de surveillance de sites web
Déploiement : Render / Fly.io / Railway
"""
import json, os, time, threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MONITOR_FILE = os.path.join(BASE_DIR, "data.json")
os.makedirs(os.path.dirname(MONITOR_FILE), exist_ok=True)

# ─── Stripe (à configurer) ───
STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUB_KEY = os.environ.get("STRIPE_PUB_KEY", "pk_test_XXXXXXXX")
MONITOR_URL = os.environ.get("MONITOR_URL", "http://localhost:5051")

# Plans
PLANS = {
    "starter": {"name": "Starter", "price": 9, "sites": 3, "interval": "5min", "alerts": "WhatsApp", "history": 7},
    "pro": {"name": "Pro", "price": 29, "sites": 10, "interval": "5min", "alerts": "WhatsApp + Email", "history": 30},
    "enterprise": {"name": "Enterprise", "price": 79, "sites": 999, "interval": "1min", "alerts": "Slack + Teams + Email", "history": 90},
}


def load_data():
    if not os.path.exists(MONITOR_FILE):
        return {"sites": {}, "alerts": []}
    with open(MONITOR_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(MONITOR_FILE, "w") as f:
        json.dump(data, f, indent=2)


def check_site(data, url):
    site = data["sites"].get(url)
    if not site:
        return
    site["total_checks"] = site.get("total_checks", 0) + 1
    start = time.time()
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "ATMAN-Monitor/2.0"})
        was_up = resp.status_code < 500
        rt = round((time.time() - start) * 1000)
        code = resp.status_code
    except Exception:
        was_up, rt, code = False, 0, 0
    prev = site.get("status", "unknown")
    new = "up" if was_up else "down"
    site["status"] = new
    site["last_response"] = rt
    site["last_check"] = datetime.now().isoformat()
    last20 = site.get("last_20", [])
    last20.append(new)
    site["last_20"] = last20[-20:]
    up_count = sum(1 for c in site["last_20"] if c == "up")
    site["uptime_30d"] = round((up_count / len(site["last_20"])) * 100, 1) if site["last_20"] else 100
    if prev not in ("unknown", "") and prev != new:
        data.setdefault("alerts", []).insert(0, {
            "type": new, "url": url, "name": site.get("name", url),
            "message": f"{'✅ En ligne' if was_up else '❌ Hors ligne'} — {rt}ms (HTTP {code})",
            "time": datetime.now().isoformat(),
        })
        data["alerts"] = data["alerts"][:200]


# ─── Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
        stripe_key=STRIPE_PUB_KEY, plans=PLANS, monitor_url=MONITOR_URL)


@app.route("/api/sites", methods=["GET", "POST", "DELETE"])
def api_sites():
    data = load_data()
    if request.method == "GET":
        sites = [{**s, "url": u} for u, s in data.get("sites", {}).items()]
        return jsonify({"sites": sites, "alerts": data.get("alerts", [])[:50]})
    if request.method == "POST":
        body = request.get_json() or {}
        url = body.get("url", "").rstrip("/")
        if not url or url == "https://":
            return jsonify({"error": "URL invalide"}), 400
        if url not in data["sites"]:
            data["sites"][url] = {
                "name": body.get("name", url), "status": "unknown",
                "uptime_30d": 100, "total_checks": 0,
                "last_response": None, "last_check": None, "last_20": [],
                "added": datetime.now().isoformat(),
            }
        save_data(data)
        return jsonify({"status": "ok"})
    if request.method == "DELETE":
        body = request.get_json() or {}
        data.get("sites", {}).pop(body.get("url", ""), None)
        save_data(data)
        return jsonify({"status": "ok"})


@app.route("/api/check-all", methods=["POST"])
def api_check_all():
    data = load_data()
    for url in list(data.get("sites", {}).keys()):
        check_site(data, url)
    save_data(data)
    return jsonify({"status": "ok"})


@app.route("/api/check-one", methods=["POST"])
def api_check_one():
    body = request.get_json() or {}
    data = load_data()
    check_site(data, body.get("url", ""))
    save_data(data)
    return jsonify({"status": "ok"})


@app.route("/api/create-checkout", methods=["POST"])
def api_create_checkout():
    """Crée une session Stripe Checkout."""
    if not STRIPE_KEY:
        return jsonify({"error": "Stripe non configuré"})
    body = request.get_json() or {}
    plan_id = body.get("plan", "pro")
    plan = PLANS.get(plan_id)
    if not plan:
        return jsonify({"error": "Plan invalide"}), 400
    try:
        import stripe
        stripe.api_key = STRIPE_KEY
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": f"ATMAN Monitor - {plan['name']}"},
                    "unit_amount": plan["price"] * 100,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            success_url=f"{MONITOR_URL}/?success=1",
            cancel_url=f"{MONITOR_URL}/?cancel=1",
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """Reçoit les événements Stripe (paiements, abonnements)."""
    payload = request.get_data(as_text=True)
    sig = request.headers.get("Stripe-Signature", "")
    if not STRIPE_KEY:
        return "", 200
    try:
        import stripe
        stripe.api_key = STRIPE_KEY
        event = stripe.Webhook.construct_event(payload, sig, os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
        if event["type"] == "checkout.session.completed":
            print(f"💰 Paiement reçu: {event['data']['object']['id']}")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"Webhook error: {e}")
        return "", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    print(f"ATMAN Monitor — http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
