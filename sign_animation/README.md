# Text → Sign Animation (3D Avatar)

Converts typed text — including full sentences and conversations —
into a sign-appropriate sequence performed by a 3D avatar, instead of
flat images/videos ([text_to_sign_web.py](../text_to_sign_web.py)) or
translating word-by-word. Entirely additive: the existing Text-to-Sign
page, all three recognizers, and the Word Dictionary are untouched.

## What "3D avatar" actually means here (read this first)

A photorealistic, professionally rigged CGI human — the kind real
commercial sign-avatar products use — is a multi-week specialist
pipeline (character riggers, animators, licensed assets, motion
retargeting). That's not something one implementation pass can
honestly deliver, and this project doesn't pretend to.

What's built (as of the seventh pass on this feature — see below): a
**real rigged, skinned, textured humanoid mesh**, genuinely
female-presenting — not a hand-built primitive figure — **animated by
retargeting real captured motion** onto its skeleton: actual MediaPipe
landmark positions extracted from this project's own WLASL sign videos
(for whole signs) and alphabet hand images (for fingerspelling), plus —
for 30 of the 220 words — real professional motion-capture data from
dedicated mocap hardware (see "Pass 6" below). It's not a guessed or
interpolated pose — every frame is real motion from a real signer,
retargeted onto the mesh's bones by rotation only (see "Pass 3" below
for exactly how and why that's the robust way to do it). Sentences
that are questions also drive real ASL non-manual
grammar (see "Pass 4" below) — eyebrow raise/furrow and a forward head
tilt, not just the hands — and phrase-final signs hold their own real
final frame longer, a documented ASL prosody effect (see "Pass 5"
below). That's what makes this both achievable and honest: the
*motion* is real, the *mesh* is a real licensed asset, and the
*non-manual/timing markers* are documented ASL grammar, not invented
geometry or cosmetic flourishes.

### Pass 7: Kozha/CWASA integration, and the real blocker found testing it

