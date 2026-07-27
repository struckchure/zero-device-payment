// Customer flows: standalone auth check and payment, using real captured images.

function ngn(v) {
  return "₦" + Number(v).toLocaleString("en-NG", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

function val(id) {
  const el = document.getElementById(id);
  return el ? el.value : undefined;
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return { status: res.status, data: await res.json() };
}

function missingCapture(modality, images) {
  if ((modality === "face" || modality === "both") && !images.face_image) return "face";
  if ((modality === "fingerprint" || modality === "both") && !images.fingerprint_image) return "fingerprint";
  return null;
}

// Dashboard: run a standalone authentication check with the captured biometric(s).
async function runAuth() {
  const box = document.getElementById("auth-result");
  const modality = val("auth-modality") || "face";
  const images = captureImages(modality);
  const missing = missingCapture(modality, images);
  if (missing) {
    box.className = "result bad";
    box.textContent = `Capture your ${missing} first (camera or upload).`;
    return;
  }
  box.className = "result";
  box.textContent = "Verifying…";
  const { data } = await postJSON("/api/authenticate", { modality, ...images });
  box.classList.add(data.accepted ? "ok" : "bad");
  box.textContent =
    `Result:    ${data.accepted ? "✅ ACCEPTED" : "❌ REJECTED"}\n` +
    `Biometric: ${data.modality}\n` +
    `Reason:    ${data.reason}\n` +
    `Face score:        ${data.face_score}\n` +
    `Fingerprint score: ${data.fingerprint_score}\n` +
    `Liveness passed:   ${data.liveness_passed}\n` +
    `Score:             ${data.fused_score}  (threshold ${data.threshold})\n` +
    `Response time:     ${data.response_ms} ms`;
}

// Payment page: authenticate with captured biometric(s), then settle.
async function submitPayment() {
  const box = document.getElementById("pay-result");
  const modality = val("modality") || "face";
  const images = captureImages(modality);
  const missing = missingCapture(modality, images);
  if (missing) {
    box.className = "result bad";
    box.textContent = `Capture your ${missing} first (camera or upload).`;
    return;
  }
  box.className = "result";
  box.textContent = "Authorizing payment…";

  const { data } = await postJSON("/api/pay", {
    merchant_id: val("merchant"), amount: val("amount"), modality, ...images,
  });
  if (data.error) {
    box.classList.add("bad");
    box.textContent = "Error: " + data.error;
    return;
  }
  box.classList.add(data.ok ? "ok" : "bad");
  box.textContent =
    `Status:    ${data.status}\n` +
    `Reference: ${data.reference}\n` +
    `Message:   ${data.message}\n` +
    `Merchant:  ${data.merchant}\n` +
    `Amount:    ${ngn(data.amount)}\n` +
    (data.new_balance != null ? `New balance: ${ngn(data.new_balance)}` : "");

  const bal = document.getElementById("balance");
  if (bal && data.new_balance != null) bal.textContent = ngn(data.new_balance);
}
