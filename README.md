# Syrma SGS — GR/IR Reconciliation & Procurement Analytics Platform
An enterprise-grade, full-stack analytical platform designed for automated reconciliation of **Goods Receipt / Invoice Receipt (GR/IR)** account balances and audit reporting.
Built using a **Python Flask** backend and a modern **React (Vite + TailwindCSS)** frontend, the dashboard processes SAP exports to instantly surface discrepancies, aging exposure, financial impact, and recommended action plans.

---

## 🚀 Key Features

* **Single-File Drag & Drop Upload:** Seamlessly upload your consolidated GR/IR `.csv` or `.xlsx` export. The platform automatically detects, maps, and validates the dataset.
* **Deterministic Reconciliation Engine:** Connects purchasing documents (POs), line items, material data, and transactional postings to classify statuses (e.g., `FULLY RECONCILED`, `GR ONLY`, `IR ONLY`, `PARTIALLY INVOICED`, `OVER INVOICED`, `FULLY REVERSED`).
* **Time-Series Trend Analysis:** Tracks month-over-month reconciliation accuracy (Match Rate) and cumulative ledger value trends (Total GR vs Total IR volume) to measure procurement efficiency over time.
* **Actionable Exceptions Tracking:** Automatically isolates critical risk items, specifically flagging transactions that are **> 90 days old** or **Over-Invoiced**.
* **Reversal Type Analysis:** Accurately isolates and computes exact financial metrics for Type 7 (Reversals) and Type P (Price Variance) postings, removing them from standard open exposure calculations to prevent inflated risk reporting.
* **Executive Summary & Action Plans:** Generates contextual recommended actions assigned to respective business owners (e.g., Accounts Payable, Sourcing, Finance Controllers) with clear business impacts, timelines, and financial severity mapping.
* **Premium Dark-Theme Interface:** Strict "Product" design register featuring high-density data tables, loading skeletons, smooth micro-animations, and interactive Recharts visualizations.

---

## 🛠️ Technology Stack

### Backend
* **Python 3.10+ / Flask:** Lightweight REST API.
* **Pandas & NumPy:** Fast, vectorized data cleaning, joining, and aggregation.
* **Werkzeug:** Secure file upload handling.

### Frontend
* **React 18 / Vite:** Ultra-fast bundler and component-based frontend shell.
* **TailwindCSS:** Modern, utility-first CSS styling strictly adhering to dark-mode product guidelines.
* **Recharts:** Responsive SVG-based interactive charts (Bar, Line, Area).
* **TanStack React Query & Axios:** Reliable state management, API integration, and cache invalidation.
* **Lucide React:** Clean, consistent iconography.

---

## 📂 Project Directory Structure

```text
SyrmaSGS_DashBoard/
├── backend/                   # Flask server entry point & API routes
│   └── app.py                 # Main application mapping to analytics services
├── services/                  # Core business logic and analytical computation
│   ├── grir_analytics_service.py # Core service: cleans data, runs engine, generates analytics
├── frontend/                  # React dashboard frontend
│   ├── src/                   
│   │   ├── features/grir/     # Core feature components (GrirDashboard.jsx)
│   │   └── index.css          # Core design tokens and custom scrollbars
│   ├── tailwind.config.js     # Typography (Outfit, JetBrains Mono) & Color definitions
│   └── vite.config.js         # Vite bundler configuration
├── grir_analysis.py           # Core pandas data processing scripts
├── requirements.txt           # Python backend dependencies
└── package.json               # Node frontend dependencies
```

---

## ⚡ Getting Started

### Prerequisites
* **Python 3.10+**
* **Node.js** (v18+ recommended) and **npm**
* **Hardware Profile:** Designed to run entirely locally on standard company laptops (CPU-only, 16GB RAM) without requiring a dedicated GPU or external cloud connections.

---

### Backend Setup

1. **Create and activate a Python Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **macOS/Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Flask Development Server:**
   ```bash
   python app.py
   ```
   The backend API will run on `http://127.0.0.1:5000`. It configures CORS automatically to accept requests from the frontend.

