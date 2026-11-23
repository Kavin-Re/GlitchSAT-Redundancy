# How we decide severity

Written from `SEVERITY_RULES` in `plain_findings.py` (one source for the app, the reports and this page).

| rule | how it works |
|---|---|
| Fewest glitches needed | 1 glitch: easiest. 2 glitches: harder (two precise hits). 3 or more: much harder. None found within the limits: Info. |
| What the attacker gets | Starting their own software, reading a key, taking over debug, opening a lock: high. Silencing an alarm or changing a step: medium. Only a crash: low. Taken from the goal of the check (`goal:` in the project file, the template, or the built-in study). Without a goal it is guessed from whole words of the signal names and the card says "please confirm"; with no match nothing is claimed and no comparison is given. |
| Base level | 1 glitch: Critical (high gain), High (medium gain), Medium (low gain). 2 glitches: High, Medium, Low. 3 or more: Medium, Low, Low. |
| Protection silently missing | If the source had a protection that the build tool or compiler removed, the level goes up by one (the designer believes it is there). |
| How sure we are | BOUNDED and SAMPLED results do not change the level, but the card says the real answer might be worse or better than shown. |
| Published attack-potential examples | PSA Certified Attack Methods v1.3, section 5.1.3, rates "a glitch required on each target device" at 20 points and "two successful glitches required" at about 21 to 23; no published example rates three or more glitches, so none is claimed here. No CVSS score is ever given. |
| No answer | A run that did not decide the question (an empty question, out of time, not run, the solver gave up, a tool error) is rated "Unknown — not checked", never Info or Low, and is counted on its own in the summary line. It is not a pass. |
| Always an estimate | Severity is our estimate for a modelled fault on a simulated chip or program, not a measured attack on real hardware. |

| level | icon | how urgent |
|---|---|---|
| Critical | `!!!` | Fix this before the design is made into a chip (or before the firmware ships). |
| High | `!!` | Fix before release; plan the change now. |
| Medium | `!` | Worth fixing, but not a blocker on its own. |
| Low | `~` | Fix when convenient, and keep an eye on it after each build change. |
| Info | `i` | Nothing to fix for this question within the limits that were checked. |
| Unknown — not checked | `?` | Not checked: this is not a pass. Fix the cause below and run again before relying on this result. |

Patterns:

- (a) **The build tool removed a protection**: The design as written has a second check or extra copies. The tool that built the chip (or the compiler that made the machine code) merged or removed them. So fewer glitches are enough. Spot it next time: After every change of build tool or compiler setting, check that each copy or second check is still there in the result (the gate list or the assembly), not only in your source.
- (b) **One skipped instruction made two values the same**: Two values that should be compared are loaded through the same register. Skipping one load leaves the first value in place, so the code compares something with itself and the check always passes. Spot it next time: Look for code that copies two pointers or values through the same register right before a compare.
- (c) **A random delay did not stop a precisely timed glitch**: The protection only adds a random wait. That makes timing harder on average, but a glitch at the right moment still works, and the attacker can simply try again. Spot it next time: A random delay is a speed bump, not a lock: check that a single well-timed fault still fails, with the delay switched off.
- (d) **One wire or branch decides the outcome**: The whole decision passes through a single point: one wire, one memory cell or one branch. Disturbing that one point is enough. Spot it next time: Follow the decision from the check to where it is used: if it passes through one signal or one branch anywhere, that point is the weak spot.
-  **The alarm itself is not protected**: The protection raises an alarm when copies disagree, but the alarm signal itself can be silenced with a glitch. Spot it next time: Ask "what if the alarm wire itself is glitched?" for every alarm in your design.
-  **No glitch was needed**: The bad outcome happens in ordinary use, without any glitch: either the design has a bug, or the question is missing what a legitimate user may do (a must-hold condition). Spot it next time: Before counting glitches, check that the question excludes ordinary, allowed use.
-  **The protection held: every copy had to be hit**: No single point decides the outcome here: the attacker has to glitch every copy of the check, each at the right moment. That is what the protection is for. Spot it next time: Count how many separate copies an attacker must hit; check that the number stays the same after the build.
-  **We could not get an answer**: The run ended without deciding the question, so nothing is known about this check: it is neither safe nor unsafe. Spot it next time: Read the reason first. A run without an answer is not a pass.
-  **No way in found within the limits**: Within the number of glitches and steps that were tried, nothing worked. Spot it next time: A "none found" only covers the limits shown; raise them to learn more.
