"""Build gold_labeling.xlsx from data/gold.csv.

Run `adclass assist` first. Assisted ads get the keyword baseline's labels
pre-filled (blue) plus a `checked` cell to confirm; blind ads are left
empty (yellow) to label from scratch. Import results with
`adclass import-labels --xlsx gold_labeling.xlsx`.
"""

import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.formatting.rule import FormulaRule  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from adclass.schema import GOALS, ISSUES  # noqa: E402

rows = list(csv.DictReader(open(ROOT / "data" / "gold.csv", encoding="utf-8")))
if not all(r.get("label_mode") for r in rows):
    sys.exit("Run `adclass assist` first so every ad is marked blind or assisted.")
N = len(rows)
N_BLIND = sum(r["label_mode"] == "blind" for r in rows)
N_ASSIST = N - N_BLIND

F = "Arial"
font = Font(name=F, size=10)
bold = Font(name=F, size=10, bold=True)
grey = Font(name=F, size=9, color="808080")
head_font = Font(name=F, size=10, bold=True, color="FFFFFF")
head_fill = PatternFill("solid", fgColor="44546A")
todo_fill = PatternFill("solid", fgColor="FFF2CC")     # yellow: fill in from scratch
suggest_fill = PatternFill("solid", fgColor="DDEBF7")  # blue: pre-filled suggestion, needs checking
na_fill = PatternFill("solid", fgColor="EDEDED")
white = PatternFill("solid", fgColor="FFFFFF")
wrap_top = Alignment(wrap_text=True, vertical="top")
thin = Border(bottom=Side(style="thin", color="D9D9D9"))

wb = Workbook()

# ---------------- Label sheet ----------------
ws = wb.active
ws.title = "Label"
cols = ["#", "ad_id", "ad_text", "gold_goal", "gold_issue", "checked", "notes", "why_suggested",
        "page_name", "source_url", "search_term", "paid_for", "started_running"]
HIDDEN = {"page_name", "source_url", "search_term", "paid_for", "started_running"}
WIDTHS = {"#": 5, "ad_id": 19, "ad_text": 80, "gold_goal": 14, "gold_issue": 20, "checked": 10, "notes": 32, "why_suggested": 38}
ws.append(cols)
for c in ws[1]:
    c.font, c.fill, c.alignment = head_font, head_fill, Alignment(vertical="center", wrap_text=True)
for i, name in enumerate(cols, start=1):
    letter = ws.cell(1, i).column_letter
    ws.column_dimensions[letter].width = WIDTHS.get(name, 20)
    ws.column_dimensions[letter].hidden = name in HIDDEN
col = {name: i + 1 for i, name in enumerate(cols)}

for n, r in enumerate(rows, start=1):
    blind = r["label_mode"] == "blind"
    values = {
        "#": n, "ad_id": r["ad_id"], "ad_text": r["ad_text"],
        "gold_goal": r["gold_goal"] or ("" if blind else r["suggested_goal"]),
        "gold_issue": r["gold_issue"] or ("" if blind else r["suggested_issue"]),
        "checked": "blind" if blind else "",
        "notes": r["notes"],
        "why_suggested": "BLIND: label from scratch" if blind else r["suggestion_reason"],
    }
    ws.append([values.get(c, r.get(c, "")) for c in cols])
    row = n + 1
    for c in ws[row]:
        c.font, c.alignment, c.border = font, wrap_top, thin
    ws.cell(row, col["#"]).font = grey
    ws.cell(row, col["ad_id"]).font = grey
    ws.cell(row, col["ad_id"]).number_format = "@"
    ws.cell(row, col["why_suggested"]).font = Font(name=F, size=9, color="595959", bold=blind)
    for name in ("gold_goal", "gold_issue"):
        ws.cell(row, col[name]).fill = todo_fill if blind else suggest_fill
    ws.cell(row, col["checked"]).fill = na_fill if blind else todo_fill
    if blind:
        ws.cell(row, col["checked"]).font = grey
    ws.cell(row, col["notes"]).fill = todo_fill
    lines = sum(max(1, math.ceil(len(p) / 85)) for p in r["ad_text"].split("\n"))
    ws.row_dimensions[row].height = min(409, max(30, 13 * lines + 5))

last = N + 1
ws.freeze_panes = "D2"
ws.auto_filter.ref = f"A1:{ws.cell(1, len(cols)).column_letter}{last}"

