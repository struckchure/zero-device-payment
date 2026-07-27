// Merchant collect: charge a customer by account ID; the customer captures a
// biometric (camera/upload) to authorize. Funds move customer -> merchant.

function ngn(v) {
  return "₦" + Number(v).toLocaleString("en-NG", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

async function collectPayment() {
  const box = document.getElementById("collect-result");
  const account_id = document.getElementById("account_id").value.trim();
  const amount = document.getElementById("amount").value;
  const modality = document.getElementById("modality").value;
  const images = captureImages(modality);

  if (!account_id) {
    box.className = "result bad"; box.textContent = "Enter the customer account ID."; return;
  }
  const needFace = (modality === "face" || modality === "both") && !images.face_image;
  const needFinger = (modality === "fingerprint" || modality === "both") && !images.fingerprint_image;
  if (needFace || needFinger) {
    box.className = "result bad";
    box.textContent = `Capture the customer's ${needFace ? "face" : "fingerprint"} (camera or upload).`;
    return;
  }

  box.className = "result";
  box.textContent = "Verifying biometric & collecting…";
  const res = await fetch("/api/collect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id, amount, modality, ...images }),
  });
  const data = await res.json();

  if (data.error) {
    box.classList.add("bad"); box.textContent = "Error: " + data.error; return;
  }
  box.classList.add(data.ok ? "ok" : "bad");
  box.textContent =
    `Status:    ${data.status}\n` +
    `Reference: ${data.reference}\n` +
    `Message:   ${data.message}\n` +
    `Customer:  ${data.customer}\n` +
    `Amount:    ${ngn(data.amount)}\n` +
    (data.new_balance != null ? `Merchant balance: ${ngn(data.new_balance)}` : "");

  if (data.ok) setTimeout(() => window.location.reload(), 1400);
}
