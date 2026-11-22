from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
import json, re
INK=RGBColor(0x1b,0x24,0x30); TEAL=RGBColor(0x1f,0x7a,0x6d); AMB=RGBColor(0xc7,0x7d,0x0a); RED=RGBColor(0xb3,0x34,0x2b)
GREY=RGBColor(0x6b,0x76,0x83); BG=RGBColor(0xfa,0xf8,0xf3); WHITE=RGBColor(255,255,255); PALE=RGBColor(0xee,0xeb,0xe3)
FONT="Calibri"
prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
blank=prs.slide_layouts[6]
FOOT="Modelled bit flips on toy designs. Nothing physical. author has not reviewed."
WORDS={}
def tb(s,x,y,w,h,text,size=20,bold=False,color=INK,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,count=True,name=None):
    t=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); tf=t.text_frame; tf.word_wrap=True
    tf.margin_left=tf.margin_right=Inches(0.05); tf.margin_top=tf.margin_bottom=Inches(0.03); tf.vertical_anchor=anchor
    lines=text if isinstance(text,list) else [text]
    for i,l in enumerate(lines):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.alignment=align; r=p.add_run(); r.text=l; f=r.font; f.size=Pt(size); f.bold=bold; f.color.rgb=color; f.name=FONT
        if i>0: p.space_before=Pt(size*0.45)
    if count: WORDS[id(s)]=WORDS.get(id(s),0)+sum(len(l.split()) for l in lines)
    return t
def rect(s,x,y,w,h,fill=PALE,line=None,shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    r=s.shapes.add_shape(shape,Inches(x),Inches(y),Inches(w),Inches(h)); r.fill.solid(); r.fill.fore_color.rgb=fill
    if line is None: r.line.fill.background()
    else: r.line.color.rgb=line; r.line.width=Pt(1.5)
    r.shadow.inherit=False
    return r
def line(s,x1,y1,x2,y2,color=INK,w=3):
    c=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2)); c.line.color.rgb=color; c.line.width=Pt(w); return c
def new(title,tag,notes,num,appendix=False):
    s=prs.slides.add_slide(blank); bg=s.background.fill; bg.solid(); bg.fore_color.rgb=BG
    tb(s,0.6,0.28,9,0.3,tag.upper(),12,True,AMB if appendix else GREY,count=False)
    tb(s,0.6,0.55,12.1,0.95,title,32,True,INK)
    tb(s,0.6,7.05,11.2,0.3,FOOT,11,False,GREY,count=False)
    tb(s,12.0,7.05,0.8,0.3,str(num),11,False,GREY,PP_ALIGN.RIGHT,count=False)
    s.notes_slide.notes_text_frame.text=notes
    return s
def label(s,x,y,w,text,color=TEAL):
    tb(s,x,y,w,0.35,text,13,True,color,count=False)
