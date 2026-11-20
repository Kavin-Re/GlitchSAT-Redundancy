# R21: Fault-injection countermeasures in real designs, and candidate V4-V6
Agent R21, 2026-11-19. License: UNDECIDED. Title: working title TBD.
Method: 8 WebSearch (standard) + 1 WebFetch of the OpenTitan guideline page. Labels: SOURCED = a fetched page or search-result text said it (URL given); SNIPPET = search summary only; UNVERIFIED = my knowledge or inference, no source seen. No full papers read, nothing run, no tool cloned. Nothing here is claimed as new. All fault costs below are EXPECTED under the glitchsat model (modelled single-cycle bit flips of gate outputs and flop Q, T=6, input nets not sites, known init); none is measured. All RTL is UNTESTED.
No host was blocked this round.

## 1. What real secure-boot / secure-element designs do (RTL/gate level)
| Countermeasure | Who / where | Label and source |
|---|---|---|
| Sparse FSM encoding, minimum Hamming distance between states, other codes invalid | OpenTitan guideline Rec. 3.3.1-3.3.2 ("Use a sparsely populated state encoding, with all others marked invalid"; "minimum Hamming distance for state machine transitions, to make single bit faults non-effective"). SYNFI: distance 1 lets one fault hijack the AES FSM; OpenTitan sparse encoding gives 3 | SOURCED https://opentitan.org/book/doc/security/implementation_guidelines/hardware/index.html (OpenTitan hardware implementation guidelines, undated, fetched 2026); SOURCED https://arxiv.org/pdf/2205.04775 (SYNFI, Nasahl et al., 2022) |
| Constant-Hamming-weight states with continuous check; terminal count not all-0/all-1 | OpenTitan Rec. 3.3.3, 3.3.4 | SOURCED same guideline page |
| Redundant copies of sensitive checks/data; run-twice-and-compare | OpenTitan Rec. 3.6, 3.7 | SOURCED same page |
| Value-and-complement through the datapath (a form of dual rail) | OpenTitan Rec. 3.4 | SOURCED same page |
| Redundant counters: double-count (two counters compared) and cross-count (up + down counter, sum compared to constant); error raises alert | OpenTitan `prim_count`; SYNFI found 2 single-fault sites that change the output counter without triggering the error logic (documented in the module) | SOURCED (search text) https://arxiv.org/pdf/2205.04775 ; SNIPPET alert_handler commits https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/b5eb15004f08862c9e64f10f9c05eae9f2cde233%5E%21 |
| Error flag to alert system; assertion that an error leads to a fatal alert within a few cycles | OpenTitan sec_cm DV framework | SOURCED (search text) https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/fcc8bac27c0a01c32baa8312dd6388ed590c24c1/doc/ug/sec_cm_dv_framework/index.md . "Sticky/latched" is not stated in what I read: UNVERIFIED for OpenTitan; the notion is standard but I have no citation. |
| Multi-bit boolean (mubi) encodings for control signals, multi-bit arbitration winner | OpenTitan Rec. 3.17 for arbitration; `prim_mubi_*` templates exist | SOURCED (arbitration) guideline page; mubi Hamming properties UNVERIFIED (docs not read) |
| Synthesis-proof primitives: `prim_sparse_fsm_flop`, "anchor" buffers/flops with don't-touch so copies are not collapsed | Sparse FSM flop so tools cannot change the encoding; mubi sync template says buffer cells carry a don't-touch constraint "such that synthesis tools won't collapse all copies into one signal" | SOURCED (search text) https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/04e4a4742705c54ade0b0e590bde5e6d4e61a6d5/util/design/data/prim_mubi_sync.sv.tpl ; sparse FSM flop SNIPPET from sec_cm DV page above. `prim_sec_anchor_*` RTL itself not seen: UNVERIFIED |
| Delay cycles from an LFSR around critical operations (randomised timing, temporal) | OpenTitan Rec. 2.4 | SOURCED guideline page. Patent on randomised execution during boot: SNIPPET https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10678927 |
| Lockstep (duplicated core + comparator) | OpenTitan Ibex lockstep; k-FRP formally verified it and found a register-file weakness fixed upstream. Arm Cortex-R lockstep is a safety feature (error reaction time) | SOURCED (abstract) https://eprint.iacr.org/2024/247.pdf (k-FRP, Tollec et al., TCHES 2024) as read in R23; Arm: SNIPPET https://developer.arm.com/community/arm-research/b/articles/posts/error-correlation-prediction-for-lockstep-processors-in-safety-critical-systems . I found no Arm security-specific lockstep source: UNVERIFIED |
| Sensors: glitch / brown-out / frequency monitors, meshes; on detection reset rather than retry | NCC Group; Karaklajic-Schmidt-Verbauwhede hardware designer's guide | SNIPPET https://www.nccgroup.com/research/alternative-approaches-for-fault-injection-countermeasures-part-33/ ; https://lirias.kuleuven.be/retrieve/334153 (A Hardware Designer's Guide to Fault Attacks, IEEE TCAD, 2013 per my memory: UNVERIFIED year) |
| Reading sensitive bits several times, discarding suspect values; survey of detection vs infection | 2025 SoK | SNIPPET https://arxiv.org/pdf/2509.18341 (SoK: A Beginner-Friendly Introduction to Fault Injection Attacks, 2025) |
| Infective computation | Software/cipher-level (corrupt the output so a faulted run leaks nothing). Not typically applied to a bare boot compare | SNIPPET only (SoK above, "infection-based"); hardware boot applicability UNVERIFIED |
| Hardened / self-checking voters | TMR voter is a known single point of failure; fault-secure and totally-self-checking voters exist (FPGA/space literature) | SNIPPET https://vufind-test.katalog.k.utb.cz/SummonRecord/FETCH-LOGICAL-i90t-b61b024518fda32fe98e6b45cb9cefcc329dd862ef847526499148e8d893e4af3 ; https://arxiv.org/pdf/2603.14411 (survey on TMR, 2026) ; Ulbrich et al. EDCC 2012 https://sys-sideshow.cs.tu-dortmund.de/publications/ulbrich_12_edcc.pdf |
| Real-world boot bypass by fault (motivation) | ESP32 CVE-2019-15894 | SNIPPET https://elvis.hcw.ac.at/wiki/index.php/Fault_Injection_Attack |

