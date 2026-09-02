"""
Shared 3D landmark extraction/remapping for the sign-animation avatar.
Deliberately separate from word_level/landmarks.py: that module
normalizes (centers + scales-to-unit) each frame independently for
*classification*, which flattens/distorts real proportions -- fine for
a model, wrong for something meant to look like a moving human body.
Here we instead remap MediaPipe's raw coordinate space once per clip
into a stable, human-proportioned 3D "avatar space":

  - origin (0,0,0) = the hip midpoint of the FIRST frame with a
    detected pose (kept fixed for the whole clip, not re-centered
    every frame, so the body doesn't jitter/re-anchor frame to frame)
  - Y flipped (image space Y grows downward; Three.js is Y-up)
  - uniformly scaled so the figure is config.AVATAR_HEIGHT_UNITS tall
"""

import mediapipe as mp
import numpy as np

import config

mp_holistic = mp.solutions.holistic
mp_hands = mp.solutions.hands

# MediaPipe Pose landmark indices used for a simplified upper-body
# skeleton (indices per mp_holistic.PoseLandmark).
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_HIP, RIGHT_HIP = 23, 24
NOSE = 0

# A curated subset of MediaPipe's 468/478-point face mesh (canonical
# indices) -- just enough real, captured facial data to drive head
# orientation, eyebrow raise, eye openness, mouth shape, and (via the
# two iris landmarks, only available with refine_face_landmarks=True)
# genuine gaze direction. Not the full face mesh: keeps per-word
# animation files small while still being 100% real captured motion,
# not synthesized.
FACE_POINTS = {
    "nose_tip": 1, "chin": 152, "forehead": 10,
    "left_cheek": 234, "right_cheek": 454,
    "left_eye_outer": 33, "left_eye_inner": 133,
    "left_eye_top": 159, "left_eye_bottom": 145,
    "right_eye_outer": 263, "right_eye_inner": 362,
    "right_eye_top": 386, "right_eye_bottom": 374,
    "left_eyebrow": 105, "right_eyebrow": 334,
    "mouth_top": 13, "mouth_bottom": 14,
    "mouth_left": 61, "mouth_right": 291,
    "left_iris": 468, "right_iris": 473,
}
FACE_POINT_NAMES = list(FACE_POINTS.keys())  # fixed order, matches the
                                              # frontend's FACE_POINTS map


def make_holistic():
    return mp_holistic.Holistic(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        refine_face_landmarks=True,  # adds the 10 iris landmarks used
                                      # for real (not simplified) gaze
    )


def make_hands(static_image_mode=True):
    return mp_hands.Hands(
        static_image_mode=static_image_mode,
        max_num_hands=1,
        min_detection_confidence=0.5,
    )


def _pose_points(pose_landmarks):
    if pose_landmarks is None:
        return None
    return np.array([[lm.x, lm.y, lm.z] for lm in pose_landmarks.landmark], dtype=np.float32)


def _hand_points(hand_landmarks):
    if hand_landmarks is None:
        return None
    return np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark], dtype=np.float32)


def _face_points(face_landmarks):
    if face_landmarks is None:
        return None
    all_lms = face_landmarks.landmark
    return np.array(
        [[all_lms[idx].x, all_lms[idx].y, all_lms[idx].z] for idx in FACE_POINTS.values()],
        dtype=np.float32,
    )


def holistic_frame_to_raw(results):
    """Raw (unremapped) points for one frame, or None per part if not detected."""
    return {
        "pose": _pose_points(results.pose_landmarks),
        "left_hand": _hand_points(results.left_hand_landmarks),
        "right_hand": _hand_points(results.right_hand_landmarks),
        "face": _face_points(results.face_landmarks),
    }


def compute_anchor_and_scale(frames):
    """Finds the first frame with a usable pose to fix the avatar's
    origin and scale for the whole clip (see module docstring)."""
    for frame in frames:
        pose = frame["pose"]
        if pose is None:
            continue

        hip_mid = (pose[LEFT_HIP] + pose[RIGHT_HIP]) / 2.0
        shoulder_mid = (pose[LEFT_SHOULDER] + pose[RIGHT_SHOULDER]) / 2.0

        torso_height = float(np.linalg.norm(shoulder_mid[:2] - hip_mid[:2]))
        if torso_height < 1e-4:
            continue

        # Real torso (hip-to-shoulder) is roughly 30% of standing
        # height -- use that ratio to get a whole-body scale from just
        # the torso, since hands/feet aren't always in frame.
        approx_body_height = torso_height / 0.3
        scale = config.AVATAR_HEIGHT_UNITS / approx_body_height

        return hip_mid, scale

    return np.array([0.5, 0.5, 0.0], dtype=np.float32), 1.0


def remap_point(point, anchor, scale):
    if point is None:
        return None
    x = (point[0] - anchor[0]) * scale
    y = -(point[1] - anchor[1]) * scale  # flip: image Y-down -> avatar Y-up
    z = -(point[2] - anchor[2]) * scale  # mediapipe z is roughly depth-into-screen
    return [round(float(x), 4), round(float(y), 4), round(float(z), 4)]


def remap_frame(frame, anchor, scale):
    out = {}
    for key in ("pose", "left_hand", "right_hand", "face"):
        pts = frame[key]
        if pts is None:
            out[key] = None
        else:
            out[key] = [remap_point(p, anchor, scale) for p in pts]
    return out
