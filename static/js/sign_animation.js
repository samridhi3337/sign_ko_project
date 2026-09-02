import * as THREE from "three";
import { OrbitControls } from "/static/js/vendor/controls/OrbitControls.js";
import { FBXLoader } from "/static/js/vendor/loaders/FBXLoader.js";

// ---------------------------------------------------------------
// MediaPipe topology (matches sign_animation/landmarks3d.py).
// ---------------------------------------------------------------
const POSE = {
    NOSE: 0, LEFT_SHOULDER: 11, RIGHT_SHOULDER: 12,
    LEFT_ELBOW: 13, RIGHT_ELBOW: 14, LEFT_WRIST: 15, RIGHT_WRIST: 16,
    LEFT_HIP: 23, RIGHT_HIP: 24,
};

// MediaPipe's 21-point hand landmark layout, grouped per finger
// (wrist=0, then 4 points per finger from base to tip).
const FINGER_LANDMARKS = {
    thumb: [1, 2, 3, 4],
    index: [5, 6, 7, 8],
    middle: [9, 10, 11, 12],
    ring: [13, 14, 15, 16],
    pinky: [17, 18, 19, 20],
};

// Fixed order matching sign_animation/landmarks3d.py's FACE_POINTS
// dict (Python 3.7+ preserves insertion order, and that's the order
// each frame's flat "face" array was written in).
const FACE_NAMES = [
    "nose_tip", "chin", "forehead", "left_cheek", "right_cheek",
    "left_eye_outer", "left_eye_inner", "left_eye_top", "left_eye_bottom",
    "right_eye_outer", "right_eye_inner", "right_eye_top", "right_eye_bottom",
    "left_eyebrow", "right_eyebrow",
    "mouth_top", "mouth_bottom", "mouth_left", "mouth_right",
    "left_iris", "right_iris",
];

// Neutral standing pose (hip-origin, Y-up, ~1.7 units/meters tall) --
// used between sentences, at idle, and as the body during
// fingerspelling (letter data has no body/face motion of its own, see
// build_letter_animations.py). face:null -> renderState falls back to
// NEUTRAL_FACE_METRICS.
const REST_POSE = {
    pose: {
        [POSE.NOSE]: [0, 0.75, 0.05],
        [POSE.LEFT_SHOULDER]: [-0.19, 0.52, 0], [POSE.RIGHT_SHOULDER]: [0.19, 0.52, 0],
        [POSE.LEFT_ELBOW]: [-0.22, 0.20, 0.05], [POSE.RIGHT_ELBOW]: [0.22, 0.20, 0.05],
        [POSE.LEFT_WRIST]: [-0.20, -0.05, 0.08], [POSE.RIGHT_WRIST]: [0.20, -0.05, 0.08],
        [POSE.LEFT_HIP]: [-0.12, 0, 0], [POSE.RIGHT_HIP]: [0.12, 0, 0],
    },
    left_hand: null,
    right_hand: null,
    face: null,
};

// Where a fingerspelled letter's hand shape is anchored in avatar
// space (letters have no body/position data of their own -- so we
// hold the body at REST_POSE and place the hand shape roughly where a
// raised signing hand would be).
const FINGERSPELL_ANCHOR = [0.30, 0.95, 0.20];

// Real ASL non-manual grammar (matches sign_animation/gloss.py's
// SENTENCE_TYPE -- see that module's docstring for the linguistics
// citation): yes/no questions hold RAISED eyebrows + forward head
// tilt through the whole question; WH-questions hold LOWERED/
// furrowed eyebrows + forward head tilt -- genuinely different
// markers, applied on top of (added to) each word's own real facial
// data, for the sentence's whole duration, not per-word.
const NEUTRAL_NON_MANUAL = { eyebrow: 0, headTiltDeg: 0 };
const NON_MANUAL_BY_TYPE = {
    statement: NEUTRAL_NON_MANUAL,
    yn_question: { eyebrow: 1, headTiltDeg: 8 },
    wh_question: { eyebrow: -1, headTiltDeg: 8 },
};
let currentNonManual = NEUTRAL_NON_MANUAL;

const LETTER_HOLD_MS = 500;
const BLEND_MS = 150;
const SENTENCE_PAUSE_MS = 600;

// ASL prosody "final lengthening" (matches
// sign_animation/gloss.py's PHRASE_FINAL_HOLD_MULTIPLIER -- see that
// module's docstring for the linguistics citation): the last sign in a
// sentence is held longer than the same sign mid-sentence. This only
// stretches how long the real captured motion is held/played -- never
// a different or invented handshape.
const PHRASE_FINAL_HOLD_MULTIPLIER = 1.4;

// ---------------------------------------------------------------
// Three.js scene setup
// ---------------------------------------------------------------
const container = document.getElementById("avatarCanvasWrap");

function makeBackdropTexture() {
    const c = document.createElement("canvas");
    c.width = 4; c.height = 256;
    const ctx = c.getContext("2d");
    const grad = ctx.createLinearGradient(0, 0, 0, 256);
    grad.addColorStop(0, "#e9edf3");
    grad.addColorStop(0.55, "#dde3ec");
    grad.addColorStop(1, "#c9d2de");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 4, 256);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
}

const scene = new THREE.Scene();
scene.background = makeBackdropTexture();

const camera = new THREE.PerspectiveCamera(38, container.clientWidth / container.clientHeight, 0.05, 20);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 0.5;
controls.maxDistance = 4;

scene.add(new THREE.AmbientLight(0xffffff, 0.65));
const keyLight = new THREE.DirectionalLight(0xfff3e6, 1.2);
keyLight.position.set(0.8, 1.9, 1.4);
scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(0xdce8ff, 0.5);
fillLight.position.set(-1.2, 1.2, 0.6);
scene.add(fillLight);
const rimLight = new THREE.DirectionalLight(0xffffff, 0.4);
rimLight.position.set(0, 1.6, -1.6);
scene.add(rimLight);

window.addEventListener("resize", () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
});

// ---------------------------------------------------------------
// Avatar: a real rigged/skinned humanoid mesh (static/models/avatar.glb --
// Ready Player Me's official "RPM_Template_Mesh", MIT licensed, sourced
// from github.com/readyplayerme/rpm-unity-sdk-core -- see
// sign_animation/README.md for full provenance). It has a proper
// Shoulder->Arm->ForeArm->Hand chain, 4-bone fingers, real eye bones,
// and viseme morph targets -- unlike a hand-built primitive figure,
// this deforms like an actual body.
//
// It is NOT driven by a canned animation: every frame, real captured
// MediaPipe motion (the same data the previous primitive-avatar build
// used) is retargeted onto this skeleton by ROTATING bones only (never
// repositioning them) -- the standard, robust mocap-retargeting
// technique, since a skinned mesh deforms correctly through its
// existing skin weights as long as bone rotations are reasonable.
// ---------------------------------------------------------------
const ARM_CHAINS = {
    left: ["LeftArm", "LeftForeArm"],
    right: ["RightArm", "RightForeArm"],
};
const HAND_BONE = { left: "LeftHand", right: "RightHand" };
const EYE_BONE = { left: "LeftEye", right: "RightEye" };