N=0
# ---------- 1 title
N+=1
s=prs.slides.add_slide(blank); s.background.fill.solid(); s.background.fill.fore_color.rgb=BG
tb(s,0.8,0.9,11.7,0.4,"WORKING TITLE TBD",14,True,GREY,count=False)
tb(s,0.8,1.4,11.7,1.6,"Which redundant copies really protect a decision?",46,True,INK)
tb(s,0.8,3.2,11.5,1.4,"Given a netlist and the bits a consumer checks: how many modelled flips defeat a redundant boot decision, and which nets do the copies share?",22,False,INK)
rect(s,0.8,5.0,11.7,1.2,PALE)
tb(s,1.0,5.15,11.3,0.9,"Three guards on one wire are really one guard.",34,True,TEAL,anchor=MSO_ANCHOR.MIDDLE)
tb(s,0.8,7.05,11.5,0.3,FOOT,11,False,GREY,count=False)
s.notes_slide.notes_text_frame.text=(""
"SAY: Here is the whole project in one sentence. A boot check is often protected with redundant copies. I give a tool a gate-level netlist and the bits that the consumer actually reads. It tells me how many modelled single-cycle bit flips defeat the decision, which wires the supposed copies share, and how that answer changes when I change the synthesis build, the counting rule or the scope. And the sentence I want you to remember: three guards on one wire are really one guard. Everything today is a model of a toy circuit. Nothing physical, nothing claimed as new.")
# ---------- 2 three guards
N+=1
s=new("Three guards, one wire","The idea",
"SAY: Picture a door with three guards. Each guard checks the code. If the code is wrong, each says no. Now look at the left: all three answers travel down one shared wire to the door. If that one wire says yes for a single moment, the door opens, and the three guards were beaten by one flip. On the right, each guard has its own wire. Now the attacker needs to flip three wires. That is the whole idea.\n"
"SAY, honest part: the drawing is an illustration, not a measurement. The measured version is our toy design V1: two copies of the check that both end in one wire called ok. The solver finds that one flip of ok at cycle 1 opens it. And even in the three-wire design, the accept flag itself can fall to one flip, which I show two slides from now.",2)
def guards(s,x0,shared):
    for i in range(3):
        gx=x0+i*1.5
        rect(s,gx,2.0,1.15,0.7,WHITE,INK); tb(s,gx,2.05,1.15,0.6,"guard "+"ABC"[i],16,True,INK,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE,count=False)
    if shared:
        cx=x0+1.5+0.575
        for i in range(3): line(s,x0+i*1.5+0.575,2.7,cx,3.55,INK,3)
        rect(s,cx-0.6,3.55,1.2,0.5,RED,None); tb(s,cx-0.6,3.55,1.2,0.5,"one wire",14,True,WHITE,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE,count=False)
        line(s,cx,4.05,cx,4.6,INK,3)
    else:
        for i in range(3):
            gx=x0+i*1.5+0.575
            line(s,gx,2.7,gx,3.55,INK,3)
            rect(s,gx-0.5,3.55,1.0,0.5,TEAL,None); tb(s,gx-0.5,3.55,1.0,0.5,"wire "+str(i+1),13,True,WHITE,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE,count=False)
            line(s,gx,4.05,x0+1.5+0.575,4.6,INK,3)
    cx=x0+1.5+0.575
    rect(s,cx-0.8,4.6,1.6,0.55,PALE,INK); tb(s,cx-0.8,4.6,1.6,0.55,"door",16,True,INK,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE,count=False)
guards(s,0.9,True); guards(s,7.4,False)
tb(s,0.9,5.1,4.3,1.0,"1",64,True,RED,PP_ALIGN.CENTER,count=False); tb(s,0.9,6.1,4.3,0.4,"flip opens the door",18,True,INK,PP_ALIGN.CENTER,count=False)
tb(s,7.4,5.1,4.3,1.0,"3",64,True,TEAL,PP_ALIGN.CENTER,count=False); tb(s,7.4,6.1,4.3,0.4,"flips needed",18,True,INK,PP_ALIGN.CENTER,count=False)
tb(s,0.6,1.35,12,0.45,"Copies that all end in one wire act as one guard.",22,False,GREY)
label(s,0.9,6.6,8,"ILLUSTRATIVE drawing (toy), not a measurement",AMB)
# ---------- 3 solver
N+=1
s=new("Our solver finds the minimum flips","Method",
"SAY: To turn the picture into a number I use a solver. Yosys turns the design into gates. The solver z3 chooses which wires to flip, and in which clock tick, and also the attacker's input. I keep lowering the flip limit until no attack exists. The last limit that still had an attack is the minimum.\n"
"SAY: Results on three toy designs, six clock ticks, at most three flips. The plain check V0 falls to one flip. V1, two copies that end in one wire, falls to one flip. V2, three copies each owning its own result bits, needs three flips. But careful: that three holds only in a narrow setting, and the next slide shows exactly which. Measured, by the command in my demo.",3)
for i,(num,cap,sub,col) in enumerate([("1","V0","plain check",RED),("1","V1","two copies, one wire",RED),("3","V2","three copies, own bits",TEAL)]):
    x=0.9+i*4.0
    rect(s,x,1.7,3.6,3.6,PALE)
    tb(s,x,1.85,3.6,1.9,num,120,True,col,PP_ALIGN.CENTER,count=False)
    tb(s,x,3.85,3.6,0.5,cap+" flips" if False else cap,26,True,INK,PP_ALIGN.CENTER)
    tb(s,x,4.4,3.6,0.7,sub,18,False,GREY,PP_ALIGN.CENTER)
