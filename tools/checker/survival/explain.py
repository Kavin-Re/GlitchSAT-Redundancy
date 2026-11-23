"""Why a countermeasure broke and the smallest change that keeps it. Text a designer can act on.

The cause is inferred from the evidence of the stage and, when the config names the Yosys script (or the flow's
command line), from the commands in it. With Yosys installed, `--bisect` replaces the inference by a measurement:
the script is re-run one command at a time and the first command after which the verdict changes is reported
(survival/bisect.py).
"""
import re

from .model import SURVIVED, NOT_CHECKED

HARDEN = "ext/harden"


def _script_facts(script):
    if not script:
        return {}
    cmds = [c.strip() for c in re.split(r"[;\n]", re.sub(r"#[^\n]*", "", script)) if c.strip()]
    names = [c.split()[0] for c in cmds]
    f = dict(cmds=cmds)
    if "flatten" in names:
        i = names.index("flatten")
        after = cmds[i + 1:]
        f["opt_merge_after_flatten"] = next((c for c in after if c.split()[0] in ("opt_merge", "opt", "synth", "opt_expr") and "-nomerge" not in c
                                             and c.split()[0] in ("opt_merge", "opt", "synth")), None)
        f["abc_after_flatten"] = next((c for c in after if c.split()[0] == "abc"), None)
    for c in cmds:
        if c.split()[0] == "synth" and "-flatten" in c:
            f["opt_merge_after_flatten"] = f["abc_after_flatten"] = c
        if c.split()[0] == "synth" and "-nofsm" not in c:
            f["fsm"] = c
        if c.split()[0] in ("fsm", "fsm_recode"):
            f["fsm"] = c
        if c.split()[0] == "abc" and "-dff" in c:
            f["abc_dff"] = c
        if c.split()[0] in ("opt_dff", "opt") and "-nodffe" not in c:
            f.setdefault("opt_dff", c)
    return f