function fingerBoneNames(side, finger) {
    const cap = side === "left" ? "Left" : "Right";
    const fcap = finger[0].toUpperCase() + finger.slice(1);
    return [1, 2, 3, 4].map(n => `${cap}Hand${fcap}${n}`);
}

const avatar = {
    root: null,
    skinnedMesh: null,
    morphIndex: {},          // viseme/morph name -> influence array index
    bones: {},                // name -> THREE.Bone
    bind: {},                 // name -> { worldQuat: Quaternion, worldPos: Vector3 }
    ready: false,
};
// Exposed for debugging the retargeting in the browser console (e.g.
// `__debug.avatar.bones.LeftHand`) -- harmless to leave in, read-only
// convenience, not used by the app itself.
window.__debug = { avatar, THREE, scene, camera, renderer, getCurrentNonManual: () => currentNonManual };

const _tmpQuatA = new THREE.Quaternion();
const _tmpQuatB = new THREE.Quaternion();
const _tmpVecA = new THREE.Vector3();
const _tmpVecB = new THREE.Vector3();
const _tmpMat = new THREE.Matrix4();

function snapshotBind(name) {
    const bone = avatar.bones[name];
    if (!bone) return;
    const worldQuat = new THREE.Quaternion();
    const worldPos = new THREE.Vector3();
    bone.getWorldQuaternion(worldQuat);
    bone.getWorldPosition(worldPos);
    avatar.bind[name] = { worldQuat, worldPos };
}

function loadAvatar() {
    return new Promise((resolve, reject) => {
        const loader = new FBXLoader();
        loader.load(
            "/static/models/avatar_feminine.fbx",
            (root) => {
                // This FBX rig (Ready Player Me's "Feminine" animation
                // template, see sign_animation/README.md for
                // provenance) is authored in centimeters; our motion
                // data is in meters.
                root.scale.setScalar(0.01);
                scene.add(root);

                let skinnedMesh = null;
                root.traverse((obj) => {
                    if (obj.isSkinnedMesh) skinnedMesh = obj;
                });

                // Read bones from the SkinnedMesh's own skeleton, not a
                // raw scene traversal: this FBX (like some FBX exports)
                // contains duplicate-named helper nodes alongside the
                // real skinning joints, so traversal-based lookup can
                // grab the wrong node. skeleton.bones is exactly the
                // set Three.js actually uses to deform the mesh.
                if (skinnedMesh) {
                    avatar.skinnedMesh = skinnedMesh;
                    avatar.morphIndex = skinnedMesh.morphTargetDictionary || {};
                    for (const bone of skinnedMesh.skeleton.bones) {
                        avatar.bones[bone.name] = bone;
                    }
                }

                root.updateMatrixWorld(true);

                const names = [
                    ...ARM_CHAINS.left, ...ARM_CHAINS.right,
                    HAND_BONE.left, HAND_BONE.right,
                    EYE_BONE.left, EYE_BONE.right,
                    "Head", "Neck",
                ];
                for (const side of ["left", "right"]) {
                    for (const finger of Object.keys(FINGER_LANDMARKS)) {
                        names.push(...fingerBoneNames(side, finger));
                    }
                }
                for (const name of names) snapshotBind(name);

                avatar.root = root;
                avatar.ready = true;
                resolve();
            },
            undefined,
            (err) => reject(err),
        );
    });
}

function toVec(p) {
    return p ? new THREE.Vector3(p[0], p[1], p[2]) : null;
}

/** Rotates `boneName` so the direction (fromPoint -> toPoint) in OUR
 * captured-motion space matches what that same segment's direction
 * would be in the REAL MESH's own bind pose -- i.e. a world-space
 * "swing" from the mesh's actual bind direction onto our real data's
 * direction, then composed onto the mesh's actual bind orientation.
 * `childBoneName` supplies that mesh-intrinsic bind reference (its
 * own captured bind world position) -- this must be the rig's own
 * bind pose, NOT any of our own coordinate data, or the reference
 * frame is inconsistent and rendering our own "rest" data just
 * reproduces the rig's raw bind pose (e.g. a T-pose) instead of
 * actually orienting the limb. Leaves the bone at its last rotation
 * if either point is missing (no real data this frame). */
function aimBoneAt(boneName, childBoneName, fromPoint, toPoint) {
    const bone = avatar.bones[boneName];
    const bind = avatar.bind[boneName];
    if (!bone || !bind || !fromPoint || !toPoint) return;

    const childBind = childBoneName ? avatar.bind[childBoneName] : null;

    const realDir = _tmpVecA.subVectors(toPoint, fromPoint);
    if (realDir.lengthSq() < 1e-8) return;
    realDir.normalize();

    let bindDir;
    if (childBind) {
        bindDir = _tmpVecB.subVectors(childBind.worldPos, bind.worldPos);
    } else {
        const parentBind = bone.parent ? avatar.bind[bone.parent.name] : null;
        if (parentBind) {
            bindDir = _tmpVecB.subVectors(bind.worldPos, parentBind.worldPos);
        } else {
            return;
        }
    }
    if (bindDir.lengthSq() < 1e-8) return;
    bindDir.normalize();

    const deltaWorld = _tmpQuatA.setFromUnitVectors(bindDir, realDir);
    const newWorldQuat = deltaWorld.multiply(bind.worldQuat.clone());

    const parentWorldQuat = _tmpQuatB;
    bone.parent.getWorldQuaternion(parentWorldQuat);
    bone.quaternion.copy(parentWorldQuat.invert().multiply(newWorldQuat));
    bone.updateMatrixWorld(true);
}

/** Sets `boneName`'s world orientation directly to `targetWorldQuat`
 * (for bones like Hand/Head/Eye whose target comes from a computed
 * basis, not a single direction). */
function orientBoneTo(boneName, targetWorldQuat) {
    const bone = avatar.bones[boneName];
    if (!bone || !targetWorldQuat) return;

    const parentWorldQuat = _tmpQuatB;
    bone.parent.getWorldQuaternion(parentWorldQuat);
    bone.quaternion.copy(parentWorldQuat.invert().multiply(targetWorldQuat));
    bone.updateMatrixWorld(true);
}

/** Builds a world-space orientation from three real points forming a
 * rough "palm" or "face" plane: originPt is the pivot, xPt defines the
 * local +X direction, yPt defines (with xPt) the local +Y-ish plane. */