tb(s,0.9,5.65,11.5,1.0,"Minimum flips found by z3. 6 cycles, at most 3 flips. MEASURED.",18,False,INK)
# ---------- 4 scope table
N+=1
s=new("The answer depends on what is counted and checked","Result: scope",
"SAY: This is the main result. The same V2 design gives different minimum flips depending on what I count and what the consumer checks. If the consumer reads the full 8-bit word on the stored netlist, three. If I re-synthesise the same source with the apt Yosys 0.33, two. If the consumer reads only the single accept flag boot_ok, one. If the consumer reads four bits, between one and three; of 68 four-bit masks, 28 need one flip, 36 need two, 4 need three. If I let the input wires be fault sites, one. If synthesis merges the three identical copies into one, it is V1 again: one.\n"
"SAY: So 'V2 resists two flips' is only true in one narrow cell: full word, inputs not attackable, known power-up state, stored netlist. I never say it without those qualifiers. Measured by the 360-cell scope matrix and the 255-mask table; all bounded at six cycles and three flips.",4)
rows=[("Full word, stored netlist","3",TEAL),("Other synthesis build","2",AMB),("Accept flag only","1",RED),("Consumer reads 4 bits","1 to 3",AMB),("Input wires attackable","1",RED),("Synthesis merges copies","1",RED)]
y=1.55
for lab,val,col in rows:
    rect(s,0.9,y,11.5,0.74,PALE)
    tb(s,1.1,y,8.2,0.74,lab,24,False,INK,anchor=MSO_ANCHOR.MIDDLE)
    tb(s,9.4,y,2.8,0.74,val,34,True,col,PP_ALIGN.RIGHT,MSO_ANCHOR.MIDDLE)
    y+=0.82
