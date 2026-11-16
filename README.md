# WalmartWarehouseOptimization


# CIS 3400 – Advanced Programming
## Project 2: Python Application Development

**Student Name:** Leland Smith  
**Project Title:** SmartStock: Walmart Storewide Freight & Inventory Tracker  
**Course:** CIS 3400 – Advanced Programming  
**Final Presentation:** December 8, 2026

---

## 1. Project Overview

**Application Name:** SmartStock Walmart Tracker

**Project Option:** Database-Enabled & Predictive ML Application

### Problem Statement
In large-scale retail environments like Walmart, managing inventory levels across the backroom receiving bay, sales floor aisles, and top-stock shelves presents significant operational challenges. Stockouts lead to missed sales, while misplaced freight slows down replenishment teams and increases labor costs. SmartStock provides a centralized, real-time tracking interface paired with predictive analytics to optimize stock levels, track incoming freight trucks, and streamline storewide inventory management.

### Intended Users
- **Store Associates:** Locate items across the backroom, top-stock, and shelf locations, and log freight movement in real time.
- **Department Managers:** Track daily inventory turnover, receive low-stock alerts, and predict reorder needs.
- **Logistics & Receiving Teams:** Track incoming freight trucks, scan receiving pallets, and assign freight to target aisles.

### Unique Features
Unlike generic inventory scripts, SmartStock combines real-time spatial location mapping (Aisle, Bay, Shelf, Top-Stock, Receiving) with lightweight machine learning to predict stock depletion based on historical sales trends and day-of-week demand spikes.

---

## 2. Application Features

- **Feature 1: Real-Time Freight & Receiving Logging:** Allows receiving teams to log incoming delivery trucks, scan shipment manifests, and auto-route pallets to specific store departments.
- **Feature 2: Spatial Inventory Locator:** Provides associates with exact shelf, top-stock, and backroom bin locations for any SKU or item name.
- **Feature 3: Predictive Reorder Engine:** Uses machine learning models to forecast stock depletion rates and suggest automatic purchase orders before items go out of stock.
- **Feature 4: Interactive Dashboard & Analytics:** Visualizes real-time inventory health, department stock metrics, and high-velocity items using an intuitive Streamlit interface.

---

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming language for application logic and data pipelines |
| Streamlit | Web interface for the real-time associate and manager dashboards |
| Pandas / NumPy | Data manipulation, inventory status aggregation, and freight metrics calculation |
| scikit-learn | Machine learning model (RandomForestRegressor) for sales and stock depletion forecasting |
| SQLite | Local relational database storing inventory tables, freight logs, and user activity |

---

## 4. Application Architecture

```text
[ User Interface (Streamlit) ]
              │
              ▼
[ Python App Logic (app.py) ] ── (Queries / Updates) ──► [ SQLite Database (walmart_stock.db) ]
              │
              ▼
[ ML Engine (model/reorder_model.py) ] ──► [ Depletion Predictions & Reorder Alerts ]
```

![Application architecture](docs/architecture.png)

### How the Application Works

1. The user logs into the Streamlit interface (as Associate, Receiving, or Manager).
2. For freight logging: The user inputs incoming truck details; Python scripts update the SQLite `freight_logs` and `inventory` tables.
3. For stock searches: Python queries the SQLite database for item location (Aisle, Bay, Top-Stock) and displays the visual map.
4. For stock forecasting: Historical sales and current stock levels are passed to the `scikit-learn` model to calculate remaining shelf-life days and alert managers.
5. All system updates are saved persistently to SQLite.

---

## 5. Project Structure

```text
walmart_smartstock/
├── app.py
├── database/
│   ├── db_manager.py
│   └── walmart_stock.db
├── model/
│   ├── reorder_model.py
│   └── predictor.joblib
├── data/
│   ├── sample_inventory.csv
│   └── sample_freight_manifest.csv
├── docs/
│   ├── architecture.png
│   ├── main-screen.png
│   └── analytics-screen.png
├── requirements.txt
└── README.md
```

### File Responsibilities
- `app.py`: Main Streamlit application running the user interface and routing.
- `database/db_manager.py`: Handles SQLite connections, table creation, and CRUD operations for inventory/freight.
- `model/reorder_model.py`: Script to train and save the scikit-learn model for predicting stock depletion.
- `requirements.txt`: Project dependencies list.

---

## 6. Installation and Running the Application

### Step 1: Clone the repository

```bash
git clone https://github.com/your-username/walmart-smartstock.git
cd walmart-smartstock
```

### Step 2: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run the application

```bash
streamlit run app.py
```

---

## 7. Testing and Validation

| Test | Expected Result | Actual Result |
|---|---|---|
| Scan/Log Incoming Freight | Pallet data is stored in DB and aisle assignment is generated | Pass |
| Item Location Search | Returns exact Aisle/Bay/Top-Stock coordinates | Pass |
| Out of Stock Input | Generates immediate restock alert and displays low stock flag | Pass |
| ML Reorder Forecast | Predicts depletion date based on velocity trends | Pass |

### Known Limitations
- Stock forecasts currently do not account for external weather events or holiday promotions.
- Database is running on SQLite, which is ideal for single-store local testing but would require migration to PostgreSQL/BigQuery for enterprise multi-store scale.

---

## 8. AI-Assisted Development Disclosure

**AI Tools Used:** ChatGPT / Gemini

### How AI Was Used
- Generated boilerplates for Streamlit layout components.
- Assisted in writing optimized SQL queries for multi-table joins between freight logs and inventory status.
- Helped troubleshoot dataframe reshaping during scikit-learn model preprocessing.

### Student Contributions
Designed the system architecture, structured the database schema tailored to Walmart inventory systems, implemented the core business logic, and integrated the machine learning model with the UI dashboard.

**Student statement:** I reviewed, tested, and can explain the code and technologies used in my application, including code developed with AI assistance.

---

## 9. Challenges and Lessons Learned

**Challenge 1:** Handling concurrency when logging fast-moving stock updates alongside incoming freight logs.  
*Solution:* Structured modular database transaction functions in `db_manager.py` with sqlite3 contexts.

**Challenge 2:** Accurate inventory forecasting given sparse historical data for new items.  
*Solution:* Fallback logic using average category-level velocity metrics when item-specific history is limited.

---

## 10. Application Screenshots

1. **Main Store Associate Search Interface Synthetic Data**
   ![Main application interface](docs/main-screen.png)

2. **Manager Analytics & Inventory Depletion Forecast**
   ![Analytics Interface](docs/analytics-screen.png)

---

## 11. Project Links

**GitHub Repository:** [Insert Link]  
**Deployed Application:** [Insert Streamlit Community Cloud Link, if applicable]  
**Demonstration Video:** [Insert Video Link, if applicable]

---

## 12. Future Improvements

1. RFID scanning integration to track freight movement automatically without manual logging.
2. Integration of seasonal holiday trend parameters into the predictive restock model.