function basisFromPoints(originPt, xPt, yPt) {
    if (!originPt || !xPt || !yPt) return null;
    const right = new THREE.Vector3().subVectors(xPt, originPt);
    const up = new THREE.Vector3().subVectors(yPt, originPt);
    if (right.lengthSq() < 1e-8 || up.lengthSq() < 1e-8) return null;
    right.normalize();
    const forward = new THREE.Vector3().crossVectors(right, up).normalize();
    if (forward.lengthSq() < 1e-8) return null;
    const trueUp = new THREE.Vector3().crossVectors(forward, right).normalize();
    _tmpMat.makeBasis(right, trueUp, forward);
    return new THREE.Quaternion().setFromRotationMatrix(_tmpMat);
}

function retargetArm(side, shoulderPt, elbowPt, wristPt) {
    const [upperName, foreName] = ARM_CHAINS[side];
    aimBoneAt(upperName, foreName, shoulderPt, elbowPt);
    aimBoneAt(foreName, HAND_BONE[side], elbowPt, wristPt);
}

function resetHandToBind(side) {
    const names = [HAND_BONE[side]];
    for (const finger of Object.keys(FINGER_LANDMARKS)) names.push(...fingerBoneNames(side, finger));
    for (const name of names) {
        const bind = avatar.bind[name];
        if (bind) orientBoneTo(name, bind.worldQuat);
    }
}

function retargetHand(side, handPoints) {
    const handBone = HAND_BONE[side];
    if (!handPoints) { resetHandToBind(side); return; }

    const wrist = toVec(handPoints[0]);
    const indexMcp = toVec(handPoints[FINGER_LANDMARKS.index[0]]);
    const pinkyMcp = toVec(handPoints[FINGER_LANDMARKS.pinky[0]]);
    const middleMcp = toVec(handPoints[FINGER_LANDMARKS.middle[0]]);
    if (!wrist || !indexMcp || !pinkyMcp || !middleMcp) { resetHandToBind(side); return; }

    const xPt = side === "left" ? pinkyMcp : indexMcp;
    const xOrigin = side === "left" ? indexMcp : pinkyMcp;
    const across = new THREE.Vector3().subVectors(xPt, xOrigin);
    const target = wrist.clone().add(across);
    const q = basisFromPoints(wrist, target, middleMcp);
    if (q) orientBoneTo(handBone, q);

    for (const finger of Object.keys(FINGER_LANDMARKS)) {
        const bones = fingerBoneNames(side, finger);
        const lmIdx = FINGER_LANDMARKS[finger];
        const pts = [wrist, ...lmIdx.map(i => toVec(handPoints[i]))];
        // 4 rotatable segments per finger (bone1: MCP, bone2: PIP, bone3: DIP, bone4: TIP)
        for (let seg = 0; seg < 4; seg++) {
            const childBone = seg < 3 ? bones[seg + 1] : null;
            aimBoneAt(bones[seg], childBone, pts[seg], pts[seg + 1]);
        }
    }
}

// ---------------------------------------------------------------
// Real facial expression / head orientation / gaze, computed from
// captured face-landmark points -- not synthesized. The mesh only
// ships viseme morph targets (no discrete eyebrow/eyelid shapes), so
// eyebrows + blink use small procedural overlays parented to the real
// Head/Eye bones (inheriting their real position + rotation); gaze
// rotates the mesh's own real eye bones directly.
// ---------------------------------------------------------------
const NEUTRAL_FACE_METRICS = {
    headQuat: null, // null = leave Head bone at bind rotation
    eyebrowRaise: 0.55, eyeOpenL: 1, eyeOpenR: 1,
    mouthOpen: 0, mouthWidth: 1,
    gazeX: 0, gazeY: 0,
};

function computeFaceMetrics(faceDict) {
    if (!faceDict) return null;
    const p = (name) => faceDict[name] ? toVec(faceDict[name]) : null;

    const nose = p("nose_tip"), chin = p("chin"), forehead = p("forehead");
    const lc = p("left_cheek"), rc = p("right_cheek");
    const leo = p("left_eye_outer"), lei = p("left_eye_inner"), let_ = p("left_eye_top"), leb = p("left_eye_bottom");
    const reo = p("right_eye_outer"), rei = p("right_eye_inner"), ret_ = p("right_eye_top"), reb = p("right_eye_bottom");
    const lb = p("left_eyebrow"), rb = p("right_eyebrow");
    const mt = p("mouth_top"), mb = p("mouth_bottom"), ml = p("mouth_left"), mr = p("mouth_right");
    const li = p("left_iris"), ri = p("right_iris");

    let headQuat = null;
    if (lc && rc && forehead && chin) {
        headQuat = basisFromPoints(nose || chin, rc, forehead);
    }

    const eyeWidthL = (leo && lei) ? leo.distanceTo(lei) : 0.03;
    const eyeWidthR = (reo && rei) ? reo.distanceTo(rei) : 0.03;
    const refScale = Math.max(((eyeWidthL || 0.03) + (eyeWidthR || 0.03)) / 2, 1e-4);

    const eyebrowRaise = (lb && let_ && rb && ret_)
        ? ((lb.distanceTo(let_) + rb.distanceTo(ret_)) / 2) / refScale
        : NEUTRAL_FACE_METRICS.eyebrowRaise;

    const eyeOpenL = (let_ && leb) ? THREE.MathUtils.clamp((let_.distanceTo(leb) / refScale) * 2.2, 0.05, 1.4) : 1;
    const eyeOpenR = (ret_ && reb) ? THREE.MathUtils.clamp((ret_.distanceTo(reb) / refScale) * 2.2, 0.05, 1.4) : 1;

    const mouthOpen = (mt && mb) ? THREE.MathUtils.clamp(mt.distanceTo(mb) / refScale, 0, 2) : 0;
    const mouthWidth = (ml && mr) ? THREE.MathUtils.clamp((ml.distanceTo(mr) / refScale) / 2.2, 0.6, 1.6) : 1;

    function gazeFor(iris, outer, inner, top, bottom) {
        if (!iris || !outer || !inner || !top || !bottom) return null;
        const cx = (outer.x + inner.x) / 2, cy = (top.y + bottom.y) / 2;
        const w = Math.abs(outer.x - inner.x) || 0.01, h = Math.abs(top.y - bottom.y) || 0.01;
        return {
            x: THREE.MathUtils.clamp((iris.x - cx) / (w / 2), -1, 1),
            y: THREE.MathUtils.clamp((iris.y - cy) / (h / 2), -1, 1),
        };
    }
    const gL = gazeFor(li, leo, lei, let_, leb);
    const gR = gazeFor(ri, reo, rei, ret_, reb);
    const gazeX = gL && gR ? (gL.x + gR.x) / 2 : (gL ? gL.x : (gR ? gR.x : 0));
    const gazeY = gL && gR ? (gL.y + gR.y) / 2 : (gL ? gL.y : (gR ? gR.y : 0));

    return { headQuat, eyebrowRaise, eyeOpenL, eyeOpenR, mouthOpen, mouthWidth, gazeX, gazeY };
}