tb(s,0.9,6.55,11.5,0.4,"V2 minimum flips. Full word needs known power-up, inputs not attackable. Other build = apt Yosys 0.33. MEASURED: 6 cycles, at most 3 flips.",14,False,GREY,count=False)
# ---------- 5 widths
N+=1
s=new("The more bits the consumer reads, the more flips it takes","Result: consumer width",
"SAY: Same V2 design, same netlist. I change only how many result bits the consumer reads: the lowest one bit, two bits, up to all eight. The minimum number of flips climbs: 0, 1, 1, 2, 2, 3, 3, 3. The zero at one bit is not a bug: the idle state already looks like acceptance on that single bit.\n"
"SAY: The lesson: a claim of protection has to say how wide the reader is. A reader that only checks four bits gets one or two flips, not three. You can reproduce this live with the sweep-widths command. Measured on the stored V2 netlist; modelled flips; 6 cycles, at most 3 flips.",5)
s.shapes.add_picture("fig/width_curve.png",Inches(0.6),Inches(1.7),width=Inches(7.9))
tb(s,8.8,1.7,4.1,1.3,"0 to 3",64,True,TEAL)
tb(s,8.8,3.1,4.1,2.4,["V2, lowest n bits read.","n = 1 costs 0: the idle state already matches on that bit."],22,False,INK)
tb(s,8.8,5.6,4.1,1.2,"MEASURED: --sweep-widths, 6 cycles, at most 3 flips.",14,False,GREY,count=False)
# ---------- 6 E2
N+=1
s=new("Same design, different build: 1, 2 or 3 flips","Result: synthesis variance",
"SAY: Now I keep the design and the scope fixed and change only how it is built. I ran V2 through 864 synthesis settings; 264 of the V2 ones were solved. In 180 of them one flip is enough. In 60 it takes two. In only 24 does it take three. The reason is that the build tool can merge or reshape the three copies so they share logic.\n"
"SAY: I do not know the exact reason two Yosys versions disagree. I only know that it happens and that a verdict belongs to one exact netlist file. This is measured, bounded, toy designs.",6)
s.shapes.add_picture("fig/e2.png",Inches(0.6),Inches(1.7),width=Inches(7.9))
tb(s,8.8,1.7,4.1,1.3,"180 of 264",52,True,RED)
tb(s,8.8,3.1,4.1,2.4,["V2 settings need only 1 flip.","The build tool decides the answer."],22,False,INK)
tb(s,8.8,5.6,4.1,1.2,"MEASURED: E2 matrix, 864 settings (792 solved in all, 264 for V2).",14,False,GREY,count=False)
# ---------- 7 SPICE
N+=1
s=new("Circuit simulation: a supply dip hits a whole rail","Physical grounding 1: SPICE (SIMULATED)",
"SAY: Is a flip a fair picture of a real disturbance? I asked a circuit simulator, ngspice with real sky130 cell models. This is simulation, not silicon.\n"
"SAY: Three things came out. One: when the supply dips, every gate with a high output on that rail sags together, and only from one to zero; low outputs stay low. So a dip is a rail-wide, one-way event, not one clean flip. Two: in 60 dip points, even down to zero volts for three nanoseconds, the stored flop value never flipped. Three: a short clock pulse, a runt, makes a flop capture its input at the wrong time, which is a wrong-time capture and not a free flip; the plot shows red where the flop captured wrongly. I do not quote voltages or timings as attack parameters, and I only tested dips up to three nanoseconds.",7)
s.shapes.add_picture("research/c2/el1_spice/plot_B_clock_runt.png",Inches(0.6),Inches(1.7),width=Inches(7.0))
tb(s,8.0,1.7,4.9,1.3,"0 of 60",64,True,TEAL)
tb(s,8.0,3.1,4.9,2.4,["Dip points that flipped a flop.","Dips pull high gates low, together.","Clock runt: wrong-time capture."],22,False,INK)
tb(s,8.0,5.6,4.9,1.2,"SIMULATED (ngspice, sky130 cells). Not silicon. Plot: clock runt, red = flop captured D.",14,False,GREY,count=False)
# ---------- 8 layout
N+=1
s=new("Layout: the three copies sit within 2.95 um","Physical grounding 2: layout (SIMULATED on a flow-demo placement)",
"SAY: I placed and routed the toy V2 with the open sky130 flow. This is a flow demonstration, nothing was made. I measured where the three comparator copies landed: the three cells that together are enough to break V2 sit within about 2.95 micrometres of each other, on one supply net. So a local disturbance could reach all three.\n"
"SAY: I then tried spreading the copies apart, to 15 micrometres or more. In the model that helps against local events, which then need more events. But a dip over the whole die that can choose which gates fall still costs one event, because the copies are still on the same supply net. And the honest part: all four spread layouts failed the LVS check because of a known flow bug, filler cells shorting a wire. So the spread layouts are an experiment, not a fix. No parasitic extraction, no IR-drop analysis.",8)
s.shapes.add_picture("fig/layout_radius.png",Inches(0.6),Inches(1.7),width=Inches(7.6))
tb(s,8.5,1.6,4.4,1.0,"2.95 um",54,True,RED)
tb(s,8.5,2.75,4.4,3.0,["Original: 3 copies, one supply net.","Spread 15 um or more: helps against local events only.","Die-wide selective dip: still 1.","Spread layouts failed LVS."],20,False,INK)
tb(s,8.5,5.9,4.4,1.0,"SIMULATED model on MEASURED placement. No extraction, no silicon.",14,False,GREY,count=False)
# ---------- 9 built
N+=1
s=new("What we built","What exists",
"SAY: What exists is a toolkit. A solver that finds the minimum flips. A command-line product, faultbound-wt, that takes a netlist and says how many flips, which wires, and under which scope; it has a scope sweep, a width sweep and a timeout so it never hangs. There are 98 tests in the main suite and 138 in the product suite with one skipped, counted on a clean copy. A mutation check killed 29 of 43 sabotaged versions, about 67 percent; that figure comes from a step report and I did not re-run it. Other tools and re-runs agree with the solver, but they share its fault model, so they check the code, not the physics.\n"
"",9)
for i,(num,cap,col) in enumerate([("98","main tests passed",TEAL),("138","product tests passed",TEAL),("67%","mutation score, 29 of 43",AMB)]):
    x=0.9+i*4.0
    rect(s,x,1.7,3.6,2.7,PALE)
    tb(s,x,1.8,3.6,1.5,num,80,True,col,PP_ALIGN.CENTER,count=False)
    tb(s,x,3.4,3.6,0.9,cap,20,False,INK,PP_ALIGN.CENTER)