The user asked to integrate the actual open-source
**[Kozha](https://github.com/zhan-a/Kozha)** project's real animation
technology — **CWASA**, a WebGL signing-avatar engine maintained by the
Virtual Humans Group, University of East Anglia — as an *additional*
rendering path alongside (not replacing) this project's own 250-word
avatar, using Kozha's real code and real ASL SiGML data, not a
recreation. This was built by reading Kozha's actual reference
implementation (`extension/panel.js`) rather than guessing at the
integration shape.

**What's real and genuinely reused, unmodified:**
- [kozha.py](kozha.py) is a direct Python port of `panel.js`'s own
  `glossBase()` / `resolveGloss()` / `fingerspellWord()` /
  `buildSigml()` logic — same gloss normalization, same 2-word-phrase-
  then-1-word-then-fingerspell resolution order, same single
  `<sigml>...</sigml>` document assembly CWASA sequences and times
  internally (no custom interpolation/timing written for this path —
  CWASA's own player owns that entirely, per the user's explicit
  request).
- `static/vendor/cwasa/allcsa.js`, `cwasa.css`, and the `anna.jar`
  avatar are Kozha's own files, vendored byte-for-byte. `cwacfg.json`
  is Kozha's own file with only its `avs`/`avsfull` lists trimmed to
  the one avatar actually vendored (a config value, not the engine).
- `data/kozha/American_SL_ASL.sigml` (14 real ASL signs) and
  `asl_alphabet_sigml.sigml` (real A–Z fingerspelling) are Kozha's own
  data files, unmodified.
- License: CWASA's own
  [Conditions of Use](https://vh.cmp.uea.ac.uk/index.php/CWASA_Conditions_of_Use)
  permit use-with-attribution and forbid distributing *modified*
  versions — satisfied here (unmodified engine, attribution in
  [About](../templates/about.html)#credits). Kozha's own pipeline code
  is MIT. The ASL sign data is sourced via Kozha from ASL-LEX 2.0,
  CC BY-NC 4.0 (non-commercial) — disclosed in Credits.

**Scope, by design**: a whole request only uses CWASA when *every*
word in it resolves to something real in Kozha's data (a real sign or
real fingerspelling) — verified against all four of the user's test
phrases: `hello` (real HELLO sign), `thank you` (the 2-word-phrase
match correctly resolves to the real THANK-YOU sign, not two separate
words), `how are you` (HOW/YOU aren't in Kozha's 14 signs, so both
real-fingerspell), `my name is Samridhi` (NAME is real, `my`/`Samridhi`
real-fingerspell). This is a strict, whole-request either/or choice —
never two different avatars mixed inside one playback — because
CWASA's character (Anna) and this project's own avatar are different,
unrelated 3D models that can't be blended into one continuous figure.
Everything not fully covered by Kozha's tiny real ASL set keeps using
this project's own much larger 250-word pipeline exactly as before,
completely untouched by this pass.

**Three real missing dependencies were found and fixed by actually
running it in a browser** (not assumed — found one at a time from the
engine's own console errors, per the user's own test checklist), all
sourced from the *same* verified-compatible official distribution, not
fabricated:

1. `avatars/COMMON.jar` — a shared archive CWASA needs to render *any*
   sign with *any* character (`AvDataAccess: Error for .../COMMON.jar:
   ZIP file not found`). Missing from Kozha's repo and 404s from every
   Kozha/UEA live path tried.
2. `h2s.xsl` — the HamNoSys→SiGML XSLT stylesheet
   (`Could not create XSLT Processor for h2s.xsl`). Also missing from
   Kozha's repo entirely.
3. `shaders/qskin.vert` / `qskin.frag` — the WebGL skinning shaders
   actually needed to *draw* the mesh (without them CWASA processes
   and "plays" a sign with zero errors, but the canvas stays a blank
   background color — the avatar never appears).

None of Kozha's own hosting (GitHub repo, `kozha-translate.com`, the
UEA live JASigning server at every version tag tried) has these files
at the paths Kozha's own code expects. What UEA *does* publish is a
complete **local-installation package**
(`https://vhg.cmp.uea.ac.uk/tech/jas/local/jas.zip`, ~456MB,
documented at
[JASigning Local Installation](https://vh.cmp.uea.ac.uk/index.php/JASigning_Local_Installation)) —
the same official source, not a third party. Its `anna.jar` is
byte-for-byte identical (SHA-256 verified) to the one Kozha bundles,
confirming version compatibility before using anything from it. The
three missing files were extracted from that package's
`jas/loc2025/cwa/` folder and added to
`static/vendor/cwasa/` — genuine official CWASA files, not
recreated, approximated, or authored here.

With all three in place, **CWASA now actually renders** — verified
live for all four of the user's test phrases (`hello`, `thank you`,
`how are you`, `my name is Samridhi`): the real "Anna" avatar loads,
processes the SiGML, and visibly signs, confirmed both visually (a
red-topped, blonde CWASA character on screen, not a blank canvas) and
via the engine's own status log (`SiGML Loaded` → `Playing starts` →
`Playing complete`). `ensureCwasaReady()` still checks for
`COMMON.jar` before loading the 4.7MB engine at all, so if any of
these files were ever removed or the vendored copies became
incompatible with a future Kozha `allcsa.js` update, the request
cleanly falls back to this project's own avatar instead of showing a
broken or blank CWASA canvas.

### Pass 6: real professional motion-capture data for a subset of words

After Pass 5's research ruled out the DFKI MMS Player itself (wrong
sign language, incompatible license, no browser rendering), the user
asked for a *different* real, existing, freely-licensed animation
source to integrate instead. Research turned up the
[Studio Galt Sign Language Mocap Archive](https://github.com/StudioGalt/Sign-Language-Mocap-Archive)
(CC0-1.0 — no rights reserved, explicitly free to use), which is a
materially different and better-founded fit than MMS was:

- **Real ASL**, the creator's own stated primary focus (with some
  BANZL — British/Australian/NZ Sign Language — content too, kept
  separate from the ASL entries this project uses).
- **Real motion capture from dedicated hardware** — an Xsens Link
  motion-capture suit plus StretchSense finger-tracking gloves, not
  estimated from 2D video the way this project's own WLASL-derived
  word data is (see "Where the animation data comes from" below). For
  any word it covers, this is a genuine accuracy upgrade: dedicated
  finger-tracking gloves capture hand articulation far more precisely
  than estimating 21 hand landmarks from a flat video frame.
- **CC0 license** — no restrictions at all, the best possible outcome
  after Pass 5's NC-ND blocker.
- **Mixamo-standard bone-named FBX exports** that matched this
  project's existing avatar rig (`avatar_feminine.fbx`) **52 of 53
  bones exactly** (verified directly — see below), meaning the
  existing avatar didn't need to change at all, only a new source and
  playback path for real bone-rotation data.