// -- Procedural eyebrow + blink + mouth overlays (parented to real
// bones once the avatar loads -- see attachFaceOverlays()). The
// "Feminine.fbx" rig ships no face morph targets at all (confirmed by
// inspection -- see sign_animation/README.md), so mouth movement is
// procedural here too, not just eyebrows/blink. --
const browMat = new THREE.MeshStandardMaterial({ color: 0x3a2a20, roughness: 0.5 });
const lidMat = new THREE.MeshStandardMaterial({ color: 0xead9c4, roughness: 0.6 });
const mouthMat = new THREE.MeshStandardMaterial({ color: 0x8a4a49, roughness: 0.6 });
let leftBrow, rightBrow, leftLid, rightLid, mouthMesh;

function attachFaceOverlays() {
    const head = avatar.bones["Head"];
    if (!head) return;

    leftBrow = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.008, 0.012), browMat);
    leftBrow.position.set(-0.032, 0.075, 0.095);
    head.add(leftBrow);

    rightBrow = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.008, 0.012), browMat);
    rightBrow.position.set(0.032, 0.075, 0.095);
    head.add(rightBrow);

    mouthMesh = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.012, 0.02), mouthMat);
    mouthMesh.position.set(0, -0.06, 0.093);
    head.add(mouthMesh);

    const leftEyeBone = avatar.bones[EYE_BONE.left];
    const rightEyeBone = avatar.bones[EYE_BONE.right];

    if (leftEyeBone) {
        leftLid = new THREE.Mesh(new THREE.SphereGeometry(0.014, 10, 10, 0, Math.PI * 2, 0, Math.PI / 2), lidMat);
        leftLid.rotation.x = Math.PI;
        leftLid.visible = false;
        leftEyeBone.add(leftLid);
    }
    if (rightEyeBone) {
        rightLid = new THREE.Mesh(new THREE.SphereGeometry(0.014, 10, 10, 0, Math.PI * 2, 0, Math.PI / 2), lidMat);
        rightLid.rotation.x = Math.PI;
        rightLid.visible = false;
        rightEyeBone.add(rightLid);
    }
}

function applyFaceMetrics(m) {
    // Real per-word head orientation, or the mesh's own bind orientation
    // when no per-frame face data is available (letters/rest -- NOT
    // world identity, which would snap the head to face the wrong way
    // on any rig whose bind pose isn't itself axis-aligned), with the
    // sentence's ASL non-manual head tilt (see NON_MANUAL_BY_TYPE)
    // layered on top as a local forward pitch -- a real grammatical
    // marker held for the whole question, not just cosmetic tilt.
    const headBind = avatar.bind["Head"];
    const baseHeadQuat = m.headQuat ? m.headQuat.clone() : (headBind ? headBind.worldQuat.clone() : null);
    if (baseHeadQuat) {
        if (currentNonManual.headTiltDeg) {
            const tiltQuat = new THREE.Quaternion().setFromAxisAngle(
                new THREE.Vector3(1, 0, 0), THREE.MathUtils.degToRad(currentNonManual.headTiltDeg),
            );
            baseHeadQuat.multiply(tiltQuat);
        }
        orientBoneTo("Head", baseHeadQuat);
    }

    // Real per-word eyebrow position, with the sentence's non-manual
    // eyebrow marker (raised for yes/no questions, furrowed for WH
    // questions) added on top.
    const browOffset = (m.eyebrowRaise - NEUTRAL_FACE_METRICS.eyebrowRaise) * 0.05
        + currentNonManual.eyebrow * 0.018;
    if (leftBrow) leftBrow.position.y = 0.075 + browOffset;
    if (rightBrow) rightBrow.position.y = 0.075 + browOffset;

    if (leftLid) { leftLid.visible = m.eyeOpenL < 0.85; }
    if (rightLid) { rightLid.visible = m.eyeOpenR < 0.85; }

    const eyeYaw = THREE.MathUtils.clamp(m.gazeX, -1, 1) * 0.35;
    const eyePitch = THREE.MathUtils.clamp(-m.gazeY, -1, 1) * 0.25;
    const gazeEuler = new THREE.Euler(eyePitch, eyeYaw, 0, "YXZ");
    const gazeLocalQuat = new THREE.Quaternion().setFromEuler(gazeEuler);

    for (const side of ["left", "right"]) {
        const bone = avatar.bones[EYE_BONE[side]];
        const bind = avatar.bind[EYE_BONE[side]];
        if (!bone || !bind) continue;
        const parentWorldQuat = _tmpQuatB;
        bone.parent.getWorldQuaternion(parentWorldQuat);
        const bindLocal = parentWorldQuat.clone().invert().multiply(bind.worldQuat);
        bone.quaternion.copy(bindLocal.multiply(gazeLocalQuat));
    }

    if (mouthMesh) {
        mouthMesh.scale.set(m.mouthWidth, Math.max(0.15, m.mouthOpen * 2.2), 1);
    }

    // Kept as a fallback for any future avatar asset that DOES ship
    // viseme morph targets (this one doesn't -- see attachFaceOverlays).
    if (avatar.skinnedMesh && avatar.skinnedMesh.morphTargetInfluences) {
        const infl = avatar.skinnedMesh.morphTargetInfluences;
        const idx = avatar.morphIndex;
        for (const key in idx) infl[idx[key]] = 0;
        if (idx["viseme_aa"] !== undefined) infl[idx["viseme_aa"]] = THREE.MathUtils.clamp(m.mouthOpen * 0.8, 0, 1);
        if (idx["viseme_E"] !== undefined) infl[idx["viseme_E"]] = THREE.MathUtils.clamp((m.mouthWidth - 1) * 1.2, 0, 1);
    }
}

/** Renders one interpolated "pose state" (see lerpState/playWord) by
 * retargeting it onto the real avatar skeleton. */
