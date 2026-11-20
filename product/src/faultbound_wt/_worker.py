"""Worker process for the hard wall-clock timeout: `python -m faultbound_wt._worker JOB.json OUT.json`.
The parent (runner.run_with_timeout) kills this process when the deadline passes, so a slow z3 model build cannot overrun it."""
import json, os, signal, sys, threading, time


def _die_with_parent():
    """H2 (N9): if the parent (the CLI) is killed, this worker must not keep running. A watcher thread polls the parent pid and then SIGKILLs the whole
    process group of this worker (the worker leads its own session), so its yosys/abc children go with it. (prctl PDEATHSIG is deliberately NOT used
    here: it would kill only the worker and leave yosys' abc child orphaned.)"""
    ppid = os.getppid()

    def poll():
        while True:
            if os.getppid() != ppid:
                try:
                    os.killpg(os.getpgrp(), signal.SIGKILL)   # also takes our yosys/abc children (same process group)
                except OSError:
                    os._exit(1)
            time.sleep(0.5)
    threading.Thread(target=poll, daemon=True).start()


def main(argv):
    _die_with_parent()
    job_path, out_path = argv[1], argv[2]
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    from . import runner
    from .config import Threat, ConfigError
    th = Threat(**job["th"])
    out = {}
    try:
        if job["kind"] == "analyze":
            def on_scope(prov, scope):   # early snapshot so a timeout report can still carry the scope block
                with open(out_path + ".scope", "w", encoding="utf-8") as g:
                    json.dump(dict(provenance=prov, scope=scope), g)
            out["result"] = runner.analyze(job["netlist"], th, command=job.get("command"), top=job.get("top"), on_scope=on_scope)
        elif job["kind"] == "synth_sweep":   # PS6
            from . import synth_sweep
            out["result"] = synth_sweep.synth_sweep(job["netlist"], th, top=job.get("top"), variants=job.get("variants"), cell_timeout_ms=job["cell_timeout_ms"],
                                                    command=job.get("command"), extra_variants=job.get("extra_variants"))
        else:
            out["result"] = runner.sweep(job["netlist"], th, masks=job.get("masks", []), cell_timeout_ms=job["cell_timeout_ms"],
                                         command=job.get("command"), top=job.get("top"), widths=job.get("widths", False), count_rules=job.get("count_rules"))
    except ConfigError as e:
        out = dict(exc="ConfigError", msg=str(e))
    except runner.InputError as e:
        out = dict(exc="InputError", msg=str(e))
    except ValueError as e:
        out = dict(exc="ValueError", msg=str(e))
    except BaseException as e:   # noqa: BLE001 - reported to the parent as an internal error, never as a verdict
        out = dict(exc=type(e).__name__, msg=str(e), internal=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
