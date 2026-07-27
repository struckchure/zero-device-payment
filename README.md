# Zero-Device Biometric Payment System

A final-year project implementing a **zero-device** payment flow. A customer
authorizes a payment using **face or fingerprint** biometrics (or both) — no
card, phone, or dedicated terminal — and a **merchant** collects it by entering
the customer's account ID. Biometrics are captured from the browser **camera** or
an **image upload** and **compared for real** (OpenCV). Only the bank is mocked,
so the whole system runs locally with no real scanners, banks, or gateways.

Two roles:
- **Customers** enrol biometrics and pay merchants.
- **Merchants** log in and collect payments from customers by account ID; the
  customer authorizes at the point of sale with a captured biometric.

Capture sources per biometric: **Camera**, **Upload**, and **External device**
(disabled — the swap point for a real scanner/anti-spoof device).

> ⚠️ Academic prototype. Matching is a classic LBP-histogram technique (not a
> production face-recognition model) and the bank is mocked; do not use any of
> this with real financial or biometric data.

---

## Tech stack

| Layer            | Choice                                                    |
|------------------|-----------------------------------------------------------|
| Backend / API    | Python + Flask (REST + server-rendered pages)             |
| Frontend         | HTML + CSS + vanilla JS (fetch-based, webcam + upload capture) |
| Database         | SQLite via SQLAlchemy                                      |
| Matching         | OpenCV: Haar face detection + Local Binary Pattern (LBP) histograms, compared by histogram intersection |
| Secrets          | `werkzeug.security` password hashing; `cryptography` (Fernet) for biometric templates |

Default currency is **NGN (₦)**.

---

## Architecture

```
app/
├── __init__.py          # app factory + session/auth helpers
├── config.py            # config & secrets from .env
├── extensions.py        # SQLAlchemy instance
├── biometrics_engine.py # REAL matching: face detect + LBP histograms + compare
├── models.py            # User, Merchant, BankAccount, BiometricTemplate,
│                        #   Transaction, AuthAttempt, SystemLog
├── mocks/               # capture/matching services + the mocked bank
│   ├── interfaces.py    #   abstract boundary (extract / match / bank)
│   ├── camera.py        #   OpenCV face service (detect + LBP)
│   ├── fingerprint.py   #   OpenCV fingerprint service (LBP)
│   ├── liveness.py      #   content-based liveness/quality check
│   └── bank.py          #   mock bank / payment gateway (balances in DB)
├── services/            # business logic
│   ├── biometrics.py    #   Fernet encryption, enrolment, face/fingerprint/both decision
│   ├── auth.py          #   extract → match → liveness → decide → log
│   ├── payments.py      #   authenticate, then atomic bank settlement
│   └── metrics.py       #   FAR / FRR / accuracy from real template comparisons
├── routes/              # main (customer) pages, JSON API (/api),
│                        #   admin panel (/admin), merchant pages (/merchant)
├── templates/           # Jinja2 templates
└── static/              # CSS + JS (capture widget, flows)
seed.py                  # create DB + demo users/merchants (no pre-enrolment)
wsgi.py                  # `flask run` entry point
```

**Real vs mocked.** Face/fingerprint matching is real (`biometrics_engine.py`).
The camera/upload capture is real (browser). Still stubbed: the **bank**
(`mocks/bank.py`), the **external capture device** (a disabled UI option), and
**liveness** (a content/quality check stands in for true anti-spoofing). Each is
reached through an abstract class in `app/mocks/interfaces.py`, so a real bank or
device can be swapped in at `init_mocks()` with no calling-code changes.

---

## Setup & run

Requires Python 3.11+.

### Option A — `uv`

```bash
uv venv
uv pip install -r requirements.txt
cp .env.example .env          # optional: edit secrets
uv run python seed.py         # create DB + demo data
uv run flask run              # http://127.0.0.1:5000
```