function renderState(state) {
    if (!avatar.ready) return;

    const pose = {};
    for (const [idx, p] of Object.entries(state.pose || {})) pose[idx] = toVec(p);

    // When fingerspelling letters (state.right_hand present, state.left_hand null),
    // position right elbow and wrist to align cleanly with FINGERSPELL_ANCHOR
    if (state.right_hand && !state.left_hand && pose[POSE.RIGHT_SHOULDER]) {
        pose[POSE.RIGHT_ELBOW] = new THREE.Vector3(0.32, 0.65, 0.15);
        pose[POSE.RIGHT_WRIST] = new THREE.Vector3(FINGERSPELL_ANCHOR[0], FINGERSPELL_ANCHOR[1], FINGERSPELL_ANCHOR[2]);
    }

    retargetArm("left", pose[POSE.LEFT_SHOULDER], pose[POSE.LEFT_ELBOW], pose[POSE.LEFT_WRIST]);
    retargetArm("right", pose[POSE.RIGHT_SHOULDER], pose[POSE.RIGHT_ELBOW], pose[POSE.RIGHT_WRIST]);

    retargetHand("left", state.left_hand);
    retargetHand("right", state.right_hand);

    const faceDict = state.face && !Array.isArray(state.face) ? state.face : null;
    const metrics = computeFaceMetrics(faceDict) || NEUTRAL_FACE_METRICS;
    applyFaceMetrics(metrics);
}

// ---------------------------------------------------------------
// Data loading + gap-filling
// ---------------------------------------------------------------
async function fetchWordAnimation(word) {
    const res = await fetch(`/api/sign-animation/word/${encodeURIComponent(word)}`);
    if (!res.ok) return null;
    const data = await res.json();
    fillGaps(data.frames);
    return data; // {fps, frames: [{pose,left_hand,right_hand,face}, ...]}
}

async function fetchLetterAnimation(letter) {
    const res = await fetch(`/api/sign-animation/letter/${encodeURIComponent(letter)}`);
    if (!res.ok) return null;
    return res.json(); // {letter, hand: [[x,y,z], ...]}
}

// Real professional motion-capture clips (Xsens suit + finger-tracking
// gloves -- see README "Pass 6") from the Studio Galt Sign Language
// Mocap Archive (CC0). Their Mixamo-mapped FBX exports use bone names
// that match this project's avatar rig 1:1 except for a "mixamorig1:"
// style prefix and one non-humanoid helper node (Locator_Root) --
// stripping the prefix and dropping any track with no matching bone
// on OUR avatar is enough to retarget the clip directly by name, no
// point-cloud math needed (unlike this project's own WLASL-derived
// word data).
async function fetchMocapClip(word) {
    try {
        const res = await fetch(`/api/sign-animation/mocap/${encodeURIComponent(word)}`);
        if (!res.ok) return null;
        const arrayBuffer = await res.arrayBuffer();
        const loader = new FBXLoader();
        const obj = loader.parse(arrayBuffer, "");
        const rawClip = obj.animations[0];
        if (!rawClip) return null;

        const tracks = [];
        for (const t of rawClip.tracks) {
            const dot = t.name.indexOf(".");
            if (dot < 0) continue;
            const nodeName = t.name.slice(0, dot);
            const prop = t.name.slice(dot);
            const stripped = nodeName.replace(/^mixamorig1?:?/, "");
            if (!avatar.bones[stripped]) continue; // e.g. Locator_Root
            t.name = stripped + prop;
            tracks.push(t);
        }
        if (!tracks.length) return null;

        return new THREE.AnimationClip(word, rawClip.duration, tracks);
    } catch (e) {
        console.warn(`Mocap clip fetch/parse failed for "${word}", falling back:`, e);
        return null;
    }
}

/** Forward/back-fills any frame where a part wasn't detected, so the
 * avatar never suddenly vanishes/glitches mid-clip. */
function fillGaps(frames) {
    for (const key of ["pose", "left_hand", "right_hand", "face"]) {
        let last = null;
        for (const f of frames) {
            if (f[key]) last = f[key]; else if (last) f[key] = last;
        }
        last = null;
        for (let i = frames.length - 1; i >= 0; i--) {
            if (frames[i][key]) last = frames[i][key]; else if (last) frames[i][key] = last;
        }
    }
}

function poseArrayToDict(poseArray) {
    const out = {};
    for (const idx of Object.values(POSE)) {
        if (poseArray && poseArray[idx]) out[idx] = poseArray[idx];
    }
    return out;
}

function faceArrayToDict(faceArray) {
    if (!faceArray) return null;
    const out = {};
    FACE_NAMES.forEach((name, i) => { if (faceArray[i]) out[name] = faceArray[i]; });
    return out;
}

// ---------------------------------------------------------------
// Building the playback queue from gloss tokens
// ---------------------------------------------------------------
async function buildPlaybackQueue(sentences) {
    // Phase 1: lay out the queue shape (order matters) with a fetch
    // Promise per item, all issued together -- much faster to load
    // than awaiting each network request one at a time.
    const plan = [];

    for (let s = 0; s < sentences.length; s++) {
        if (s > 0) plan.push({ kind: "pause", ms: SENTENCE_PAUSE_MS, nonManual: NEUTRAL_NON_MANUAL });

        const nonManual = NON_MANUAL_BY_TYPE[sentences[s].type] || NEUTRAL_NON_MANUAL;

        for (const token of sentences[s].tokens) {
            const holdMultiplier = token.phrase_final ? PHRASE_FINAL_HOLD_MULTIPLIER : 1;
            if (token.type === "word" && token.mocap) {
                plan.push({ kind: "mocapWord", token, nonManual, holdMultiplier, promise: fetchMocapClip(token.text) });
            } else if (token.type === "word") {
                plan.push({ kind: "word", token, nonManual, holdMultiplier, promise: fetchWordAnimation(token.text) });
            } else if (token.type === "fingerspell") {
                const letters = token.text.toUpperCase();
                for (let li = 0; li < letters.length; li++) {
                    // Only the sentence's actual last letter gets the
                    // longer hold, not every letter of the word.
                    const isLastLetter = li === letters.length - 1;
                    plan.push({
                        kind: "letter", token, letter: letters[li], nonManual,
                        holdMultiplier: isLastLetter ? holdMultiplier : 1,
                        promise: fetchLetterAnimation(letters[li]),
                    });
                }
            }
        }
    }

    await Promise.all(plan.map(p => p.promise).filter(Boolean));

    // Phase 2: resolve into the final queue in original order.
    const queue = [];
    for (const item of plan) {
        if (item.kind === "pause") {
            queue.push(item);
            continue;
        }

        const result = await item.promise;

        if (item.kind === "mocapWord") {
            if (result) {
                queue.push({
                    kind: "mocapWord",
                    token: item.token,
                    nonManual: item.nonManual,
                    holdMultiplier: item.holdMultiplier,
                    clip: result,
                });
            } else {
                // Mocap fetch/parse failed (network hiccup, etc.) --
                // fall back to this project's own WLASL-derived data
                // for the word rather than dropping it silently.
                const fallback = await fetchWordAnimation(item.token.text);
                if (fallback) {
                    queue.push({
                        kind: "word",
                        token: item.token,
                        nonManual: item.nonManual,
                        holdMultiplier: item.holdMultiplier,
                        fps: fallback.fps || 25,
                        states: fallback.frames.map(f => ({
                            pose: poseArrayToDict(f.pose),
                            left_hand: f.left_hand,
                            right_hand: f.right_hand,
                            face: faceArrayToDict(f.face),
                        })),
                    });
                }
            }
            continue;
        }

        if (!result) continue;

        if (item.kind === "word") {
            queue.push({
                kind: "word",
                token: item.token,
                nonManual: item.nonManual,
                holdMultiplier: item.holdMultiplier,
                fps: result.fps || 25,
                states: result.frames.map(f => ({
                    pose: poseArrayToDict(f.pose),
                    left_hand: f.left_hand,
                    right_hand: f.right_hand,
                    face: faceArrayToDict(f.face),
                })),
            });
        } else if (item.kind === "letter") {
            const anchored = result.hand.map(p => [
                p[0] + FINGERSPELL_ANCHOR[0],
                p[1] + FINGERSPELL_ANCHOR[1],
                p[2] + FINGERSPELL_ANCHOR[2],
            ]);
            queue.push({
                kind: "letter",
                token: item.token,
                letter: item.letter,
                nonManual: item.nonManual,
                holdMultiplier: item.holdMultiplier,
                state: { pose: REST_POSE.pose, left_hand: null, right_hand: anchored, face: null },
            });
        }
    }

    return queue;
}

