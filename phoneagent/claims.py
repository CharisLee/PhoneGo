"""Check an answer's numbers against what the run actually saw.

The agent finished by returning whatever ``finish`` said. Nothing looked at the
claim itself -- and the claims are almost always numbers: 人均 ¥92, 评分 4.8, 车费
11 元起. A vision model misreading 192 as 92 is invisible to the user, because the
page it read is already gone.

This is not a proof. It answers one narrow question: does this figure appear in
what the run wrote down, or on the screen right now? A figure that appears
nowhere is still worth saying out loud, in the answer, rather than passing it
off as read.
"""
from __future__ import annotations

import re

#: What can be checked at all. Times ("30 分钟") and distances are left out on
#: purpose: they are computed by the app being read, not copied from the page.
PRICE = re.compile(r"[¥￥]\s*(\d{1,6}(?:\.\d{1,2})?)")
YUAN = re.compile(r"(\d{1,6}(?:\.\d{1,2})?)\s*元")
#: "15分钟" is a duration, not a rating: the first version read it as 5分.
RATING = re.compile(r"(?:评分|得分|rating)\s*[:：]?\s*(\d(?:\.\d)?)"
                    r"|(?<![\d.])(\d(?:\.\d)?)\s*分(?!钟)")
NAME = re.compile(r"「([^」\n]{2,24})」")

#: A name inside 「」 is usually a claim, but these are the model talking about
#: its own flow, not something on a page.
NOT_A_NAME = {"继续", "算了", "好了", "继续做", "继续吧", "重试", "下一步"}

MAX_CLAIMS = 12


def _number_probe(amount: str) -> re.Pattern:
    """A number with no digit on either side: 92 must not match 192 or 9.2."""
    return re.compile(rf"(?<![\d.]){re.escape(amount)}(?![\d.])")


def extract(answer: str) -> list[dict]:
    """The checkable claims in an answer, in the order they appear."""
    found: list[dict] = []
    seen: set = set()

    def add(kind: str, raw: str, probe: str) -> None:
        key = (kind, probe)
        if key in seen or len(found) >= MAX_CLAIMS:
            return
        seen.add(key)
        found.append({"kind": kind, "raw": raw, "probe": probe})

    for match in PRICE.finditer(answer):
        add("price", match.group(0), match.group(1))
    for match in YUAN.finditer(answer):
        add("price", match.group(0), match.group(1))
    for match in RATING.finditer(answer):
        amount = match.group(1) or match.group(2)
        if not amount:
            continue
        # "45 小时 0 分" is a duration, not a rating. The regex cannot see the
        # word before it, so the check happens here.
        around = answer[max(0, match.start() - 4):match.start()]
        if "小时" in around:
            continue
        add("rating", match.group(0), amount)
    for match in NAME.finditer(answer):
        name = match.group(1).strip()
        if not name or name in NOT_A_NAME or name.isdigit():
            continue
        # A list inside 「」 ("0 分、省电与电池") is prose the model wrote, not a
        # label copied off a page: page titles do not carry separators.
        if any(sep in name for sep in "、，,；;"):
            continue
        add("name", name, name)
    return found


def verify(answer: str, sources, given: str = "") -> tuple[list[dict], list[str]]:
    """Split the claims into "seen somewhere" and "nowhere".

    ``sources`` are the texts worth trusting: what the run wrote into its
    workspace, and what is on the screen now. ``given`` is what the user asked
    for -- a figure copied from there ("人均100左右") is not a claim the page has
    to prove, and flagging it was the first version's false alarm.
    """
    joined = "\n".join(str(s) for s in sources if s)
    if not joined:
        return [], []
    claims = extract(answer)
    if not claims:
        return [], []
    checked: list[dict] = []
    missing: list[str] = []
    asked = set()
    for claim in extract(given) if given else []:
        asked.add(claim["probe"])
    if given:
        # "人均100左右" carries no ¥ and no 元, so it read as no claim at all --
        # every bare number in the instruction is something the user said, not
        # something the page has to prove.
        for number in re.finditer(r"\d{1,6}(?:\.\d{1,2})?", given):
            asked.add(number.group(0))
    for claim in claims:
        if claim["probe"] in asked:
            continue
        if claim["kind"] == "name":
            hit = claim["probe"] in joined
        else:
            hit = _number_probe(claim["probe"]).search(joined) is not None
        if hit:
            checked.append(claim)
        else:
            missing.append(claim["raw"])
    return checked, missing