### Option B — plain `venv` + `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed.py
flask run                     # FLASK_APP=wsgi.py is set in .env
```

Then open **http://127.0.0.1:5000**.

> No `.env`? The app still runs with insecure demo defaults (a Fernet key is
> derived from `SECRET_KEY`). Provide a real `.env` for anything shareable.

---

## Demo accounts (created by `seed.py`)

**Customers** (funded to ₦50,000; enrol your own biometrics after logging in):

| Username | Password      | Role  | Notes                            |
|----------|---------------|-------|----------------------------------|
| `alice`  | `Password123` | user  | balance ₦50,000                  |
| `bob`    | `Password123` | user  | balance ₦50,000                  |
| `admin`  | `Admin12345`  | admin | admin panel + metrics dashboard  |

> Biometrics are **not** pre-seeded — matching is real, so each customer enrols a
> face and/or fingerprint (camera or upload) before they can pay.

**Merchants** (log in at `/merchant/login` to collect payments):

| Username   | Password     | Business       |
|------------|--------------|----------------|
| `coffee`   | `Merchant123`| Corner Coffee  |
| `transit`  | `Merchant123`| City Transit   |
| `booknook` | `Merchant123`| BookNook       |

---

## Try it end-to-end

### 1 · Enrol (customer)
1. Log in as `alice` / `Password123` → **Biometrics**.
2. For **Face** and/or **Fingerprint**, pick a source (**Camera** to snap a
   frame, or **Upload** to choose an image file) and capture.
3. Click **Enrol captured biometrics**. The images are turned into encrypted LBP
   templates. (Face capture must contain a detectable face.)

> Tip for testing: use **Upload** with the same image file at enrol and at
> pay-time for a guaranteed match, or the webcam for a live face — the same
> person still matches, a different image does not.

### 2 · Pay (customer-initiated) ✅
1. Go to **Pay**, pick a merchant and amount, choose a **Biometric**.
2. Capture that biometric (camera/upload) and click **Authenticate & pay**.
   A real comparison runs → **APPROVED** on a match (balance drops, merchant
   credited), **AUTH_FAILED** on a non-match (no funds move).

### 3 · Collect (merchant-initiated) 🏪
1. Log in at **/merchant/login** as `coffee` / `Merchant123`.
2. Copy a customer account ID from the *Demo customer account IDs* table, enter
   an amount, choose a **Biometric**, capture the customer's biometric, and click
   **Capture biometric & collect** → funds move customer → merchant.

### Quick auth test
**Dashboard → Quick auth test** verifies a captured biometric against your
enrolled template (with scores) without making a payment.

### 📊 Performance metrics (admin)
1. Log in as `admin` / `Admin12345` → **Admin**.
2. **Compute FAR / FRR / accuracy** compares the *real* enrolled templates:
   genuine = each template against itself; impostor = across users. Enrol at
   least two users (both with the same modality) for a meaningful FAR.
3. **Matching controls** let you tune the match threshold and liveness minimum
   quality, then recompute.

---

## How authentication works

1. **Capture**: the browser sends a real image (webcam frame or uploaded file).
2. **Extract** (`biometrics_engine.py`): face images are detected (Haar cascade)
   and cropped; then a spatial **Local Binary Pattern (LBP)** histogram is built
   from the (equalised) crop. Fingerprints use the whole ridge image. This
   histogram is the encrypted template.
3. **Match**: histogram intersection between probe and enrolled template gives a
   0–1 similarity (1.0 identical, lower for different images).
4. **Liveness/quality**: the capture must actually contain a usable biometric
   with enough contrast (stands in for true anti-spoofing hardware).
5. **Decision rule** (`services/biometrics.py`) — the customer chooses which
   biometric to use:

   ```
   face        →  accept ⇔ liveness_ok AND face ≥ threshold
   fingerprint →  accept ⇔ liveness_ok AND fingerprint ≥ threshold
   both        →  accept ⇔ liveness_ok AND (w_face·face + w_fp·fingerprint) ≥ threshold
   ```

   The threshold (`MATCH_THRESHOLD`, default 0.55) and fusion weights are set in
   `.env` and tunable live in the admin panel.

Every attempt is persisted to `auth_attempts`; every payment to `transactions`;
notable events to `system_logs`.

---

## Security defaults

- Passwords hashed with `werkzeug.security` (salted PBKDF2); `bcrypt` also
  available.
- Biometric templates encrypted at rest with **Fernet**; plaintext embeddings
  exist only in memory during matching.
- Parameterized queries via SQLAlchemy ORM (no string-built SQL).
- Hardened session cookies (HttpOnly, SameSite=Lax; set `SESSION_COOKIE_SECURE=1`
  behind HTTPS).
- Secrets and the SQLite DB are git-ignored.

## Metrics glossary

- **FAR** — False Acceptance Rate: impostors wrongly accepted / all impostors.
- **FRR** — False Rejection Rate: genuine users wrongly rejected / all genuine.
- **Accuracy** — correct decisions / all decisions.
- **Avg response time** — mean end-to-end auth latency (ms).