## 2. Where these fail for structural reasons our toolkit exposes
| Failure | Evidence | Label |
|---|---|---|
| Synthesis merges or weakens redundancy | OpenTitan guideline Rec. 11.1: "Sometimes synthesis will optimize away redundant (but necessary for security) logic"; "`dont_touch` or `size_only` attributes may sometimes be needed"; Rec. 11.2: "Value-and-complement strategies can also be optimized away". SYNFI: sparse FSM went 3 -> 2 faults after synthesis. Ours: V2 spike 3 vs apt-0.33 2 (B2, MEASURED) | SOURCED + MEASURED (B2) |
| Shared decision net: one net owns the verdict (`boot_ok`, a shared comparator, a shared voter) | Ours: boot_ok 1 flip (CT-1, B2); V2s shared voter = 1 for every non-colliding mask (M1, MEASURED). Literature: voter is a single point of failure | MEASURED + SNIPPET |
| Consumer decodes few bits | M1: V2 is 1 flip for 88/228 masks, 3 only for 44/228 (MEASURED). Rule: min flips = min(state route, copy-subset route) | MEASURED (M1) |
| Voting without hardened voter or wide consumer | M1: V2m per-bit 2-of-3 lowers full word 3 -> 2; narrow masks still 1 | MEASURED (M1) |
| Redundant-counter style checks have single sites that move the output without raising the error | SYNFI: 2 single-fault sites in `prim_count` | SOURCED |
| Error flag itself is a flip site: flipping or never latching the flag defeats it unless sticky and outside the cone | UNVERIFIED as a literature claim; follows from model: any net is a site |
| Reset / power-up state: no reset means the accept code can be the power-up value (cost 0); with reset, flipping `rst` in all reset cycles costs 3 | B2 (MEASURED) |
| Input nets: a flip on a shared input net feeds all copies (redundant compares see the same wrong value). B2: V2 drops to 1 when input nets are sites | MEASURED (B2). Temporal sampling (V3) fixes only partly |
| Equal-copy redundancy can fail against a correlated fault (same node in all copies, our V2 witness) | MEASURED (M1 witness: same internal node of three copies, 3 flips; our model counts each flip separately, a physical fault that hits all three at once would be 1: model limit, no hardware claim) |
| Comparator `==` output as single net before a wide code | Rec. 3.17 / hamming distance: attacker flips comparator output and all bits it owns move together (M1 rule) | MEASURED (M1) |

