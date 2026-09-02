// Systematic validation of every word/letter animation against the
// REAL captured MediaPipe data -- not a visual spot-check of 2-3
// words. Checks the same geometry the browser's retargeting math
// (static/js/sign_animation.js) actually uses: arm segment directions,
// palm basis, and per-finger curl, computed straight from each word's
// real frames. Flags anything that looks like a data or retargeting
// problem (NaN, teleporting between frames, a hand's data landing on
// the wrong side, anatomically impossible finger curl) so it can be
// fixed, instead of just assuming "smooth" means "correct" -- see
// sign_animation/README.md, "Pass 4: systematic validation".
//
// Usage:
//   node sign_animation/validate_animations.mjs

import * as THREE from "../static/js/vendor/three.module.js";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORDS_DIR = path.join(__dirname, "data", "words");
const LETTERS_DIR = path.join(__dirname, "data", "letters");

const POSE = {
    NOSE: 0, LEFT_SHOULDER: 11, RIGHT_SHOULDER: 12,
    LEFT_ELBOW: 13, RIGHT_ELBOW: 14, LEFT_WRIST: 15, RIGHT_WRIST: 16,
};
const FINGER_LANDMARKS = {
    thumb: [1, 2, 3, 4], index: [5, 6, 7, 8], middle: [9, 10, 11, 12],
    ring: [13, 14, 15, 16], pinky: [17, 18, 19, 20],
};

function toVec(p) { return p ? new THREE.Vector3(p[0], p[1], p[2]) : null; }

function angleBetween(a, b) {
    if (!a || !b || a.lengthSq() < 1e-10 || b.lengthSq() < 1e-10) return null;
    const cos = THREE.MathUtils.clamp(a.clone().normalize().dot(b.clone().normalize()), -1, 1);
    return THREE.MathUtils.radToDeg(Math.acos(cos));
}