# ---------------- dropdown sources ----------------
ls = wb.create_sheet("Lists")
ls["A1"], ls["B1"], ls["C1"] = "goal", "issue", "checked"
for i, g in enumerate(GOALS, start=2):
    ls.cell(i, 1, g)
for i, s in enumerate(ISSUES, start=2):
    ls.cell(i, 2, s)
ls["C2"] = "yes"
ls.sheet_state = "hidden"


def add_list(letter: str, src: str, label: str, prompt: str) -> None:
    v = DataValidation(type="list", formula1=src, allow_blank=True)
    v.errorTitle, v.error, v.errorStyle = f"Invalid {label}", f"Pick a {label} from the list.", "stop"
    v.promptTitle, v.prompt = label, prompt
    v.showErrorMessage = v.showInputMessage = True
    ws.add_data_validation(v)
    v.add(f"{letter}2:{letter}{last}")


L = {name: ws.cell(1, col[name]).column_letter for name in cols}
add_list(L["gold_goal"], f"=Lists!$A$2:$A${len(GOALS) + 1}", "goal", "Codebook goal label (see Guide tab).")
add_list(L["gold_issue"], f"=Lists!$B$2:$B${len(ISSUES) + 1}", "issue", "Codebook issue label (see Guide tab).")
add_list(L["checked"], "=Lists!$C$2:$C$2", "checked", "Pick yes once you agree with (or have corrected) both labels.")

# A row turns white once it's final: assisted + checked, or blind + labeled.
g, i_, k = L["gold_goal"], L["gold_issue"], L["checked"]
ws.conditional_formatting.add(
    f"{g}2:{i_}{last}",
    FormulaRule(formula=[f'OR(${k}2="yes",AND(${k}2="blind",{g}2<>""))'], fill=white),
)
ws.conditional_formatting.add(f"{k}2:{k}{last}", FormulaRule(formula=[f'{k}2="yes"'], fill=white))

# ---------------- Guide sheet ----------------
gs = wb.create_sheet("Guide", 0)
gs.column_dimensions["A"].width = 24
gs.column_dimensions["B"].width = 100


def put(r, a, b="", fa=font, fb=font, fill=None):
    gs.cell(r, 1, a).font = fa
    gs.cell(r, 2, b).font = fb
    for c in (1, 2):
        gs.cell(r, c).alignment = wrap_top
    if fill:
        gs.cell(r, 2).fill = fill
    if isinstance(b, str) and len(b) > 100:
        gs.row_dimensions[r].height = 13 * math.ceil(len(b) / 100) + 4


put(1, "Political ad labeling", "", Font(name=F, size=14, bold=True))
r = 3
put(r, "Two kinds of rows", "", bold); r += 1
put(r, f"Assisted ({N_ASSIST})", "gold_goal and gold_issue are PRE-FILLED in blue by the keyword-rule model; why_suggested shows the words that drove it. Read the ad, fix either label if it's wrong, then set checked = yes. A suggestion only counts as your label once checked = yes.", bold, fill=suggest_fill); r += 1
put(r, f"Blind ({N_BLIND})", "No suggestion (checked shows 'blind'). Label from scratch in the yellow cells. These randomly chosen ads are the clean benchmark, and they measure how much the suggestions sway you, so don't skip them or look up the rule model's answer.", bold, fill=todo_fill); r += 1
put(r, "Done looks like", "A row turns white when it's final. Notes are optional: one line on any close call.", bold); r += 1
put(r, "Don't rubber-stamp", "If you find you're accepting nearly every suggestion without reading the ad, slow down. The import reports how often you changed the suggested labels.", bold); r += 1
put(r, "Hidden columns", "page_name, source_url, search_term, paid_for, and started_running are hidden on purpose; label from the words only. Leave them in the file.", bold); r += 1
put(r, "When done", "Save as .xlsx and run: adclass import-labels --xlsx gold_labeling.xlsx (or send the file back).", bold); r += 2

put(r, "Example (not a real ad)", "", bold); r += 1
put(r, "ad_text", "Polls open 7am-7pm on Nov 3. Find your polling place at example.org."); r += 1
put(r, "gold_goal / gold_issue", "mobilization / other", fill=suggest_fill); r += 1
put(r, "why_suggested", 'goal: civic action "polling place" (rule 2); issue: no topic keywords', grey, grey); r += 1
put(r, "checked", "yes", fill=white); r += 2

