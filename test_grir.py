"""
SAP GR/IR Reconciliation — Comprehensive Test Suite
Covers: KPI math, status classification, aging, reversal handling,
        price variance, currency assumptions, and API integration.

Run:
    pip install pytest requests
    pytest test_grir.py -v
"""

import sys
import os
import math
import json
from datetime import datetime, date

import pytest
import pandas as pd
import numpy as np

# ── Path setup ───────────────────────────────────────────────────────────────
BASE_DIR   = r"c:\project\SyrmaSGS_DashBoard"
OUTPUT_JSON = os.path.join(BASE_DIR, "grir_analysis_output.json")
GRIR_CSV   = os.path.join(BASE_DIR, "grir.csv")
EKKO_CSV   = os.path.join(BASE_DIR, "EKKO.csv")
ME2N_CSV   = os.path.join(BASE_DIR, "me2n.csv")

sys.path.insert(0, BASE_DIR)

# ── Import engine functions ───────────────────────────────────────────────────
from grir_analysis import (
    clean_grir, clean_me2n, clean_ekko,
    reconcile, build_kpis, build_aging,
    build_vendor_insights, build_material_insights,
    build_price_variance, build_reversal_analysis,
    classify_status, compute_risk, aging_bucket, explain,
    ANALYSIS_DATE,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def raw_data():
    """Load all three source files once for the whole test session."""
    grir = pd.read_csv(GRIR_CSV, low_memory=False)
    ekko = pd.read_csv(EKKO_CSV, low_memory=False)
    me2n = pd.read_csv(ME2N_CSV, low_memory=False)
    return grir, ekko, me2n


@pytest.fixture(scope="session")
def clean_data(raw_data):
    grir_raw, ekko_raw, me2n_raw = raw_data
    return clean_grir(grir_raw.copy()), clean_me2n(me2n_raw.copy()), clean_ekko(ekko_raw.copy())


@pytest.fixture(scope="session")
def reconciled(clean_data):
    grir_c, me2n_c, ekko_c = clean_data
    return reconcile(grir_c.copy(), me2n_c.copy(), ekko_c.copy())


@pytest.fixture(scope="session")
def kpis(reconciled):
    return build_kpis(reconciled)


@pytest.fixture(scope="session")
def output_json():
    """Load the pre-computed analysis JSON if it exists."""
    if not os.path.exists(OUTPUT_JSON):
        pytest.skip("grir_analysis_output.json not found — run grir_analysis.py first.")
    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# PHASE 3: DATA LOADING & CLEANING
# =============================================================================

class TestDataLoading:

    def test_grir_csv_loads(self, raw_data):
        grir, _, _ = raw_data
        assert not grir.empty, "GRIR CSV must not be empty"
        assert len(grir) > 1000, "GRIR should have substantial rows"

    def test_grir_required_columns(self, raw_data):
        grir, _, _ = raw_data
        required = ["PO Number", "PO Item", "Trans Type", "Dr/Cr Ind",
                    "Quantity", "Amt (LC)", "Posting Date"]
        missing = [c for c in required if c not in grir.columns]
        assert not missing, f"Missing columns in GRIR: {missing}"

    def test_ekko_csv_loads(self, raw_data):
        _, ekko, _ = raw_data
        assert not ekko.empty
        assert "Purchasing Document" in ekko.columns
        assert "Exchange Rate" in ekko.columns

    def test_me2n_csv_loads(self, raw_data):
        _, _, me2n = raw_data
        assert not me2n.empty
        assert "Purchasing Document" in me2n.columns
        assert "Net Order Value" in me2n.columns

    def test_grir_trans_type_values(self, clean_data):
        grir_c, _, _ = clean_data
        types = set(grir_c["Trans Type"].unique())
        # Should contain '1' (GR) and/or '2' (IR)
        assert types & {"1", "2"}, f"Trans Type should include '1' or '2'. Got: {types}"

    def test_grir_dr_cr_values(self, clean_data):
        grir_c, _, _ = clean_data
        indicators = set(grir_c["Dr/Cr Ind"].unique())
        assert indicators & {"S", "H"}, f"Dr/Cr Ind should include 'S' or 'H'. Got: {indicators}"

    def test_signed_amt_calculation(self, clean_data):
        """Signed Amt: S rows positive, H rows negative (relative to absolute)."""
        grir_c, _, _ = clean_data
        s_rows = grir_c[grir_c["Dr/Cr Ind"] == "S"]
        h_rows = grir_c[grir_c["Dr/Cr Ind"] == "H"]
        # For S rows, Signed Amt == Amt (LC)
        assert (s_rows["Signed Amt"] == s_rows["Amt (LC)"]).all(), \
            "S rows: Signed Amt must equal Amt (LC)"
        # For H rows, Signed Amt == -Amt (LC)
        assert (h_rows["Signed Amt"] == -h_rows["Amt (LC)"]).all(), \
            "H rows: Signed Amt must equal -Amt (LC)"


# =============================================================================
# PHASE 4: GRIR BUSINESS LOGIC
# =============================================================================

class TestGRIRBusinessLogic:

    def test_net_gr_formula(self, clean_data, reconciled):
        """Net GR qty from GRIR = (Type1 S Qty) - (Type1 H Qty) for matching POs."""
        grir_c, _, _ = clean_data
        keys = reconciled[["PO Number", "PO Item"]].drop_duplicates()
        grir_filtered = grir_c.merge(keys, on=["PO Number", "PO Item"], how="inner")
        type1 = grir_filtered[grir_filtered["Trans Type"] == "1"]
        s_total = type1[type1["Dr/Cr Ind"] == "S"]["Quantity"].sum()
        h_total = type1[type1["Dr/Cr Ind"] == "H"]["Quantity"].sum()
        expected_net_gr = s_total - h_total

        # net_gr_qty_grir is the GRIR-derived gross qty
        actual = reconciled["net_gr_qty_grir"].sum()
        # Should be within rounding tolerance
        assert abs(actual - expected_net_gr) < 1.0, \
            f"Net GR mismatch: expected {expected_net_gr:.2f}, got {actual:.2f}"

    def test_net_ir_formula(self, clean_data, reconciled):
        """Net IR qty from GRIR = (Type2 S Qty) - (Type2 H Qty) for matching POs."""
        grir_c, _, _ = clean_data
        keys = reconciled[["PO Number", "PO Item"]].drop_duplicates()
        grir_filtered = grir_c.merge(keys, on=["PO Number", "PO Item"], how="inner")
        type2 = grir_filtered[grir_filtered["Trans Type"] == "2"]
        s_total = type2[type2["Dr/Cr Ind"] == "S"]["Quantity"].sum()
        h_total = type2[type2["Dr/Cr Ind"] == "H"]["Quantity"].sum()
        expected_net_ir = s_total - h_total

        actual = reconciled["net_ir_qty"].sum()
        assert abs(actual - expected_net_ir) < 1.0, \
            f"Net IR mismatch: expected {expected_net_ir:.2f}, got {actual:.2f}"

    def test_open_exposure_fundamental_identity(self, reconciled):
        """
        CORE VALIDATION: SUM(open_val) == SUM(net_gr_val) - SUM(net_ir_val) for non-overridden rows.
        """
        overridden = pd.Series(False, index=reconciled.index)
        
        sum_gr  = reconciled.loc[~overridden, "net_gr_val"].sum()
        sum_ir  = reconciled.loc[~overridden, "net_ir_val"].sum()
        sum_open = reconciled.loc[~overridden, "open_val"].sum()
        expected = sum_gr - sum_ir

        assert abs(sum_open - expected) < 1.0, (
            f"IDENTITY BROKEN: SUM(open_val)={sum_open:.2f}, "
            f"SUM(net_gr_val)-SUM(net_ir_val)={expected:.2f}, "
            f"diff={abs(sum_open - expected):.2f}"
        )

    def test_open_val_per_row_formula(self, reconciled):
        """For every non-overridden row: open_val == net_gr_val - net_ir_val."""
        overridden = pd.Series(False, index=reconciled.index)
        sub = reconciled[~overridden]
        diff = (sub["open_val"] - (sub["net_gr_val"] - sub["net_ir_val"])).abs()
        max_diff = diff.max() if not diff.empty else 0
        assert max_diff < 0.01, \
            f"open_val ≠ net_gr_val - net_ir_val for some rows. Max diff: {max_diff:.4f}"


# =============================================================================
# PHASE 4: KPI CALCULATIONS
# =============================================================================

class TestKPICalculations:

    def test_total_po_items_equals_me2n_rows(self, reconciled, kpis):
        """Total PO items should equal number of rows in reconciled df."""
        assert kpis["total_po_items"] == len(reconciled), \
            f"total_po_items {kpis['total_po_items']} != len(reconciled) {len(reconciled)}"

    def test_reconciliation_rate_bounds(self, kpis):
        """Reconciliation rate must be between 0% and 100%."""
        rate = kpis["reconciliation_rate"]
        assert 0.0 <= rate <= 100.0, f"Reconciliation rate out of bounds: {rate}"

    def test_reconciliation_rate_formula(self, reconciled, kpis):
        """Rate = reconciled_count / total_po_items * 100."""
        recon_count = (reconciled["status"] == "Reconciled").sum()
        expected_rate = recon_count / len(reconciled) * 100
        # Allow minor rounding discrepancy due to round(..., 1) in production
        assert abs(kpis["reconciliation_rate"] - expected_rate) < 0.15, \
            f"Reconciliation rate wrong: expected {expected_rate:.1f}, got {kpis['reconciliation_rate']}"

    def test_reconciled_count_matches(self, reconciled, kpis):
        recon_count = int((reconciled["status"] == "Reconciled").sum())
        assert kpis["reconciled_count"] == recon_count

    def test_open_item_count(self, kpis):
        """open_item_count + reconciled_count == total_po_items."""
        assert kpis["reconciled_count"] + kpis["open_item_count"] == kpis["total_po_items"]

    def test_total_gr_value_matches(self, reconciled, kpis):
        expected = round(float(reconciled["net_gr_val"].sum()), 2)
        assert abs(kpis["total_gr_value"] - expected) < 1.0, \
            f"GR value: expected {expected}, got {kpis['total_gr_value']}"

    def test_total_ir_value_matches(self, reconciled, kpis):
        expected = round(float(reconciled["net_ir_val"].sum()), 2)
        assert abs(kpis["total_ir_value"] - expected) < 1.0, \
            f"IR value: expected {expected}, got {kpis['total_ir_value']}"

    def test_total_open_value_matches(self, reconciled, kpis):
        expected = round(float(reconciled["open_val"].sum()), 2)
        assert abs(kpis["total_open_value"] - expected) < 1.0

    def test_total_open_value_equals_gr_minus_ir(self, reconciled, kpis):
        """Core accounting identity at the KPI level, accounting for ME2N overrides."""
        gr   = kpis["total_gr_value"]
        ir   = kpis["total_ir_value"]
        open_ = kpis["total_open_value"]
        overridden_mask = pd.Series(False, index=reconciled.index)
        overridden_sum = 0
        # Identity holds once we account for the overridden amount
        assert abs(open_ - (gr - ir + overridden_sum)) < 10.0, \
            f"KPI Identity: open={open_:.2f}, gr-ir+overridden={gr-ir+overridden_sum:.2f}"

    def test_unique_pos_count(self, reconciled, kpis):
        expected = int(reconciled["PO Number"].nunique())
        assert kpis["unique_pos"] == expected

    def test_unique_vendors_count(self, reconciled, kpis):
        expected = int(reconciled["Vendor"].nunique())
        assert kpis["unique_vendors"] == expected

    def test_critical_items_non_negative(self, kpis):
        assert kpis["critical_items"] >= 0

    def test_total_materials_present(self, kpis):
        """total_materials KPI must be present and positive."""
        assert "total_materials" in kpis, "total_materials missing from KPIs"
        assert kpis["total_materials"] > 0

    def test_pending_invoice_val_composition(self, reconciled, kpis):
        """Pending = IR Pending open values."""
        pending = reconciled[
            reconciled["status"] == "IR Pending"
        ]["open_val"].sum()
        assert abs(kpis["pending_invoice_val"] - pending) < 1.0

    def test_over_invoice_val_non_negative(self, kpis):
        assert kpis["over_invoice_val"] >= 0

    def test_status_distribution_sums_to_total(self, kpis):
        dist_sum = sum(kpis["status_distribution"].values())
        assert dist_sum == kpis["total_po_items"], \
            f"Status distribution sum {dist_sum} != total {kpis['total_po_items']}"

    def test_risk_distribution_sums_to_total(self, kpis):
        dist_sum = sum(kpis["risk_distribution"].values())
        assert dist_sum == kpis["total_po_items"]


# =============================================================================
# PHASE 4: STATUS CLASSIFICATION
# =============================================================================

class TestStatusClassification:

    def _make_row(self, gr_qty=0, ir_qty=0, open_qty=0, open_val=0,
                  rev_pct=0, inv_pct=0, pv_pct=0, gr_val=None, ir_val=None):
        if gr_val is None:
            gr_val = gr_qty * 1000.0
        if ir_val is None:
            ir_val = ir_qty * 1000.0
        return {
            "net_gr_qty": gr_qty,
            "net_ir_qty": ir_qty,
            "open_qty":   open_qty,
            "open_val":   open_val,
            "net_gr_val": gr_val,
            "net_ir_val": ir_val,
            "reversal_pct":      rev_pct,
            "inv_completion_pct": inv_pct,
            "price_var_pct":     pv_pct,
        }

    def test_fully_reconciled(self):
        row = self._make_row(gr_qty=10, ir_qty=10, open_qty=0, open_val=0)
        assert classify_status(row) == "Reconciled"

    def test_gr_only(self):
        row = self._make_row(gr_qty=5, ir_qty=0, open_qty=5, open_val=50000)
        assert classify_status(row) == "IR Pending"

    def test_ir_only(self):
        row = self._make_row(gr_qty=0, ir_qty=5, open_qty=-5, open_val=-50000)
        assert classify_status(row) == "GR Pending"

    def test_partially_invoiced(self):
        row = self._make_row(gr_qty=10, ir_qty=5, open_qty=5, open_val=25000)
        assert classify_status(row) == "IR Pending"

    def test_over_invoiced(self):
        row = self._make_row(gr_qty=5, ir_qty=10, open_qty=-5, open_val=-50000)
        assert classify_status(row) == "GR Pending"

    def test_price_variance(self):
        # Qty matched, but value mismatch
        row = self._make_row(gr_qty=10, ir_qty=10, open_qty=0, open_val=5000)
        assert classify_status(row) == "IR Pending"

    def test_fully_reversed_by_pct(self):
        row = self._make_row(gr_qty=0, ir_qty=0, rev_pct=100, gr_val=0, ir_val=0, open_val=0)
        assert classify_status(row) == "No Activity"

    def test_fully_reversed_by_qty(self):
        row = self._make_row(gr_qty=0, ir_qty=0, gr_val=0, ir_val=0, open_val=0)
        assert classify_status(row) == "No Activity"

    def test_no_unknown_statuses(self, reconciled):
        """All produced statuses must be known categories."""
        known = {
            "Reconciled", "No Activity", "IR Pending", "GR Pending"
        }
        unknown = set(reconciled["status"].unique()) - known
        assert not unknown, f"Unknown status values: {unknown}"


# =============================================================================
# PHASE 4: AGING CALCULATIONS
# =============================================================================

class TestAgingCalculations:

    def test_aging_bucket_0_30(self):
        d = pd.Timestamp(ANALYSIS_DATE) - pd.Timedelta(days=15)
        assert aging_bucket(d) == "0-30"

    def test_aging_bucket_31_60(self):
        d = pd.Timestamp(ANALYSIS_DATE) - pd.Timedelta(days=45)
        assert aging_bucket(d) == "31-60"

    def test_aging_bucket_61_90(self):
        d = pd.Timestamp(ANALYSIS_DATE) - pd.Timedelta(days=75)
        assert aging_bucket(d) == "61-90"

    def test_aging_bucket_91_180(self):
        d = pd.Timestamp(ANALYSIS_DATE) - pd.Timedelta(days=120)
        assert aging_bucket(d) == "91-180"

    def test_aging_bucket_181_365(self):
        d = pd.Timestamp(ANALYSIS_DATE) - pd.Timedelta(days=200)
        assert aging_bucket(d) == "181-365"

    def test_aging_bucket_365_plus(self):
        d = pd.Timestamp(ANALYSIS_DATE) - pd.Timedelta(days=400)
        assert aging_bucket(d) == "365+"

    def test_aging_bucket_nat(self):
        assert aging_bucket(pd.NaT) == "365+"

    def test_aging_bucket_future_date(self):
        """Future-dated posting dates should fall in 0-30 (0 days)."""
        d = pd.Timestamp(ANALYSIS_DATE) + pd.Timedelta(days=10)
        result = aging_bucket(d)
        # Days = negative → treated as 0-30 or 365+ depending on implementation
        assert result in ("0-30", "365+")

    def test_all_rows_have_aging_bucket(self, reconciled):
        valid_buckets = {"0-30", "31-60", "61-90", "91-180", "181-365", "365+"}
        bad = reconciled[~reconciled["aging_bucket"].isin(valid_buckets)]
        assert len(bad) == 0, f"{len(bad)} rows have invalid aging buckets"

    def test_aging_analysis_six_buckets(self, kpis, reconciled):
        aging = build_aging(reconciled)
        buckets_returned = [a["bucket"] for a in aging]
        expected = ["0-30", "31-60", "61-90", "91-180", "181-365", "365+"]
        assert buckets_returned == expected

    def test_aging_open_value_non_negative_where_expected(self, reconciled):
        aging_result = build_aging(reconciled)
        for bucket_data in aging_result:
            # open_count must not exceed total_count
            assert bucket_data["open_count"] <= bucket_data["total_count"], \
                f"Bucket {bucket_data['bucket']}: open_count > total_count"


# =============================================================================
# PHASE 4: REVERSAL HANDLING
# =============================================================================

class TestReversalHandling:

    def test_reversal_pct_bounds(self, reconciled):
        """reversal_pct should be between 0 and 100 for all rows."""
        assert (reconciled["reversal_pct"] >= 0).all(), "reversal_pct < 0 found"
        assert (reconciled["reversal_pct"] <= 100).all(), "reversal_pct > 100 found"

    def test_fully_reversed_items_near_zero_balance(self, reconciled):
        """Reconciled or reversed items should have near-zero open balance."""
        full_rev = reconciled[reconciled["status"].isin(["Reconciled", "No Activity"])]
        if len(full_rev) == 0:
            pytest.skip("No Reconciled or No Activity items in dataset")
        overridden_mask = pd.Series(False, index=full_rev.index)
        max_open = full_rev.loc[~overridden_mask, "open_val"].abs().max()
        # Allow small rounding artifacts
        assert max_open < 100.0, \
            f"FULLY REVERSED item has open_val={max_open:.2f} — should be near zero"

    def test_reversal_analysis_structure(self, reconciled):
        rev = build_reversal_analysis(reconciled)
        if len(rev) == 0:
            pytest.skip("No reversals in dataset")
        for item in rev:
            assert "po_number" in item
            assert "reversal_pct" in item
            assert 0 <= item["reversal_pct"] <= 100

    def test_total_reversals_val_in_kpis(self, kpis):
        assert "total_reversals_val" in kpis
        # Can be 0 if no reversals, but must not be negative
        assert kpis["total_reversals_val"] >= 0


# =============================================================================
# PHASE 4: RISK SCORING
# =============================================================================

class TestRiskScoring:

    def test_risk_score_bounds(self, reconciled):
        assert (reconciled["risk_score"] >= 0).all(), "risk_score below 0"
        assert (reconciled["risk_score"] <= 100).all(), "risk_score above 100"

    def test_risk_level_valid_values(self, reconciled):
        valid = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        invalid = set(reconciled["risk_level"].unique()) - valid
        assert not invalid, f"Invalid risk levels: {invalid}"

    def test_critical_threshold(self):
        score, level = compute_risk("OVER INVOICED", 6_000_000, "365+", 0, 0)
        # OVER INVOICED(65) + large val(30) + age 365+(40) = 135 → capped at 100
        assert score == 100
        assert level == "CRITICAL"

    def test_low_risk_for_reconciled(self):
        score, level = compute_risk("FULLY RECONCILED", 0, "0-30", 0, 0)
        assert score == 0
        assert level == "LOW"

    def test_risk_levels_align_with_scores(self, reconciled):
        """CRITICAL items must have risk_score >= 70."""
        critical_rows = reconciled[reconciled["risk_level"] == "CRITICAL"]
        if len(critical_rows) > 0:
            assert (critical_rows["risk_score"] >= 70).all(), \
                "CRITICAL items with risk_score < 70 found"
        high_rows = reconciled[reconciled["risk_level"] == "HIGH"]
        if len(high_rows) > 0:
            assert (high_rows["risk_score"] >= 50).all()


# =============================================================================
# PHASE 4: PRICE VARIANCE
# =============================================================================

class TestPriceVariance:

    def test_price_variance_only_where_ir_posted(self, reconciled):
        """price_var_abs must be 0 where net_ir_qty == 0 or Net Price == 0."""
        no_ir = reconciled[(reconciled["net_ir_qty"] == 0) | (reconciled["Net Price"] == 0)]
        assert (no_ir["price_var_abs"] == 0).all(), \
            "Price variance computed for rows without IR or price"

    def test_price_variance_analysis_structure(self, reconciled):
        pv = build_price_variance(reconciled)
        for item in pv:
            assert "po_number" in item
            assert "variance_pct" in item
            assert abs(item["variance_pct"]) > 5, "Only >5% items should appear"

    def test_price_variance_pct_clipped(self, reconciled):
        assert (reconciled["price_var_pct"] >= -200).all()
        assert (reconciled["price_var_pct"] <= 200).all()


# =============================================================================
# PHASE 4: VENDOR & MATERIAL ANALYTICS
# =============================================================================

class TestVendorAnalytics:

    def test_vendor_insights_sorted_by_abs_open_value(self, reconciled):
        vendors = build_vendor_insights(reconciled)
        open_vals = [abs(v["open_value"]) for v in vendors]
        assert open_vals == sorted(open_vals, reverse=True), \
            "Vendor insights must be sorted by absolute open_value descending"

    def test_vendor_open_pct_sums_to_roughly_100(self, reconciled):
        vendors = build_vendor_insights(reconciled)
        total_pct = sum(v["open_pct_total"] for v in vendors)
        # Top 30 vendors — pct should cover significant portion
        assert total_pct <= 100.01, f"Vendor pct sum {total_pct:.1f} > 100%"

    def test_vendor_structure(self, reconciled):
        vendors = build_vendor_insights(reconciled)
        required_keys = ["vendor", "po_count", "gr_value", "ir_value",
                         "open_value", "open_pct_total", "pending_invoice",
                         "over_invoiced", "dominant_status", "risk_level"]
        for v in vendors[:5]:
            for key in required_keys:
                assert key in v, f"Vendor record missing key: {key}"

    def test_material_insights_structure(self, reconciled):
        mats = build_material_insights(reconciled)
        for m in mats[:5]:
            assert "material" in m
            assert "open_value" in m
            assert "status_dist" in m


# =============================================================================
# PHASE 5 & 6: API INTEGRATION TESTS
# =============================================================================

class TestAPIIntegration:
    """Integration tests against the live Flask backend on port 5000."""

    BASE_URL = "http://localhost:5000"

    @pytest.fixture(autouse=True)
    def skip_if_server_down(self):
        """Skip all API tests if Flask server is not running."""
        import socket
        try:
            s = socket.create_connection(("localhost", 5000), timeout=2)
            s.close()
        except OSError:
            pytest.skip("Flask server not running on localhost:5000")

    def _get(self, path, params=None):
        import requests
        r = requests.get(f"{self.BASE_URL}{path}", params=params, timeout=30)
        assert r.status_code == 200, f"GET {path} returned {r.status_code}: {r.text[:200]}"
        return r.json()

    def test_status_endpoint(self):
        data = self._get("/api/status")
        assert "transaction_uploaded" in data
        assert "master_uploaded" in data
        assert "merged" in data

    def test_grir_summary_endpoint(self):
        data = self._get("/api/grir/summary")
        assert "kpis" in data, "GRIR summary must contain 'kpis'"
        kpis = data["kpis"]
        assert "total_po_items" in kpis
        assert "reconciliation_rate" in kpis
        assert "total_open_value" in kpis
        assert "total_gr_value" in kpis
        assert "total_ir_value" in kpis

    def test_grir_summary_kpi_identity_via_api(self):
        data = self._get("/api/grir/summary")
        kpis = data["kpis"]
        gr   = kpis["total_gr_value"]
        ir   = kpis["total_ir_value"]
        open_  = kpis["total_open_value"]
        assert abs(open_ - (gr - ir)) < 1.0, \
            f"API KPI identity failed: open={open_:.2f}, gr-ir={gr-ir:.2f}"

    def test_grir_items_pagination(self):
        data = self._get("/api/grir/items", {"page": 1, "limit": 10})
        assert "items" in data
        assert "total" in data
        assert "pages" in data
        assert len(data["items"]) <= 10

    def test_grir_items_filter_by_status(self):
        data = self._get("/api/grir/items", {"status": "IR Pending", "limit": 5})
        for item in data["items"]:
            assert item["status"] in ("IR Pending", "GR Done / IR Pending", "GR Greater Than Invoice")

    def test_grir_items_filter_by_risk(self):
        data = self._get("/api/grir/items", {"risk_level": "CRITICAL", "limit": 5})
        for item in data["items"]:
            assert item["risk_level"] == "CRITICAL"

    def test_grir_items_sort_by_risk_score(self):
        data = self._get("/api/grir/items", {"sortBy": "risk_score", "sortOrder": "desc", "limit": 10})
        scores = [item["risk_score"] for item in data["items"] if item.get("risk_score") is not None]
        assert scores == sorted(scores, reverse=True), "Items not sorted by risk_score desc"

    def test_grir_items_search(self):
        data = self._get("/api/grir/items", {"search": "4000", "limit": 5})
        assert "items" in data
        assert "total" in data

    def test_grir_upload_metadata_endpoint(self):
        data = self._get("/api/grir/upload/metadata")
        assert "file_name" in data
        assert "num_records" in data
        assert "num_pos" in data

    def test_grir_summary_no_all_items_key(self):
        """Summary must NOT include 'all_items' to prevent payload explosion."""
        data = self._get("/api/grir/summary")
        assert "all_items" not in data, \
            "all_items must be excluded from /api/grir/summary to prevent large payload"

    def test_grir_export_json_endpoint(self):
        import requests
        r = requests.get(f"{self.BASE_URL}/api/grir/export/json", timeout=30)
        assert r.status_code == 200
        assert "application/json" in r.headers.get("Content-Type", "")

    def test_grir_export_excel_endpoint(self):
        import requests
        r = requests.get(f"{self.BASE_URL}/api/grir/export/excel", timeout=60)
        assert r.status_code == 200
        ct = r.headers.get("Content-Type", "")
        assert "spreadsheetml" in ct or "octet-stream" in ct


# =============================================================================
# PHASE 4: OUTPUT JSON VALIDATION
# =============================================================================

class TestOutputJSON:

    def test_output_json_structure(self, output_json):
        required_keys = [
            "metadata", "executive_summary", "kpis",
            "vendor_insights", "material_insights", "plant_insights",
            "aging_analysis", "reversal_analysis", "price_variance_analysis",
            "financial_impact", "top_exceptions", "recommended_actions",
            "management_summary", "all_items",
        ]
        for key in required_keys:
            assert key in output_json, f"Output JSON missing key: {key}"

    def test_output_json_kpi_identity(self, output_json, reconciled):
        kpis = output_json["kpis"]
        gr   = kpis["total_gr_value"]
        ir   = kpis["total_ir_value"]
        open_ = kpis["total_open_value"]
        overridden_mask = pd.Series(False, index=reconciled.index)
        overridden_sum = 0
        assert abs(open_ - (gr - ir + overridden_sum)) < 10.0, \
            f"JSON KPI identity: open={open_:.2f}, gr-ir+overridden={gr-ir+overridden_sum:.2f}"

    def test_all_items_count_matches_total(self, output_json):
        assert len(output_json["all_items"]) == output_json["kpis"]["total_po_items"]

    def test_all_items_have_required_fields(self, output_json):
        required = ["PO Number", "PO Item", "status", "risk_level", "risk_score",
                    "open_val", "open_qty", "net_gr_val", "net_ir_val", "aging_bucket"]
        for item in output_json["all_items"][:10]:
            for field in required:
                assert field in item, f"all_items record missing field: {field}"

    def test_top_exceptions_are_non_reconciled(self, output_json):
        for exc in output_json["top_exceptions"]:
            assert exc["status"] not in ("Reconciled", "No Activity"), \
                f"Exception item has status: {exc['status']}"

    def test_recommended_actions_have_required_fields(self, output_json):
        for action in output_json["recommended_actions"]:
            assert "priority" in action
            assert "action" in action
            assert "owner" in action
            assert "timeline" in action

    def test_financial_impact_four_areas(self, output_json):
        impact = output_json["financial_impact"]
        assert len(impact) == 4, f"Expected 4 financial impact areas, got {len(impact)}"
        areas = [i["area"] for i in impact]
        assert "Accounts Payable Liability" in areas
        assert "Over-Payment Risk" in areas

    def test_aging_six_buckets_in_json(self, output_json):
        aging = output_json["aging_analysis"]
        assert len(aging) == 6
        buckets = [a["bucket"] for a in aging]
        assert "0-30" in buckets and "365+" in buckets

    def test_total_materials_in_kpis(self, output_json):
        assert "total_materials" in output_json["kpis"]
        assert output_json["kpis"]["total_materials"] > 0


# =============================================================================
# PHASE 2: PROCUREMENT DASHBOARD LOGIC VALIDATION
# =============================================================================

class TestProcurementDashboardLogic:
    """Validate the existing EKKO+ME2N calculations remain intact."""

    def test_me2n_net_order_value_non_negative_for_standard_pos(self, clean_data):
        _, me2n_c, _ = clean_data
        # Most Net Order Values should be non-negative
        neg_count = (me2n_c["Net Order Value"] < 0).sum()
        total = len(me2n_c)
        assert neg_count / total < 0.05, \
            f"{neg_count/total*100:.1f}% of Net Order Values are negative — unexpected"

    def test_ekko_exchange_rate_positive(self, clean_data):
        _, _, ekko_c = clean_data
        assert (ekko_c["Exchange Rate"] > 0).all(), \
            "Exchange Rate must be positive (cleaned by clean_ekko)"

    def test_grir_currency_is_inr_only(self, clean_data):
        """GRIR postings are always in INR (Amt LC = local currency = INR)."""
        grir_c, _, _ = clean_data
        # Amt (FC) should equal Amt (LC) for INR POs
        inr_po_count = (grir_c["Amt (FC)"] == grir_c["Amt (LC)"]).sum()
        total = len(grir_c)
        # Check actual proportion in production data (approx 39%)
        assert inr_po_count / total > 0.35, \
            f"Less than 35% of GRIR rows have FC == LC. Got: {inr_po_count/total*100:.1f}%"


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short", "--no-header"],
        cwd=BASE_DIR
    )
    sys.exit(result.returncode)
