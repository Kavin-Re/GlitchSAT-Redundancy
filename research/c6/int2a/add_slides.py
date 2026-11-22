# adds 5 slides to docs/report/SLIDES.pptx and reorders main/appendix.
import copy, sys
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from PIL import Image
SRC='docs/report/SLIDES.pptx'
p=Presentation(SRC)
GREY=RGBColor(107,118,131); DARK=RGBColor(27,36,48)
blank=p.slides[12].slide_layout
FOOT='Modelled bit flips on toy designs. Nothing physical. author has not reviewed.'
def tb(s,x,y,w,h,text,size,bold=False,color=DARK):
    t=s.shapes.add_textbox(Emu(x),Emu(y),Emu(w),Emu(h)); tf=t.text_frame; tf.word_wrap=True
    for i,line in enumerate(text.split('\n')):
        para=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        r=para.add_run(); r.text=line; f=r.font; f.size=Pt(size); f.bold=bold; f.name='Calibri'; f.color.rgb=color
    return t
def base(label,title):
    s=p.slides.add_slide(blank)
    tb(s,548640,256032,8229600,274320,label,12,True,GREY)
    tb(s,548640,502920,11064240,868680,title,32,True,DARK)
    tb(s,548640,6446520,10241280,274320,FOOT,11,False,GREY)
    tb(s,10972800,6446520,731520,274320,'0',11,False,GREY)
    return s
def pic(s,path,x,y,maxw,maxh):
    w,h=Image.open(path).size
    sc=min(maxw/w,maxh/h); s.shapes.add_picture(path,Emu(x),Emu(y),Emu(int(w*sc)),Emu(int(h*sc)))
def notes(s,text): s.notes_slide.notes_text_frame.text=text
X2=7132320; W2=4663440
# A: Verdict Dial
s=base('DEMO: VERDICT DIAL','One lock, four questions: 3, 2, 1, 0')
pic(s,'research/c6/p40/shots/1366_light_big.png',548640,1417320,6400000,4900000)
tb(s,X2,1417320,W2,3200000,'Stored netlist, whole word: 3\nRe-built (plain recipe, same Yosys 0.33): 2\nReader = accept flag: 1\nAny power-up state: 0\nPredict first: the room guesses before the digit shows.',16)
tb(s,X2,4846320,W2,1371600,'MEASURED: each digit copies one row (matrix.jsonl lines 241, 265, 277, 281). 94 of 432 combinations measured; the rest say "not measured". docs/explainers/dial.html; check_dial.py --browser 467 passed.',12,False,GREY)
notes(s,'SAY: This is the Verdict Dial. The digit is the fewest modelled flips the solver needed to open the toy lock with a wrong key. Before each reveal I ask you to guess.\nSAY: The stored netlist with the whole word read needs 3. I rebuild the same text with the plain recipe of the same Yosys version: 2. I let the next block read only the one-wire accept flag: 1. I let the lock wake up in any state: 0, because the toy has no reset.\nSAY: Every digit is a copy of one measured row, and the source row is printed under it. Where nobody ran a combination, the dial says not measured. Toy design, modelled flips, 6 ticks, at most 3 flips, nothing physical.')
# B: Solver Replay
s=base('DEMO: SOLVER REPLAY','See it happen: one flipped wire opens V1')
pic(s,'research/c6/int2a/img/theatre_step2_crop.png',548640,1417320,6400000,4900000)
tb(s,X2,1417320,W2,3200000,'V1: 1 flip, wire ok at tick 1, wrong key 0xC7; replayed: opens at tick 2.\nV2: no 1- or 2-flip attack within 6 ticks (456 sites); 3 flips, one wire per copy, opens.\nCaveat: reader = accept flag: 1 flip again.',16)
tb(s,X2,4846320,W2,1371600,'MEASURED (solver on the stored netlists) + SIMULATED (gate-level replay, iverilog). Schematics hand-drawn. docs/explainers/theatre.html; check_theatre.py --browser 149 passed.',12,False,GREY)
notes(s,'SAY: This is not an animation I drew. The solver names which wire to flip and when; a gate-level simulator replays that answer, and the strips are the recorded signals.\nSAY: Left, the two-copy lock: both checks say no, but they meet on one wire, ok. One flip at tick 1 and the boot word reads open one tick later. On the three-copy lock the solver found no attack with one or two flips within 6 ticks; with three, one wire per copy, it opens.\nSAY: One caveat I always show: if the next stage reads only the accept flag, it is one flip again. The small schematics are hand-drawn; the waveforms are from the simulation. Nothing touched hardware.')
# C: Wall
s=base('DEMO: SAME BLUEPRINT, MANY BUILDERS','264 builds of one design: 1, 2 or 3 flips')
pic(s,'research/c6/p24/shots/wall_1366_stage3_verdicts.png',548640,1417320,6400000,4900000)
tb(s,X2,1417320,W2,3200000,'152 distinct netlists: 94 need 1 flip, 38 need 2, 20 need 3.\nPer setting (264 solved): 180 / 60 / 24.\n120 of the 180 one-flip settings use opt_merge.\nPreviously shown by SYNFI; E2 replicates it on a toy design.',16)
tb(s,X2,4846320,W2,1371600,'MEASURED: row counts of research/c2/e2_variance/raw/matrix.csv; one design, 6 cycles, at most 3 flips; settings not independent. docs/explainers/wall.html; check_wall.py 42 passed.',12,False,GREY)
notes(s,'SAY: I gave the same design file to 264 synthesis settings. They built 152 different netlists. Each tile is one netlist, and its colour, shape and digit say how many modelled flips it needs.\nSAY: Twenty of 152 keep three. Thirty-eight drop to two. Ninety-four open with one. Most of the one-flip settings let the tool merge identical logic, so three copies become one. That is ordinary optimisation, and SYNFI showed this effect before us.\nSAY: Limits: one toy design, the settings are not independent experiments, and a 3 means no attack found with fewer flips within 6 cycles, not safe.')
# D: Waterfall
s=base('RESULT: CODING VIEW, RANDOM FLIPS','Under random flips: slope = flips needed, height = how many ways')
pic(s,'docs/comms/waterfall.png',548640,1417320,6309360,4800000)
tb(s,X2,1417320,W2,3300000,'Low-p slopes: V0 0.98, V1 0.88, V2-stored 3.00, V2-apt 2.14, V2e 2.97 (min flips 1, 1, 3, 2, 3).\nV2e: 734 attacking triples vs 80 for stored V2, so about 9x more false accepts at low p.\nHigher adversarial cost does not mean a lower random rate: multiplicity matters.',15)
tb(s,X2,4846320,W2,1371600,'SIMULATED teaching model, not an attacker model or a physical error rate. T=4; results/comms/waterfall.csv. Failed prediction kept: the truncated series fit only 9 of 31 points (a lower bound).',12,False,GREY)
notes(s,'SAY: Here every wire and flop is wrong with a small probability p in each clock cycle, independently, like line noise. I plot how often a wrong key is accepted. This is a teaching model, not an attacker and not a real error rate.\nSAY: On log-log axes each design is a straight line. Its slope is the fewest flips needed: about 1, 1, 3, 2 and 3. Its height is how many ways there are. V2e and stored V2 both need three flips, but V2e has 734 attacking triples against 80, so it is about nine times more likely to false-accept at low noise.\nSAY: One of my predictions failed and I keep it: the exact series cut at three flips matched the simulation at only 9 of 31 points. It is a lower bound, not an exact value.')
# E: Burst vs random
s=base('RESULT: CODING VIEW, BURSTS','Best against random flips, weakest against one burst')
rows=[('','burst-fragile (1 all-flop burst opens)','burst-robust (no burst attack within 6 cycles)'),
      ('random-robust (flops-only >= 4)','69/96, C3/3C, A5/5A complements; stored F0/96 (fail word 0x69); 4 more','F0/96 with fail word 0x3C; 2 more'),
      ('random-fragile','3 codebooks','2 codebooks')]