put(r, "GOAL", "What the ad primarily asks of the viewer", bold, bold); r += 1
for a, b in [
    ("persuasion", "Change or reinforce what the viewer thinks about a candidate, party, or issue (contrast, attack, biography)."),
    ("mobilization", "A civic action other than money: register, request/return a ballot, find a polling place, learn early-voting dates, make a plan to vote (no named candidate), volunteer, attend, sign a petition or pledge."),
    ("fundraising", "Asks for money, even while arguing a position."),
    ("other", "None of the above (lead generation, merchandise, streaming, service announcements, thank-yous)."),
    ("Tie-break 1", "Any explicit request for money -> fundraising."),
    ("Tie-break 2", "Practical voting info, or a petition / pledge / volunteer ask -> mobilization, even if the ad also argues a position."),
    ("Tie-break 3", "Urging a vote for a named candidate or ballot measure is persuasion, even with a date, unless the ad also gives practical voting info. A get-out-the-vote ask naming no candidate is mobilization."),
]:
    put(r, a, b, bold if a.startswith("Tie") else font); r += 1
r += 1
put(r, "ISSUE", "The main policy topic: whichever gets the most words", bold, bold); r += 1
for a, b in [
    ("economy", "Jobs, wages, prices, inflation, taxes, housing costs, trade, budget"),
    ("healthcare", "Insurance, Medicare/Medicaid, drug prices, ACA, pre-existing conditions"),
    ("abortion", "Abortion access or restrictions, reproductive rights, IVF, contraception"),
    ("immigration", "Border, deportation, asylum, legal immigration"),
    ("democracy_voting", "Voting rights, election integrity, ballot access, courts as institutions, threats to democracy"),
    ("candidate_character", "Mainly about a person's honesty, scandal, competence, or biography rather than a policy"),
    ("public_safety", "Crime, policing, guns, drugs"),
    ("other", "Anything else (climate, education, veterans, foreign policy), or no identifiable topic"),
    ("Tie-break 1", "Two issues present -> the one with more of the ad's words."),
    ("Tie-break 2", "Mobilization ad with no topic -> other."),
    ("Tie-break 3", "Fundraising ad -> the issue the appeal is built around, else other."),
]:
    put(r, a, b, bold if a.startswith("Tie") else font); r += 1

r += 1
put(r, "PROGRESS", "", bold); r += 1
rng = lambda name: f"Label!${L[name]}$2:${L[name]}${last}"  # noqa: E731
left = Alignment(horizontal="left")
gs.cell(r, 1, "Assisted checked").font = font
gs.cell(r, 2, f'=COUNTIF({rng("checked")},"yes")').font = font
gs.cell(r, 3, f"of {N_ASSIST}").font = grey
checked_row = r; r += 1
gs.cell(r, 1, "Blind labeled").font = font
gs.cell(r, 2, f'=COUNTIFS({rng("checked")},"blind",{rng("gold_goal")},"<>",{rng("gold_issue")},"<>")').font = font
gs.cell(r, 3, f"of {N_BLIND}").font = grey
blind_row = r; r += 1
gs.cell(r, 1, "Rows remaining").font = bold
gs.cell(r, 2, f"={N}-B{checked_row}-B{blind_row}").font = bold
r += 2
put(r, "Final counts per label", "Counts only finished rows. Labels with fewer than about 5 ads will have unreliable scores.", bold, grey); r += 1
for name, values in (("gold_goal", GOALS), ("gold_issue", ISSUES)):
    for v in values:
        gs.cell(r, 1, f"{name.split('_')[1]}: {v}").font = font
        gs.cell(r, 2, f'=COUNTIFS({rng(name)},"{v}",{rng("checked")},"yes")+COUNTIFS({rng(name)},"{v}",{rng("checked")},"blind")').font = font
        r += 1
for row_cells in gs.iter_rows(min_row=checked_row, max_row=r, min_col=2, max_col=2):
    for c in row_cells:
        c.alignment = left

for sheet in (ws, gs):
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
ws.print_title_rows = "1:1"
wb.active = 1

out = Path.cwd() / "gold_labeling.xlsx"
wb.save(out)
print(f"saved {out}: {N} ads ({N_ASSIST} assisted, {N_BLIND} blind)")
