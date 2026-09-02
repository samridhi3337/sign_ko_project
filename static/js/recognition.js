function showRecognitionTab(mode) {
    const alphaPane = document.getElementById("alphabetWisePane");
    const wordPane = document.getElementById("wordWisePane");
    const alphaBtn = document.getElementById("tabBtnAlphabet");
    const wordBtn = document.getElementById("tabBtnWord");

    if (mode === "word") {
        alphaPane.style.display = "none";
        wordPane.style.display = "block";
        if (alphaBtn) alphaBtn.className = "inactive-tab";
        if (wordBtn) wordBtn.className = "active-tab";
    } else {
        alphaPane.style.display = "block";
        wordPane.style.display = "none";
        if (alphaBtn) alphaBtn.className = "active-tab";
        if (wordBtn) wordBtn.className = "inactive-tab";
    }
}

function startRecognition() {
    const btn = event.currentTarget;
    if (btn) btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Camera Running...';
    fetch("/start-recognition");
}

function startAlphabetRecognition() {
    const btn = event.currentTarget;
    if (btn) btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Camera Running...';
    fetch("/start-alphabet-recognition");
}

function startWordRecognition() {
    const btn = event.currentTarget;
    if (btn) btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Camera Running...';
    fetch("/start-word-recognition");
}

// Format prediction display with confidence pill badge if present
function formatPredictionHTML(predText, confText) {
    const text = predText || "Waiting...";
    if (!confText) return text;
    return `${text} <span style="font-size:12px; font-weight:700; color:#4F46E5; background:#EEF2FF; padding:3px 10px; border-radius:12px; border:1px solid #C7D2FE; margin-left:6px; vertical-align:middle;">${confText}</span>`;
}

// 1. Alphabet Recognition Polling
setInterval(function () {
    fetch("/get_alphabet_prediction")
        .then(response => response.json())
        .then(data => {
            const letterEl = document.getElementById("alphaLetter");
            const exprEl = document.getElementById("alphaExpression");
            const wordEl = document.getElementById("alphaWord");
            const sentEl = document.getElementById("alphaSentence");

            if (letterEl) letterEl.innerHTML = formatPredictionHTML(data.letter, data.confidence);
            if (exprEl) exprEl.innerText = data.expression || "Neutral 😐";
            if (wordEl) wordEl.innerText = data.word || "Waiting...";
            if (sentEl) sentEl.innerText = data.sentence || "Waiting...";

            const container = document.getElementById("alphaExpressions");
            if (container) {
                container.innerHTML = "";
                (data.expressions || []).forEach(item => {
                    const wrapper = document.createElement("div");
                    wrapper.style.textAlign = "center";
                    wrapper.style.margin = "4px";

                    const label = document.createElement("div");
                    label.innerText = item.letter;
                    label.style.fontWeight = "bold";
                    label.style.fontSize = "13px";
                    label.style.color = "#334155";
                    wrapper.appendChild(label);

                    if (item.image) {
                        const img = document.createElement("img");
                        img.src = "/static/alphabet_expressions/" + item.image;
                        img.width = 46;
                        img.height = 46;
                        img.style.borderRadius = "50%";
                        img.style.border = "2px solid #4F46E5";
                        img.style.objectFit = "cover";
                        wrapper.appendChild(img);
                    }
                    container.appendChild(wrapper);
                });
            }
        })
        .catch(() => {});
}, 400);

let lastReferenceWord = null;

function updateWordReferenceVideo(predictedWord) {
    const video = document.getElementById("wordReferenceVideo");
    const none = document.getElementById("wordReferenceNone");
    if (!video || !none) return;

    const word = (predictedWord || "").toLowerCase().trim();
    if (!word || word === "waiting..." || word === "listening..." || word === lastReferenceWord) {
        return;
    }

    fetch("/word-clip/" + encodeURIComponent(word), { method: "HEAD" })
        .then(res => {
            lastReferenceWord = word;
            if (res.ok) {
                video.src = "/word-clip/" + encodeURIComponent(word);
                video.style.display = "inline-block";
                none.style.display = "none";
            } else {
                video.style.display = "none";
                none.style.display = "block";
                none.innerText = "No reference video for \"" + word + "\".";
            }
        })
        .catch(() => {});
}

// 2. Word-Level Recognition Polling
setInterval(function () {
    fetch("/get_word_prediction")
        .then(response => response.json())
        .then(data => {
            const predEl = document.getElementById("wordPrediction");
            const exprEl = document.getElementById("wordExpression");
            const sentEl = document.getElementById("wordSentence");

            if (predEl) predEl.innerHTML = formatPredictionHTML(data.prediction, data.confidence);
            if (exprEl) exprEl.innerText = data.expression || "Neutral 😐";
            if (sentEl) sentEl.innerText = data.sentence || "Waiting...";

            updateWordReferenceVideo(data.prediction);

            const emergencyWords = ["help", "danger", "emergency", "pain"];
            const predicted = (data.prediction || "").toLowerCase();
            const emergencyBox = document.getElementById("wordEmergencyBox");
            const emergencyWordEl = document.getElementById("wordEmergencyWord");

            if (emergencyBox && emergencyWordEl) {
                if (emergencyWords.includes(predicted)) {
                    emergencyBox.style.display = "block";
                    emergencyWordEl.innerText = data.prediction.toUpperCase();
                } else {
                    emergencyBox.style.display = "none";
                }
            }
        })
        .catch(() => {});
}, 400);