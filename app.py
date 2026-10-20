"""Walmart Edition B buy-side research interface; presentation never changes model logic."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from src.app_state import editable_driver_rows, load_analyst_edits, rows_to_overrides, save_analyst_edits
from src.assumption_registry import completeness_report, load_ai_log, load_challenges
from src.comps import CompsValidationError, included_peer_multiples, load_peer_candidates, load_peer_financials, multiple_ranges, peer_removal_sensitivity
from src.config import ROOT, load_config, load_evidence, load_json
from src.historical import derived_gross_profit, fy2026_opening_reconciliation, historical_reconciliation_errors, load_historical
from src.scenarios import load_scenario_cases, run_case, run_named_cases
from src.three_statement import ThreeStatementModelError, load_model_inputs, run_all_scenarios, run_scenario_with_overrides
from src.validation import validate_dcf_inputs
from src.wmt_dcf import DCFModelError, calculate_wacc, dcf_enterprise_value, enterprise_to_equity_bridge, forecast_fcff, require_current_market_price, reverse_dcf_uniform_fcff_multiplier, sensitivity_table

st.set_page_config(page_title="Walmart | Edition B Research", page_icon="W", layout="wide")

def read_json_path(path: Path) -> dict[str, Any] | None:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None

def usd_m(value: Any) -> str:
    return "Unavailable" if value is None or pd.isna(value) else f"${float(value):,.0f}m"

def usd_share(value: Any) -> str:
    return "Unavailable" if value is None or pd.isna(value) else f"${float(value):,.2f}"

def pct(value: Any) -> str:
    return "Unavailable" if value is None or pd.isna(value) else f"{100 * float(value):.1f}%"

def export_frame(label: str, frame: pd.DataFrame, filename: str) -> None:
    st.download_button(label, frame.to_csv(index=False).encode("utf-8"), filename, "text/csv")

def source_note() -> None:
    st.caption("Reported facts are read-only. Analyst edits live separately in data/analyst_edits.json and are not source evidence.")

def workbench_overrides(base: dict[str, Any], values: dict[str, float]) -> dict[str, Any]:
    """Map only bounded operating controls into an independent Base-case override."""
    sales_shift = values["sales_growth_shift"]
    membership_shift = values["membership_growth_shift"]
    return {
        "walmart_us_sales_growth": [x + sales_shift for x in base["walmart_us_sales_growth"]],
        "international_sales_growth": [x + sales_shift for x in base["international_sales_growth"]],
        "sams_sales_growth": [x + sales_shift for x in base["sams_sales_growth"]],
        "membership_growth": [x + membership_shift for x in base["membership_growth"]],
        "gross_margin": {"walmart_us": values["walmart_us_margin"], "international": values["international_margin"], "sams": values["sams_margin"]},
        "sga_as_percent_total_revenue": values["sga"],
        "capex_as_percent_total_revenue": values["capex"],
        "borrowing_rate": values["borrowing_rate"],
    }

config, history, edits = load_config(), load_historical(), load_analyst_edits()
run_log = read_json_path(ROOT / "outputs" / "validation_execution_results.json")
validation_result = validate_dcf_inputs(config["dcf_inputs"])
historical_errors = historical_reconciliation_errors(history)
pytest_ok = bool(run_log and run_log.get("pytest_exit_code") == 0)

st.title("Walmart Inc. (WMT) | Edition B Research")
st.caption("Buy-side working application · Financial statements: USD millions · Per-share values: USD/share")
page = st.sidebar.radio("Research navigation", ["Executive Dashboard", "Historical Financials", "Three-Statement Model", "DCF Valuation", "Scenarios", "Comparable Companies", "Assumption Challenges", "Validation", "Investment Committee"])
st.sidebar.divider()
st.sidebar.error("NOT DECISION-READY" if not validation_result.passed else "DCF inputs pass gate")
st.sidebar.caption("No automatic recommendation is generated.")

if page == "Executive Dashboard":
    st.subheader("Investment-committee snapshot")
    price = load_json("dcf_valuation_inputs.json")["market_price"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Edition B valuation date", config["edition_b_valuation_date"] or "Not set")
    c2.metric("Sourced WMT share price", usd_share(price.get("value")))
    c3.metric("DCF valuation range", "Blocked" if not validation_result.passed else "See DCF")
    c4.metric("Human committee action", edits["committee"]["action"])
    st.caption("A missing price is not treated as zero; it is unavailable until a source and matching valuation date are recorded.")
    st.subheader("Critical decision blockers")
    blockers = list(validation_result.errors)
    if not pytest_ok: blockers.append("Latest validation run is missing or failed; approved valuation output is blocked.")
    for blocker in blockers or ["No critical data gate is currently reported. Human review remains required."]:
        st.error(blocker)
    left, right = st.columns((3, 2))
    with left:
        income = pd.DataFrame(history["income_statement"])
        income_trend = income.set_index("line_item").T.reset_index(names="year")
        cols = [x for x in ["Net sales", "Operating income", "Consolidated net income"] if x in income_trend]
        chart_data = income_trend.melt(id_vars="year", value_vars=cols, var_name="metric", value_name="USD millions")
        st.plotly_chart(px.line(chart_data, x="year", y="USD millions", color="metric", markers=True, title="Reported operating trend"), width="stretch")
    with right:
        st.subheader("Latest model run")
        if run_log:
            st.metric("Validation result", "PASS" if pytest_ok else "FAIL")
            st.write("Test date (UTC):", run_log.get("test_date_utc", "Unknown"))
            st.caption("Known-answer DCF comparison remains pending an independently published reference answer.")
        else: st.warning("No validation execution log found.")
    st.subheader("Material risks and monitoring")
    risks = pd.DataFrame(load_scenario_cases()["cases"])
    st.dataframe(risks[["name", "risks", "evidence_that_would_change"]], width="stretch", hide_index=True)

elif page == "Historical Financials":
    st.subheader("Reported financial history and normalizations")
    source_note()
    statement = st.selectbox("Reported statement", ["income_statement", "balance_sheet", "cash_flow", "segments"], format_func=lambda v: v.replace("_", " ").title())
    reported = pd.DataFrame(history[statement])
    st.dataframe(reported, width="stretch", hide_index=True)
    export_frame("Export selected historical statement", reported, f"wmt_{statement}.csv")
    st.subheader("FY2026 reported-to-normalized bridge")
    normalization = pd.DataFrame(load_json("normalization_catalog.json"))
    cols = [c for c in ["item", "fiscal_period", "reported_value", "adjustment", "normalized_value", "rationale", "source", "analyst_approval_status"] if c in normalization]
    st.dataframe(normalization[cols], width="stretch", hide_index=True)
    st.info("No potential item is normalized automatically. An analyst must approve an evidence-backed adjustment.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("FY2026 opening balance-sheet reconciliation")
        st.dataframe(pd.DataFrame(fy2026_opening_reconciliation(history)), width="stretch", hide_index=True)
        st.success("PASS" if not historical_errors else "FAIL")
    with c2:
        st.subheader("Revenue and gross-profit definitions")
        st.write("**Total revenues = net sales + membership and other income.** These are not interchangeable forecast inputs.")
        st.dataframe(pd.DataFrame(derived_gross_profit(history)), width="stretch", hide_index=True)
    evidence = pd.DataFrame(load_evidence())
    st.subheader("Dated evidence registry")
    st.dataframe(evidence, width="stretch", hide_index=True)
    export_frame("Export evidence registry", evidence, "wmt_evidence_registry.csv")

elif page == "Three-Statement Model":
    st.subheader("FY2027–FY2031 integrated pro-forma")
    st.warning("Forecasts are screen-grade analyst assumptions, not management guidance or verified valuation evidence.")
    model_inputs = load_model_inputs()
    scenario = st.selectbox("Named operating case", list(model_inputs["scenarios"]))
    try:
        table = pd.DataFrame(run_all_scenarios(model_inputs)[scenario])
        tabs = st.tabs(["Income statement", "Balance sheet", "Cash flow", "Checks & exports"])
        with tabs[0]:
            cols = [c for c in ["year", "total_revenue", "gross_profit", "sga_including_depreciation", "depreciation_embedded_in_sga", "ebit", "interest_expense", "pretax_income", "taxes", "net_income", "diluted_eps"] if c in table]
            st.dataframe(table[cols], width="stretch", hide_index=True)
            st.plotly_chart(px.line(table, x="year", y=["total_revenue", "ebit", "net_income"], markers=True, title="Income statement trajectory (USD millions)"), width="stretch")
        with tabs[1]:
            cols = [c for c in ["year", "cash", "receivables", "inventory", "other_operating_assets", "ppe", "accounts_payable", "other_operating_liabilities", "debt", "operating_lease_liabilities", "finance_lease_liabilities", "walmart_equity"] if c in table]
            st.dataframe(table[cols], width="stretch", hide_index=True)
        with tabs[2]:
            cols = [c for c in ["year", "cash_from_operations", "capex", "investing_cash_flow", "debt_issuance", "scheduled_debt_repayment", "dividends", "buybacks", "net_cash_movement", "cash"] if c in table]
            st.dataframe(table[cols], width="stretch", hide_index=True)
        with tabs[3]:
            checks = table[[c for c in ["year", "balance_sheet_check", "cash_flow_check", "ppe_rollforward_check", "debt_rollforward_check", "equity_rollforward_check"] if c in table]]
            st.dataframe(checks, width="stretch", hide_index=True)
            export_frame("Export full three-statement forecast", table, f"wmt_{scenario.lower()}_three_statement.csv")
    except ThreeStatementModelError as exc: st.error(f"The model rejected this input set: {exc}")
    st.subheader("Editable operating assumptions — local working layer")
    st.caption("The statement engine, FY2026 reported base, provenance, and checks are locked. Only bounded controls are exposed. Bounds come from the existing scenario/stress envelope; they are provisional analyst constraints, not historical evidence or approved valuation assumptions.")
    controls_record = load_json("workbench_controls.json")
    controls = controls_record["controls"]
    saved_values = edits.get("workbench_values", {})
    reset_col, save_col, status_col = st.columns([1, 1, 3])
    if reset_col.button("Reset to Base"):
        edits["workbench_values"] = {}
        edits["operating_overrides"] = {}
        for control in controls:
            st.session_state.pop(f"wb_{control['id']}", None)
        save_analyst_edits(edits)
        st.rerun()
    status_col.info("Local working inputs persist only in data/analyst_edits.json. They never overwrite named scenarios or source facts.")
    live_values: dict[str, float] = {}
    panel_left, panel_right = st.columns(2)
    for index, control in enumerate(controls):
        parent = panel_left if index % 2 == 0 else panel_right
        candidate = saved_values.get(control["field"], control["default"])
        candidate = min(max(float(candidate), control["minimum"]), control["maximum"])
        with parent:
            live_values[control["field"]] = st.slider(
                control["label"], control["minimum"], control["maximum"], candidate, control["step"],
                format="%.2f pp" if control["units"] == "percentage points" else "%.2f%%",
                key=f"wb_{control['id']}", help=f"Bounds basis: {control['basis']} Evidence that would change it: {control['evidence_that_would_change']}"
            )
            st.caption(f"{control['units']} · {control['basis']}")
    overrides = workbench_overrides(model_inputs["scenarios"]["Base"], live_values)
    if save_col.button("Save working case"):
        edits["workbench_values"] = live_values
        edits["operating_overrides"] = overrides
        save_analyst_edits(edits)
        st.success("Saved bounded working inputs to data/analyst_edits.json.")
    try:
        workbench = pd.DataFrame(run_scenario_with_overrides(model_inputs, "Base", overrides, "Bounded Analyst Working Case"))
        workbench_fcff = pd.DataFrame(forecast_fcff(workbench.to_dict("records"), model_inputs["scenarios"]["Base"]["tax_rate"]))
        output = workbench[["year", "total_revenue", "gross_profit", "ebit", "net_income", "cash", "debt", "balance_sheet_check", "cash_flow_check", "ppe_rollforward_check", "debt_rollforward_check", "equity_rollforward_check"]].merge(workbench_fcff[["year", "fcff"]], on="year")
        st.subheader("Live five-year statements and FCFF")
        st.dataframe(output, width="stretch", hide_index=True)
        checks = ["balance_sheet_check", "cash_flow_check", "ppe_rollforward_check", "debt_rollforward_check", "equity_rollforward_check"]
        checks_pass = all(abs(value) <= model_inputs["tolerance"] for value in output[checks].to_numpy().flatten())
        if checks_pass:
            st.success("All five-year balance-sheet, cash-flow, PP&E, debt, and equity checks pass within model tolerance.")
        else:
            st.error("CHECK FAILURE: this working combination violates a locked model articulation check. Do not use it for valuation.")
        st.error("Valuation range remains withheld: WACC, terminal growth, valuation-date bridge, current diluted shares, and market price are unresolved.")
    except ThreeStatementModelError as exc:
        st.error(f"CHECK FAILURE: the engine rejected this input combination: {exc}")
    st.subheader("One-driver sensitivity — same Base, bounded endpoints")
    sensitivity_driver = st.selectbox("Driver to stress", [item["field"] for item in controls], format_func=lambda field: next(item["label"] for item in controls if item["field"] == field))
    sensitivity_rows = []
    selected_control = next(item for item in controls if item["field"] == sensitivity_driver)
    for label, level in [("Low bound", selected_control["minimum"]), ("Base", selected_control["default"]), ("High bound", selected_control["maximum"])]:
        test_values = {item["field"]: item["default"] for item in controls}
        test_values[sensitivity_driver] = level
        try:
            forecast = run_scenario_with_overrides(model_inputs, "Base", workbench_overrides(model_inputs["scenarios"]["Base"], test_values), f"Sensitivity {label}")
            fcff = forecast_fcff(forecast, model_inputs["scenarios"]["Base"]["tax_rate"])
            final, final_fcff = forecast[-1], fcff[-1]
            passed = all(abs(final[k]) <= model_inputs["tolerance"] for k in ["balance_sheet_check", "cash_flow_check", "ppe_rollforward_check", "debt_rollforward_check", "equity_rollforward_check"])
            sensitivity_rows.append({"case": label, "input": level, "FY2031 revenue": final["total_revenue"], "FY2031 EBIT": final["ebit"], "FY2031 FCFF": final_fcff["fcff"], "checks": "PASS" if passed else "FAIL"})
        except ThreeStatementModelError as exc:
            sensitivity_rows.append({"case": label, "input": level, "FY2031 revenue": None, "FY2031 EBIT": None, "FY2031 FCFF": None, "checks": f"FAIL: {exc}"})
    sensitivity_frame = pd.DataFrame(sensitivity_rows)
    st.dataframe(sensitivity_frame, width="stretch", hide_index=True)
    export_frame("Export workbench sensitivity", sensitivity_frame, "wmt_workbench_sensitivity.csv")
    with st.expander("Locked drivers and required evidence before exposure"):
        st.dataframe(pd.DataFrame(controls_record["locked_load_bearing_drivers"]), width="stretch", hide_index=True)
    with st.expander("Driver rationale, challenge, and evidence that would change it"):
        st.dataframe(pd.DataFrame(load_json("three_statement_driver_registry.json")), width="stretch", hide_index=True)
    st.stop()
    rows, saved_overrides = editable_driver_rows(), edits.get("operating_overrides", {})
    for row in rows:
        value = saved_overrides.get(row["driver"])
        if isinstance(value, list) and row.get("year"): row["value"] = value[model_inputs["forecast_years"].index(row["year"])]
        elif isinstance(value, dict) and row.get("segment"): row["value"] = value.get(row["segment"], row["value"])
        elif isinstance(value, (int, float)): row["value"] = value
    edited_rows = st.data_editor(pd.DataFrame(rows), disabled=["driver", "year", "segment", "units"], width="stretch", hide_index=True, key="operating_driver_editor")
    if st.button("Save local operating assumptions"):
        edits["operating_overrides"] = rows_to_overrides(edited_rows.to_dict("records")); save_analyst_edits(edits)
        st.success("Saved. Refresh to use the local working layer.")
    if saved_overrides:
        try:
            local = pd.DataFrame(run_scenario_with_overrides(model_inputs, "Base", saved_overrides, "Local Analyst Working Case"))
            st.caption("Local working-case output — not an approved named scenario.")
            st.dataframe(local[["year", "total_revenue", "ebit", "cash", "debt", "balance_sheet_check", "cash_flow_check"]], width="stretch", hide_index=True)
        except ThreeStatementModelError as exc: st.error(f"Saved local assumptions fail model checks: {exc}")
    with st.expander("Driver units, basis, rationale, and evidence that would change them"):
        st.dataframe(pd.DataFrame(load_json("three_statement_driver_registry.json")), width="stretch", hide_index=True)

elif page == "DCF Valuation":
    st.subheader("FCFF discounted cash flow")
    st.caption("Enterprise-value architecture: FCFF = EBIT × (1 − normalized operating tax rate) + D&A − capex − change in operating NWC.")
    dcf, model_inputs = load_json("dcf_valuation_inputs.json"), load_model_inputs()
    scenario = dcf["forecast_scenario"]
    forecast = run_all_scenarios(model_inputs)[scenario]
    fcff = forecast_fcff(forecast, model_inputs["scenarios"][scenario]["tax_rate"])
    fcff_frame = pd.DataFrame(fcff)
    st.dataframe(fcff_frame, width="stretch", hide_index=True)
    export_frame("Export FCFF schedule", fcff_frame, "wmt_fcff_schedule.csv")
    st.subheader("WACC inputs, definitions, and source dates")
    wacc_rows = pd.DataFrame([{"input": key, **value} for key, value in dcf["wacc_inputs"].items()])
    st.dataframe(wacc_rows, width="stretch", hide_index=True)
    values = {key: item["value"] for key, item in dcf["wacc_inputs"].items() if key != "terminal_growth"}
    try:
        wacc = calculate_wacc(values)["wacc"]
        valuation = dcf_enterprise_value(fcff, wacc, dcf["wacc_inputs"]["terminal_growth"]["value"])
        c1, c2, c3 = st.columns(3)
        c1.metric("WACC", pct(wacc)); c2.metric("Enterprise value", usd_m(valuation["enterprise_value"])); c3.metric("Terminal value / EV", pct(valuation["terminal_value_share_of_ev"]))
        st.dataframe(pd.DataFrame(valuation["fcff_schedule"]), width="stretch", hide_index=True)
        sensitivity = pd.DataFrame(sensitivity_table(fcff, dcf["sensitivity"]["wacc"], dcf["sensitivity"]["terminal_growth"]))
        st.subheader("WACC versus terminal-growth sensitivity — enterprise value")
        pivot = sensitivity.pivot(index="terminal_growth", columns="wacc", values="enterprise_value")
        st.plotly_chart(px.imshow(pivot, text_auto=".0f", aspect="auto", labels={"x": "WACC", "y": "Terminal growth", "color": "Enterprise value (USD m)"}, title="Sensitivity heatmap"), width="stretch")
        export_frame("Export DCF sensitivity", sensitivity, "wmt_dcf_sensitivity.csv")
        bridge = {key: item["value"] for key, item in dcf["bridge"].items()}
        bridge_result = enterprise_to_equity_bridge(valuation["enterprise_value"], bridge)
        st.subheader("Enterprise-to-equity bridge")
        st.dataframe(pd.DataFrame([bridge_result]), width="stretch", hide_index=True)
        st.metric("Diluted per-share value", usd_share(bridge_result["value_per_share"]))
        market_price = require_current_market_price(dcf["market_price"], dcf["valuation_date"])
        implied_equity = market_price * bridge["diluted_shares"]
        multiplier = reverse_dcf_uniform_fcff_multiplier(fcff, wacc, dcf["wacc_inputs"]["terminal_growth"]["value"], implied_equity, bridge)
        st.subheader("Reverse DCF — market-implied expectation")
        st.info(f"At the sourced price of {usd_share(market_price)}, all modeled FY2027–FY2031 FCFF and terminal FCFF require a uniform {multiplier:.2f}× multiplier versus the selected operating case.")
    except DCFModelError as exc:
        st.error(f"DCF and per-share valuation are blocked: {exc}")
        st.info("FCFF is displayed for auditability; it is not a completed valuation until WACC, terminal growth, bridge claims, current diluted shares, and a matched-date price are supported.")
    st.subheader("Bridge treatment")
    st.dataframe(pd.DataFrame([{"item": key, **value} for key, value in dcf["bridge"].items()]), width="stretch", hide_index=True)
    st.caption("Operating leases are excluded from the bridge unless operating lease expense is removed from EBIT. This prevents double counting.")

elif page == "Scenarios":
    st.subheader("Causal scenarios and named stress tests")
    catalog = load_scenario_cases(); st.warning(f"Base-case approval: {catalog['base_case_approval_status']}. No probabilities are assigned.")
    results, base = run_named_cases(catalog), next(row for row in run_named_cases(catalog) if row["name"] == "Base")
    summary = []
    for result in results:
        final, final_fcff = (result["forecast"][-1], result["fcff"][-1]) if result["forecast"] else ({}, {})
        summary.append({"case": result["name"], "FY2031 revenue": final.get("total_revenue"), "FY2031 EBIT": final.get("ebit"), "FY2031 FCFF": final_fcff.get("fcff"), "enterprise_value": result["enterprise_value"], "equity_value": result["equity_value"], "per_share_value": result["per_share_value"], "change vs base FCFF": final_fcff.get("fcff") - base["fcff"][-1]["fcff"] if final_fcff else None, "checks_pass": result["checks_pass"], "valuation_status": result["valuation_status"]})
    scenario_frame = pd.DataFrame(summary)
    st.dataframe(scenario_frame, width="stretch", hide_index=True)
    export_frame("Export scenario results", scenario_frame, "wmt_scenario_results.csv")
    st.plotly_chart(px.bar(scenario_frame.dropna(subset=["FY2031 FCFF"]), x="case", y="FY2031 FCFF", color="checks_pass", title="FY2031 FCFF by causal case (USD millions)"), width="stretch")
    selected = st.selectbox("Inspect narrative and driver changes", [case["name"] for case in catalog["cases"]])
    case = next(item for item in catalog["cases"] if item["name"] == selected)
    st.write(case["narrative"]); st.json(case["overrides"]); st.write("**Risks:**", case["risks"]); st.write("**Observable evidence:**", case["evidence_that_would_change"])
    st.subheader("What-if operating case")
    st.caption("Controls change independent operating drivers, then rerun all statements. No arbitrary valuation haircut is applied.")
    growth_shift = st.slider("Sales-growth shift (percentage points)", -5.0, 5.0, 0.0, 0.25) / 100
    margin_shift = st.slider("OS&G&A shift (percentage points of revenue)", -3.0, 5.0, 0.0, 0.25) / 100
    capex_shift = st.slider("Capex shift (percentage points of revenue)", -2.0, 5.0, 0.0, 0.25) / 100
    drivers = load_model_inputs()["scenarios"]["Base"]
    custom = {"walmart_us_sales_growth": [x + growth_shift for x in drivers["walmart_us_sales_growth"]], "international_sales_growth": [x + growth_shift for x in drivers["international_sales_growth"]], "sams_sales_growth": [x + growth_shift for x in drivers["sams_sales_growth"]], "sga_as_percent_total_revenue": drivers["sga_as_percent_total_revenue"] + margin_shift, "capex_as_percent_total_revenue": drivers["capex_as_percent_total_revenue"] + capex_shift}
    what_if = run_case({"name": "Interactive what-if", "overrides": custom})
    if what_if["forecast"]: st.dataframe(pd.DataFrame(what_if["forecast"])[["year", "total_revenue", "ebit", "cash", "debt", "balance_sheet_check", "cash_flow_check"]], width="stretch", hide_index=True)
    else: st.error(what_if["valuation_status"])
    st.warning("Recommendation impact is blocked: no sourced market price or analyst-defined margin-of-safety threshold is recorded. Committee action is never changed automatically.")

elif page == "Comparable Companies":
    st.subheader("Comparable-company valuation")
    st.caption("Multiples require matched-date market data, authoritative financials, and consistent EV and earnings definitions.")
    candidates, peers = pd.DataFrame(load_peer_candidates()), load_peer_financials()
    st.dataframe(candidates, width="stretch", hide_index=True)
    source_table = pd.DataFrame(peers["peers"]); st.dataframe(source_table, width="stretch", hide_index=True)
    export_frame("Export peer source table", source_table, "wmt_comparables_source_status.csv")
    try:
        multiple_rows = included_peer_multiples(peers)
        st.dataframe(pd.DataFrame(multiple_rows), width="stretch", hide_index=True)
        st.dataframe(pd.DataFrame(multiple_ranges(multiple_rows)).T.reset_index(names="multiple"), width="stretch", hide_index=True)
        st.subheader("Peer-removal sensitivity"); st.dataframe(pd.DataFrame(peer_removal_sensitivity(multiple_rows, "ev_ebitda")), width="stretch", hide_index=True)
    except CompsValidationError as exc: st.warning(f"Comparable valuation withheld: {exc}")
    st.info("Transaction multiples are excluded because control premiums, synergies, timing, and comparability are not evidenced in this record.")
    st.markdown("Peer selection policy: `docs/peer_selection_policy.md`")

elif page == "Assumption Challenges":
    st.subheader("Assumption challenge registry")
    st.warning("AI suggestions are not human challenges or approvals. Empty Weeks 5–6 partner entries remain intentionally blank until a real reviewer participates.")
    records = pd.DataFrame(load_challenges())
    reviewed = st.data_editor(records, width="stretch", hide_index=True, num_rows="dynamic", key="challenge_editor")
    if st.button("Save challenge registry"):
        (ROOT / "data" / "assumption_challenge_registry.json").write_text(json.dumps(reviewed.to_dict("records"), indent=2) + "\n", encoding="utf-8"); st.success("Saved human edits to the explicit registry.")
    export_frame("Export challenge registry", reviewed, "wmt_assumption_challenge_registry.csv")
    st.subheader("Completeness report"); st.dataframe(pd.DataFrame(completeness_report(reviewed.to_dict("records"))), width="stretch", hide_index=True)
    st.subheader("AI-use record")
    ai_log = pd.DataFrame(load_ai_log())
    edited_log = st.data_editor(ai_log, width="stretch", hide_index=True, num_rows="dynamic", key="ai_log_editor")
    if st.button("Save AI-use record"):
        (ROOT / "data" / "ai_use_log.json").write_text(json.dumps(edited_log.to_dict("records"), indent=2) + "\n", encoding="utf-8"); st.success("Saved human AI-use decisions.")
    export_frame("Export AI-use record", edited_log, "wmt_ai_use_log.csv")

elif page == "Validation":
    st.subheader("Validation dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pytest cold run", "PASS" if pytest_ok else "FAIL / missing")
    c2.metric("Historical reconciliation", "PASS" if not historical_errors else "FAIL")
    c3.metric("DCF input gate", "PASS" if validation_result.passed else "BLOCKED")
    if run_log:
        st.write("Latest successful run:", run_log.get("test_date_utc", "Unknown"))
        st.write("Known-answer status:", run_log.get("training_case_known_answer", {}).get("status", "Unknown"))
        st.download_button("Export machine-readable validation result", json.dumps(run_log, indent=2).encode("utf-8"), "validation_execution_results.json", "application/json")
    else: st.error("Validation execution result is missing. Run `python scripts/run_validation.py`.")
    for error in validation_result.errors: st.error(error)
    for warning in validation_result.warnings: st.warning(warning)
    for error in historical_errors: st.error(error)
    unresolved = pd.DataFrame([
        {"area": "Sam's Club charges", "question": "Quantify and assess FY2026 supply-chain reorganization charges before any normalization."},
        {"area": "Revenue", "question": "Select a consistent forecast definition: total revenues or net sales plus membership and other income."},
        {"area": "Working capital", "question": "Reconcile receivables, inventory, payables, accrued liabilities, and acquisition/disposition effects."},
        {"area": "Equity bridge", "question": "Determine valuation-date treatment of cash, debt, leases, and noncontrolling interests."},
    ])
    st.subheader("Unresolved source and definition questions")
    st.dataframe(unresolved, width="stretch", hide_index=True)
    export_frame("Export validation and unresolved items", unresolved, "wmt_validation_unresolved_items.csv")

else:
    st.subheader("Investment Committee")
    st.warning("This field is owned by the human analyst and committee. The model cannot approve or change an investment action.")
    actions = ["INITIATE", "WATCH/DEFER", "DO NOT INITIATE"]
    action = st.selectbox("Committee action", actions, index=actions.index(edits["committee"]["action"]))
    rationale = st.text_area("Analyst rationale", value=edits["committee"].get("rationale", ""), placeholder="Document valuation range, evidence, risks, and decision owner.")
    triggers = st.text_area("Monitoring triggers", value=edits["committee"].get("monitoring_triggers", ""), placeholder="Specify observable milestones or disconfirming evidence.")
    if st.button("Save human committee record"):
        edits["committee"] = {"action": action, "rationale": rationale, "monitoring_triggers": triggers}; save_analyst_edits(edits); st.success("Saved to data/analyst_edits.json.")
    memo = pd.DataFrame([{"company": config["company"], "ticker": config["ticker"], "edition_b_valuation_date": config["edition_b_valuation_date"], "committee_action": action, "analyst_rationale": rationale, "monitoring_triggers": triggers, "validation_status": "PASS" if validation_result.passed and pytest_ok else "BLOCKED", "latest_validation_run": run_log.get("test_date_utc") if run_log else None}])
    st.subheader("Committee memo export"); st.dataframe(memo, width="stretch", hide_index=True); export_frame("Export committee memo", memo, "wmt_committee_memo.csv")
    if not validation_result.passed or not pytest_ok: st.error("An approved valuation output is blocked until unresolved source inputs are completed and validation is passing.")