4. **Install & Configure Local LLM (Ollama) for Chatbot (Optional):**
   The dashboard includes an AI Assistant that analyzes the dataset. It requires [Ollama](https://ollama.com/) to run local models.
   
   **Step 1: Install Ollama**
   Download and install Ollama for your operating system from the [official website](https://ollama.com/download).

   **Step 2: Pull the Model**
   Open your terminal and pull a model. Since most users run this on standard company laptops (16GB RAM, CPU-only, no dedicated GPU), here is a guide to what you should pull based on the performance you want:

   **Comfortable (fast enough to chat, 5–15 tokens/sec):**
   * `ollama run llama3.2:3b` — Llama 3.2 1B / 3B (Q4_K_M): best all-rounder for your specs
   * `ollama run qwen2.5:3b` — Qwen 2.5 1.5B / 3B: strong reasoning for size, great at coding
   * `ollama run gemma2:2b` — Gemma 2 2B: solid quality, very efficient
   * `ollama run phi3:mini` — Phi-3.5 Mini (3.8B) Q4: punches above its weight on reasoning
   * `ollama run tinyllama` — TinyLlama 1.1B, SmolLM2 1.7B: fastest, lowest quality

   **Usable but slow (1–4 tokens/sec, ok for non-interactive tasks):**
   * `ollama run llama3.1:8b` — Llama 3.1 8B Q4_K_M (~5 GB RAM): best quality you’ll get, but expect coffee-break speeds
   * `ollama run mistral` — Mistral 7B / Qwen 2.5 7B Q4: similar story
   * `ollama run deepseek-coder:6.7b` — DeepSeek-Coder 6.7B Q4: if you specifically want coding help

   *(Note: The backend automatically detects the model you pull. No environment variable configuration is needed for local use—just run the pull command and start the backend!)*
   
   **Step 3: Centralized GPU Servers (Optional)**
   If Ollama is hosted centrally on a powerful machine, point your local dashboard to it:
   *Windows (PowerShell):*
   ```powershell
   $env:OLLAMA_URL="http://<SERVER_IP>:11434/api/chat"
   python backend/app.py
   ```

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

## 🖥️ Usage Guide

1. **Upload Dataset:** On launching the application, you will be presented with a dark-themed upload zone. Drag and drop your SAP GR/IR export file (`.csv`, `.xls`, or `.xlsx`) into the zone.
2. **Analysis Pending State:** The dashboard will display an animating skeleton layout while the backend pandas engine processes the thousands of ledger lines.
3. **Review KPIs:** Once loaded, the top row displays Total Open Exposure, Total IR Value, Actionable Exceptions (critical metric), Open PO Count, and Reversal Totals.
4. **Analyze Trends:** Use the dual charts to track *Reconciliation Accuracy Trend* (Match Rate % over time) and the *Cumulative Ledger Value Trend*.
5. **Drill Down into Actions:** Review the "Financial Statement Impact" and "Recommended Workflows" panels to see concrete, rule-based escalation protocols and their associated financial severity.
6. **Data Exploration:** Scroll down to the interactive data table to search by PO number, filter by status, or view explicit values for Type 7 and Type P metrics per line item.

---

## 🧪 Testing

A comprehensive suite of unit and integration test scripts is included to validate the data mappings, status classifications, API routes, and calculation accuracy.

To run the test scripts from the project root:

```bash
# Core Reconciliation Logic
python test_grir.py                # Main test suite for GR/IR data processing logic
python test_reconciliation.py      # Validates specific PO matching algorithms

# Data Classification & KPIs
python test_actionable.py          # Verifies actionable exception logic (>90 days, over-invoiced)
python cal_check.py                # Utility check for specific financial calculations

# API & Workflows
python test_endpoints.py           # Validates backend REST API endpoints
python test_upload.py              # Tests basic file upload handling
python test_upload_workflow.py     # End-to-end test of the upload and processing pipeline
```