def explain(cm, res, stage):
    """Fill res.cause and res.fix for a result that is not SURVIVED."""
    if res.verdict in (SURVIVED, NOT_CHECKED):
        return res
    facts = _script_facts(stage.get("script_text"))
    m = res.measured
    kind = stage.get("kind")
    if cm.kind in ("redundant_copies", "complement_pair") and kind == "netlist":
        inst = cm.intent.get("instances") or []
        cell = cm.intent.get("cell")
        if res.verdict == "UNTRACKED":
            res.cause = ("The checker could not find the copies here. Without an unoptimised netlist of the RTL it knows "
                         "the instance names but not the function, and this netlist kept no names.")
            res.fix = ["Add a stage with the unoptimised netlist (Yosys: `proc; flatten; techmap; write_json`), or run "
                       "with Yosys installed so the checker makes it, or keep hierarchy names in the flow."]
            return res
        if m.get("distinct_nets", 0) <= 1 and not m.get("shared_cells"):
            step = facts.get("opt_merge_after_flatten")
            res.cause = ("Identical logic with identical inputs was merged into one copy (common-subexpression "
                         "elimination). " + (f"The script runs `{step}` after `flatten`: once the copies are in one "
                                             "module, `opt_merge` treats them as duplicates." if step else
                                             "In Yosys this is `opt_merge` (also inside `opt` and `synth`) once the copies "
                                             "are in one module, or structural hashing in ABC when the copies are "
                                             "optimised together."))
        elif m.get("shared_on_inputs"):
            res.cause = ("The copies read their inputs through the same cells (shared buffers or input logic in front of "
                         "the copies): one fault on such a cell reaches every copy.")
        else:
            step = facts.get("abc_after_flatten") or facts.get("abc_dff")
            res.cause = ("The copies were optimised together and now share gates. " +
                         (f"The script runs `{step}` on the flattened design, so ABC sees all copies at once and "
                          "shares their common sub-expressions." if step else
                          "This happens when technology mapping (ABC) runs after `flatten`, or with `abc -dff`."))
        res.fix = []
        if cell:
            res.fix.append(f"RTL: put `(* keep_hierarchy *)` on module `{cell}` and map before flattening "
                           "(`abc` per module, then `flatten`), with no `opt_merge`/`opt`/`synth` after the flatten.")
        res.fix.append("Constraint: mark each copy's cells `keep` / `dont_touch` before any pass that sees more than one "
                       "copy (Yosys: `setattr -set keep 1 " + (" ".join(f"{i}/*" for i in inst[:3]) or "<copy>/*") +
                       "`; Design Compiler / Genus: `set_dont_touch` on the copy instances).")
        res.fix.append(f"{HARDEN}: `glitchsat harden design <design> --goal N --out fixes/` writes a Yosys script with this "
                       "copy-separation guard; `glitchsat harden netlist <netlist.json> --groups ...` duplicates the "
                       "shared gates of an existing netlist (\"remove single points\").")
        if m.get("shared_on_inputs"):
            res.fix.insert(0, "Give every copy its own input path: buffer the inputs per copy (and mark those buffers "
                              "`keep`), or disable buffer sharing in front of the copies.")
    elif cm.kind in ("redundant_copies", "complement_pair") and kind == "placement":
        res.cause = (f"Placement put cells of different copies next to each other: {m.get('r_pair_um')} um is enough to "
                     f"reach two copies and {m.get('r_all_um')} um to reach all of them. Placers minimise wire length, "
                     "and copies that read the same inputs are pulled together.")
        res.fix = ["Placement constraint: one region (OpenROAD `create_region`/`place_cell` fences, Innovus "
                   "`createInstGroup` + `createRegion`, ICC2 `create_bound -exclusive`) per copy, at least "
                   f"{2 * float(stage.get('spot_radius_um', 0.5)):.2f} um apart edge to edge (twice the spot radius), "
                   "including the cells each copy alone drives.",
                   "The repository's pinned layouts (research/c4/l2_inputs: v8, s8, v15, rr) show the effect; "
                   "ext/shots gives the number of shots for each radius."]
    elif cm.kind == "sparse_encoding" and kind == "placement":
        res.cause = ("The state flops in which two codes differ sit inside one spot of the configured radius.")
        res.fix = ["Spread the state flops (placement region per group of flops), or choose codes whose differing bits "
                   f"are in flops that are far apart; {HARDEN} `--allow encoding` searches other code words."]
    elif cm.kind == "sparse_encoding":
        if m.get("recoded") or res.verdict == "UNTRACKED":
            step = facts.get("fsm")
            res.cause = ("The state register was re-encoded by FSM extraction" +
                         (f" (`{step}` runs the `fsm` passes)." if step else " (Yosys `fsm`/`fsm_recode`, part of `synth`; "
                          "other tools: FSM compilation/`fsm_auto_inferring`).") +
                         " The tool picks its own code words (binary or one-hot), so the distances written in the RTL are gone.")
            res.fix = [f"RTL: `(* fsm_encoding = \"none\" *)` on register `{cm.intent.get('register')}` "
                       "(Yosys also accepts `(* fsm_encoding = \"user\" *)`), or run `synth -nofsm`.",
                       "Design Compiler: `set_fsm_encoding_style none` / do not run `extract`; Vivado: "
                       "`(* fsm_encoding = \"none\" *)` or `-fsm_extraction off`; Genus: `set_db fsm_encoding none`.",
                       "OpenTitan style: instantiate the state register as its own module (prim_sparse_fsm_flop) and "
                       "mark it `dont_touch`/`keep_hierarchy`."]
        else:
            res.cause = ("The register still exists, but the set of codes it can reach on this netlist has a smaller "
                         "minimum Hamming distance than the RTL constants.")
            res.fix = [f"Check the codes listed in the evidence against the RTL; {HARDEN}: `glitchsat harden design "
                       "<design> --allow encoding` searches code words that meet a fault goal."]
    elif cm.kind == "redundant_register":
        res.cause = ("Flops that always hold the same (or the complemented) value were merged or removed "
                     "(Yosys `opt_merge -share_all`, `opt_dff`, `opt_clean`; equivalent-register removal in other tools).")
        res.fix = ["Mark both registers `(* keep *)` (Yosys) / `dont_touch`, `preserve` (other tools) and disable "
                   "equivalent/inverted register merging for them "
                   "(DC: `set_register_merging <reg> false`; Vivado: `(* equivalent_register_removal = \"no\" *)`)."]
    elif cm.kind == "alarm":
        res.cause = ("The alarm compares signals that the tool proved equal (after merging the redundant copies, "
                     "`a != a` is constant 0), so the alarm logic was removed as dead code.")
        res.fix = ["Fix the redundancy it observes first (the copies must stay separate); then keep the alarm cone: "
                   "`(* keep *)` on the compare nets, or `dont_touch` on the alarm logic."]
    elif cm.kind == "mubi":
        res.cause = "Several bits of the multi-bit value are now driven by one net, so one fault changes several bits."
        res.fix = ["Drive each bit from its own logic (`prim_buf`/`keep` per bit, as OpenTitan's prim_mubi senders do)."]
    elif cm.kind == "fw_repeated_check":
        res.cause = ("The compiler proved the repeated checks equivalent (same expression, nothing in between that it must "
                     "assume can change) and kept one: common-subexpression elimination and jump threading, enabled "
                     "from -O1/-O2 (-fgcse, -ftree-dominator-opts, LLVM GVN/EarlyCSE/SimplifyCFG).")
        res.fix = ["Compiler barrier: pass each checked value through an empty inline-asm barrier, as "
                   "ext/firmware/src/rom.h `LAUNDER(x)` (`__asm__ volatile(\"\" : \"+r\"(v))`, OpenTitan `launder32`), "
                   "once per check.",
                   "Or read the checked data through `volatile` (ext/firmware build mode `vol`). Both keep all "
                   "repeats at -O1, -O2 and -Os in ext/firmware's measurements.",
                   "Keep this check in CI: a compiler upgrade can undo a barrier that works today."]
    elif cm.kind == "fw_flow_counter":
        res.cause = ("The counter is an ordinary variable, so the compiler computed its final value at compile time and "
                     "folded the updates and/or the comparison.")
        res.fix = ["Launder the counter at every update and before the compare (ext/firmware/src/rom_cfi.c `CFI_INC` "
                   "with `LAUNDER`), or declare it `volatile`."]
    if not res.cause:
        res.cause = "No specific cause identified from the available evidence."
    return res