**Honest caveat, stated directly by the archive's own creator and
carried forward here rather than glossed over**: they say plainly they
are *"a hearing person, not Deaf or native ASL signer"* and that
*"my knowledge of ASL is not complete"* — and that *"while 100%
accuracy is the goal, mistake can and will happen,"* with no formal
Deaf-community audit process described. This is real captured motion
from a real (if, by the creator's own account, sometimes imperfect)
signer — not fabricated, not generated, not a different language
silently relabeled — but it is not a guarantee of zero errors either,
and neither is any other single source. This is disclosed here and in
"Known limitations" rather than the omission the user explicitly
warned against ("do not claim the animation is accurate just because
it looks smooth").

**Verification before integrating anything** (matching this project's
established pattern of testing before trusting a new source): a real
clip ("Alcohol") was downloaded and its skeleton compared bone-by-bone
against this project's own avatar rig — 52/53 bones matched by name
exactly (the one miss, `Locator_Root`, is a non-humanoid IK helper
node, correctly dropped). The clip was then actually retargeted onto
the live avatar in the browser via Three.js's own `AnimationMixer`
(not this project's point-cloud math, since the source data is already
real bone rotations) and the resulting bone quaternions inspected
directly — real, valid, non-degenerate rotations that differed
meaningfully from the bind pose at the arm, hand, and finger level.

**What's integrated**: [fetch_mocap_words.py](fetch_mocap_words.py)
resolves and downloads a real archive clip for any of this project's
220 known words the archive has a matching entry for (choosing the
newest take per word, since the archive's own guidance is that newer
recordings are more accurate). As of this pass, **30 of 220 words**
are covered this way (the archive currently only has entries starting
with the letters A, B, C, D, E, F, H, M, N, O, P, T, V, W, Y, so words
starting with other letters can't match yet regardless of vocabulary
overlap) — including `hello`, this page's own default example. The
archive's internal folder layout has changed several times over its
life; the fetch script tries each known layout per word rather than
assuming one fixed structure, and four very recent words (`decide`,
`decorate`, `delay`, `delicious`) use a newer layout that doesn't
currently include a Mixamo export at all, so they still fall back to
this project's own WLASL-derived data.

**Playback** ([static/js/sign_animation.js](../static/js/sign_animation.js),
`fetchMocapClip`/`playMocapWord`): [gloss.py](gloss.py) tags a "word"
token `"mocap": true` when a real clip is available; the frontend
fetches the raw FBX (`/api/sign-animation/mocap/<word>` in
[app.py](../app.py)), strips the Mixamo bone-name prefix, drops any
track with no matching bone on this avatar, and plays the result via
`THREE.AnimationMixer` bound directly to the avatar's real skeleton —
a different, simpler playback mechanism than `playWord`'s point-cloud
retargeting, used only because the source data here is already real
bone rotations. If the fetch or parse fails for any reason (network
hiccup, etc.), it falls back to this project's own WLASL-derived data
for that word rather than dropping it. The sentence's real ASL
non-manual marker (question eyebrow/head-tilt) and phrase-final hold
(see "Pass 5") both still apply on top, exactly as for any other word
— this is a new *source*, not a parallel, disconnected feature.

To (re-)download or extend the mocap word set after adding more words
to the vocabulary:

```bash
source .venv/bin/activate
python sign_animation/fetch_mocap_words.py
```

### Pass 5: DFKI MMS Player research, and what was adopted from it

The user asked to replace this whole system with the **DFKI MMS
Player** (`github.com/DFKI-SignLanguage/MMS-Player`, GPL-3.0). It was
researched in depth before writing any code:

- The player itself is a **Blender-based offline renderer**, invoked
  as `blender_exe --background --python main.py -- --export-mp4 ...`.
  It does not output to a browser at all — its own README says web
  browsers "would require separate rendering infrastructure." Its own
  authors state it "DOES NOT represent whatsoever an application ready
  for the production of intelligible and quality approved sign
  language videos," and facial animation is incomplete. Its first two
  public releases were 9 and 2 days before this pass — a brand-new
  research prototype, not a mature player.
- The player is just a generic gloss/timing/inflection playback engine
  — it needs a "dictionary" of real motion-captured signs to be useful
  at all. The only one that exists for it (downloaded and inspected
  directly, 1.85GB) is a subset of the **AVASAG corpus**, whose own
  stated purpose is *"automatic translation of German texts into
  German Sign Language (DGS)"* — a different, mutually unintelligible
  language from ASL, the same category of problem already ruled out
  once for the Kaggle ISL dataset in "Pass 3" below. It's also licensed
  **CC BY-NC-ND 4.0** ("for research purposes only," no redistribution
  of derivatives) and its own README calls it an unpublished preview
  subset, not the real corpus.
- Conclusion, put to the user directly: there is no path to "the real
  MMS Player producing correct ASL signs, live in the browser" — the
  language, the licensing, and the rendering architecture all block
  it. Feeding this project's own ASL data into MMS Player's Blender
  pipeline instead was offered as an option but not chosen — it would
  mean authoring into an unfinished research prototype's dictionary
  format and still building a from-scratch browser renderer for its
  output, a large, uncertain undertaking with no guarantee of a better
  result than what's already here.

What the user chose instead: keep this real-ASL-motion browser avatar,
but adopt two of MMS's actual conceptual contributions — its
"gloss + timing + inflection" idea of parametrically modifying *real*
captured signs rather than only ever replaying them at fixed timing:

1. **Phrase-final hold lengthening.** ASL prosody research (e.g.
   Wilbur's work on stress/prosodic structure in ASL) documents that
   the last sign in a sentence is held measurably longer than the same
   sign mid-sentence — the same "final lengthening" spoken languages
   show at phrase boundaries. [gloss.py](gloss.py) marks each
   sentence's last token `"phrase_final": true`; the frontend
   ([sign_animation.js](../static/js/sign_animation.js),
   `PHRASE_FINAL_HOLD_MULTIPLIER = 1.4`) holds that sign's own real
   final captured frame 40% longer after it finishes — never slowing
   down or altering the real articulated motion itself, only how long
   it's held at the end, matching MMS's own "Duration"/"Hold" example
   category.
2. **Honest disclosure of unsignable words**, instead of silently
   dropping them. MMS's dictionary treats numbers as their own
   grammatical category (dedicated `Numbers-0-19` etc. examples) — a
   reminder that ASL numbers use dedicated handshapes, not
   letter-by-letter fingerspelling, and this project has no captured
   motion for them (the alphabet dataset is A-Z only, no digits).
   Rather than fabricate a number handshape (which nothing here has
   real data for) or silently drop the word, `text_to_gloss()` now
   returns an `"unsigned"` list per sentence, and the frontend shows a
   visible `⚠ "5" not signed` note next to the gloss breakdown — the
   gap is disclosed, not hidden.

### Pass 3: a real rigged/skinned mesh, researched and sourced properly

Before this pass, research was done into the systems the user
specifically asked about:

- **SiMAX** (the CORDIS article referenced): a proprietary commercial
  cloud translation service. No open-source component, nothing to
  build on. Ruled out.
- **JASigning / SiGML / CWASA** (University of East Anglia, CC-BY-SA):
  real and legitimate, but it animates from **HamNoSys/SiGML
  linguistic notation** hand-authored per sign by trained linguists —
  there is no comprehensive freely-available ASL SiGML dictionary at
  anything near this project's 220-word scale, and authoring it myself
  would mean guessing at linguistic notation, exactly the "don't
  invent signs" risk to avoid. Their avatar characters also aren't
  distributed as standalone files outside their own player. Ruled out.
- **The Kaggle "Indian Sign Language Animated Videos" dataset**: ISL is
  a **different language from ASL** — different grammar, different
  handshapes, not mutually intelligible. Not a resource for an ASL
  system; flagging this rather than silently mixing two unrelated sign
  languages together.
- **Ready Player Me**: their live avatar creator (`readyplayer.me`,
  `models.readyplayer.me`) is DNS-blocked in this sandbox, confirmed by
  direct testing — a custom-built avatar via their creator isn't
  reachable here. Their official open-source repo
  (`github.com/readyplayerme/rpm-unity-sdk-core`, **MIT licensed**,
  reachable via `raw.githubusercontent.com`) bundles
  `RPM_Template_Mesh.glb`, which was downloaded and inspected directly:
  a real sculpted/textured skinned mesh with a full
  `Hips→Spine→...→Shoulder→Arm→ForeArm→Hand` chain, 4-bone fingers (5
  fingers × 2 hands), real eye bones, and viseme morph targets. This is
  what `static/models/avatar.glb` now is.

**Honest limitation**: this is Ready Player Me's own bundled
default/template character (visibly male-presenting), not a
custom-built female persona — the interactive creator that would allow
choosing that is unreachable in this sandbox. What changed is the
**quality of the mesh and rig itself** (real geometry, real fabric
shading, a real finger/face skeleton), not the specific character
design. Swapping in a different RPM-compatible avatar later is
possible — see "Extending" below.

**Retargeting** ([static/js/sign_animation.js](../static/js/sign_animation.js),
`aimBoneAt`/`orientBoneTo`): bones are only ever *rotated*, never
repositioned — the standard, robust mocap technique, since a skinned
mesh deforms correctly through its existing skin weights as long as
rotations are reasonable. Two real bugs were caught and fixed via
visual testing in the browser while building this:

1. The bind-pose reference direction for each bone was initially
   sourced from this project's own "arms hanging down" rest
   coordinates instead of the *mesh's own actual bind pose* (a wide
   T-pose) — mathematically, that made the rest state always
   reproduce the mesh's raw T-pose regardless of the intended pose.
   Fixed by deriving the bind reference from each bone's own captured
   bind-pose world position (`avatar.bind[name].worldPos`), so the
   retargeting math is internally consistent.
2. Fingers held their last shape frozen after a sign ended (no data
   that frame) instead of relaxing — fixed by explicitly resetting
   hand/finger bones to the mesh's bind rotation when no real hand data
   is present for that frame (`resetHandToBind`).
3. The default camera framing (tuned for the earlier primitive figure)
   cropped hands during wide gestures like the real ASL "hello" motion,
   which reaches above head height — widened so the full real signing
   space stays in frame.

### Pass 4: female-presenting rig, systematic validation, and ASL question grammar

Three independent improvements on top of Pass 3, requested together:
a more human/less "basic demo" avatar, a real accuracy check (not just
"it looks smooth"), and non-manual facial grammar for questions.

**Avatar swap to a genuinely female-presenting rig.** Pass 3's mesh
(`RPM_Template_Mesh.glb`) is Ready Player Me's androgynous/male-leaning
default template. Reusing the same open-source, MIT-licensed
`readyplayerme/rpm-unity-sdk-core` repo, `Feminine.fbx` was sourced
instead — a full humanoid rig with genuinely gendered body proportions
(narrower shoulders, different hip/waist ratio) rather than a shared
generic frame. This is now `static/models/avatar_feminine.fbx`, loaded
via a newly vendored `FBXLoader.js`
(`static/js/vendor/loaders/FBXLoader.js`, plus its `fflate`/NURBS
dependencies). Three real technical issues came up switching formats,
each caught by inspecting the parsed file directly rather than assumed
away:

1. **Duplicate bone nodes.** FBX export produces two scene-graph nodes
   with the same name (e.g. two `LeftArm` nodes at the same world
   position, one wrapping the other) — a plain `root.traverse()` bone
   lookup would silently grab the wrong one for some bones. Fixed by
   reading bones exclusively from `skinnedMesh.skeleton.bones` (the
   array Three.js actually uses to deform the mesh, guaranteed unique
   and correctly parented) instead of scene traversal.
2. **Unit mismatch.** The FBX is authored in centimeters (a shoulder
   height around 143 units); this project's motion data is in meters.
   Fixed with `root.scale.setScalar(0.01)` after load.
3. **No morph targets.** Confirmed by direct inspection
   (`morphTargetDictionary` is `null`) — unlike Pass 3's mesh, this rig
   ships no viseme blendshapes at all. The mouth is instead a small
   procedural overlay mesh parented to the `Head` bone (same pattern
   already used for the eyebrow/eyelid overlays in Pass 2/3), driven by
   the same real mouth-open/mouth-width data — see
   `attachFaceOverlays()`/`applyFaceMetrics()`.

**Systematic validation, not a visual spot-check.**
[validate_animations.mjs](validate_animations.mjs) checks every one of
the 220 word files and 26 letter files against the same real captured
data the browser's retargeting math actually consumes: non-finite
values, frame-to-frame wrist teleports, handedness (left/right hand
data landing on the correct side of the body), and finger-curl
plausibility. Run it with:

```bash
node sign_animation/validate_animations.mjs
```

This is a real check that found a real bug, not a rubber stamp: the
first run flagged 12/220 words (`basketball`, `bowling`, `chat`,
`cool`, `corn`, `example`, `fat`, `hair`, `hat`, `laugh`, `like`,
`many`) for a wrist position that jumps 0.6–0.8m in a single frame —
almost certainly a MediaPipe depth mis-detection for one frame, not
real motion. The first fix attempt
([smooth_outliers.py](smooth_outliers.py)) was too blunt: alongside a
correct targeted detector, it also applied one fixed global step-size
cap to *every* landmark in *all 220 words*, which touched over 40,000
points — almost certainly damping real fast motion in the 208 words
that were never flagged as a problem, with no saved baseline to check
against. That was caught by re-checking the change's actual scope
instead of trusting that the validator would go green, exactly the
kind of "don't claim it's correct just because it looks smooth" check
this pass was asked to apply to itself. The fix: regenerate every
word's animation data fresh from the original, untouched source video
(`build_word_animations.py`), then apply a single, principled
per-word/per-landmark **adaptive** threshold (median + 6×
median-absolute-deviation of that landmark's own step sizes within
that specific word) that only repairs a frame confirmed anomalous on
*both* sides (the step in **and** the step out), via linear
interpolation across just that anomalous run — so a real fast
sentence-boundary motion is never mistaken for a glitch.

Re-running the full pipeline (regenerate from source → adaptive
repair → validate) leaves **209/220 words clean**, up from 208/220
before any of this pass's work, having touched only 527 points across
84 words (versus the discarded first attempt's 40,343 points across
all 220). **11 words remain flagged** for a large single-frame wrist
jump: `basketball`, `bowling`, `chat`, `corn`, `example`, `fat`,
`form`, `hair`, `laugh`, `like`, `many`. These were investigated
directly rather than assumed fixable: plotting the raw wrist
trajectory (e.g. `chat`'s left wrist: steady around z≈0.3–0.4 for nine
frames, then z≈1.25 for the rest of the clip, while x/y move smoothly
throughout) shows a genuine MediaPipe **Z/depth estimation regime
shift** — X/Y stay continuous, only Z jumps and then holds at the new
value, which is a known MediaPipe weakness (Z is a monocular estimate,
far less reliable than the directly-observed X/Y), not a spike that
returns to normal. Because it doesn't return, the adaptive repair's
"both neighboring steps must be anomalous" rule correctly leaves it
alone (repairing a value that keeps going, instead of bouncing back,
risks cutting into real motion). A second, physically-motivated
approach was tried and explicitly rejected before touching any data:
capping frame-to-frame speed at a generous 5 m/s (real ASL wrist speed
rarely exceeds ~3 m/s) — a dry run showed this would flag over 8,700
point-steps across 218/220 words, meaning normalized "avatar-space"
motion routinely exceeds naive human-speed priors and an absolute
velocity cap can't distinguish it from genuine fast signing. Rather
than risk repeating the first over-broad smoothing mistake, these 11
words are left as-is and disclosed here and in "Known limitations"
below, instead of silently claiming the data is fully clean.

**Real ASL non-manual question grammar.** Documented ASL linguistics
(e.g. Baker-Shenk & Cokely; Neidle et al.) mark yes/no questions with
**raised eyebrows** and a forward head tilt held through the whole
question, and WH-questions (`what/where/when/why/who/how`) with
**lowered/furrowed eyebrows** plus the same forward tilt — genuinely
different markers, not one generic "question face." `gloss.py`
classifies each sentence as `statement` / `yn_question` / `wh_question`
(`SENTENCE_TYPE`), and `static/js/sign_animation.js` holds the
matching eyebrow offset and head-tilt rotation for that sentence's full
duration, layered additively on top of the real per-frame head/eyebrow
data from `applyFaceMetrics()` — never overriding real motion, only
adding the grammatical marker on top of it.

### Pass 2: real face, head orientation, and gaze

### Upgrade pass: real face, head orientation, and gaze

The first version only animated pose + both hands. This pass adds a
curated 21-point subset of MediaPipe Holistic's face mesh (including
the two iris landmarks, via `refine_face_landmarks=True` — confirmed
to cost *zero* extra inference time, since Holistic already computes
the full face internally) — see `FACE_POINTS` in
[landmarks3d.py](landmarks3d.py). From those real points,
[static/js/sign_animation.js](../static/js/sign_animation.js)
computes, every frame:

- **Head orientation** — a real rotation (turning, tilting, nodding),
  from an orthonormal basis built out of the cheek-to-cheek and
  chin-to-forehead vectors. Not simplified to "always facing camera."
- **Eyebrow raise, eye openness (blink), mouth shape** — real
  landmark distances, normalized by eye width so they stay meaningful
  across clips of different scale.
- **Gaze direction** — real iris position relative to the eye corners,
  not simplified to "always looking at camera." (It isn't fully
  independent of head orientation, though — see Known limitations.)

Also reworked in this pass: human-proportioned capsule limbs instead
of bare cylinders (a real bug was caught and fixed here — the first
version baked a radius into both the geometry *and* the per-frame
scale, squaring it into an almost-invisible sliver), a torso/hair/
clothing silhouette, studio lighting + backdrop, a wider camera framing
so raised hands don't crop out of frame, and frame-to-frame
interpolation during playback (not just snapping to the nearest
captured frame) for smoother perceived motion from the same real data.

## The gloss layer — not word-by-word translation

[gloss.py](gloss.py) turns input text into a sequence of signable
tokens instead of a literal per-word translation:

- Splits into sentences, expands contractions, strips punctuation.
- Drops English function words ASL conventionally omits (articles,
  copula "be" forms, empty "do/does/did").
- **Explicitly preserves negation** ("not"/"n't") — this is the one
  function word that must never be dropped, since removing it inverts
  the sentence's meaning.
- Reorders WH-questions (`what/where/when/why/who/how`) to the end of
  the sequence, matching real ASL gloss convention, instead of English
  word order (`"What is your name?"` → `name` `what`, not
  `what` `name`).
- Maps each remaining word to a known sign (if it's one of the 220
  words in [word_level/data/labels.json](../word_level/data/labels.json))
  or falls back to fingerspelling it letter-by-letter.

This is a documented, deliberately simplified heuristic — real ASL
grammar (topic-comment structure, classifiers, spatial referencing,
non-manual markers) is a genuine linguistics research problem, not
something a rule-based function can fully capture. The point is that
it demonstrably does *not* just translate word-by-word (see the
examples in "Verifying it works" below).

## Where the animation data comes from

- `sign_animation/build_word_animations.py` — for each of the 220
  words, takes the exact same representative clip
  [word_video_lookup.py](../word_video_lookup.py) already serves for
  video preview elsewhere in the app, runs MediaPipe Holistic over
  every frame, and remaps the raw coordinates into a stable
  human-proportioned "avatar space" (see
  [landmarks3d.py](landmarks3d.py) — centered on the hip midpoint of
  the first well-detected frame, Y-up, scaled to ~1.7 units tall).
  This is deliberately *not* the same normalization
  [word_level/landmarks.py](../word_level/landmarks.py) uses for
  classification, which re-centers every frame independently and
  would flatten/distort real body proportions.
- `sign_animation/build_letter_animations.py` — one static held
  hand-shape per letter, from the same source image
  [alphabet/prepare_assets.py](../alphabet/prepare_assets.py) uses.
  Fingerspelling genuinely *is* a sequence of held letter shapes, so a
  static frame per letter is accurate, not a shortcut.
- Output: small per-word/per-letter JSON files in `data/words/` and
  `data/letters/`, fetched on demand by the frontend (not one giant
  bundle) via `/api/sign-animation/word/<word>` and
  `/api/sign-animation/letter/<letter>` in [app.py](../app.py).
- `sign_animation/fetch_mocap_words.py` — for 30 of the 220 words (see
  "Pass 6"), downloads a real professional motion-capture FBX clip
  from the Studio Galt Sign Language Mocap Archive instead, recorded
  with dedicated mocap hardware rather than estimated from video. This
  is a *preferred alternative* source for the words it covers, not a
  replacement for the pipeline above — `gloss.py` picks whichever data
  a given word actually has.

Rebuild after changing the word-level vocabulary or the alphabet
dataset:

```bash
source .venv/bin/activate
python sign_animation/build_word_animations.py
python sign_animation/build_letter_animations.py
```

## Frontend

[templates/sign_animation.html](../templates/sign_animation.html) +
[static/js/sign_animation.js](../static/js/sign_animation.js). Three.js
is vendored locally into `static/js/vendor/` (no CDN dependency at
runtime). The avatar is redrawn every frame directly from landmark
positions — spheres at each joint, cylinders connecting them per a
fixed connection list matching MediaPipe's own pose/hand topology —
which is what makes it robust: there's no bone-rig calibration or
retargeting math that could go wrong, it's simply plotting real
captured 3D points.

Playback: fetches the full gloss's animation data up front, then plays
each word at its real captured frame rate, holds each fingerspelled
letter briefly, blends (~150ms linear interpolation) between
consecutive signs so the avatar doesn't teleport, and returns to a
neutral rest pose between sentences and at the end. Play/Pause/Replay
and a speed slider are provided; drag to orbit the camera.

## Verifying it works

```bash
python -c "
import sys; sys.path.insert(0, 'sign_animation')
import gloss
print(gloss.text_to_gloss('What is your name?'))
print(gloss.text_to_gloss('I am not hungry.'))
"
```

The first should show `what` moved to the end; the second should show
`not` preserved (not dropped) even though "am" is. Neither is a
literal word-by-word pass-through. Both also carry a `"type"` field
(`wh_question` for the first, `statement` for the second) driving the
non-manual eyebrow/head-tilt marker described in "Pass 4" above.

To validate the underlying captured motion data itself (not just the
gloss layer), run:

```bash
node sign_animation/validate_animations.mjs
```

To see which words currently use real mocap data versus this
project's own WLASL-derived data:

```bash
python -c "
import sys; sys.path.insert(0, 'sign_animation')
import config
print(sorted(config.mocap_words()))
"
```

To see Kozha/CWASA's real ASL vocabulary and test its SiGML
resolution directly (see "Pass 7"):

```bash
python -c "
import sys; sys.path.insert(0, 'sign_animation')
import kozha, gloss
print('Real signs:', kozha.available_glosses())
for t in ['hello', 'thank you', 'how are you', 'my name is Samridhi']:
    words = gloss.sentence_to_gloss_words(t, is_question=False)
    print(t, '->', 'eligible' if kozha.try_build_sigml(words) else 'not eligible')
"
```

See "Pass 4" above for what this checks and its current, honest
results (209/220 words clean).

## Known limitations

- **CWASA's own facial/non-manual detail is whatever its own SiGML
  data encodes** — it isn't driven by this project's own real ASL
  non-manual markers (Pass 4) or phrase-final timing (Pass 5); those
  are specific to this project's own avatar/data pipeline.
- **CWASA's camera framing and canvas sizing are CWASA's own
  defaults**, not tuned to match this project's own avatar framing —
  a cosmetic difference between the two avatars' presentation, not a
  functional one.
- **Kozha's real ASL data is only 14 signs**, self-described by Kozha
  as not yet Deaf-native reviewed, licensed CC BY-NC 4.0 (non-
  commercial) via ASL-LEX. It is used only as an addition alongside —
  never instead of — this project's own 250-word primary avatar.
- **Real mocap data (Pass 6) covers 30/220 words**, and its own
  creator states plainly they are a hearing, non-native ASL signer
  with no formal Deaf-community audit process — real captured motion
  from a real signer, not a guarantee of zero errors. The other
  190 words still use this project's own WLASL-derived data (see
  below), and words starting with letters the archive doesn't have yet
  (G, I, J, K, L, Q, R, S, U, X, Z) can't be matched at all regardless
  of vocabulary overlap.
