# Responsible disclosure

GlitchSAT is a defensive tool. It analyses designs you own, or designs that are openly licensed, to help
harden them. This page says what the project does when its analysis points at a weakness in someone else's
work, and how to report a problem in GlitchSAT itself.

## 1. What a GlitchSAT result is, and is not

A result is a statement inside a model: "under fault model M, within these bounds, this goal can be reached
with these modelled faults". It is not a demonstrated attack on a device.

- The faults are modelled, not physical. No result in this repository was measured on hardware.
- Many results come from **open-flow builds**: an open synthesis tool, an open cell library, the project's
  own scripts. A weakness that appears only in such a build is a property of that build. It may be absent
  from the netlist a product ships with.

So the project never describes a result as "a vulnerability in project X" on the strength of a model run
alone.

## 2. If the tool points at a weakness in someone else's design or code

1. **Verify first.** Re-run from a clean checkout in the pinned environment. Replay the witness in an
   independent simulator. Write down the model, bounds, tool versions and input hashes.
2. **Find where it enters.** Is the weakness present in the source (RTL or source code), or does it appear
   only after a particular synthesis or compiler setting? Say which.
3. **Keep it private.** No public issue, post, talk, commit, test name or file name that identifies the
   weakness or its location. Material lives outside this repository until the steps below are complete. The
   repository's wording check refuses a list of withheld identifiers for this reason.
4. **Choose the channel by what was found.**
   - *Source-level weakness that could matter on real devices:* the affected project's own private security
     channel, as its security policy names it. If it has none, a private message to the maintainers asking
     where to send a report.
   - *Weakness seen only in an open-flow build:* a normal issue or discussion, worded "observed in the
     open-flow build with <tool, version, script>; please confirm with your production flow". It is not sent
     through a security channel unless the source itself is affected.
5. **Send a report the reader can check in minutes:** what was analysed (commit, files, build settings);
   the model and its limits in two sentences; the minimal reproduction; what is not known (no hardware
   test, a simulated result); a suggested fix if there is one.
6. **Agree on timing.** Publish nothing until the maintainers have fixed the issue, declined it, or an
   agreed date has passed. If no date is agreed, the default is 90 days from the first report. If there is
   no reply at all after two polite reminders, ask an experienced person for advice before doing anything
   else.
7. **Publish honestly afterwards.** Credit the maintainers' fix. State the model, the bounds and the fact
   that it was a modelled result. Remove the identifier from the withheld list only then.

Only the project owner contacts an affected project. Contributors and tools working in this repository do
not contact third parties about findings.

One study in this project (a bootloader's fault-hardening code, analysed in a simulator) is in step 3 at
the time of writing. Its details are deliberately absent from this repository.

## 3. What the project will not do

- Target products in the field, or designs it has no right to analyse.
- Publish step-by-step instructions for attacking a specific deployed device.
- Present a modelled result as a physical one, or a build artefact as a product weakness.
- Print lab ratings or scheme scores for anyone's design.

## 4. If you use GlitchSAT on your own design

Reports and SARIF files contain fault-attack paths for your design. Handle them as security-sensitive design
information. The tool makes no network calls; the continuous-integration action does not upload results by
default. Think before you attach a result file to a public issue.

## 5. Reporting a security problem in GlitchSAT itself

Use the repository's private vulnerability reporting ("Report a vulnerability" under the Security tab) once
it is enabled (backlog #034); until then, open an issue that says only "security report, please open a
private channel", with no details. Known at the time of writing, with fixes scheduled in the roadmap's
Phase 0.5: the installed command can import code from a parent folder of the current directory, so run it
only in folders you trust; Yosys is not sandboxed, so analyse only Verilog you trust. See `SECURITY.md`.

## 6. For teachers

Fault injection on devices you do not own, or against access controls, can be illegal where you live.
Classroom use of this project stays in simulation and on open designs. When you teach the true stories,
teach how each was reported and fixed as well as how it worked.