tb(s,0.9,4.8,11.5,1.6,["Solver, and a product CLI with scope sweep, width sweep and timeout."],24,False,INK)
tb(s,0.9,5.9,11.5,0.9,"Tests MEASURED on a clean copy (1 product test skipped). Mutation score REPORTED.",14,False,GREY,count=False)
# ---------- 10 not proven
N+=1
s=new("What is NOT proven","Honest scope",
"SAY: Now what I do not claim. Nothing is physical: a flip is a modelling choice, and SPICE is simulation, not silicon. These are toy 8-bit designs, bounded at six cycles and three flips; greater than three means no attack found up to three, not secure. The base method is covered by earlier tools: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI. Nothing here is established as new, and I have not read the k-FRP full text. A predictor that guesses the answer without the solver was exact on 150 of 163 fresh toy cells, 92 percent, and only 58 percent when two or more flips are needed; it is a quick pre-check and the solver stays the judge. And whether a real supply dip can choose which gates fall is open.",10)
items=["Nothing physical: modelled flips.","Toy designs, 6 cycles, 3 flips.","Prior art covers the method.","Predictor 92% exact; solver judges."]
y=1.65
for it in items:
    rect(s,0.9,y,0.18,0.62,RED,None,MSO_SHAPE.RECTANGLE)
    tb(s,1.3,y-0.02,11.2,0.7,it,26,False,INK,anchor=MSO_ANCHOR.MIDDLE); y+=1.0
tb(s,0.9,5.8,11.5,0.9,"Predictor: VER audit, 150 of 163 fresh cells; 58% when 2 or more flips are needed.",14,False,GREY,count=False)
# ---------- 11 author
N+=1
s=new("What I did","Author",
"",11)
rect(s,0.9,1.9,11.5,3.2,WHITE,GREY)
tb(s,0.9,2.9,11.5,1.2,"",54,True,GREY,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE,count=False)
tb(s,0.9,5.5,11.5,1.0,"",22,False,INK)
# ---------- 12 close
N+=1
s=new("The sentence to keep","Takeaway",
"SAY: If you remember one thing: a claim like 'three copies resist two faults' means nothing unless it says what counts as a fault, which output is attacked, how the chip starts and which circuit file was tested. I built a small tool that re-runs the question under each choice and shows which choice decides the answer. V2 is the example, not a recommendation. Everything is a bounded simulation of a toy, and nothing is claimed as new. Questions, please.",12)
rect(s,0.9,1.8,11.5,3.4,PALE)
tb(s,1.2,1.95,10.9,3.1,"'Three copies resist two faults' means nothing without: what counts as a fault, which output, how the chip starts, which netlist.",32,True,INK,anchor=MSO_ANCHOR.MIDDLE)
tb(s,0.9,5.5,11.5,0.9,"V2 is the example. Questions?",24,False,TEAL)
# ---------- appendix
def appx(title,notes,num,bullets,src):
    s=new(title,"Appendix: backup for hard questions",notes,num,True)
    y=1.55
    for b in bullets:
        rect(s,0.9,y+0.12,0.14,0.14,AMB,None,MSO_SHAPE.RECTANGLE)
        t=tb(s,1.2,y,11.4,0.9,b,20,False,INK); y+=0.95 if len(b)>95 else 0.75
    tb(s,0.9,6.5,11.5,0.5,src,13,False,GREY,count=False)
    return s
