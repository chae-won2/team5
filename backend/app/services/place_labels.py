"""Use reviewed official names and addresses; unknown translations stay Korean."""
import json
import re
from pathlib import Path

LABELS = json.loads(Path(__file__).with_name("official_place_labels.json").read_text(encoding="utf-8"))


def identity_text(value):
    return re.sub(r"\s+", "", value.replace("부산광역시", "부산"))


def official_labels(place_id, name, address, language):
    if language == "ko":
        return {}
    matches = [row for row in LABELS
               if (not place_id or row["id"] == place_id)
               and identity_text(row["name_ko"]) == identity_text(name)
               and identity_text(row["address_ko"]) == identity_text(address)]
    if len(matches) != 1:
        return {}
    return matches[0]["translations"].get(language, {})
