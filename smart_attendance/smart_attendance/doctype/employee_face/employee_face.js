// Copyright (c) 2025, pradip and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Face", {
    refresh(frm) {
        // Only show if not already saved or if user wants to re-enroll
        frm.add_custom_button(__("Enroll Face (Camera)"), () => {
            new FaceEnrollment(frm);
        }).addClass("btn-primary");
    },
    custom_enrolled_employee(frm) {
        new FaceEnrollment(frm);
    }
});

class FaceEnrollment {
    constructor(frm) {
        this.frm = frm;
        this.dialog = null;
        this.stream = null;
        this.videoEl = null;
        this.canvasEl = null;
        this.ctx = null;
        this.isModelLoaded = false;
        this.modelUrl = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.min.js";

        // Liveness vars
        this.lastBlink = 0;
        this.blinkCount = 0;
        this.isProcessing = false;
        this.scanActive = false;

        this.init();
    }

    async init() {
        await this.loadFaceApi();
        this.makeDialog();
    }

    async loadFaceApi() {
        if (typeof faceapi !== "undefined") return;

        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = this.modelUrl;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    makeDialog() {
        this.dialog = new frappe.ui.Dialog({
            title: __("Face Enrollment - Live Check"),
            fields: [
                {
                    fieldtype: "HTML",
                    fieldname: "cam_area",
                    options: `
                        <div class="face-enroll-wrapper" style="text-align:center; position:relative; min-height:400px; background:#000; border-radius:8px; overflow:hidden;">
                            <video id="enrollVideo" autoplay playsinline muted style="width:100%; height:100%; object-fit:cover; opacity:0.6;"></video>
                            <canvas id="enrollCanvas" style="position:absolute; top:0; left:0; width:100%; height:100%;"></canvas>
                            <div id="enrollStatus" style="position:absolute; bottom:20px; left:0; right:0; text-align:center; color:#fff; font-size:18px; font-weight:bold; text-shadow:0 2px 4px rgba(0,0,0,0.8);">Loading Models...</div>
                            <div id="enrollGuidance" style="
                                position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);
                                width:260px; height:340px; border:3px dashed rgba(255,255,255,0.5); border-radius:140px; pointer-events:none;
                            "></div>
                        </div>
                    `
                }
            ],
            primary_action_label: __("Capture Manual"),
            primary_action: () => this.capture(true)
        });

        this.dialog.onhide = () => this.stopCamera();
        this.dialog.show();

        this.$wrapper = this.dialog.fields_dict.cam_area.$wrapper;
        this.videoEl = this.$wrapper.find("#enrollVideo")[0];
        this.canvasEl = this.$wrapper.find("#enrollCanvas")[0];
        this.statusEl = this.$wrapper.find("#enrollStatus");

        this.startCamera();
    }

    async startCamera() {
        try {
            this.statusEl.text("Loading AI Models...");
            await Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri('https://raw.githubusercontent.com/vladmandic/face-api/master/model'),
                faceapi.nets.faceLandmark68Net.loadFromUri('https://raw.githubusercontent.com/vladmandic/face-api/master/model')
            ]);

            this.isModelLoaded = true;
            this.statusEl.text("Starting Camera...");

            // SHIM for getUserMedia in insecure contexts (HTTP)
            if (!navigator.mediaDevices) {
                navigator.mediaDevices = {};
            }
            if (!navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia = function (constraints) {
                    const getUserMedia = navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.getUserMedia;
                    if (!getUserMedia) {
                        return Promise.reject(new Error('Browser does not support camera (or block insecure context). Use HTTPS.'));
                    }
                    return new Promise((resolve, reject) => getUserMedia.call(navigator, constraints, resolve, reject));
                };
            }

            this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
            this.videoEl.srcObject = this.stream;

            // Force play and wait
            this.videoEl.play().catch(e => console.warn("Play error", e));

            // Setup detection loop once video is ready
            if (this.videoEl.readyState >= 2) {
                this.onVideoReady();
            } else {
                this.videoEl.onloadedmetadata = () => this.onVideoReady();
                // Fallback if event misses
                setTimeout(() => {
                    if (this.videoEl.readyState >= 2 && !this.scanActive) this.onVideoReady();
                }, 2000);
            }

        } catch (err) {
            console.error(err);
            this.statusEl.html(`<span style="color:red">Camera blocked (Insecure Context).<br>Please upload a photo instead.</span>`);
            this.showUploadUI();
        }
    }

    showUploadUI() {
        this.$wrapper.find("#enrollVideo").hide();
        this.$wrapper.find("#enrollCanvas").show(); // We will draw image here

        // Add Upload Button if not exists
        if (this.$wrapper.find("#btnUploadFace").length === 0) {
            $(`<button class="btn btn-default btn-sm" id="btnUploadFace" style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); z-index:10;">
                📁 Upload Photo
            </button>`).appendTo(this.$wrapper.find(".face-enroll-wrapper"))
                .click(() => this.$wrapper.find("#enrollFile").click());

            // Add File Input
            $(`<input type="file" id="enrollFile" accept="image/*" style="display:none;">`)
                .appendTo(this.$wrapper)
                .change((e) => this.handleFileSelect(e));
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (evt) => {
            const img = new Image();
            img.onload = async () => {
                // Draw to canvas
                this.canvasEl.width = this.videoEl.clientWidth || 640;
                this.canvasEl.height = this.videoEl.clientHeight || 480;
                this.ctx = this.canvasEl.getContext("2d");

                // Scale to fit
                const scale = Math.min(this.canvasEl.width / img.width, this.canvasEl.height / img.height);
                const w = img.width * scale;
                const h = img.height * scale;
                const x = (this.canvasEl.width - w) / 2;
                const y = (this.canvasEl.height - h) / 2;

                this.ctx.clearRect(0, 0, this.canvasEl.width, this.canvasEl.height);
                this.ctx.drawImage(img, x, y, w, h);

                // Run Detection
                this.statusEl.text("Analyzing Image...");
                const detections = await faceapi.detectAllFaces(this.canvasEl, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks();

                if (detections && detections.length > 0) {
                    const result = detections[0];
                    new faceapi.draw.DrawBox(result.detection.box, { label: "Face Detected", boxColor: "#0f0" }).draw(this.canvasEl);
                    this.statusEl.html(`<span style="color:#0f0">✅ Valid Face! Click 'Capture Manual' to Save.</span>`);
                    // We can also auto-save? Let's leave it to manual for confirmation
                } else {
                    this.statusEl.html(`<span style="color:red">❌ No Face Detected. Try another.</span>`);
                }
            };
            img.src = evt.target.result;
        };
        reader.readAsDataURL(file);
    }

    resizeCanvas() {
        if (!this.videoEl || !this.canvasEl) return;
        const dims = faceapi.matchDimensions(this.canvasEl, this.videoEl, true);
    }

    onVideoReady() {
        if (this.scanActive) return; // already started
        this.resizeCanvas();
        this.startDetectionLoop();
    }

    async startDetectionLoop() {
        this.scanActive = true;
        let detectionCount = 0;

        const loop = async () => {
            if (!this.scanActive || !this.dialog.display) return;
            if (this.videoEl.paused || this.videoEl.ended) return setTimeout(loop, 100);

            const detections = await faceapi.detectAllFaces(this.videoEl, new faceapi.TinyFaceDetectorOptions({ scoreThreshold: 0.5 })).withFaceLandmarks();

            // Clear Canvas
            this.ctx = this.canvasEl.getContext("2d");
            this.ctx.clearRect(0, 0, this.canvasEl.width, this.canvasEl.height);

            if (detections && detections.length > 0) {
                const result = detections[0];
                const dims = faceapi.matchDimensions(this.canvasEl, this.videoEl, true);
                const resized = faceapi.resizeResults(result, dims);

                // Draw Box
                const box = resized.detection.box;
                new faceapi.draw.DrawBox(box, { label: "Face Detected", boxColor: "#0f0" }).draw(this.canvasEl);

                // Auto-Capture logic (Simple)
                detectionCount++;
                if (detectionCount > 5) { // Wait for ~5 stable frames
                    this.statusEl.html(`<span style="color:#0f0; font-size:24px;">✅ Face Detected! Capturing...</span>`);
                    this.scanActive = false;
                    setTimeout(() => this.capture(false), 500);
                    return;
                } else {
                    this.statusEl.text(`Hold Steady... ${Math.floor((detectionCount / 5) * 100)}%`);
                }

            } else {
                detectionCount = 0;
                this.statusEl.text("Looking for face...");
            }

            requestAnimationFrame(loop);
        };
        loop();
    }

    getEAR(eye) {
        // EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
        // p1..p6 are points of eye
        const p1 = eye[0];
        const p2 = eye[1];
        const p3 = eye[2];
        const p4 = eye[3];
        const p5 = eye[4];
        const p6 = eye[5];

        const dist = (p1, p2) => Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2));

        const v1 = dist(p2, p6);
        const v2 = dist(p3, p5);
        const h = dist(p1, p4);

        return (v1 + v2) / (2.0 * h);
    }

    capture(manual = false) {
        this.scanActive = false;

        // Draw frame to hidden canvas
        const capCanvas = document.createElement("canvas");
        capCanvas.width = this.videoEl.videoWidth;
        capCanvas.height = this.videoEl.videoHeight;
        capCanvas.getContext("2d").drawImage(this.videoEl, 0, 0);

        // Get Base64
        const dataURL = capCanvas.toDataURL("image/jpeg", 0.9);

        this.stopCamera();
        this.dialog.hide();

        this.uploadImage(dataURL);
    }

    uploadImage(dataURL) {
        const file_name = `face_${frappe.utils.get_random(6)}.jpg`;

        // Helper to convert dataURL to Blob
        const block = dataURL.split(";");
        const contentType = block[0].split(":")[1];
        const realData = block[1].split(",")[1];
        const blob = this.b64toBlob(realData, contentType);

        let formData = new FormData();
        formData.append("file", blob, file_name);
        formData.append("is_private", 0);
        formData.append("folder", "Home");
        formData.append("doctype", this.frm.doctype);
        formData.append("docname", this.frm.docname);

        frappe.show_progress("Uploading Face", 10, 100, "Please wait...");

        // Use standard XHR for reliable file upload
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/method/upload_file");
        xhr.setRequestHeader("X-Frappe-CSRF-Token", frappe.csrf_token);

        xhr.onreadystatechange = () => {
            if (xhr.readyState === 4) {
                frappe.hide_progress();
                if (xhr.status === 200) {
                    const r = JSON.parse(xhr.responseText);
                    if (r.message) {
                        // Success
                        this.frm.set_value("face_image", r.message.file_url);
                        this.frm.save_or_update();
                        frappe.msgprint({
                            title: __('Success'),
                            indicator: 'green',
                            message: __('Face Enrolled & Saved Successfully!')
                        });
                    }
                } else {
                    // Error
                    let errorMsg = "Upload Failed";
                    try {
                        const r = JSON.parse(xhr.responseText);
                        if (r._server_messages) {
                            errorMsg = JSON.parse(r._server_messages).join("\n");
                        }
                    } catch (e) { }
                    frappe.msgprint({
                        title: __('Upload Error'),
                        indicator: 'red',
                        message: errorMsg
                    });
                }
            }
        };
        xhr.send(formData);
    }

    b64toBlob(b64Data, contentType, sliceSize = 512) {
        const byteCharacters = atob(b64Data);
        const byteArrays = [];

        for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
            const slice = byteCharacters.slice(offset, offset + sliceSize);
            const byteNumbers = new Array(slice.length);
            for (let i = 0; i < slice.length; i++) {
                byteNumbers[i] = slice.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            byteArrays.push(byteArray);
        }

        return new Blob(byteArrays, { type: contentType });
    }

    stopCamera() {
        this.scanActive = false;
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
}