N+=1
appx("A1. Counting rule: one flipped net is one fault",
"SAY: A flip of a net, called a stem, counts as one fault however many gates read it. That is the convention of the published tools; FIRMER counts per gate the same way. Counting a net read by f gates as f faults is a stress test, not a claim. Under the stem rule V2 needs only 2 flips on 26 of 32 rebuilt netlists and 3 on 6. Under fanout counting it needs 3 on all 32. A second step replicated the numbers on 64 of 64 rows, but with one reused recipe list, so it is not independent. I do not claim either rule is physical; no source I found gives a physical 'right' rule.",N,
["Headline rule: flipping a net counts once, however many gates read it (matches FIRMER's per-gate counting).","Stem rule: V2 needs 2 flips on 26 of 32 rebuilt netlists, 3 on 6.","Fanout counting (a stress test): 3 flips on 32 of 32.","Replicated on 64 of 64 rows with one reused recipe list, so not independent. Neither rule is shown physical."],
"MEASURED: research/c3/rep/REP_REPORT.md; R22 (physical fault-model literature, snippets and fetched pages).")
N+=1
appx("A2. Predictor: a quick pre-check, not a verdict",
"SAY: I tested whether a structural rule could predict the minimum without the solver. On the first corpus it looked perfect, 928 of 928, but that corpus was easy and effectively three to five designs. An independent audit on 163 fresh cells from 76 new netlists found it exact on 150, 92 percent, within one flip on 156, and only 18 of 31, 58 percent, when two or more flips are needed. It missed the pre-registered 98 percent bar, and it was 1.4 times slower than the solver. What stays is a sound lower bound: in 928 plus 163 plus 60 cells the bound never exceeded the solver. So it is a pre-check, and the solver is the reference.",N,
["Fresh toy cells: exact on 150 of 163 (92.0%); within one flip on 156 (95.7%).","When 2 or more flips are needed: exact on 18 of 31 (58%).","Missed the pre-registered 98% bar; 1.4x slower than the solver.","Lower bound never above the solver in 928 + 163 + 60 cells. The old 928/928 is an easy, near-duplicate corpus."],
"MEASURED: research/c4/ver/VER_REPORT.md; docs/NUMBERS.md section 7.")
N+=1
appx("A3. The one unbounded proof (PDR)",
"SAY: There is exactly one unbounded result. With the ABC PDR engine in SymbiYosys, for the stored V2 netlist, no attack exists with two or fewer flips for any number of cycles. It passed in 0.83 seconds. It covers this netlist, this fault model and a constant attacker input only; with three flips an attack exists; the apt-built 85-gate netlist is covered only at one flip. There is no independent proof certificate and no second tool replicated it. So I use it as one data point, not as a claim that V2 is secure.",N,
["Stored V2 netlist, 2 or fewer flips: PASS for any number of cycles (ABC PDR, 0.83 s).","Covers this netlist, this fault model, constant attacker input.","With 3 flips an attack exists. Apt-built 85-gate netlist: PDR pass only at 1 flip.","No independent certificate; not replicated by a second tool."],
"MEASURED at integration, not re-run by RECON: formal/FORMAL.md section 4; docs/NUMBERS.md F.pdr.")
N+=1
appx("A4. Layout: what DRC and LVS do and do not say",
"SAY: The original V2 layout: router design-rule violations zero, antenna violations zero, LVS matches uniquely, 430 devices against 430, and slack about plus seven nanoseconds, which is an estimate from global-route parasitics, not signoff. Magic still lists errors inside the library cell definitions; they look tap-dependent, and I tested that in context for one cell type only, so I do not claim the layout is DRC-clean. The four spread layouts: router clean, antenna clean, but LVS failed in all four, for example 428 against 430 devices, because a signal wire on li1 touches a filler's ground in magic's view. That is a known flow bug and I did not fix it. Costs: wire length plus 29 to 50 percent, die area times 1.26 to 2.5. No extraction, no IR-drop, no silicon.",N,
["Original: router DRC 0, antenna 0, LVS match uniquely (430 vs 430), slack +7.035 ns (estimate).","Magic errors in library cells are tap-dependent; tested in context for one cell only. Not claimed DRC-clean.","4 spread layouts: router and antenna clean, LVS failed in all 4 (filler flow bug, not fixed).","Cost of spreading: wire length +29 to +50%, die area x1.26 to x2.5."],
"MEASURED: research/c4/l2/L2_REPORT.md, layout/verify/VERIFY.md. No extraction, no IR-drop, no silicon.")
prs.save("SLIDES.pptx")
cnt=[(i+1,WORDS.get(id(sl),0)) for i,sl in enumerate(prs.slides)]
json.dump(cnt,open("wordcount.json","w")); print(cnt)