## 3. Three candidate example designs V4, V5, V6
Common: all UNTESTED sketches for the toy (key 0xC3, goal `sig != KEY` but accepted, accept word 0x96). Expected fault costs are predictions from the M1 rule and B2 matrix, to be measured with `mat.py`/glitchsat before any statement is made. Report each as a (design, consumer mask, scope) triple, never as a bare number.

### V4: sparse accept code with large Hamming distance plus complement rail (code-based, "data EDC")
Idea: M1's floor is the Hamming distance from idle states (F0, CC) to the accept word on checked bits. Choose an accept code far from every legal and idle state, and store value and complement so a consumer checks 16 bits.
```verilog
// UNTESTED sketch. Reset value and idle/error states chosen so HD(accept, any other legal state) >= 8 over 16 bits.
module v4(input clk, input [7:0] sig, output [15:0] boot_word, output boot_ok);
  (* keep *) reg [7:0] st, stn;           // value and complement
  initial begin st = 8'hF0; stn = 8'h0F; end
  wire m = (sig == 8'hC3);
  // accept = {8'h96, 8'h69}; reject = any other
  wire [7:0] nxt  = m ? 8'h96 : 8'h69;
  wire [7:0] nxtn = ~nxt;               // synthesis will likely merge: needs keep_hierarchy / dont_touch on a separate cell
  always @(posedge clk) begin st <= nxt; stn <= nxtn; end
  assign boot_word = {st, stn};
  assign boot_ok   = (boot_word == 16'h9669);
endmodule
```
Expected cost (ESTIMATED): with a consumer on all 16 bits, floor is min(HD idle->accept, comparator-owned bits) ; one shared `m` still owns all bits, so a flip of `m` costs 1 unless `m` is triplicated per rail. Likely 1 as drawn (shared m); this is a useful negative-ish demo that complement rails do not help against a shared decision net. Caveat: Yosys/ABC will see `stn = ~st` and merge (OpenTitan Rec. 11.2). Variant V4b: separate compare copies for st and stn, expected 2 to 3. Shows: code distance alone is not enough.

### V5: self-checking voter (hardened voter) with sticky alert
Idea: fix M1's V2m/V2s finding: voting only helps with a hardened voter. Three compare copies, per-bit 2-of-3 voter built twice (duplicated voter, compared), disagreement sets a sticky alert that gates accept.
```verilog
// UNTESTED sketch
module v5(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  wire m0,m1,m2;  // three keep_hierarchy cmp8 copies
  (* keep_hierarchy *) wire [7:0] vA = vote8(m0,m1,m2);   // voter instance A
  (* keep_hierarchy *) wire [7:0] vB = vote8(m0,m1,m2);   // voter instance B, different gate structure (e.g. mux form)
  (* keep *) reg alert;                                    // sticky, never cleared
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire dis = (vA != vB) | ~((m0==m1)&(m1==m2));
  always @(posedge clk) begin
    alert <= alert | dis;
    st <= (st==8'hF0) ? 8'hCC : (st==8'hCC && !alert && !dis) ? w(vA) : st;
  end
  assign boot_word = st;
  assign boot_ok   = (st == 8'h96) & ~alert;
endmodule
```
Expected cost (ESTIMATED): to reach the accept word without raising the alert, attacker must make A and B agree on the wrong value: two comparator copies plus the alert path; predicted 3 to 4 for full word; narrow masks may still be 1 via the `st` register bits and the `dis` or `alert` nets (each a single flip site). Caveats: alert and `dis` nets are themselves single sites (a flip of `dis` in the decisive cycle costs 1 and may be the cheapest attack: then V5 shows the honest limit "detector inside the cone"); the toolkit counts any net as a site so this is expected to show. Good for demonstrating the cone of the detector.