- **Mocap-sourced signs have no facial data** — the archive's own
  motion capture is body/hand only for these entries, so the face
  stays at its neutral baseline (still receiving the real ASL
  non-manual question marker on top, just not per-word facial detail
  the way WLASL-derived words have from their own real video).
- **Entering/exiting a mocap-sourced sign is a direct cut** to/from the
  clip's own first/last frame, not smoothly interpolated the way two
  WLASL-derived signs blend into each other — the surrounding blend to
  a neutral rest pose still smooths the approach, only the final short
  hop onto the clip's own real first frame is a cut. A disclosed
  simplification, not a broken transition.
- **Character is Ready Player Me's own bundled `Feminine.fbx` template**
  (see "Pass 4"), not a custom character built to match any specific
  reference image — the interactive creator that would allow a custom
  design is unreachable from this sandbox (DNS-blocked). What changed
  across passes is the quality and now the gendered proportions of the
  mesh/rig itself, not a bespoke character design.
- **No native facial blendshapes at all on this mesh** (confirmed by
  direct inspection — `morphTargetDictionary` is empty). Eyebrows,
  eyelids, and mouth are all small procedural overlays parented to the
  real Head/Eye bones instead, driven by real captured data (mouth
  shape, eyebrow height) or real ASL grammar rules (question eyebrow
  marker — see "Pass 4"), not native mesh geometry — see
  `attachFaceOverlays()` in
  [static/js/sign_animation.js](../static/js/sign_animation.js).