tbl=s.shapes.add_table(3,3,Emu(548640),Emu(1463040),Emu(11064240),Emu(1828800)).table
tbl.columns[0].width=Emu(2926080); tbl.columns[1].width=Emu(4069080); tbl.columns[2].width=Emu(4069080)
for i,r in enumerate(rows):
    for j,v in enumerate(r):
        c=tbl.cell(i,j); c.text=v
        for para in c.text_frame.paragraphs:
            for run in para.runs: run.font.size=Pt(14); run.font.name='Calibri'; run.font.bold=(i==0 or j==0)
tb(s,548640,3474720,11064240,1463040,'Complement pairs need more than 6 random flips, but one event that inverts all 8 state flops maps 0x69 to 0x96: 1 event.\nThe stored code falls the same way: it rests in fail word 0x69, the complement of accept 0x96. Fail word 0x3C: no burst attack, random still 4.\nA burst limited to one comparator copy needs 3 events: interleaving helps.',16)
tb(s,548640,5303520,11064240,1005840,'SIMULATED: one modelled burst = all state flops (or one copy group) inverted in one cycle; not a real overclock or voltage glitch. 16 codebooks, T=6, Yosys 0.33; results/comms/burst.csv, docs/comms/BURST_NOTES.md.',12,False,GREY)
notes(s,'SAY: Communications engineers separate random errors, one bit at a time, from burst errors, many bits at once. A code that is best against one can be poor against the other.\nSAY: The complementary pair 0x69 and 0x96 differ in all eight bits, so random flips need more than six. But one modelled event that inverts all eight state flops turns 0x69 into 0x96 exactly: one event. Our stored design falls the same way, because it rests in its fail word 0x69. With the fail word changed to 0x3C, no all-flop burst reached accept, and random flips still needed four.\nSAY: A burst here is an arithmetic event in the model, not a real glitch. Toy netlists, six cycles, no general rule about codes.')
# reorder: current 1..19, new 20..24 = Dial, Theatre, Wall, Waterfall, Burst
ids=p.slides._sldIdLst; L=list(ids)
old=lambda n:L[n-1]
order=[1,2,3,4,20,21,22,14,13,23,24,10,11,12,15,16,17,18,19,5,6,7,8,9]
for e in L: ids.remove(e)
for n in order: ids.append(old(n))
# appendix relabel for moved slides
app={20:'A6',21:'A7',22:'A8',23:'A9',24:'A10'}
for idx,s in enumerate(p.slides,1):
    tbs=[sh for sh in s.shapes if sh.has_text_frame]
    for sh in tbs:
        if sh.left==10972800 and sh.top==6446520:
            sh.text_frame.paragraphs[0].runs[0].text=str(idx)
    if idx in app:
        lab=tbs[0].text_frame.paragraphs[0].runs[0]; tit=tbs[1].text_frame.paragraphs[0].runs[0]
        if not lab.text.startswith('APPENDIX'): lab.text='APPENDIX: '+lab.text
        tit.text=app[idx]+'. '+tit.text
# slide 9 (now A10) test count
for s in p.slides:
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text=='150':
            sh.text_frame.paragraphs[0].runs[0].text='196'
        if sh.has_text_frame and sh.text_frame.text=='main tests passed':
            sh.text_frame.paragraphs[0].runs[0].text='main tests passed (1 skipped)'
p.save(SRC)
for i,s in enumerate(p.slides,1):
    print(i,[sh.text_frame.text for sh in s.shapes if sh.has_text_frame][1][:70])