// ---------------------------------------------------------------
// Playback engine
// ---------------------------------------------------------------
let playbackQueue = [];
let playing = false;
let paused = false;
let speed = 1.0;
let animFrameHandle = null;

function lerpPointArray(a, b, t) {
    if (!a || !b) return t < 0.5 ? a : b;
    return a.map((p, i) => {
        const q = b[i];
        if (!p || !q) return p;
        return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t, p[2] + (q[2] - p[2]) * t];
    });
}

function lerpState(a, b, t) {
    const lerpPart = (pa, pb) => {
        if (!pa || !pb) return t < 0.5 ? pa : pb;
        const out = {};
        const keys = new Set([...Object.keys(pa), ...Object.keys(pb)]);
        for (const k of keys) {
            const va = pa[k], vb = pb[k];
            if (!va || !vb) { out[k] = t < 0.5 ? va : vb; continue; }
            out[k] = [
                va[0] + (vb[0] - va[0]) * t,
                va[1] + (vb[1] - va[1]) * t,
                va[2] + (vb[2] - va[2]) * t,
            ];
        }
        return out;
    };

    const lerpFaceDict = (fa, fb) => {
        if (!fa || !fb) return t < 0.5 ? fa : fb;
        const out = {};
        for (const name of FACE_NAMES) {
            const va = fa[name], vb = fb[name];
            if (!va || !vb) { out[name] = t < 0.5 ? va : vb; continue; }
            out[name] = [
                va[0] + (vb[0] - va[0]) * t,
                va[1] + (vb[1] - va[1]) * t,
                va[2] + (vb[2] - va[2]) * t,
            ];
        }
        return out;
    };

    return {
        pose: lerpPart(a.pose, b.pose),
        left_hand: lerpPointArray(a.left_hand, b.left_hand, t),
        right_hand: lerpPointArray(a.right_hand, b.right_hand, t),
        face: lerpFaceDict(a.face, b.face),
    };
}

function lastStateOf(item) {
    if (item.kind === "word") return item.states[item.states.length - 1];
    if (item.kind === "letter") return item.state;
    return REST_POSE;
}
function firstStateOf(item) {
    if (item.kind === "word") return item.states[0];
    if (item.kind === "letter") return item.state;
    return REST_POSE;
}

function setActiveGlossToken(token) {
    document.querySelectorAll(".gloss-token").forEach(el => el.classList.remove("active"));
    if (!token) return;
    const el = document.querySelector(`.gloss-token[data-ref="${token._ref}"]`);
    if (el) el.classList.add("active");
}

/**
 * Runs one timed phase of playback (a blend, a word's frames, a
 * letter hold, or a pause) driven entirely by requestAnimationFrame
 * and real elapsed time (performance.now()), rather than chained
 * setTimeout delays -- robust regardless of tab throttling or frame
 * hiccups, since it always computes "what should be showing right
 * now" instead of counting down a queued delay.
 */
function runTimedPhase(durationMs, onTick) {
    return new Promise(resolve => {
        const start = performance.now();

        function step() {
            if (!playing) { resolve(); return; }
            if (paused) { animFrameHandle = requestAnimationFrame(step); return; }

            const elapsed = (performance.now() - start) * speed;
            const t = durationMs <= 0 ? 1 : Math.min(1, elapsed / durationMs);

            const keepGoing = onTick(t, elapsed);
            if (keepGoing === false || elapsed >= durationMs) {
                resolve();
            } else {
                animFrameHandle = requestAnimationFrame(step);
            }
        }

        animFrameHandle = requestAnimationFrame(step);
    });
}

async function blendTo(fromState, toState, ms) {
    await runTimedPhase(ms, (t) => {
        renderState(lerpState(fromState, toState, t));
    });
}

async function playWord(item) {
    setActiveGlossToken(item.token);
    const frameMs = 1000 / (item.fps || 25);
    const totalMs = item.states.length * frameMs;

    await runTimedPhase(totalMs, (t, elapsed) => {
        // Interpolate BETWEEN the two real captured frames straddling
        // the current elapsed time, instead of snapping to the
        // nearest one -- smooths motion using the same real data,
        // without needing a higher source frame rate.
        const raw = elapsed / frameMs;
        const idx = Math.min(item.states.length - 1, Math.floor(raw));
        const nextIdx = Math.min(item.states.length - 1, idx + 1);
        const frac = raw - idx;
        renderState(lerpState(item.states[idx], item.states[nextIdx], frac));
    });

    // ASL phrase-final lengthening (see PHRASE_FINAL_HOLD_MULTIPLIER):
    // hold the sign's own real final frame a bit longer, rather than
    // slowing down the whole articulation, which would distort the
    // real captured motion's actual speed.
    if (item.holdMultiplier && item.holdMultiplier > 1) {
        const extraMs = totalMs * (item.holdMultiplier - 1);
        const finalState = item.states[item.states.length - 1];
        await runTimedPhase(extraMs, () => {
            renderState(finalState);
        });
    }
}

