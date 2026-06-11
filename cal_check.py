from pathlib import Path

import pandas as pd


def load_grir_data(file_path: Path) -> pd.DataFrame:
	df = pd.read_csv(file_path)
	df.columns = df.columns.str.strip()

	amount_column = "Amt (LC)" if "Amt (LC)" in df.columns else "Amt (FC)"
	df[amount_column] = pd.to_numeric(df[amount_column], errors="coerce").fillna(0.0)
	df["Dr/Cr Ind"] = df.get("Dr/Cr Ind", "S").fillna("S").astype(str).str.strip().str.upper()
	df["Trans Type"] = df["Trans Type"].astype(str).str.strip()
	df["Signed Amount"] = df[amount_column].where(df["Dr/Cr Ind"] == "S", -df[amount_column])
	return df


def calculate_net_gr_ir(df: pd.DataFrame) -> float:
	gr_total = df.loc[df["Trans Type"] == "1", "Signed Amount"].sum()
	ir_total = df.loc[df["Trans Type"] == "2", "Signed Amount"].sum()
	return gr_total - ir_total


def calculate_unique_po_count(df: pd.DataFrame) -> int:
	return df["PO Number"].astype(str).str.strip().nunique()


if __name__ == "__main__":
	grir_file = Path(__file__).with_name("grir.csv")
	grir_df = load_grir_data(grir_file)

	net_gr_ir = calculate_net_gr_ir(grir_df)
	unique_po_count = calculate_unique_po_count(grir_df)

	print(f"Loaded {len(grir_df)} GR/IR rows from {grir_file.name}")
	print(f"Unique PO count: {unique_po_count}")
	print(f"Net GR - IR: {net_gr_ir:.2f}")
