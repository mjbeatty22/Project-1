"""FCFF DCF calculations linked to the three-statement forecast; no FCFE."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from src.config import load_json
from src.three_statement import run_scenario

class DCFModelError(ValueError): pass

def load_dcf_inputs() -> dict[str,Any]: return load_json("dcf_valuation_inputs.json")

def operating_nwc(row:dict[str,float])->float:
    return row["receivables"]+row["inventory"]+row["other_operating_assets"]-row["accounts_payable"]-row["other_operating_liabilities"]

def forecast_fcff(three_statement:list[dict[str,float]], normalized_operating_tax_rate:float)->list[dict[str,float]]:
    if len(three_statement)!=5: raise DCFModelError("FCFF requires exactly five forecast years.")
    if not 0 <= normalized_operating_tax_rate < 1: raise DCFModelError("Normalized operating tax rate must be from 0% to under 100%.")
    previous_nwc=None; out=[]
    for row in three_statement:
        nwc=operating_nwc(row)
        # The three-statement CFO uses balance-sheet deltas; carry its operating NWC delta to preserve linkage.
        if previous_nwc is None:
            change_nwc=(row["receivables"]-11172)+(row["inventory"]-58851)+(row["other_operating_assets"]-4124)-(row["accounts_payable"]-63061)-(row["other_operating_liabilities"]-31783)
        else: change_nwc=nwc-previous_nwc
        fcff=row["ebit"]*(1-normalized_operating_tax_rate)+row["depreciation_embedded_in_sga"]-row["capex"]-change_nwc
        out.append({"year":row["year"],"ebit":row["ebit"],"normalized_operating_tax_rate":normalized_operating_tax_rate,"nopat":row["ebit"]*(1-normalized_operating_tax_rate),"d_and_a":row["depreciation_embedded_in_sga"],"capex":row["capex"],"change_operating_nwc":change_nwc,"fcff":fcff})
        previous_nwc=nwc
    return out

def calculate_wacc(values:dict[str,float])->dict[str,float]:
    required=("risk_free_rate","equity_risk_premium","beta","pretax_cost_of_debt","tax_rate","market_value_equity","market_value_debt")
    if any(not isinstance(values.get(k),(int,float)) for k in required): raise DCFModelError("WACC is blocked: required sourced input is missing.")
    if values["market_value_equity"]<=0 or values["market_value_debt"]<0: raise DCFModelError("Market-value capital weights are invalid.")
    cost_equity=values["risk_free_rate"]+values["beta"]*values["equity_risk_premium"]; aftertax_debt=values["pretax_cost_of_debt"]*(1-values["tax_rate"]); total=values["market_value_equity"]+values["market_value_debt"]
    return {"cost_of_equity":cost_equity,"after_tax_cost_of_debt":aftertax_debt,"equity_weight":values["market_value_equity"]/total,"debt_weight":values["market_value_debt"]/total,"wacc":cost_equity*values["market_value_equity"]/total+aftertax_debt*values["market_value_debt"]/total}

def dcf_enterprise_value(fcff:list[dict[str,float]], wacc:float, terminal_growth:float)->dict[str,Any]:
    if len(fcff)!=5: raise DCFModelError("Use an explicit five-year discount period.")
    if wacc<=terminal_growth: raise DCFModelError("WACC must exceed terminal growth.")
    if wacc<=0: raise DCFModelError("WACC must be positive.")
    pv_rows=[]
    for period,row in enumerate(fcff,start=1): pv_rows.append({**row,"discount_period":period,"present_value":row["fcff"]/(1+wacc)**period})
    year6_fcff=fcff[-1]["fcff"]*(1+terminal_growth); terminal_value=year6_fcff/(wacc-terminal_growth); pv_terminal=terminal_value/(1+wacc)**5; ev=sum(x["present_value"] for x in pv_rows)+pv_terminal
    return {"fcff_schedule":pv_rows,"year6_fcff":year6_fcff,"terminal_value_end_fy2031":terminal_value,"pv_terminal_value":pv_terminal,"enterprise_value":ev,"terminal_value_share_of_ev":pv_terminal/ev if ev else None}

def enterprise_to_equity_bridge(ev:float, bridge:dict[str,float])->dict[str,float]:
    required=("cash","debt","finance_leases","redeemable_nci","nonredeemable_nci","other_claims","diluted_shares")
    if any(not isinstance(bridge.get(k),(int,float)) for k in required): raise DCFModelError("Per-share value suppressed: enterprise-to-equity bridge or current diluted shares is unresolved.")
    if bridge["diluted_shares"]<=0: raise DCFModelError("Diluted share denominator must be positive and in millions.")
    equity=ev+bridge["cash"]-bridge["debt"]-bridge["finance_leases"]-bridge["redeemable_nci"]-bridge["nonredeemable_nci"]-bridge["other_claims"]
    return {"enterprise_value":ev,"cash_added":bridge["cash"],"debt_subtracted":bridge["debt"],"finance_leases_subtracted":bridge["finance_leases"],"redeemable_nci_subtracted":bridge["redeemable_nci"],"nonredeemable_nci_subtracted":bridge["nonredeemable_nci"],"other_claims_subtracted":bridge["other_claims"],"equity_value":equity,"diluted_shares_millions":bridge["diluted_shares"],"value_per_share":equity/bridge["diluted_shares"]}

def require_current_market_price(market_price:dict[str,Any], valuation_date:str|None)->float:
    if not valuation_date or not isinstance(market_price.get("value"),(int,float)) or market_price["value"]<=0:
        raise DCFModelError("Reverse DCF and upside/downside are blocked: a sourced market price and valuation date are required.")
    if market_price.get("as_of") != valuation_date:
        raise DCFModelError("Market price is stale or does not match the valuation date.")
    return market_price["value"]

def sensitivity_table(fcff:list[dict[str,float]], waccs:list[float], growths:list[float])->list[dict[str,Any]]:
    rows=[]
    for wacc in waccs:
        for growth in growths:
            rows.append({"wacc":wacc,"terminal_growth":growth,"enterprise_value":None if growth>=wacc else dcf_enterprise_value(fcff,wacc,growth)["enterprise_value"]})
    return rows

def reverse_dcf_uniform_fcff_multiplier(fcff:list[dict[str,float]], wacc:float, growth:float, target_equity_value:float, bridge:dict[str,float])->float:
    if target_equity_value<=0: raise DCFModelError("Target equity value must be positive.")
    # Linear because each FCFF and terminal value scale with the same multiplier.
    base_ev=dcf_enterprise_value(fcff,wacc,growth)["enterprise_value"]; net_claims=bridge["cash"]-bridge["debt"]-bridge["finance_leases"]-bridge["redeemable_nci"]-bridge["nonredeemable_nci"]-bridge["other_claims"]
    return (target_equity_value-net_claims)/base_ev

def integrated_dcf(inputs:dict[str,Any]|None=None)->dict[str,Any]:
    config=deepcopy(inputs if inputs else load_dcf_inputs()); scenario=config["forecast_scenario"]
    tax=config["wacc_inputs"]["tax_rate"]["value"]
    if not isinstance(tax,(int,float)): raise DCFModelError("DCF is blocked: normalized operating tax rate is unsourced.")
    forecast=run_scenario(load_json("three_statement_inputs.json"),scenario); fcff=forecast_fcff(forecast,tax)
    wacc_values={k:v["value"] for k,v in config["wacc_inputs"].items() if k in {"risk_free_rate","equity_risk_premium","beta","pretax_cost_of_debt","tax_rate","market_value_equity","market_value_debt"}}
    wacc=calculate_wacc(wacc_values)["wacc"]; growth=config["wacc_inputs"]["terminal_growth"]["value"]; result=dcf_enterprise_value(fcff,wacc,growth)
    return {"wacc":wacc,**result}
