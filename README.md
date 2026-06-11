# Syrma SGS GR/IR Reconciliation & Procurement Analytics Dashboard

An interactive, full-stack analytical platform designed for automated reconciliation of **Goods Receipt / Invoice Receipt (GR/IR)** account balances, procurement risk profiling, and audit reporting. 

Built using a **Python Flask** backend and a modern **React (Vite + TailwindCSS)** frontend, the dashboard processes standard SAP exports (`GRIR`, `EKKO`, and `ME2N`) to surface discrepancies, aging exposure, and recommended action plans.

---

## 🚀 Key Features

* **Multi-dataset Upload & Auto-Detection:** Seamless drag-and-drop file upload interface that automatically detects, maps, and validates SAP datasets (`grir.csv`, `EKKO.csv`, and `me2n.csv`).
* **Deterministic Reconciliation Engine:** Connects purchasing documents (POs), line items, material data, and transactional postings to classify statuses (`FULLY RECONCILED`, `GR ONLY`, `IR ONLY`, `PARTIALLY INVOICED`, `OVER INVOICED`, `FULLY REVERSED`, `PRICE VARIANCE`).
* **Interactive Dashboard:** Premium dark-themed UI featuring key performance metrics, interactive stacked bar charts (Aging composition), status distribution, and details.
* **Risk Scoring & Audit Findings:** Automatically flags high-exposure transactions, overdue aging buckets (>90 days), control violations (invoices without goods receipts), and potential duplicate or over-invoicing risks.
* **Automated Action Plan:** Generates contextual recommended actions assigned to respective business owners (e.g., Accounts Payable, Sourcing, Finance Controllers) with clear business impacts and timelines.
* **PDF Report Generation:** One-click download of a multi-page, formatted PDF Audit Report utilizing ReportLab, perfect for executive review and audit trails.
* **Power BI Integration:** Includes a pre-configured Power BI report (`Syrma_SGS_Power_BI_Report.pbix`) for alternative reporting configurations.

---

## 🛠️ Technology Stack

### Backend
* **Python 3.10+ / Flask:** Lightweight REST API.
* **Pandas & NumPy:** Fast, vectorized data cleaning, joining, and aggregation.
* **ReportLab:** Direct programmatic PDF generation for audit reports.

### Frontend
* **React 18 / Vite:** Ultra-fast bundler and component-based frontend shell.
* **TailwindCSS:** Modern, utility-first CSS styling.
* **Recharts:** Responsive SVG-based interactive charts.
* **TanStack React Query & Axios:** Reliable state management and API integration.
* **Framer Motion:** Smooth micro-animations and page transitions.

---

## 📂 Project Directory Structure

```text
SyrmaSGS_DashBoard/
├── backend/                   # Flask server entry point & uploaded file processing
│   ├── app.py                 # Main Flask application with API endpoints
│   └── core/                  # Core services imports
├── services/                  # Business logic and analytical computation
│   ├── grir_analytics_service.py # Main service containing reconciliation & KPI computation
│   └── grir_kpi_builder.py    # Backup KPI calculations and helper methods
├── frontend/                  # React dashboard frontend
│   ├── src/                   # React source code (components, feature panels)
│   │   ├── features/grir/     # Main dashboard feature files (GrirDashboard.jsx)
│   │   └── index.css          # Design system stylesheet
│   ├── package.json           # Frontend dependencies & npm scripts
│   └── vite.config.js         # Vite configuration
├── data/                      # Local storage and test data files
├── test_*.py                  # Python integration & unit test suites
├── requirements.txt           # Python backend dependencies
└── Syrma_SGS_Power_BI_Report.pbix # Offline Power BI report file
```

---

## ⚡ Getting Started

### Prerequisites
* **Python 3.10+**
* **Node.js** (v18+ recommended) and **npm**

---

### Backend Setup

1. **Navigate to the root directory & create a Python Virtual Environment:**
   ```bash
   python -m venv venv
   ```

2. **Activate the Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   * **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Flask Development Server:**
   ```bash
   python backend/app.py
   ```
   The backend API will run on `http://127.0.0.1:5000`.

---

### Frontend Setup

1. **Navigate to the frontend folder:**
   ```bash
   cd frontend
   ```

2. **Install node packages:**
   ```bash
   npm install
   ```

3. **Start the Frontend development server:**
   ```bash
   npm run dev
   ```
   Open your browser and navigate to `http://localhost:5173` to view the dashboard.

---

## 📊 Expected Data Formats

The dashboard requires three standard SAP exports:

1. **GRIR Data:** Transactional history containing posting types, posting dates, PO numbers, item indices, debit/credit indicators, and document details.
2. **EKKO Data:** Purchase Order header details, including purchase document IDs, vendor info, exchange rates, and PO currencies.
3. **ME2N Data:** Purchase Order line-item tracking detailing order quantities, prices, open values, delivery dates, and open delivery/invoice quantities.

*Note: The platform features an auto-detection system that dynamically aligns column headers containing varying abbreviations or aliases exported from SAP.*

---

## 🧪 Running Tests

A suite of unit and integration test scripts is included to validate the data mappings, status classifications, and API routes.

To run the reconciliation tests:
```bash
python test_reconciliation.py
python test_upload_workflow.py
```
