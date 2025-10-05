# ============================================================
#  🏇 PUREUNITY STABLE + EW GUARDRAIL + MULTI-GOLD + NAP/NB
#  3-run window | EW-safe | Auto NAP/NB
#  Author: Carl Kennett  |  Timezone: Europe/London
# ============================================================

import pdfplumber, re, pandas as pd

# ------------------------------------------------------------
# 1️⃣ PARSER — Raw-Line Scan (no dropped runners)
# ------------------------------------------------------------
def parse_races_from_pdf(path: str):
    """Extracts all races and runner form lines from an ATR 'Form Printouts' PDF."""
    races, current_race = [], None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if re.search(r"\(R\d+\)", line):
                    if current_race:
                        if current_race["runners"] == 0:
                            current_race["runners"] = len(current_race["horses"])
                        races.append(current_race)
                    time_match = re.search(r"\d{1,2}:\d{2}", line)
                    race_time = time_match.group() if time_match else "??:??"
                    current_race = {"time": race_time, "runners": 0, "horses": []}
                    for la in lines[i:i+3]:
                        m = re.search(r"(\d+)\s+RUNNERS", la.upper())
                        if m:
                            current_race["runners"] = int(m.group(1))
                elif current_race and "ATR VERDICT" not in (line or ""):
                    parts = (line or "").strip().split()
                    if len(parts) > 1:
                        form = parts[-1]
                        name = " ".join(parts[:-1])
                        if re.match(r"^[\dA-Z\-PBFUR]+$", form):
                            current_race["horses"].append({"name": name, "form": form})
        if current_race:
            if current_race["runners"] == 0:
                current_race["runners"] = len(current_race["horses"])
            races.append(current_race)
    return races


# ------------------------------------------------------------
# 2️⃣ REL SCORING — 3-run window
# ------------------------------------------------------------
def score_rel(form: str) -> int:
    """REL4 = ≥2 wins or 3 placings last 3; REL3 = 1 win or 2 placings last 3."""
    digits = [int(ch) for ch in re.sub(r"[^0-9]", "", form)[-3:]]
    if digits.count(1) >= 2 or sum(d <= 3 for d in digits) >= 3:
        return 4
    elif digits.count(1) >= 1 or sum(d <= 3 for d in digits) >= 2:
        return 3
    elif sum(d <= 4 for d in digits) >= 1:
        return 2
    return 1


# ------------------------------------------------------------
# 3️⃣ MAIN FILTER LOGIC — EW Guardrail + Multi-Gold + NAP/NB
# ------------------------------------------------------------
def stable_filter(races):
    out = []

    for race in races:
        horses = race["horses"]
        for h in horses:
            h["rel"] = score_rel(h["form"])
            digits = [int(ch) for ch in re.sub(r"[^0-9]", "", h["form"])]
            h["lto"] = digits[-1] if digits else 99

        ranked = sorted(horses, key=lambda h: (-h["rel"], h["lto"], h["name"]))
        if not ranked:
            continue

        # Multi-Gold rule (identical REL + LTO)
        golds = [ranked[0]["name"]]
        if len(ranked) > 1 and ranked[0]["rel"] == ranked[1]["rel"] and ranked[0]["lto"] == ranked[1]["lto"]:
            golds.append(ranked[1]["name"])

        silver = ranked[1]["name"] if len(ranked) > 1 and ranked[1]["name"] not in golds else None

        guardrail = "✅ EW OK" if 7 <= race["runners"] <= 13 else "🚫 Observe"

        out.append({
            "Time": race["time"],
            "Runners": race["runners"],
            "🥇 Gold": "; ".join(golds),
            "🥈 Silver": silver,
            "Guardrail": guardrail
        })

    df = pd.DataFrame(out)
    # --- Auto NAP/NB (among EW-qualified races)
    ew_df = df[df["Guardrail"] == "✅ EW OK"].copy()
    nap = nb = None
    if not ew_df.empty:
        nap = ew_df.iloc[0]["🥇 Gold"]
        if len(ew_df) > 1:
            nb = ew_df.iloc[1]["🥇 Gold"]

    print(df.to_markdown(index=False))
    print("\n🏆 NAP:", nap)
    print("⭐ NB:", nb)
    return df
