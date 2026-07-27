// Reusable biometric capture widget.
// Renders three sources — Camera, Upload, External device (disabled) — inside any
// <div class="capture" data-modality="face|fingerprint" data-label="Face">.
// Exposes getCapture(modality).getDataUrl() -> base64 data URL (or null).

const _captures = {};

class BiometricCapture {
  constructor(root) {
    this.root = root;
    this.modality = root.dataset.modality;
    this.label = root.dataset.label || this.modality;
    this.dataUrl = null;
    this.stream = null;
    this._build();
    _captures[this.modality] = this;
  }

  _build() {
    this.root.innerHTML = `
      <div class="capture-head">${this.label}</div>
      <div class="capture-sources">
        <button type="button" data-src="camera" class="src-btn active">📷 Camera</button>
        <button type="button" data-src="upload" class="src-btn">📁 Upload</button>
        <button type="button" data-src="external" class="src-btn" disabled
                title="External device support coming soon">🔌 External device</button>
      </div>
      <div class="capture-body">
        <video class="cap-video" playsinline muted hidden></video>
        <img class="cap-preview" alt="preview" hidden>
        <input type="file" class="cap-file" accept="image/*" hidden>
        <div class="cap-controls"></div>
        <div class="cap-status muted"></div>
      </div>`;

    this.video = this.root.querySelector(".cap-video");
    this.preview = this.root.querySelector(".cap-preview");
    this.file = this.root.querySelector(".cap-file");
    this.controls = this.root.querySelector(".cap-controls");
    this.status = this.root.querySelector(".cap-status");

    this.root.querySelectorAll(".src-btn").forEach((b) => {
      b.addEventListener("click", () => this._selectSource(b.dataset.src, b));
    });
    this.file.addEventListener("change", () => this._onFile());
    this._selectSource("camera", this.root.querySelector('[data-src="camera"]'));
  }

  _selectSource(src, btn) {
    this._stopCamera();
    this.root.querySelectorAll(".src-btn").forEach((b) => b.classList.remove("active"));
    if (btn) btn.classList.add("active");
    this.controls.innerHTML = "";
    if (src === "camera") this._cameraUI();
    else if (src === "upload") this._uploadUI();
  }

  _cameraUI() {
    const start = document.createElement("button");
    start.type = "button"; start.className = "btn btn-ghost"; start.textContent = "Start camera";
    const snap = document.createElement("button");
    snap.type = "button"; snap.className = "btn"; snap.textContent = "Capture"; snap.disabled = true;
    start.onclick = () => this._startCamera(snap);
    snap.onclick = () => this._snap();
    this.controls.append(start, snap);
  }

  _uploadUI() {
    const pick = document.createElement("button");
    pick.type = "button"; pick.className = "btn btn-ghost"; pick.textContent = "Choose image";
    pick.onclick = () => this.file.click();
    this.controls.append(pick);
    this.status.textContent = "Select a face/fingerprint image file.";
  }

  async _startCamera(snap) {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      this.video.srcObject = this.stream;
      this.video.hidden = false;
      await this.video.play();
      snap.disabled = false;
      this.status.textContent = "Camera live — frame your " + this.label.toLowerCase() + ", then Capture.";
    } catch (err) {
      this.status.textContent = "Camera unavailable: " + err.message + " (try Upload).";
    }
  }

  _stopCamera() {
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = null;
    if (this.video) { this.video.srcObject = null; this.video.hidden = true; }
  }

  _snap() {
    const canvas = document.createElement("canvas");
    canvas.width = this.video.videoWidth || 320;
    canvas.height = this.video.videoHeight || 240;
    canvas.getContext("2d").drawImage(this.video, 0, 0, canvas.width, canvas.height);
    this.dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    this._showPreview("Captured from camera.");
    this._stopCamera();
  }

  _onFile() {
    const f = this.file.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => { this.dataUrl = reader.result; this._showPreview("Loaded " + f.name + "."); };
    reader.readAsDataURL(f);
  }

  _showPreview(msg) {
    this.preview.src = this.dataUrl;
    this.preview.hidden = false;
    this.status.textContent = msg;
  }

  getDataUrl() { return this.dataUrl; }
}

function getCapture(modality) { return _captures[modality]; }

// Collect captured images for the modalities a flow needs.
function captureImages(modality) {
  const out = {};
  if (modality === "face" || modality === "both") {
    const c = getCapture("face"); if (c) out.face_image = c.getDataUrl();
  }
  if (modality === "fingerprint" || modality === "both") {
    const c = getCapture("fingerprint"); if (c) out.fingerprint_image = c.getDataUrl();
  }
  return out;
}

// Show only the capture widgets relevant to the chosen modality.
function toggleCaptureWidgets(modality) {
  document.querySelectorAll(".capture").forEach((el) => {
    const show = modality === "both" || modality === el.dataset.modality;
    el.style.display = show ? "" : "none";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".capture").forEach((el) => new BiometricCapture(el));
  window.addEventListener("pagehide", () => Object.values(_captures).forEach((c) => c._stopCamera()));
});