/**
 * Plays a real professional motion-capture clip (see fetchMocapClip)
 * directly via Three.js's own AnimationMixer, bone-name-matched onto
 * this avatar's real skeleton -- a different playback mechanism from
 * playWord's point-cloud retargeting, because the source data is
 * already real bone rotations, not landmark points (see README
 * "Pass 6"). Entry/exit are a direct cut to/from the clip's own first/
 * last frame rather than smoothly interpolated (unlike between two
 * point-cloud-sourced signs) -- a disclosed simplification, not a
 * correctness bug: the surrounding blendTo(..., REST_POSE, ...) calls
 * (see firstStateOf/lastStateOf) still smooth the approach to/from
 * rest, only the final short hop onto the clip's own real first frame
 * is a cut.
 *
 * This archive's own creator states they are a hearing, non-native
 * ASL signer and that mistakes can happen -- real captured motion
 * from a real signer, not fabricated, but not a guarantee of
 * linguistic perfection either. See README "Pass 6".
 */
async function playMocapWord(item) {
    setActiveGlossToken(item.token);
    const mixer = new THREE.AnimationMixer(avatar.root);
    const action = mixer.clipAction(item.clip);
    action.clampWhenFinished = true;
    action.setLoop(THREE.LoopOnce);
    action.play();

    const totalMs = item.clip.duration * 1000;

    await runTimedPhase(totalMs, (t, elapsed) => {
        mixer.setTime(elapsed / 1000);
        avatar.root.updateMatrixWorld(true);
        // This archive's mocap data is body/hand motion only (no
        // face capture -- see README "Pass 6"), so the face stays at
        // its neutral baseline; applyFaceMetrics still layers the
        // sentence's real ASL non-manual marker (question eyebrow/
        // head-tilt, see currentNonManual) on top of that neutral
        // baseline, same as every other item in the queue.
        applyFaceMetrics(NEUTRAL_FACE_METRICS);
    });

    if (item.holdMultiplier && item.holdMultiplier > 1) {
        const extraMs = totalMs * (item.holdMultiplier - 1);
        await runTimedPhase(extraMs, () => {
            applyFaceMetrics(NEUTRAL_FACE_METRICS);
        });
    }

    mixer.stopAllAction();
    mixer.uncacheClip(item.clip);
}

async function playLetter(item) {
    setActiveGlossToken(item.token);
    const holdMs = LETTER_HOLD_MS * (item.holdMultiplier || 1);
    await runTimedPhase(holdMs, () => {
        renderState(item.state);
    });
}

async function playQueue(queue) {
    playbackQueue = queue;
    playing = true;
    paused = false;

    let prevState = REST_POSE;
    renderState(prevState);

    for (let i = 0; i < queue.length; i++) {
        if (!playing) return;
        const item = queue[i];

        currentNonManual = item.nonManual || NEUTRAL_NON_MANUAL;

        await blendTo(prevState, firstStateOf(item), BLEND_MS);
        if (!playing) return;

        if (item.kind === "pause") {
            await runTimedPhase(item.ms, () => {});
        } else if (item.kind === "word") {
            await playWord(item);
        } else if (item.kind === "letter") {
            await playLetter(item);
        } else if (item.kind === "mocapWord") {
            await playMocapWord(item);
        }

        prevState = lastStateOf(item);
    }

    setActiveGlossToken(null);
    currentNonManual = NEUTRAL_NON_MANUAL;
    await blendTo(prevState, REST_POSE, BLEND_MS * 2);
    playing = false;
    setStatus("Done.");
}

function renderLoop() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(renderLoop);
}
renderLoop();

// ---------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------
function setStatus(text) {
    document.getElementById("animStatus").innerText = text;
}

function renderGlossDisplay(sentences) {
    const container = document.getElementById("glossDisplay");
    container.innerHTML = "";
    let ref = 0;

    sentences.forEach((sentence, si) => {
        sentence.tokens.forEach(token => {
            token._ref = ref++;
            const el = document.createElement("span");
            el.className = "gloss-token " + token.type + (token.mocap ? " mocap" : "");
            el.dataset.ref = token._ref;
            el.innerText = token.type === "fingerspell"
                ? token.text.toUpperCase().split("").join("-")
                : token.text;
            if (token.mocap) {
                // Real professional motion-capture data (Xsens suit +
                // finger-tracking gloves) for this specific word,
                // instead of this project's own WLASL-derived data --
                // see README "Pass 6". Marked visibly so the upgrade
                // is actually seen, not just invisible under the hood.
                el.title = "Real professional motion-capture data for this sign (Studio Galt Sign Language Mocap Archive) -- higher-fidelity hand articulation than this project's own video-derived data.";
                const badge = document.createElement("span");
                badge.className = "mocap-badge";
                badge.innerText = "✦";
                el.appendChild(badge);
            }
            container.appendChild(el);
        });
        // Words this project has no real sign or fingerspelling data
        // for (currently: numbers/symbols -- ASL numbers use dedicated
        // handshapes this project has no captured motion for) are
        // disclosed here instead of silently vanishing from the
        // animation -- see gloss.py's word_to_token / "unsigned".
        for (const word of sentence.unsigned || []) {
            const el = document.createElement("span");
            el.className = "gloss-unsigned";
            el.title = "No real ASL sign or fingerspelling data available for this word -- not shown in the animation.";
            el.innerText = `⚠ "${word}" not signed`;
            container.appendChild(el);
        }
        if (si < sentences.length - 1) {
            const br = document.createElement("div");
            br.className = "gloss-sentence-break";
            container.appendChild(br);
        }
    });

    const anyMocap = sentences.some(s => s.tokens.some(t => t.mocap));
    document.getElementById("mocapLegend").style.display = anyMocap ? "block" : "none";
}

// ---------------------------------------------------------------
// Kozha/CWASA -- a separate, additional real-ASL rendering path
// (see sign_animation/kozha.py and README "Pass 7"). Used only for a
// whole request when the backend reports every word in it resolves to
// something real in Kozha's own (much smaller) verified ASL data --
// never mixed mid-sentence with this project's own primary avatar.
// The CWASA engine itself (extension/cwa/allcsa.js, vendored
// unmodified) is loaded lazily so it never costs anything for the
// vast majority of requests that use this project's own 250-word
// avatar as always.
// ---------------------------------------------------------------
let cwasaScriptPromise = null;
let cwasaReadyPromise = null;

function loadCwasaScript() {
    if (cwasaScriptPromise) return cwasaScriptPromise;
    cwasaScriptPromise = new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "/static/vendor/cwasa/allcsa.js";
        s.onload = () => resolve();
        s.onerror = () => reject(new Error("Failed to load the CWASA engine script"));
        document.head.appendChild(s);
    });
    return cwasaScriptPromise;
}

/** Loads + initializes the real CWASA player exactly once, mirroring
 * Kozha's own extension/panel.js initCwasa() call shape (same init
 * options), pointed at this project's own vendored copy instead of
 * Kozha's server. Returns true once genuinely ready, false if CWASA
 * couldn't load/init for any reason (missing WebGL, blocked script,
 * etc.) -- callers fall back to this project's own avatar in that case. */
