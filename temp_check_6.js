            window.addEventListener('load', async function () {
                console.log("DEBUG: Kiosk Script Starting...");
                const debugBanner = document.getElementById('debug-banner');
                if (debugBanner) debugBanner.innerText += " JS Started...";
                /* ---------- Elements ---------- */
                const kioskCard = document.getElementById('kioskCard');
                const camera = document.getElementById('camera');
                const bboxCanvas = document.getElementById('bboxCanvas');
                const bboxCtx = bboxCanvas.getContext('2d');
                const canvas = document.getElementById('capture_canvas');
                const ctx = canvas.getContext('2d');
                const empInput = document.getElementById('employee_id');
                const captureBtn = document.getElementById('capture_btn');
                const previewBtn = document.getElementById('preview_toggle');
                const imgPreview = document.getElementById('imgPreview');
                const resultBox = document.getElementById('resultBox');
                const resultLeft = document.getElementById('resultLeft');
                const resultRight = document.getElementById('resultRight');
                const debug = document.getElementById('debug');
                const inoutBadge = document.getElementById('inoutBadge');
                const cameraBg = document.getElementById('cameraBg');
                const historyRows = document.getElementById('historyRows');

                const feature_sound = document.getElementById('feature_sound');
                const feature_vibrate = document.getElementById('feature_vibrate');
                const feature_facepct = document.getElementById('feature_facepct');
                const feature_autocapture = document.getElementById('feature_autocapture');
                const feature_colormode = document.getElementById('feature_colormode');

                const colorA = document.getElementById('colorA');
                const colorB = document.getElementById('colorB');
                const btnA = document.getElementById('btnA');
                const btnB = document.getElementById('btnB');
                const resetTheme = document.getElementById('resetTheme');
                const themeSaved = document.getElementById('themeSaved');
                const modelStatus = document.getElementById('modelStatus');

                cameraBg.style.backgroundImage = "url('/files/0c261b40-99c5-4c9d-9a56-a9a8707f309e_image.png')";

                /* ---------- FETCH WRAPPER (REPLACES frappe.call) ---------- */
                async function callURL(method, args = {}) {
                    // Build query params
                    const params = new URLSearchParams();
                    for (const [key, value] of Object.entries(args)) {
                        params.append(key, value);
                    }

                    try {
                        const res = await fetch(`/api/method/${method}?${params.toString()}`, {
                            method: 'GET', // or POST if needed, but GET is simpler for reads
                            headers: {
                                'Accept': 'application/json',
                                'X-Frappe-CSRF-Token': frappe.csrf_token || ''
                            }
                        });
                        const data = await res.json();
                        return data;
                    } catch (e) {
                        console.error("API Call Error", e);
                        return { message: null };
                    }
                }

                // POST version for writes
                async function callPost(method, args = {}) {
                    const formData = new FormData();
                    for (const [key, value] of Object.entries(args)) {
                        formData.append(key, value);
                    }

                    try {
                        const res = await fetch(`/api/method/${method}`, {
                            method: 'POST',
                            headers: {
                                'X-Frappe-CSRF-Token': frappe.csrf_token || ''
                            },
                            body: formData
                        });
                        const data = await res.json();
                        return data;
                    } catch (e) {
                        console.error("API Post Error", e);
                        return { message: null };
                    }
                }

                /* ---------- Backend Settings ---------- */
                const kioskFlags = {
                    sound: false,
                    vibration: false,
                    showFacePercentage: false,
                    colourMode: false
                };

                async function loadKioskSettings() {
                    try {
                        const data = await callURL("smart_attendance.smart_attendance.api.custom_page_handler.get_kiosk_settings");
                        if (!data.message) return;
                        const s = data.message.settings;

                        // Apply theme colors from backend
                        document.documentElement.style.setProperty("--aurora-a", s.theme.aurora_a);
                        document.documentElement.style.setProperty("--aurora-b", s.theme.aurora_b);
                        document.documentElement.style.setProperty("--button-a", s.theme.button_a);
                        document.documentElement.style.setProperty("--button-b", s.theme.button_b);

                        // Update color pickers
                        colorA.value = s.theme.aurora_a;
                        colorB.value = s.theme.aurora_b;
                        btnA.value = s.theme.button_a;
                        btnB.value = s.theme.button_b;

                        // Apply feature flags
                        kioskFlags.sound = !!s.features.sound;
                        kioskFlags.vibration = !!s.features.vibration;
                        kioskFlags.showFacePercentage = !!s.features.show_face_percentage;
                        kioskFlags.colourMode = !!s.advanced.colour_mode;

                        // Update UI toggles
                        feature_sound.checked = kioskFlags.sound;
                        feature_vibrate.checked = kioskFlags.vibration;
                        feature_facepct.checked = kioskFlags.showFacePercentage;
                        feature_colormode.checked = kioskFlags.colourMode;

                        // Apply color mode
                        document.body.classList.toggle("light-mode", kioskFlags.colourMode);

                        // Apply theme
                        applyTheme(colorA.value, colorB.value, btnA.value, btnB.value);
                    } catch (e) {
                        console.error("Failed to load kiosk settings:", e);
                    }
                }



                // /* ---------- Theme ---------- */
                function applyTheme(cA, cB, bA, bB) {
                    document.documentElement.style.setProperty('--aurora-a', cA);
                    document.documentElement.style.setProperty('--aurora-b', cB);
                    document.documentElement.style.setProperty('--button-a', bA);
                    document.documentElement.style.setProperty('--button-b', bB);
                    document.documentElement.style.setProperty('--accent-gradient', `linear-gradient(90deg, ${bA}, ${bB})`);

                    // Update capture button background
                    document.querySelectorAll('.capture-btn').forEach(el => el.style.background = `linear-gradient(90deg, ${bA}, ${bB})`);

                    // Update IN/OUT button backgrounds
                    document.querySelectorAll('.in-btn, .out-btn').forEach(el => el.style.background = `linear-gradient(90deg, ${bA}, ${bB})`);
                }


                /* ---------- Color Mode Toggle ---------- */
                feature_colormode.addEventListener('change', function () {
                    kioskFlags.colourMode = this.checked;
                    document.body.classList.toggle("light-mode", kioskFlags.colourMode);
                });

                /* ---------- Audio ---------- */
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                const audioCtx = AudioCtx ? new AudioCtx() : null;
                function playTone(freq, dur = 120, type = 'sine', gain = 0.12) { if (!audioCtx) return; const o = audioCtx.createOscillator(), g = audioCtx.createGain(); o.type = type; o.frequency.value = freq; g.gain.value = 0; o.connect(g); g.connect(audioCtx.destination); const now = audioCtx.currentTime; g.gain.linearRampToValueAtTime(gain, now + 0.01); o.start(now); g.gain.exponentialRampToValueAtTime(0.0001, now + dur / 1000); o.stop(now + dur / 1000 + 0.02); }
                function playSuccessTone(profile) { if (!audioCtx || !feature_sound.checked) return; if (profile === 'soft') { playTone(880, 140, 'sine', 0.12); setTimeout(() => playTone(1320, 110, 'sine', 0.08), 140); } else if (profile === 'arcade') { playTone(1040, 80, 'square', 0.14); setTimeout(() => playTone(760, 90, 'square', 0.12), 90); } else playTone(900, 90, 'sine', 0.12); }
                function playFailTone(profile) { if (!audioCtx || !feature_sound.checked) return; if (profile === 'soft') { playTone(300, 220, 'sawtooth', 0.16); setTimeout(() => playTone(220, 130, 'sawtooth', 0.12), 160); } else if (profile === 'arcade') { playTone(220, 200, 'sawtooth', 0.18); setTimeout(() => playTone(160, 160, 'sawtooth', 0.12), 140); } else playTone(220, 180, 'sine', 0.14); }

                /* ---------- Vibration & TTS ---------- */
                function doVibrate(ok = true) { if (!feature_vibrate.checked) return; if (!('vibrate' in navigator)) return; if (ok) navigator.vibrate([30, 60]); else navigator.vibrate([160, 80, 60]); }
                function speak(text) { try { if (!('speechSynthesis' in window)) return; const u = new SpeechSynthesisUtterance(text); u.lang = 'en-IN'; speechSynthesis.speak(u); } catch (e) { console.warn(e); } }

                /* ---------- 3D notify ---------- */
                function show3DNotify(type, text) {
                    const box = document.getElementById('notify3d');
                    box.className = `notify3d ${type}`;
                    box.innerHTML = text;
                    box.style.opacity = '1';
                    box.classList.remove('hidden');
                    if (type === 'in') { playSuccessTone('soft'); doVibrate(true); }
                    else if (type === 'out') { playSuccessTone('arcade'); doVibrate(true); }
                    else if (type === 'error') { playFailTone('soft'); doVibrate(false); }
                    setTimeout(() => { box.classList.add('hidden'); box.style.opacity = '0'; }, 2600);
                }

                /* ---------- Card tilt ---------- */
                function onMove(e) { const bounds = kioskCard.getBoundingClientRect(); const x = (e.clientX - bounds.left) / bounds.width - 0.5; const y = (e.clientY - bounds.top) / bounds.height - 0.5; const rotX = (-y) * 6; const rotY = (x) * 10; kioskCard.style.transform = `rotateX(${rotX}deg) rotateY(${rotY}deg) translateZ(6px)`; }
                function onLeave() { kioskCard.style.transform = `rotateX(0deg) rotateY(0deg) translateZ(0)`; }
                window.addEventListener('mousemove', onMove); kioskCard.addEventListener('mouseleave', onLeave);

                /* ---------- Camera ---------- */
                async function startCamera() { try { const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false }); camera.srcObject = stream; await camera.play(); resizeOverlay(); logDebug('Camera started'); } catch (e) { show3DNotify('error', 'Camera error'); logDebug('Camera error: ' + (e.message || e)); } }
                startCamera();
                function resizeOverlay() { const rect = camera.getBoundingClientRect(); bboxCanvas.width = rect.width * devicePixelRatio; bboxCanvas.height = rect.height * devicePixelRatio; bboxCanvas.style.width = rect.width + 'px'; bboxCanvas.style.height = rect.height + 'px'; bboxCtx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0); }
                window.addEventListener('resize', resizeOverlay);

                /* ---------- face-api models ---------- */
                /* ---------- face-api models ---------- */
                const modelUrl = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/';
                modelStatus.innerText = 'Loading models (CDN)…';

                let detectOptions;

                try {
                    if (typeof faceapi === 'undefined') {
                        throw new Error("face-api library not loaded from CDN");
                    }

                    await faceapi.nets.tinyFaceDetector.loadFromUri(modelUrl);
                    await faceapi.nets.faceLandmark68Net.loadFromUri(modelUrl);
                    modelStatus.innerText = 'Models loaded';
                    logDebug('face-api loaded');

                    detectOptions = new faceapi.TinyFaceDetectorOptions({
                        inputSize: 256,
                        scoreThreshold: 0.5
                    });

                } catch (e) {
                    console.error("Critical Kiosk Error:", e);
                    modelStatus.innerText = 'Error: AI Models Failed';
                    show3DNotify('error', 'AI Model Error');
                    // Stop execution of further logic that depends on faceapi
                    return;
                }

                // ---------- AI helpers ----------
                let stableSince = null;
                let detecting = true;

                async function detectionLoop() {
                    if (!detecting || camera.readyState < 2) {
                        requestAnimationFrame(detectionLoop);
                        return;
                    }

                    try {
                        const dets = await faceapi
                            .detectAllFaces(camera, detectOptions)
                            .withFaceLandmarks();

                        drawDetections(dets);

                        const hint = document.getElementById("camera-hint");

                        if (!dets || dets.length === 0) {
                            hint.style.display = "block";
                            stableSince = null;
                            requestAnimationFrame(detectionLoop);
                            return;
                        }

                        // ❌ Multiple faces
                        if (dets.length > 1) {
                            hint.style.display = "block";
                            stableSince = null;
                            show3DNotify('error', '❌ Multiple faces detected');
                            requestAnimationFrame(detectionLoop);
                            return;
                        }

                        // ✅ Single face
                        hint.style.display = "block";
                        hint.innerText = "Face Detected";

                        // 🧠 Direct Auto Capture (No Liveness)
                        if (feature_autocapture.checked) {
                            handleAutoCapture(dets[0]);
                        }


                    } catch (e) {
                        console.warn('detect error', e);
                    }

                    requestAnimationFrame(detectionLoop);
                } // End detectionLoop


                /* -----------------------------------------------------------
                 *  Liveness Logic Removed
                 * ----------------------------------------------------------- */




                detectionLoop();



                function clearBoxes() { bboxCtx.clearRect(0, 0, bboxCanvas.width, bboxCanvas.height); }
                function drawDetections(dets) {
                    clearBoxes();
                    if (!dets || dets.length === 0) return;
                    const displaySize = { width: camera.clientWidth, height: camera.clientHeight };
                    const scaleX = displaySize.width / (camera.videoWidth || displaySize.width);
                    const scaleY = displaySize.height / (camera.videoHeight || displaySize.height);
                    bboxCtx.lineWidth = 3;
                    dets.forEach(d => {
                        const box = d.detection.box;
                        const x = box.x * scaleX;
                        const y = box.y * scaleY;
                        const w = box.width * scaleX;
                        const h = box.height * scaleY;
                        bboxCtx.strokeStyle = 'rgba(0,255,150,0.9)';
                        bboxCtx.fillStyle = 'rgba(0,255,150,0.08)';
                        roundRect(bboxCtx, x, y, w, h, 8);
                        const score = Math.round(d.detection.score * 100) / 100;
                        bboxCtx.font = '14px Inter, Arial';
                        bboxCtx.fillStyle = 'rgba(0,0,0,0.7)';
                        bboxCtx.fillRect(x, y - 22, 110, 20);
                        bboxCtx.fillStyle = 'rgba(255,255,255,0.95)';
                        const txt = feature_facepct.checked ? `face ${score}` : `face`;
                        bboxCtx.fillText(txt, x + 6, y - 7);
                    });
                }
                function roundRect(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); ctx.fill(); ctx.stroke(); }

                /* ---------- Helpers ---------- */
                function logDebug(msg) { debug.classList.remove('hidden'); debug.innerText = typeof msg === 'string' ? msg : JSON.stringify(msg, null, 2); console.log('[KIOSK]', msg); }
                function startLoading() { /* placeholder */ }
                function stopLoading() { /* placeholder */ }



                /* =========================================================
                   Employee Exists (frappe.db.exists via backend)
                  /* =========================================================
                   Employee Exists (FIXED)
                   ========================================================= */
                async function employeeExists(employee_id) {
                    if (!employee_id) return false;

                    return new Promise(async resolve => {
                        const r = await callURL("smart_attendance.smart_attendance.api.custom_checkin_employee_id.check_employee_exists", { employee_id });
                        resolve(r?.message === true);
                    });
                }



                /* ================= DAILY LOGS POPUP LOGIC ================= */
                async function fetchAndShowDailyLogs(employee_id) {
                    detecting = false; // Pause detection

                    // Update Title
                    document.querySelector('#dailyLogsModal .modal-title').innerText = `Daily Logs: ${employee_id}`;

                    // Fetch logs
                    try {
                        const logsData = await callURL("frappe.client.get_list", {
                            doctype: "Employee Checkin",
                            filters: JSON.stringify([
                                ["employee", "=", employee_id],
                                ["time", ">=", frappe.datetime.get_today() + " 00:00:00"],
                                ["time", "<=", frappe.datetime.get_today() + " 23:59:59"]
                            ]),
                            fields: JSON.stringify(["name", "log_type", "time", "employee_name"]),
                            order_by: "time desc",
                            limit_page_length: 100
                        });
                        const logs = logsData.message || [];

                        const list = document.getElementById('modalLogsList');
                        list.innerHTML = '';

                        if (logs.length === 0) {
                            list.innerHTML = '<div style="padding:14px; text-align:center; color:#64748b;">No logs found today</div>';
                            document.querySelector('#dailyLogsModal .modal-title').innerText = `Daily Logs (0)`;
                        } else {
                            // Update title with Name and Count
                            const count = logs.length;
                            const name = logs[0].employee_name || employee_id;
                            document.querySelector('#dailyLogsModal .modal-title').innerText = `Daily Logs (${count}): ${name}`;

                            logs.forEach(l => {
                                const time = l.time.split(' ')[1].substring(0, 5); // HH:mm
                                const typeClass = l.log_type === 'IN' ? 'in' : 'out';
                                list.innerHTML += `
                    <div class="modal-log-item">
                        <div style="flex:1; text-align:left;">
                            <div style="font-weight:600; font-size:15px; color:#fff;">${time}</div>
                            <div style="font-size:11px; color:#64748b;">${l.name}</div>
                        </div>
                        <span class="${typeClass}" style="font-size:15px; align-self:center;">${l.log_type}</span>
                    </div>
                `;
                            });
                        }

                        const modal = document.getElementById('dailyLogsModal');
                        modal.classList.add('active');

                    } catch (e) {
                        console.error("Error fetching logs", e);
                        // If error, just resume
                        detecting = true;
                    }

                    document.getElementById('modalOkBtn').addEventListener('click', () => {
                        document.getElementById('dailyLogsModal').classList.remove('active');

                        // ✅ Reset for the NEXT person
                        empInput.value = '';
                        inoutBadge.classList.add('hidden');
                        inoutBtn.innerText = '✅ IN'; // Default reset
                        inoutBtn.className = 'in-btn';

                        // Hide preview
                        imgPreview.classList.add('hidden');

                        // Resume detection
                        setTimeout(() => { detecting = true; stableSince = null; }, 600);
                    });
                } // End fetchAndShowDailyLogs


                /* ---------- ERPNext API helpers (frappe.call) ---------- */
                /* Get last Employee Checkin's log_type */
                async function getLastLogType(employee_id) {
                    try {
                        if (!employee_id) return null;
                        const r = await callURL("smart_attendance.smart_attendance.api.custom_checkin_employee_id.get_last_log", { employee_id });
                        return r?.message || "OUT";
                    } catch (e) { console.error('Last log error', e); return null; }
                }


                /* Create Employee Checkin using frappe.client.insert */
                // Old helpers removed



                /* =========================================================
                   FINAL markAttendance (WITH VALIDATION)
                   ========================================================= */
                async function markAttendance(employee_id, explicit_type = null, image_base64 = null) {
                    try {
                        // 1. If Employee ID is provided, validate it exists (Optional optimization)
                        if (employee_id) {
                            const exists = await employeeExists(employee_id);
                            if (!exists) {
                                show3DNotify('error', '❌ Employee not found');
                                return;
                            }
                        } else {
                            // If no Employee ID, we MUST have an image
                            if (!image_base64) {
                                show3DNotify('error', '❌ Face or ID required');
                                return;
                            }
                        }

                        // 2. Call Backend to Mark Attendance (Using Face Verification API)
                        // Use POST for marking attendance
                        const r = await callPost("smart_attendance.smart_attendance.api.verify_face", {
                            employee: employee_id || "",
                            image_base64: image_base64 || "",
                            log_type: explicit_type || "AUTO"
                        });

                        if (r.message && r.message.ok) {
                            const type = r.message.log_type;
                            const name = r.message.employee_name || r.message.employee;
                            show3DNotify(type === 'IN' ? 'in' : 'out', type === 'IN' ? `✅ IN: ${name}` : `⛔ OUT: ${name}`);

                            const detectedId = r.message.employee;

                            // ✅ Update Input
                            document.getElementById('employee_id').value = detectedId;

                            updateInOutUI(detectedId);
                            setTimeout(() => fetchAndShowDailyLogs(detectedId), 800);
                        } else {
                            show3DNotify('error', r.message?.message || '❌ Attendance Failed');
                        }

                    } catch (e) {
                        console.error(e);
                        show3DNotify('error', '❌ Network Error');
                    }
                }


                /* ---------- UI update ---------- */
                const inoutBtn = document.getElementById('inout_btn');
                async function updateInOutUI(employee_id) {
                    try {
                        const last = await getLastLogType(employee_id);
                        const next = last === 'IN' ? 'OUT' : 'IN';

                        // Button shows NEXT action
                        if (next === 'IN') {
                            inoutBtn.innerText = '✅ IN';
                            inoutBtn.className = 'in-btn';
                        } else {
                            inoutBtn.innerText = '⛔ OUT';
                            inoutBtn.className = 'out-btn';
                        }

                        // Badge shows CURRENT status (last)
                        if (last === 'IN') {
                            inoutBadge.className = 'badge in';
                            inoutBadge.innerText = 'IN';
                        } else {
                            inoutBadge.className = 'badge out';
                            inoutBadge.innerText = 'OUT';
                        }
                        inoutBadge.classList.remove('hidden');

                        // hide badge after short while
                        setTimeout(() => inoutBadge.classList.add('hidden'), 1600);
                    } catch (e) { console.error(e); }
                }




                /* ---------- Auto-capture handler ---------- */
                let lastAutoCaptureAt = 0;
                async function handleAutoCapture(detection) {
                    const now = Date.now();
                    if (now - lastAutoCaptureAt < 2800) return;
                    lastAutoCaptureAt = now;
                    await prepareCaptureCanvas();
                    ctx.drawImage(camera, 0, 0, canvas.width, canvas.height);
                    const dataUrl = canvas.toDataURL('image/jpeg', 0.86);
                    imgPreview.src = dataUrl;
                    imgPreview.classList.remove('hidden');
                    const emp = empInput.value.trim();

                    // Auto-capture: Let backend decide IN/OUT
                    // Pass image!
                    markAttendance(emp, null, dataUrl);
                }

                async function prepareCaptureCanvas() {
                    const w = camera.videoWidth || 1280;
                    const h = camera.videoHeight || 720;
                    canvas.width = w; canvas.height = h;
                }

                /* ---------- Button bindings ---------- */
                /* ---------- Button bindings ---------- */
                captureBtn.addEventListener('click', async () => {
                    const emp = empInput.value.trim();

                    ctx.drawImage(camera, 0, 0, canvas.width, canvas.height);
                    const dataUrl = canvas.toDataURL('image/jpeg', 0.86);
                    imgPreview.src = dataUrl;
                    imgPreview.classList.remove('hidden');

                    // Let backend decide
                    markAttendance(emp, null, dataUrl);
                });

                inoutBtn.addEventListener('click', async () => {
                    const emp = empInput.value.trim();
                    // For manual IN/OUT without capture, we might still want an image or at least ID.
                    // If no ID, we MUST capture.

                    let dataUrl = null;
                    if (!emp) {
                        await prepareCaptureCanvas();
                        ctx.drawImage(camera, 0, 0, canvas.width, canvas.height);
                        dataUrl = canvas.toDataURL('image/jpeg', 0.86);
                    }

                    // If we have ID, we technically don't NEED face for manual button if we trust it, 
                    // but this is a face kiosk so let's always try to send face if available or allow fallback?
                    // For now, let's assume if they click the button, they want to mark.
                    // But `mark_attendance_by_face` REQUIRES image if no ID (and even with ID it compares).
                    // So we should always capture.

                    if (!dataUrl) {
                        await prepareCaptureCanvas();
                        ctx.drawImage(camera, 0, 0, canvas.width, canvas.height);
                        dataUrl = canvas.toDataURL('image/jpeg', 0.86);
                    }

                    // Let backend decide
                    markAttendance(emp, null, dataUrl);
                });

                previewBtn.addEventListener('click', () => imgPreview.classList.toggle('hidden'));

                /* ================= HOLIDAY LIST (FINAL & CLEAN) ================= */
                /* ================= HOLIDAY LIST (FINAL & CLEAN) ================= */
                // Promoted to main scope

                // Event listener for employee input change
                empInput.addEventListener('change', function () {
                    const emp = this.value.trim();
                    if (emp) loadNext15DaysHolidays(emp);
                });

                /* ================= LOAD HOLIDAYS ================= */

                async function loadNext15DaysHolidays(employee_id = null) {
                    try {
                        const args = {};
                        if (employee_id) args.employee = employee_id;

                        const data = await callURL("smart_attendance.smart_attendance.api.fetch_next_15_days_holidays", args);
                        // console.log("Holiday API Response:", data);

                        renderNext15Days(data.message || {});
                    } catch (e) {
                        console.error("Holiday fetch error:", e);
                    }
                }

                /* ================= RENDER ================= */

                function renderNext15Days(data) {
                    const holidayBox = document.getElementById("holidayBox");
                    const holidayRange = document.getElementById("holidayRange");

                    holidayBox.innerHTML = "";
                    holidayRange.innerText = "";

                    if (!data.holidays || !data.holidays.length) {
                        holidayBox.innerHTML = "<p>No holidays</p>";
                        return;
                    }

                    holidayRange.innerText = "Next 15 Days";

                    data.holidays.forEach((h, i) => {
                        holidayBox.innerHTML += `
      <div class="holiday-item">
        <b>${i + 1}. ${h.date}</b><br>
        ${h.name}
      </div>
    `;
                    });
                }

                /* ================= INIT ================= */

                // ✅ Load holidays on page load (today → next 15 days)
                // ✅ Load holidays on page load (today → next 15 days)
                loadNext15DaysHolidays();

                /* ================= INIT ================= */



                document.addEventListener("click", function once() {
                    unlockAudio();
                    document.removeEventListener("click", once);
                });

                /* ---------- Page load updates ---------- */
                setTimeout(() => { const emp = empInput.value.trim(); if (emp) updateInOutUI(emp); }, 800);

                /* ---------- Unlock audio on first interaction ---------- */
                document.addEventListener('click', function once() {
                    try { audioCtx && audioCtx.resume && audioCtx.resume(); } catch (e) { }
                    document.removeEventListener('click', once);
                });

                /* ---------- Initial load ---------- */
                async function initKiosk() {
                    console.log("Initializing Kiosk...");
                    try {
                        await loadKioskSettings();
                    } catch (err) {
                        console.error("Error loading kiosk settings:", err);
                    }

                    try {
                        loadNext15DaysHolidays();
                    } catch (err) {
                        console.error("Error loading holidays:", err);
                    }

                    setTimeout(resizeOverlay, 600);
                }

                if (document.readyState === 'complete') {
                    initKiosk();
                } else {
                    window.addEventListener('load', initKiosk);
                }

            }
            }); // End window load

