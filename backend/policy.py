import os
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "policies.yaml")


class PolicyRegistry:
    def __init__(self, path: str = _CONFIG_PATH):
        self._path = path
        self.reload()

    def reload(self):
        with open(self._path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f)
        self.version = self._raw["version"]
        self.geo_overrides = self._raw["geo_overrides"]
        self.use_cases = self._raw["use_cases"]

    def get(self, use_case: str) -> dict:
        if use_case not in self.use_cases:
            raise KeyError(f"Unknown use case '{use_case}'. Known: {list(self.use_cases.keys())}")
        return self.use_cases[use_case]

    def severity_multiplier(self, geo: str) -> float:
        override = self.geo_overrides.get(geo, self.geo_overrides["DEFAULT"])
        return override.get("pii_severity_multiplier", 1.0)

    def list_use_cases(self) -> list[dict]:
        return [{"key": k, "label": v["label"], "mode": v["mode"]} for k, v in self.use_cases.items()]


def decide(overall_score: float, thresholds: dict) -> str:
    if overall_score < thresholds["allow_below"]:
        return "allow"
    if overall_score < thresholds["edit_below"]:
        return "edit"
    if overall_score < thresholds["block_at"]:
        return "flag_for_review"
    return "block"
