// Enrolment: send captured face/fingerprint images to /api/enrol.

async function submitEnrol() {
  const box = document.getElementById("enrol-result");
  const face = getCapture("face").getDataUrl();
  const finger = getCapture("fingerprint").getDataUrl();

  if (!face && !finger) {
    box.className = "result bad";
    box.textContent = "Capture a face or fingerprint first (camera or upload).";
    return;
  }

  box.className = "result";
  box.textContent = "Enrolling…";
  const res = await fetch("/api/enrol", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ face_image: face, fingerprint_image: finger }),
  });
  const data = await res.json();

  if (data.error) {
    box.classList.add("bad");
    box.textContent = "Error: " + data.error;
    return;
  }
  const ok = data.enrolled && data.enrolled.length;
  box.classList.add(ok ? "ok" : "bad");
  box.textContent =
    (ok ? `✅ Enrolled: ${data.enrolled.join(", ")}\n` : "❌ Nothing enrolled\n") +
    (data.errors && data.errors.length ? `Issues: ${data.errors.join("; ")}\n` : "") +
    `Now enrolled: ${data.enrolled_modalities.join(", ") || "none"}`;
  if (ok) setTimeout(() => window.location.reload(), 1400);
}
