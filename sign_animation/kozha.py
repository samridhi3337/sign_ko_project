"""
Resolves gloss words against the real Kozha/CWASA ASL sign data and
builds a SiGML document for CWASA's own player to render -- ported
directly from Kozha's own reference implementation
(extension/panel.js: glossBase/loadSigmlXml/resolveGloss/
fingerspellWord/buildSigml), not reimplemented from scratch, per the
project owner's explicit instruction to reuse Kozha's actual logic.

Source data (unmodified, vendored as-is):
  - data/kozha/American_SL_ASL.sigml -- 14 real ASL signs, HamNoSys/
    SiGML, sourced from ASL-LEX 2.0 (CC BY-NC 4.0) via the Kozha
    project (MIT-licensed pipeline/code; the DATA license is CC BY-NC,
    separate from Kozha's own code license -- see README "Pass 7").
  - data/kozha/asl_alphabet_sigml.sigml -- real ASL fingerspelling
    handshapes for A-Z, same source.

This is a SEPARATE, ADDITIONAL pipeline from this project's own
220+30-word avatar (see gloss.py/config.py) -- it is only used for a
whole request when EVERY word in it can be satisfied by this real,
tiny, verified-as-real (if not yet Deaf-reviewed -- see README)
dataset, so a request is never split across two different avatars
mid-playback. Everything else keeps using this project's own,
much larger, already-tested pipeline exactly as before.
"""

import os
import re
import xml.etree.ElementTree as ET

import config

_gloss_to_xml = None   # lowercase gloss / normalized base -> <hns_sign> XML string
_letter_to_xml = None  # "A".."Z" -> <hns_sign> XML string
_primary_glosses = None  # ordered list of the actual gloss= attribute values


def _glossbase(gloss):
    """Port of Kozha's own extension/panel.js glossBase(): strips
    parentheticals, trailing sense-numbers, and punctuation so close
    gloss variants (e.g. "THANK-YOU" vs "thank you") still match."""
    g = gloss.lower()
    g = re.sub(r"\(.*?\)", "", g)
    g = re.sub(r"#\d+$", "", g)
    g = re.sub(r"\d+[a-z]?\^?$", "", g)
    g = re.sub(r"^_num-", "", g)
    g = re.sub(r"_\(.*?\)", "", g)
    g = re.sub(r"[^a-z0-9]+", " ", g)
    return g.strip()


def _element_outer_xml(el):
    return ET.tostring(el, encoding="unicode")


def _load():
    global _gloss_to_xml, _letter_to_xml, _primary_glosses
    if _gloss_to_xml is not None:
        return

    _gloss_to_xml = {}
    _letter_to_xml = {}
    _primary_glosses = []

    sigml_path = os.path.join(config.KOZHA_DIR, "American_SL_ASL.sigml")
    if os.path.exists(sigml_path):
        tree = ET.parse(sigml_path)
        for sign in tree.getroot().findall(".//hns_sign"):
            raw_gloss = (sign.get("gloss") or "").strip()
            gloss = raw_gloss.lower()
            if not gloss:
                continue
            xml_str = _element_outer_xml(sign)
            _gloss_to_xml[gloss] = xml_str
            _primary_glosses.append(raw_gloss)
            base = _glossbase(gloss)
            if base and base != gloss:
                _gloss_to_xml.setdefault(base, xml_str)

    alphabet_path = os.path.join(config.KOZHA_DIR, "asl_alphabet_sigml.sigml")
    if os.path.exists(alphabet_path):
        tree = ET.parse(alphabet_path)
        for sign in tree.getroot().findall(".//hns_sign"):
            gloss = (sign.get("gloss") or "").strip()
            if len(gloss) == 1 and gloss.isalpha():
                _letter_to_xml[gloss.upper()] = _element_outer_xml(sign)


def available_glosses():
    """The real ASL words this pipeline can render as an actual sign
    (not fingerspelled) -- for display/debugging, matches gloss.py's
    mocap_words()-style introspection helper."""
    _load()
    return sorted(_primary_glosses)


def _resolve_gloss(word):
    _load()
    w = word.lower().strip()
    if w in _gloss_to_xml:
        return _gloss_to_xml[w]
    base = _glossbase(w)
    return _gloss_to_xml.get(base)


def _fingerspell(word):
    _load()
    blocks = []
    for ch in word.upper():
        if ch in _letter_to_xml:
            blocks.append(_letter_to_xml[ch])
    return blocks


def try_build_sigml(words):
    """
    words: an ordered list of already-cleaned content words (function
    words already dropped) for ONE full request -- see gloss.py's
    sentence_to_gloss_words for the same cleaning this project's own
    pipeline already applies, reused here for consistency.

    Tries a 2-word phrase match first (e.g. "thank","you" ->
    THANK-YOU), matching how a human gloss like "thank you" is one
    ASL sign, not two -- falling back to single-word gloss match, then
    real fingerspelling. If literally every word resolves to
    something real (a sign or at least one fingerspelled letter),
    returns the full SiGML document string exactly as Kozha's own
    buildSigml() assembles it (one <sigml> root, CWASA sequences and
    times the contained signs itself). Returns None if any word has
    nothing real to render (so the caller falls back entirely to this
    project's own 250-word pipeline for the WHOLE request, rather than
    ever mixing two different avatars in one playback).
    """
    _load()
    if not words:
        return None

    blocks = []
    i = 0
    n = len(words)
    while i < n:
        matched = None

        if i + 1 < n:
            phrase = f"{words[i]} {words[i + 1]}"
            matched = _resolve_gloss(phrase)
            if matched:
                blocks.append(matched)
                i += 2
                continue

        matched = _resolve_gloss(words[i])
        if matched:
            blocks.append(matched)
            i += 1
            continue

        spelled = _fingerspell(words[i])
        if not spelled:
            return None  # nothing real to render this word with at all
        blocks.extend(spelled)
        i += 1

    if not blocks:
        return None

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<sigml>\n'
        + "\n".join(blocks)
        + "\n</sigml>"
    )