### V6: temporal redundancy with randomised check order and state-bound checks (re-check after a delay)
Idea: compare `sig` in two different cycles with two separate flop-held copies and require a state-sequence code (sparse FSM) F0 -> A1 -> A2 -> ACCEPT where each step needs its own compare result; skipping a step lands in an invalid state with distance >= 3. LFSR delay is modelled as an input schedule (our model has no timing jitter, so the random delay itself cannot be shown: say so).
```verilog
// UNTESTED sketch; 3-step sequence, one-hot-ish 8-bit codes with HD>=3 between legal states
module v6(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st;  initial st = 8'hF0;
  (* keep *) reg [7:0] s1, s2;                       // sig sampled in two cycles
  wire m1 = (s1 == 8'hC3), m2 = (s2 == 8'hC3);
  always @(posedge clk) begin
    s1 <= sig; s2 <= s1;
    case (st)
      8'hF0: st <= 8'hCC;
      8'hCC: st <= m1 ? 8'h3C : 8'h69;               // 3C = checked once; 69 = reject sink
      8'h3C: st <= m2 ? 8'h96 : 8'h69;
      8'h96, 8'h69: st <= st;
      default: st <= 8'h69;                           // invalid state -> reject sink
    endcase
  end
  assign boot_word = st;  assign boot_ok = (st == 8'h96);
endmodule
```
Expected cost (ESTIMATED): attacker needs both compares fooled (m1 and m2) or flip `st` bits across states; with HD(3C,96)=4 and HD(CC,96)=4 the state route is about 4 flips; compare route is 2 (one flip per compare) so predicted 2. Because `sig` is constant in our model the two samples are not independent; this V6 will not show a benefit from temporal diversity unless input is time-varying (B2 V3 free-input mode, measured 3 in some cells, MEASURED). Caveats: sink state `69` is absorbing (good); default branch is the invalid-state handler; Yosys `fsm` pass may recode the FSM (use nofsm / keep, SYNFI sourced).

Choice rationale: V4 shows code distance and the shared-decision-net failure, V5 shows voting plus detector and where the detector cone breaks, V6 shows temporal redundancy and the limit of a constant-input model. Together they cover EDC, hardened-voter/sticky-alert, and temporal/sparse-FSM patterns, and each has a predicted weak spot the toolkit should expose. Not chosen: glitch detectors (sensor, physical, outside a bit-flip model), infective computation (cipher-level), lockstep (needs a CPU; k-FRP does this), randomised delays (no timing in our model).

## 4. Q&A paragraph (plain words)
Real secure-boot and secure-element designs do not rely on one check. They use several layers: state machines whose valid states differ in many bits, so one flipped bit lands in an invalid state; duplicated or triplicated checks with a comparator; counters kept twice; values stored together with their complement; an alert that, once raised, is held; and sensors that reset the chip when a glitch is seen. Open projects such as OpenTitan write these rules down and also warn that the synthesis tool can quietly delete or merge the redundant copies, so they mark them "dont_touch". What our toolkit does is small: for a toy boot check at gate level, it asks a solver "what is the fewest single-cycle bit flips that make the design accept the wrong key", and it shows how that number changes with what the consumer reads, how the design was synthesised, and which nets may be flipped. It found, for example, that "needs 3 flips" holds only when the reader decodes all result bits and the synthesis keeps all three copies. It does not model physical glitches, does not prove anything beyond a bounded number of cycles and flips, and is not a replacement for the large published tools (SYNFI, k-FRP, FIRMER), which check real designs. Its place is a small, reproducible way to see why a countermeasure's count depends on its assumptions.

## 5. Not done
No full papers read. Arm-specific lockstep security documentation not found. `prim_sec_anchor_*` RTL, mubi docs, sticky-alert wording not read. V4-V6 not synthesised or run; all costs ESTIMATED. Voter-hardening literature came from search summaries only.