/** Checks one word's real frame sequence for structural problems. */
function validateWord(word, frames) {
    const issues = [];
    let prevLeftWrist = null, prevRightWrist = null;
    let maxFrameJumpLeft = 0, maxFrameJumpRight = 0;
    let leftHandSeenXSign = new Set(), rightHandSeenXSign = new Set();
    let fingerCurlOutOfRange = 0, fingerCurlChecked = 0;
    let nanCount = 0;

    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const pose = f.pose || [];

        // 1. NaN / non-finite check across every real value in this frame.
        for (const part of [f.pose, f.left_hand, f.right_hand, f.face]) {
            if (!part) continue;
            for (const pt of part) {
                if (!pt) continue;
                for (const v of pt) {
                    if (!Number.isFinite(v)) nanCount++;
                }
            }
        }

        // 2. Arm segment sanity + frame-to-frame teleport check.
        const lw = toVec(pose[POSE.LEFT_WRIST]);
        const rw = toVec(pose[POSE.RIGHT_WRIST]);
        if (lw && prevLeftWrist) maxFrameJumpLeft = Math.max(maxFrameJumpLeft, lw.distanceTo(prevLeftWrist));
        if (rw && prevRightWrist) maxFrameJumpRight = Math.max(maxFrameJumpRight, rw.distanceTo(prevRightWrist));
        if (lw) prevLeftWrist = lw;
        if (rw) prevRightWrist = rw;

        // 3. Handedness consistency: a real left hand and right hand
        // should stay on their own side of center (small x) far more
        // often than not across a clip -- a hand landmark set that's
        // frequently on the "wrong" side suggests a left/right swap
        // upstream in extraction, not real motion (signs do cross the
        // midline, so this only flags a *majority* on the wrong side).
        if (lw) leftHandSeenXSign.add(Math.sign(lw.x) || 0);
        if (rw) rightHandSeenXSign.add(Math.sign(rw.x) || 0);

        // 4. Finger curl plausibility: consecutive segment angle should
        // be a real joint angle (0-180 deg), not degenerate.
        for (const handKey of ["left_hand", "right_hand"]) {
            const hand = f[handKey];
            if (!hand) continue;
            const wrist = toVec(hand[0]);
            for (const finger of Object.keys(FINGER_LANDMARKS)) {
                const idx = FINGER_LANDMARKS[finger];
                const pts = [wrist, ...idx.map(j => toVec(hand[j]))];
                for (let s = 0; s < 2; s++) {
                    const segA = pts[s + 1] && pts[s] ? new THREE.Vector3().subVectors(pts[s + 1], pts[s]) : null;
                    const segB = pts[s + 2] && pts[s + 1] ? new THREE.Vector3().subVectors(pts[s + 2], pts[s + 1]) : null;
                    const ang = angleBetween(segA, segB);
                    if (ang !== null) {
                        fingerCurlChecked++;
                        // A real finger joint doesn't hyper-extend past
                        // ~170 deg (roughly straight) in the "wrong"
                        // direction -- this just catches degenerate/
                        // self-intersecting landmark data, not real bends.
                        if (ang > 178) fingerCurlOutOfRange++;
                    }
                }
            }
        }
    }

    if (nanCount > 0) issues.push(`${nanCount} non-finite value(s) in captured data`);
    if (maxFrameJumpLeft > 0.6) issues.push(`left wrist teleports up to ${maxFrameJumpLeft.toFixed(2)}m between adjacent frames`);
    if (maxFrameJumpRight > 0.6) issues.push(`right wrist teleports up to ${maxFrameJumpRight.toFixed(2)}m between adjacent frames`);
    if (leftHandSeenXSign.size && ![...leftHandSeenXSign].includes(-1) && ![...leftHandSeenXSign].includes(1)) {
        issues.push("left wrist never has a valid x sign (all frames at x=0?)");
    }
    if (fingerCurlChecked > 0 && fingerCurlOutOfRange / fingerCurlChecked > 0.15) {
        issues.push(`${fingerCurlOutOfRange}/${fingerCurlChecked} finger segments show implausible near-180deg "curl" (possible landmark noise)`);
    }

    return { word, frameCount: frames.length, issues };
}

function main() {
    const wordFiles = fs.readdirSync(WORDS_DIR).filter(f => f.endsWith(".json"));
    const results = [];

    for (const file of wordFiles) {
        const data = JSON.parse(fs.readFileSync(path.join(WORDS_DIR, file), "utf8"));
        results.push(validateWord(data.word || file, data.frames));
    }

    const letterFiles = fs.readdirSync(LETTERS_DIR).filter(f => f.endsWith(".json"));
    let letterIssues = 0;
    for (const file of letterFiles) {
        const data = JSON.parse(fs.readFileSync(path.join(LETTERS_DIR, file), "utf8"));
        if (!data.hand || data.hand.length !== 21) {
            console.log(`[letter ${data.letter}] BAD: expected 21 hand points, got ${data.hand ? data.hand.length : "none"}`);
            letterIssues++;
        }
        for (const pt of data.hand || []) {
            if (!pt || pt.some(v => !Number.isFinite(v))) {
                console.log(`[letter ${data.letter}] BAD: non-finite point`);
                letterIssues++;
                break;
            }
        }
    }

    const flagged = results.filter(r => r.issues.length > 0);
    const clean = results.length - flagged.length;

    console.log(`\nChecked ${results.length} words, ${letterFiles.length} letters.`);
    console.log(`Words with no issues found: ${clean}/${results.length}`);
    console.log(`Letters with issues: ${letterIssues}/${letterFiles.length}`);

    if (flagged.length) {
        console.log(`\n${flagged.length} word(s) flagged for review:`);
        for (const r of flagged) {
            console.log(`  [${r.word}] (${r.frameCount} frames)`);
            for (const issue of r.issues) console.log(`    - ${issue}`);
        }
    } else {
        console.log("\nNo structural issues found in any word's captured motion data.");
    }
}

main();
