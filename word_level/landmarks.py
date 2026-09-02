"""
Shared MediaPipe Holistic landmark extraction + normalization used by
both the offline dataset builder (extract_features.py) and the live
recognizer (predict_word_sign.py), so training and inference use the
exact same feature representation.
"""

import numpy as np
import mediapipe as mp

import config

mp_holistic = mp.solutions.holistic


def make_holistic(static_image_mode=False):
    return mp_holistic.Holistic(
        static_image_mode=static_image_mode,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def _landmarks_to_array(landmark_list, num_points):
    """Returns an (num_points, 3) array of (x, y, z), zero-filled if absent."""
    if landmark_list is None:
        return np.zeros((num_points, 3), dtype=np.float32)
    pts = np.array(
        [[lm.x, lm.y, lm.z] for lm in landmark_list.landmark], dtype=np.float32
    )
    return pts


def extract_hand_static_features(results):
    """
    Extracts the 42-element normalized hand landmark feature vector
    matching create_dataset.py and model.pkl in the root directory.
    """
    if not results:
        return None
    hand_lm = None
    if results.right_hand_landmarks is not None:
        hand_lm = results.right_hand_landmarks.landmark
    elif results.left_hand_landmarks is not None:
        hand_lm = results.left_hand_landmarks.landmark

    if hand_lm is None:
        return None

    features = []
    base_x = hand_lm[0].x
    base_y = hand_lm[0].y

    for lm in hand_lm:
        features.append(lm.x - base_x)
        features.append(lm.y - base_y)

    max_value = max(max(abs(x) for x in features), 1e-6)
    return [x / max_value for x in features]


def extract_frame_features(results):
    """
    Builds a single flat (config.FEATURES_PER_FRAME,) feature vector for
    one MediaPipe Holistic result: pose + left hand + right hand,
    normalized to be translation- and scale-invariant.
    """
    pose = _landmarks_to_array(results.pose_landmarks, config.NUM_POSE_LANDMARKS)
    lhand = _landmarks_to_array(results.left_hand_landmarks, config.NUM_HAND_LANDMARKS)
    rhand = _landmarks_to_array(results.right_hand_landmarks, config.NUM_HAND_LANDMARKS)

    # Normalize relative to the midpoint of the shoulders (pose indices
    # 11 = left shoulder, 12 = right shoulder), scaled by shoulder width.
    if results.pose_landmarks is not None and np.abs(pose).sum() > 1e-4:
        left_shoulder = pose[11]
        right_shoulder = pose[12]
        center = (left_shoulder + right_shoulder) / 2.0
        scale = np.linalg.norm(left_shoulder[:2] - right_shoulder[:2])
        scale = max(scale, 1e-4)
    elif results.right_hand_landmarks is not None and np.abs(rhand).sum() > 1e-4:
        center = rhand[0]
        scale = np.linalg.norm(rhand[0][:2] - rhand[9][:2])
        scale = max(scale, 1e-4)
    elif results.left_hand_landmarks is not None and np.abs(lhand).sum() > 1e-4:
        center = lhand[0]
        scale = np.linalg.norm(lhand[0][:2] - lhand[9][:2])
        scale = max(scale, 1e-4)
    else:
        center = np.zeros(3, dtype=np.float32)
        scale = 1.0

    pose = (pose - center) / scale
    lhand = (lhand - center) / scale
    rhand = (rhand - center) / scale

    return np.concatenate([pose.flatten(), lhand.flatten(), rhand.flatten()])


def resample_sequence(frames, target_len=config.SEQUENCE_LENGTH):
    """
    Uniformly resamples a list/array of per-frame feature vectors to
    exactly `target_len` frames (via nearest-index sampling), so clips
    of different lengths/frame-rates all produce equal-length sequences.
    """
    frames = np.asarray(frames, dtype=np.float32)
    n = len(frames)

    if n == 0:
        return np.zeros((target_len, config.FEATURES_PER_FRAME), dtype=np.float32)

    if n == target_len:
        return frames

    indices = np.linspace(0, n - 1, target_len)
    indices = np.round(indices).astype(int)
    indices = np.clip(indices, 0, n - 1)

    return frames[indices]


def extract_sequence_features(seq_30):
    """
    Transforms a (30, 225) resampled landmark sequence into a rich 2025-dim
    feature vector capturing hand shape, finger positions, wrist rotation,
    movement direction, velocity, and timing over time.
    """
    seq_30 = np.asarray(seq_30, dtype=np.float32)
    if seq_30.ndim == 1:
        seq_30 = seq_30.reshape(config.SEQUENCE_LENGTH, config.FEATURES_PER_FRAME)

    mean_f = np.mean(seq_30, axis=0)
    std_f = np.std(seq_30, axis=0)
    min_f = np.min(seq_30, axis=0)
    max_f = np.max(seq_30, axis=0)
    first_f = seq_30[0]
    last_f = seq_30[-1]

    diffs = np.diff(seq_30, axis=0)
    vel_mean = np.mean(diffs, axis=0)
    vel_std = np.std(diffs, axis=0)
    vel_max = np.max(diffs, axis=0)

    return np.hstack([mean_f, std_f, min_f, max_f, first_f, last_f, vel_mean, vel_std, vel_max])


def detect_anchor_sign(results):
    """
    Evaluates exact geometric finger landmark constraints for core high-frequency signs
    (water, hello, help, i, need, danger, you) from live MediaPipe Holistic results.
    Returns (anchor_word, confidence) if matched with high certainty, else (None, 0.0).
    """
    if not results:
        return None, 0.0

    lhand = _landmarks_to_array(results.left_hand_landmarks, config.NUM_HAND_LANDMARKS) if results.left_hand_landmarks is not None else None
    rhand = _landmarks_to_array(results.right_hand_landmarks, config.NUM_HAND_LANDMARKS) if results.right_hand_landmarks is not None else None
    pose = _landmarks_to_array(results.pose_landmarks, config.NUM_POSE_LANDMARKS) if results.pose_landmarks is not None else None

    has_l = lhand is not None and np.abs(lhand).sum() > 1e-4
    has_r = rhand is not None and np.abs(rhand).sum() > 1e-4

    if not has_l and not has_r:
        return None, 0.0

    nose = pose[0] if (pose is not None and np.abs(pose).sum() > 1e-4) else np.array([0.5, 0.3, 0.0], dtype=np.float32)

    # 1. HELP: Two hands active near chest/midsection OR single-hand thumbs-up / fist at chest level
    if has_l and has_r:
        l_wrist = lhand[0]
        r_wrist = rhand[0]
        hand_dist = np.linalg.norm(l_wrist - r_wrist)
        if hand_dist < 0.45 and l_wrist[1] > nose[1] + 0.10 and r_wrist[1] > nose[1] + 0.10:
            return "help", 0.95

    active_hands = []
    if has_r: active_hands.append(rhand)
    if has_l: active_hands.append(lhand)

    for hand in active_hands:
        wrist = hand[0]
        thumb_tip, thumb_mcp = hand[4], hand[2]
        index_tip, index_mcp = hand[8], hand[5]
        middle_tip, middle_mcp = hand[12], hand[9]
        ring_tip, ring_mcp = hand[16], hand[13]
        pinky_tip, pinky_mcp = hand[20], hand[17]

        index_ext = index_tip[1] < index_mcp[1]
        middle_ext = middle_tip[1] < middle_mcp[1]
        ring_ext = ring_tip[1] < ring_mcp[1]
        pinky_ext = pinky_tip[1] < pinky_mcp[1]

        thumb_up = thumb_tip[1] < thumb_mcp[1]
        all_other_folded = not index_ext and not middle_ext and not ring_ext and not pinky_ext

        # 1b. HELP: Single hand thumbs-up / fist gesture at chest/waist level (as in ASL HELP)
        if thumb_up and all_other_folded and wrist[1] > nose[1] + 0.08:
            return "help", 0.95

        # 2. WATER: "W" handshape (Index, Middle, AND Ring fingers extended; Pinky folded)
        if index_ext and middle_ext and ring_ext and not pinky_ext:
            return "water", 0.96

        # 3. HELLO: Open hand (all 4 main fingers extended) high near head/forehead
        near_head = (wrist[1] < nose[1] + 0.22) and (abs(wrist[0] - nose[0]) < 0.45)
        if near_head and index_ext and middle_ext and ring_ext and pinky_ext:
            return "hello", 0.95

        # 4. DANGER: All fingers extended at throat/neck height
        near_throat = abs(wrist[1] - (nose[1] + 0.22)) < 0.18 and abs(wrist[0] - nose[0]) < 0.38
        if near_throat and index_ext and middle_ext and ring_ext and pinky_ext:
            return "danger", 0.93

        # 5. I: Only pinky finger extended upright (Index, Middle, Ring folded)
        if pinky_ext and not index_ext and not middle_ext and not ring_ext:
            return "i", 0.95

        # 6. YOU: Only index finger extended straight pointing forward (index tip significantly higher than MCP)
        if (index_tip[1] < index_mcp[1] - 0.04) and not middle_ext and not ring_ext and not pinky_ext:
            return "you", 0.95

        # 7. NEED: Index hooked / bent downwards at chest height
        index_hooked = (index_tip[1] >= index_mcp[1] - 0.03) and (index_tip[1] < wrist[1]) and not middle_ext and not ring_ext and not pinky_ext
        if index_hooked and wrist[1] > nose[1] + 0.08:
            return "need", 0.92

    return None, 0.0