/** CWASA needs a shared "COMMON" avatar-config archive (avatars/COMMON.jar)
 * for ANY avatar to actually render a sign, regardless of which
 * character is selected -- it isn't included in Kozha's public repo
 * (verified directly, and it 404s from the university's own live
 * JASigning host too, at every path/version tried -- see README
 * "Pass 7"). Checking for it before paying the cost of loading the
 * 4.7MB engine script avoids ever showing a CWASA avatar that would
 * silently fail to actually play a sign. */
async function cwasaCommonAssetAvailable() {
    try {
        const res = await fetch("/static/vendor/cwasa/avatars/COMMON.jar", { method: "HEAD" });
        return res.ok;
    } catch (e) {
        return false;
    }
}

function ensureCwasaReady() {
    if (cwasaReadyPromise) return cwasaReadyPromise;
    cwasaReadyPromise = (async () => {
        try {
            if (!(await cwasaCommonAssetAvailable())) {
                console.warn("CWASA's required COMMON avatar-config archive is not available; using the primary avatar instead.");
                return false;
            }
            await loadCwasaScript();
            if (typeof CWASA === "undefined") {
                throw new Error("CWASA global not defined after script load");
            }
            CWASA.init({
                useClientConfig: false,
                useCwaConfig: true,
                jasBase: "/static/vendor/cwasa/",
                cwaBase: "/static/vendor/cwasa/",
                avSettings: [{
                    width: 660,
                    height: 460,
                    avList: "avs",
                    initAv: "anna",
                    ambIdle: true,
                    allowFrameSteps: false,
                    allowSiGMLText: false,
                    initSpeed: 3,
                }],
            });
            await CWASA.ready;

            const canvas = document.querySelector("#cwasaAvatarWrap canvas");
            if (canvas) {
                canvas.addEventListener("webglcontextlost", (e) => {
                    e.preventDefault();
                    cwasaReadyPromise = null; // force re-init attempt next time
                });
            }
            return true;
        } catch (e) {
            console.warn("CWASA failed to initialize; falling back to the primary avatar:", e);
            return false;
        }
    })();
    return cwasaReadyPromise;
}

function showCwasaAvatar() {
    document.getElementById("avatarCanvasWrap").style.display = "none";
    document.getElementById("playbackControls").style.display = "none";
    document.getElementById("cwasaAvatarWrap").style.display = "block";
    document.getElementById("cwasaNotice").style.display = "block";
}

function showPrimaryAvatar() {
    document.getElementById("cwasaAvatarWrap").style.display = "none";
    document.getElementById("cwasaNotice").style.display = "none";
    document.getElementById("avatarCanvasWrap").style.display = "block";
    document.getElementById("playbackControls").style.display = "block";
}

async function animate() {
    playing = false; // stop any current playback
    const text = document.getElementById("animInput").value.trim();
    if (!text) return;

    if (!avatar.ready) {
        setStatus("Avatar is still loading...");
        return;
    }

    setStatus("Simplifying text into sign gloss...");
    const glossRes = await fetch("/api/sign-animation/gloss", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
    });
    const { sentences, kozha } = await glossRes.json();

    let usedCwasa = false;
    if (kozha && kozha.eligible) {
        setStatus("Loading CWASA (Kozha real ASL data)...");
        const ready = await ensureCwasaReady();
        if (ready) {
            try {
                document.getElementById("glossDisplay").innerHTML = "";
                document.getElementById("mocapLegend").style.display = "none";
                showCwasaAvatar();
                CWASA.playSiGMLText(kozha.sigml, 0);
                setStatus("Playing (via CWASA)...");
                usedCwasa = true;
            } catch (e) {
                console.warn("CWASA playback failed, falling back to the primary avatar:", e);
            }
        }
    }
    if (!usedCwasa) {
        showPrimaryAvatar();
    } else {
        return;
    }

    if (!sentences.length) {
        setStatus("Nothing signable was found in that text.");
        document.getElementById("glossDisplay").innerHTML = "";
        return;
    }

    renderGlossDisplay(sentences);
    setStatus("Loading sign data...");

    const queue = await buildPlaybackQueue(sentences);
    setStatus("Playing...");
    playQueue(queue);
}

document.getElementById("animateBtn").addEventListener("click", animate);

document.getElementById("playPauseBtn").addEventListener("click", (e) => {
    paused = !paused;
    e.target.innerText = paused ? "Resume" : "Pause";
});

document.getElementById("replayBtn").addEventListener("click", () => {
    if (playbackQueue.length) {
        playing = false;
        paused = false;
        document.getElementById("playPauseBtn").innerText = "Pause";
        setStatus("Playing...");
        setTimeout(() => playQueue(playbackQueue), 50);
    }
});

function setSpeed(newSpeed) {
    speed = parseFloat(newSpeed);
    const slider = document.getElementById("speedSlider");
    const label = document.getElementById("speedLabel");
    if (slider) slider.value = speed;
    if (label) label.innerText = speed.toFixed(1) + "x";

    document.querySelectorAll(".speed-btn").forEach(btn => {
        const btnSpeed = parseFloat(btn.getAttribute("data-speed"));
        if (Math.abs(btnSpeed - speed) < 0.05) {
            btn.style.background = "#2b6cff";
            btn.style.color = "#ffffff";
            btn.classList.add("active");
        } else {
            btn.style.background = "transparent";
            btn.style.color = "#475569";
            btn.classList.remove("active");
        }
    });

    if (typeof CWASA !== "undefined" && CWASA.ready) {
        try {
            CWASA.setSpeed(0, Math.round(speed * 3));
        } catch (e) {}
    }
}

document.querySelectorAll(".speed-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        setSpeed(btn.getAttribute("data-speed"));
    });
});

document.getElementById("speedSlider").addEventListener("input", (e) => {
    setSpeed(e.target.value);
});

// ---------------------------------------------------------------
// Boot: load the avatar, frame the camera on it, then animate the
// default example text.
// ---------------------------------------------------------------
setStatus("Loading avatar...");
loadAvatar().then(() => {
    attachFaceOverlays();
    renderState(REST_POSE);

    // Frame the camera on the loaded mesh's actual chest/head height
    // (this rig's own coordinate origin is at the feet, not the hips).
    const chestY = avatar.bind["Neck"] ? avatar.bind["Neck"].worldPos.y - 0.15 : 1.3;
    // Pulled back enough that arms fully extended out to the sides
    // (a real, common sign-language hand position) stay in frame,
    // not just a tight headshot.
    camera.position.set(0, chestY + 0.05, 2.3);
    controls.target.set(0, chestY, 0);
    controls.update();

    setStatus("Ready.");
    animate();
}).catch((err) => {
    console.error("Failed to load avatar:", err);
    setStatus("Failed to load the 3D avatar model.");
});