- **No spine/torso lean** — only arms, hands, head, and face are
  retargeted; the torso stays at its bind orientation. Real ASL
  involves some upper-body shift, not captured here yet.
- **Gaze isn't fully independent of head orientation.** Real iris
  landmarks drive the gaze offset, but without eye-region-only tracking
  isolated from head pose, a big head turn will read as "looking that
  way" even if the eyes themselves didn't move much relative to the
  head. Directionally real, not lab-accurate.
- **Facial expression metrics use fixed normalization heuristics**
  (e.g. what counts as a "neutral" eyebrow height), not a per-signer
  calibrated baseline — real relative motion within a clip is accurate,
  but the absolute rendered intensity is an approximation.
- Each sign uses one representative clip; natural variation between
  repeated signings of the same word isn't captured.
- The gloss simplification is a heuristic (see above), not a
  linguistically complete ASL grammar model.
- Words outside the 220-word vocabulary are fingerspelled, which is
  correct ASL practice for unknown terms but reads much slower than a
  native sign for common words not yet in the vocabulary — see
  [word_level/README.md](../word_level/README.md) for how to add more.
- **Non-manual grammar covers only question marking** (eyebrows + head
  tilt for yes/no vs. WH questions — see "Pass 4"). Real ASL uses
  non-manual markers for far more than questions (topic marking,
  conditionals, adverbial mouth morphemes, role shift via body/gaze,
  intensity); those aren't modeled here.
- **Numbers aren't signed at all** — ASL numbers use dedicated
  handshapes this project has no captured motion for (the alphabet
  dataset is A-Z only), so they're disclosed as `unsigned` rather than
  fingerspelled or invented (see "Pass 5"). Adding real captured
  number handshapes later would let `word_to_token()` in
  [gloss.py](gloss.py) map them like any other known word.
- **Phrase-final lengthening (Pass 5) is a single fixed 1.4x hold**,
  not a graded/context-sensitive duration the way real ASL prosody
  varies it by emphasis, sentence length, and register.
- **11/220 words still show one large single-frame wrist jump each**
  (`basketball`, `bowling`, `chat`, `corn`, `example`, `fat`, `form`,
  `hair`, `laugh`, `like`, `many`) — a genuine MediaPipe Z-depth
  estimation artifact (see "Pass 4"), confirmed by inspection to be a
  regime shift rather than a spike-and-return, and confirmed (by a
  rejected dry run) not to be safely separable from real fast motion
  with a simple automated rule. Run
  `node sign_animation/validate_animations.mjs` any time to see the
  current, honest list rather than assuming it's clean.
