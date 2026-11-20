"""INT deck edit: add 2 slides before the appendix, fix slide 6 notes, renumber."""
import copy
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
SRC = 'docs/report/SLIDES.pptx'
p = Presentation(SRC)
s6 = p.slides[5]
nt = s6.notes_slide.notes_text_frame
old = "SAY: I do not know the exact reason two Yosys versions disagree. I only know that it happens and that a verdict belongs to one exact netlist file. This is measured, bounded, toy designs."
new = ("SAY: I used to say two Yosys versions disagree. That was wrong: the stored netlist was made by the same Yosys 0.33. "
       "The real cause is the encoding, which I show on slide 'Why 2 and not 3?'. Encoding sets the floor; the synthesis flow decides whether the floor is reached. "
       "A build or flow difference changes the netlist, not the underlying weakness. This is measured, bounded, toy designs.")
t = nt.text
assert old in t, 'slide 6 note text not found'
nt.text = t.replace(old, new)

DARK = RGBColor(0x1B, 0x24, 0x30); GREY = RGBColor(0x6B, 0x76, 0x83); RED = RGBColor(0xB3, 0x34, 0x2B); GREEN = RGBColor(0x1F, 0x7A, 0x6D)
bg = s6.background.fill.fore_color.rgb
blank = s6.slide_layout
def tb(s, x, y, w, h, lines, size, bold=False, color=DARK):
    b = s.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h)); tf = b.text_frame; tf.word_wrap = True
    for i, ln in enumerate(lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = para.add_run(); r.text = ln; r.font.size = Emu(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name = 'Calibri'
        if i: para.space_before = Pt(8)
    return b
def base(kicker, title, num):
    s = p.slides.add_slide(blank)
    s.background.fill.solid(); s.background.fill.fore_color.rgb = bg
    tb(s, 548640, 256032, 8229600, 274320, [kicker], 152400, True, GREY)
    tb(s, 548640, 502920, 11064240, 868680, [title], 406400, True, DARK)
    tb(s, 548640, 6446520, 10241280, 274320, ['Modelled bit flips on toy designs. Nothing physical. owner has not reviewed.'], 139700, False, GREY)
    tb(s, 10972800, 6446520, 731520, 274320, [str(num)], 139700, False, GREY)
    return s

# Slide 13: Redundancy is a code
a = base('RESULT: CODING VIEW', 'Redundancy is a code', 13)
img_w = 6309360; img_h = int(img_w * 930 / 1290)
a.shapes.add_picture('docs/comms/staircase.png', Emu(548640), Emu(1463040), Emu(img_w), Emu(img_h))
tb(a, 7132320, 1463040, 4663440, 3474720, [
   'The state words are codewords of a textbook code (distance 4); the copies are a repetition code.',
   'Flops only: flips needed = distance to the nearest non-accept word (15 of 15 codebooks).',
   'All nets: about one flip per copy; 3 of 16 three-copy codebooks fall to 2 (my prediction failed).'], 228600)
tb(a, 7132320, 5029200, 4663440, 1188720, [
   'Modelled, toy, observed not a theorem. MEASURED: 19 codebooks, T=6, apt Yosys 0.33; results/comms/distance_sweep.csv, docs/comms/CODING_VIEW.md.'], 165100, False, GREY)
a.notes_slide.notes_text_frame.text = (
 "SAY: Here is a way a communications engineer would read the design. The state words of the boot machine form a small textbook code, a Reed-Muller code with distance four, and the copied comparators are a repetition code.\n"
 "SAY: On this plot, the diagonal is what happens when only the state register may flip: in all 15 codebooks with distance up to six, the flips needed equal the distance to the nearest word that is not accept. When every net may flip, the curve stops at about one flip per comparator copy, so a bigger distance buys nothing past three.\n"
 "SAY: Some of my predictions failed and I keep them visible. The flops-only count follows the nearest fail word, not the idle word. On the project flow 3 of 16 three-copy codebooks sit at 2, and the order of the words matters: F0 then CC gives 2, CC then F0 gives 3. I did not dissect why. This is modelled, on a toy design, observed and not a theorem, and nothing here is new coding theory.")

# Slide 14: Why 2 and not 3?
b = base('RESULT: ROOT CAUSE', 'Why 2 and not 3?', 14)
tb(b, 548640, 1371600, 11064240, 1554480, [
   'At cycle 0 the machine loads the armed word 0xCC. 0xCC xor 0x96 = bits {1,3,4,6}: they belong to only 2 of the 3 copies.',
   'So 2 flips of next-state nets can turn that load into 0x96. Not a Yosys-version effect: the stored netlist (3 flips) is also Yosys 0.33, another flow.'], 228600)
rows = [('Design (8 synthesis flows, apt Yosys 0.33)', 'Minimum flips per flow'),
        ('v2: armed 0xCC, touches 2 copies', '2  1  1  2  2  2  2  2'),
        ('v2e: armed 0xA5, touches 3 copies', '3  1  1  3  3  3  3  3')]
gt = b.shapes.add_table(3, 2, Emu(548640), Emu(3017520), Emu(11064240), Emu(1097280)).table
gt.columns[0].width = Emu(6400800); gt.columns[1].width = Emu(4663440)
for i, (c0, c1) in enumerate(rows):
    for j, v in enumerate((c0, c1)):
        cell = gt.cell(i, j); cell.text = v
        for para in cell.text_frame.paragraphs:
            for r in para.runs:
                r.font.size = Emu(203200); r.font.bold = (i == 0 or j == 1); r.font.name = 'Calibri'
tb(b, 548640, 4251960, 11064240, 640080, [
   'The 1s are flows that merge the copies (opt_merge, flatten before ABC): no encoding fixes those.'], 203200)
tb(b, 548640, 4892040, 11064240, 640080, [
   'Encoding sets the floor; the synthesis flow decides whether it is reached.'], 279400, True, GREEN)
tb(b, 548640, 5577840, 11064240, 640080, [
   'MEASURED by agent P01a, re-run by the lead 2026-11-20: docs/report/WHY_TWO_FLIPS.md, rtl/v2e.v. Stem rule, T=6, k<=3, toy design; conda 0.38 gives 3 only on its plain flow.'], 165100, False, GREY)
b.notes_slide.notes_text_frame.text = (
 "SAY: Earlier I blamed the Yosys version for V2 needing three flips on one netlist and two on another. That was wrong, and a fresh-eyes review caught it: both netlists come from Yosys 0.33.\n"
 "SAY: The real reason is in the encoding. Before the key check, the machine loads the armed word CC. CC and the accept word 96 differ in four bits, and those four bits belong to only two of the three comparator copies. So an attacker does not need to fool all three copies: two flips at the moment CC is loaded are enough, if the netlist has one shared net per copy.\n"
 "SAY: To test that, only the one constant was changed to A5, which touches all three copies. Over the same eight synthesis flows V2 gives 2, 1, 1, 2, 2, 2, 2, 2 and the re-encoded design gives 3, 1, 1, 3, 3, 3, 3, 3. The ones are flows that merge the copies, and no encoding fixes that. So: encoding sets the floor, the flow decides whether it is reached. Toy design, modelled flips, bounded at six cycles and three flips.")

# move the two new slides (now last) to positions 12 and 13 (0-based), i.e. after slide 12
lst = p.slides._sldIdLst
ids = list(lst)
na, nb = ids[-2], ids[-1]
lst.remove(na); lst.remove(nb)
lst.insert(12, na); lst.insert(13, nb)
# renumber page-number boxes on every slide
for i, s in enumerate(p.slides, 1):
    for sh in s.shapes:
        if sh.has_text_frame and sh.left == 10972800 and sh.top == 6446520:
            r = sh.text_frame.paragraphs[0].runs[0]; r.text = str(i)
p.save(SRC)
print('slides', len(p.slides))
