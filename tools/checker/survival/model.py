"""Data model: what a countermeasure is, and what a stage says about it."""
import dataclasses
import hashlib

SURVIVED, WEAKENED, REMOVED, UNTRACKED, NOT_CHECKED = "SURVIVED", "WEAKENED", "REMOVED", "UNTRACKED", "NOT_CHECKED"
ORDER = {SURVIVED: 0, NOT_CHECKED: 0, UNTRACKED: 1, WEAKENED: 2, REMOVED: 3}

KINDS = {
    "redundant_copies": "duplicated / triplicated logic",
    "sparse_encoding": "sparse state encoding",
    "mubi": "multi-bit boolean",
    "complement_pair": "complemented copy",
    "redundant_register": "redundant register / counter",
    "alarm": "alarm path",
    "fw_repeated_check": "firmware check repeated in source",
    "fw_flow_counter": "firmware control-flow counter",
}


@dataclasses.dataclass
class Countermeasure:
    id: str
    kind: str
    origin: str                 # rtl-scan | netlist-scan | annotation | yaml | c-scan
    where: str = ""             # file:line of the declaration, when known
    intent: dict = dataclasses.field(default_factory=dict)
    track: dict = dataclasses.field(default_factory=dict)   # filled at the first stage that resolves it

    def title(self):
        i = self.intent
        if self.kind == "redundant_copies":
            return f"{i.get('copies', '?')} copies of {i.get('what', 'one function')}"
        if self.kind == "sparse_encoding":
            d = i.get("min_distance")
            return f"register {i.get('register')} with {len(i.get('codes', []))} codes" + (f", distance {d}" if d else "")
        if self.kind == "redundant_register":
            return "registers " + " / ".join(i.get("registers", []))
        if self.kind == "alarm":
            return f"alarm {i.get('signal')}"
        if self.kind == "mubi":
            return f"multi-bit boolean {i.get('signal')}"
        if self.kind == "complement_pair":
            return f"complemented rails of {i.get('what', 'one function')}"
        if self.kind == "fw_repeated_check":
            return f"check `{i.get('condition')}` written {i.get('copies')} times in {i.get('function')}"
        if self.kind == "fw_flow_counter":
            return f"flow counter `{i.get('variable')}` in {i.get('function')}"
        return self.id

    def to_json(self):
        d = dataclasses.asdict(self)
        d["track"] = {k: v for k, v in self.track.items() if not k.startswith("_")}
        d["title"] = self.title()
        return d


@dataclasses.dataclass
class StageResult:
    cm: str
    stage: str
    verdict: str
    measured: dict = dataclasses.field(default_factory=dict)
    evidence: list = dataclasses.field(default_factory=list)
    cause: str = ""
    fix: list = dataclasses.field(default_factory=list)
    label: str = "MEASURED"     # MEASURED (read from the files) | SIMULATED (model output) | RECORDED

    def to_json(self):
        return dataclasses.asdict(self)


def worst(verdicts):
    v = [x for x in verdicts if x]
    return max(v, key=lambda x: ORDER[x]) if v else NOT_CHECKED


def fingerprint(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]
