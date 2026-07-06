"""Generation layer: turn an approved brief into structured assets via the LLM.

Each function returns a Python data structure (dict/list). The output layer renders +
writes. Keeping generation separate makes stages independently cacheable/resumable.
"""
from __future__ import annotations

import logging
from typing import Any

from factory.brief import OfferBrief
from factory.llm import LLMClient
from factory.prompts import checkout as ck
from factory.prompts import content_pack as cp
from factory.prompts import dm_automation as dm
from factory.prompts import product_package as pp

logger = logging.getLogger("factory.generators")


# --- Product & commercial scaffolding ----------------------------------------

def gen_product_package(llm: LLMClient, brief: OfferBrief) -> dict[str, Any]:
    logger.info("Generating product package...")
    return llm.generate_json(*pp.build_product_package(brief))


def gen_core_deliverables(llm: LLMClient, brief: OfferBrief) -> list[dict[str, Any]]:
    logger.info("Generating core deliverables...")
    return _as_list(llm.generate_json(*pp.build_core_deliverables(brief)))


def gen_bonus_deliverables(llm: LLMClient, brief: OfferBrief) -> list[dict[str, Any]]:
    logger.info("Generating bonus deliverables...")
    return _as_list(llm.generate_json(*pp.build_bonus_deliverables(brief)))


def gen_order_bump(llm: LLMClient, brief: OfferBrief) -> dict[str, Any]:
    logger.info("Generating order bump...")
    r = llm.generate_json(*pp.build_order_bump(brief))
    return r if isinstance(r, dict) else {"product": "none", "copy": "", "positioning": "", "delivery_method": ""}


# --- Content pack ------------------------------------------------------------

def gen_reels(llm: LLMClient, brief: OfferBrief, total: int = 30, batch: int = 10) -> dict[str, list]:
    ideas: list[dict] = []
    start, attempts = 1, 0
    while len(ideas) < total and attempts < total * 2:
        attempts += 1
        n = min(batch, total - len(ideas))
        logger.info("Reel ideas %d-%d", start, start + n - 1)
        got = _as_list(llm.generate_json(*cp.build_reel_ideas(brief, n, start)))[:n]
        if not got:
            break
        ideas.extend(got)
        start += len(got)
    scripts: list[dict] = []
    for i in range(0, len(ideas), batch):
        chunk = ideas[i:i + batch]
        logger.info("Reel scripts for %d ideas", len(chunk))
        scripts.extend(_as_list(llm.generate_json(*cp.build_reel_scripts(brief, chunk))))
    return {"ideas": ideas, "scripts": scripts}


def gen_carousels(llm: LLMClient, brief: OfferBrief, total: int = 15, batch: int = 8) -> list[dict]:
    out: list[dict] = []
    start, attempts = 1, 0
    while len(out) < total and attempts < total * 2:
        attempts += 1
        n = min(batch, total - len(out))
        logger.info("Carousels %d-%d", start, start + n - 1)
        got = _as_list(llm.generate_json(*cp.build_carousels(brief, n, start)))[:n]
        if not got:
            break
        out.extend(got)
        start += len(got)
    return out


def gen_posts(llm: LLMClient, brief: OfferBrief, post_type: str, total: int, batch: int = 8) -> list[dict]:
    out: list[dict] = []
    start, attempts = 1, 0
    while len(out) < total and attempts < total * 2:
        attempts += 1
        n = min(batch, total - len(out))
        logger.info("Posts (%s) %d-%d", post_type, start, start + n - 1)
        got = _as_list(llm.generate_json(*cp.build_posts(brief, post_type, n, start)))[:n]
        if not got:
            break
        out.extend(got)
        start += len(got)
    return out


def gen_all_posts(llm: LLMClient, brief: OfferBrief) -> dict[str, list]:
    return {
        "direct_pitch": gen_posts(llm, brief, "direct_pitch", 15),
        "nurture": gen_posts(llm, brief, "nurture", 15),
        "objection": gen_posts(llm, brief, "objection", 10),
        "proof": gen_posts(llm, brief, "proof", 10),
    }


def gen_story_prompts(llm: LLMClient, brief: OfferBrief, total: int = 10) -> list[dict]:
    logger.info("Generating story prompts...")
    return _as_list(llm.generate_json(*cp.build_story_prompts(brief, total)))


def gen_cta_captions(llm: LLMClient, brief: OfferBrief) -> list[dict]:
    logger.info("Generating CTA captions...")
    return _as_list(llm.generate_json(*cp.build_cta_captions(brief)))


def gen_dm_keyword_prompts(llm: LLMClient, brief: OfferBrief, keywords: list[str]) -> list[dict]:
    logger.info("Generating DM keyword map...")
    return _as_list(llm.generate_json(*cp.build_dm_keyword_prompts(brief, keywords)))


def gen_manychat(llm: LLMClient, brief: OfferBrief, keywords: list[str]) -> dict[str, Any]:
    logger.info("Generating ManyChat copy...")
    r = llm.generate_json(*cp.build_manychat(brief, keywords))
    return r if isinstance(r, dict) else {"flow_name": "", "trigger_keyword": "", "steps": [], "handoff_condition": ""}


# --- DM automation & checkout ------------------------------------------------

def gen_dm_automation(llm: LLMClient, brief: OfferBrief, keywords: list[str]) -> dict[str, Any]:
    logger.info("Generating DM automation sequence...")
    r = llm.generate_json(*dm.build_dm_automation(brief, keywords))
    return r if isinstance(r, dict) else {}


def gen_checkout(llm: LLMClient, brief: OfferBrief) -> dict[str, Any]:
    logger.info("Generating checkout assets...")
    r = llm.generate_json(*ck.build_checkout(brief))
    return r if isinstance(r, dict) else {}


# --- helpers -----------------------------------------------------------------

def collect_keywords(assets: dict[str, Any]) -> list[str]:
    """Pull every cta_keyword/keyword mentioned across generated content."""
    kws: list[str] = []

    def scan(obj: Any):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("cta_keyword", "keyword", "trigger_keyword") and isinstance(v, str):
                    kws.append(v)
                else:
                    scan(v)
        elif isinstance(obj, list):
            for item in obj:
                scan(item)

    for key in ("reels", "carousels", "posts", "story_prompts", "cta_captions"):
        scan(assets.get(key))
    return sorted({k.strip() for k in kws if k and k.strip() and k.lower() != "null"})


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        for key in ("items", "results", "data", "ideas", "scripts", "deliverables", "posts"):
            if isinstance(value.get(key), list):
                return [v for v in value[key] if isinstance(v, dict)]
        return [value]
    return []
