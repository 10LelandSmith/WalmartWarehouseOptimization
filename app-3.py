import os
import sqlite3
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Walmart Store Stock & Freight Tracker",
    page_icon="🏪",
    layout="wide"
)

DB_PATH = "walmart_store_tracker.db"


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_and_seed_if_missing(db_path: str = DB_PATH) -> None:
    """Initializes the SQLite database with the exact notebook schema and seed data if not already present."""
    db_exists = os.path.exists(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        department TEXT NOT NULL,
        aisle_location TEXT NOT NULL,
        backroom_bin TEXT NOT NULL,
        floor_qty INTEGER NOT NULL DEFAULT 0 CHECK (floor_qty >= 0),
        backroom_qty INTEGER NOT NULL DEFAULT 0 CHECK (backroom_qty >= 0),
        reorder_point INTEGER NOT NULL DEFAULT 20 CHECK (reorder_point >= 0),
        avg_daily_sales REAL NOT NULL DEFAULT 5.0,
        unit_price REAL NOT NULL CHECK (unit_price >= 0)
    );

    CREATE TABLE IF NOT EXISTS freight_shipments (
        shipment_id TEXT PRIMARY KEY,
        trailer_number TEXT NOT NULL,
        dc_origin TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        status TEXT NOT NULL CHECK (status IN ('In Transit', 'At Dock', 'Unloaded', 'Stocked')),
        eta TEXT NOT NULL,
        FOREIGN KEY (sku) REFERENCES products(sku) ON UPDATE CASCADE ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS movement_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        sku TEXT NOT NULL,
        action_type TEXT NOT NULL CHECK (action_type IN ('FREIGHT_UNLOAD', 'FLOOR_REPLENISH', 'POS_SALE')),
        quantity_change INTEGER NOT NULL,
        resulting_floor_qty INTEGER NOT NULL CHECK (resulting_floor_qty >= 0),
        resulting_backroom_qty INTEGER NOT NULL CHECK (resulting_backroom_qty >= 0),
        source_location TEXT NOT NULL,
        destination_location TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (sku) REFERENCES products(sku) ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        sample_products = [
            ('WM-1001', 'Great Value Whole Milk 1 Gal', 'Grocery', 'Aisle G12', 'BR-COOL-01', 25, 50, 25, 16.0, 3.68),
            ('WM-1002', 'Great Value Purified Water 40pk', 'Grocery', 'Aisle G04', 'BR-DRY-04', 30, 70, 30, 20.0, 5.36),
            ('WM-1003', 'Great Value Large White Eggs 18ct', 'Grocery', 'Aisle G11', 'BR-COOL-02', 20, 45, 20, 14.0, 4.12),
            ('WM-2010', 'onn. 55" 4K UHD Roku TV', 'Electronics', 'Aisle E01', 'BR-SEC-02', 6, 14, 5, 2.0, 248.00),
            ('WM-2015', 'Apple AirPods Pro (2nd Gen)', 'Electronics', 'Aisle E05', 'BR-SEC-01', 10, 20, 8, 3.0, 189.00),
            ('WM-3040', 'Bounty Select-A-Size Paper Towels 12pk', 'Household', 'Aisle H02', 'BR-BULK-03', 18, 40, 15, 8.5, 22.44),
            ('WM-3045', 'Tide Pods Liquid Laundry Detergent 81ct', 'Household', 'Aisle H06', 'BR-BULK-01', 22, 35, 15, 6.5, 21.44),
            ('WM-4012', 'George Men Crewneck Tee 3pk', 'Apparel', 'Zone A03', 'BR-APP-02', 28, 45, 20, 5.5, 14.98),
            ('WM-4018', 'Athletic Works Running Socks 6pk', 'Apparel', 'Zone A07', 'BR-APP-04', 24, 40, 18, 5.0, 11.98),
            ('WM-5008', 'Equate Ibuprofen 200mg 500ct', 'Health & Wellness', 'Aisle P03', 'BR-PHM-01', 18, 30, 15, 4.0, 9.97)
        ]
        cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_products)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sample_freight = [
            ('FR-1001', 'TRL-4800', 'DC #6040 (Shelby, NC)', 'WM-1001', 60, 'At Dock', now_str),
            ('FR-1002', 'TRL-4800', 'DC #6040 (Shelby, NC)', 'WM-1002', 80, 'At Dock', now_str),
            ('FR-1003', 'TRL-4817', 'DC #6011 (Brookhaven, MS)', 'WM-2010', 12, 'In Transit', now_str),
            ('FR-1004', 'TRL-4817', 'DC #6011 (Brookhaven, MS)', 'WM-3040', 40, 'In Transit', now_str),
        ]
        cursor.executemany("INSERT INTO freight_shipments VALUES (?, ?, ?, ?, ?, ?, ?)", sample_freight)

    conn.commit()
    conn.close()


def classify_stock_status(row: pd.Series) -> str:
    """
    Classifies item inventory health:
    - Out of Stock: total_on_hand == 0 or floor_qty == 0
    - Overstock: total_on_hand > reorder_point * 3 (or > 14 days of supply)
    - Low Stock: floor_qty < reorder_point (and > 0)
    - In Stock: healthy shelf and backroom balance
    """
    total = row["floor_qty"] + row["backroom_qty"]
    overstock_limit = row["reorder_point"] * 3
    if total == 0 or row["floor_qty"] == 0:
        return "Out of Stock"
    elif total > overstock_limit:
        return "Overstock"
    elif row["floor_qty"] < row["reorder_point"]:
        return "Low Stock"
    return "In Stock"


def record_movement(
    sku: str,
    action_type: str,
    quantity: int,
    shipment_id: str = None,
    notes: str = ""
) -> tuple[bool, str]:
    """
    Processes a movement record with strict SKU validation and zero-negative inventory guards.
    Supported action_types:
    - FREIGHT_UNLOAD: Adds quantity to backroom_qty (optionally marks shipment_id as Unloaded)
    - FLOOR_REPLENISH: Moves quantity from backroom_qty to floor_qty
    - POS_SALE: Deducts quantity from floor_qty
    """
    if quantity <= 0:
        return False, "Quantity must be greater than zero."

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT item_name, aisle_location, backroom_bin, floor_qty, backroom_qty FROM products WHERE sku = ?",
            (sku,)
        )
        product = cursor.fetchone()
        if not product:
            return False, f"SKU '{sku}' does not exist in the products database."

        item_name, aisle_loc, bin_loc, floor_qty, backroom_qty = product
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action_type == "FREIGHT_UNLOAD":
            if shipment_id:
                cursor.execute(
                    "SELECT sku, quantity, status, trailer_number FROM freight_shipments WHERE shipment_id = ?",
                    (shipment_id,)
                )
                ship = cursor.fetchone()
                if not ship:
                    return False, f"Shipment ID '{shipment_id}' not found."
                ship_sku, ship_qty, ship_status, trailer = ship
                if ship_sku != sku:
                    return False, f"Shipment {shipment_id} is for SKU {ship_sku}, not {sku}."
                if ship_status in ("Unloaded", "Stocked"):
                    return False, f"Shipment {shipment_id} is already {ship_status}."
                quantity = ship_qty
                src_loc = f"Trailer {trailer}"
                cursor.execute("UPDATE freight_shipments SET status = 'Unloaded' WHERE shipment_id = ?", (shipment_id,))
            else:
                src_loc = "Receiving Dock"

            new_floor = floor_qty
            new_backroom = backroom_qty + quantity
            qty_change = quantity
            dst_loc = bin_loc

        elif action_type == "FLOOR_REPLENISH":
            if backroom_qty < quantity:
                return False, f"Insufficient backroom stock for {sku}. Available in {bin_loc}: {backroom_qty} units."
            new_floor = floor_qty + quantity
            new_backroom = backroom_qty - quantity
            qty_change = quantity
            src_loc = bin_loc
            dst_loc = aisle_loc

        elif action_type == "POS_SALE":
            if floor_qty < quantity:
                return False, f"Insufficient sales floor stock for {sku}. Available on {aisle_loc}: {floor_qty} units."
            new_floor = floor_qty - quantity
            new_backroom = backroom_qty
            qty_change = -quantity
            src_loc = aisle_loc
            dst_loc = "Customer POS Checkout"

        else:
            return False, f"Unsupported action type: {action_type}"

        if new_floor < 0 or new_backroom < 0:
            return False, "Operation blocked: inventory cannot go below zero."

        cursor.execute(
            "UPDATE products SET floor_qty = ?, backroom_qty = ? WHERE sku = ?",
            (new_floor, new_backroom, sku)
        )
        cursor.execute(
            """
            INSERT INTO movement_logs (
                timestamp, sku, action_type, quantity_change,
                resulting_floor_qty, resulting_backroom_qty,
                source_location, destination_location, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, sku, action_type, qty_change, new_floor, new_backroom, src_loc, dst_loc, notes or action_type)
        )
        conn.commit()
        return True, (
            f"Recorded {action_type} for {sku} ({item_name}): "
            f"Floor = {new_floor}, Backroom = {new_backroom}."
        )
    except sqlite3.Error as exc:
        conn.rollback()
        return False, f"Database error: {exc}"
    finally:
        conn.close()


def load_tables():
    conn = get_db_connection()
    inv_df = pd.read_sql_query("SELECT * FROM products ORDER BY sku", conn)
    freight_df = pd.read_sql_query(
        """
        SELECT f.shipment_id, f.trailer_number, f.dc_origin, f.sku, p.item_name, f.quantity, f.status, f.eta
        FROM freight_shipments f
        JOIN products p ON f.sku = p.sku
        ORDER BY f.eta DESC, f.shipment_id ASC
        """,
        conn
    )
    logs_df = pd.read_sql_query(
        """
        SELECT m.log_id, m.timestamp, m.sku, p.item_name, m.action_type,
               m.quantity_change, m.resulting_floor_qty, m.resulting_backroom_qty,
               m.source_location, m.destination_location, m.notes
        FROM movement_logs m
        JOIN products p ON m.sku = p.sku
        ORDER BY m.log_id DESC
        """,
        conn
    )
    conn.close()

    inv_df["total_on_hand"] = inv_df["floor_qty"] + inv_df["backroom_qty"]
    inv_df["overstock_threshold"] = inv_df["reorder_point"] * 3
    inv_df["days_of_supply"] = np.round(inv_df["total_on_hand"] / inv_df["avg_daily_sales"], 1)
    inv_df["stock_status"] = inv_df.apply(classify_stock_status, axis=1)
    return inv_df, freight_df, logs_df


# Initialize DB on first run
init_and_seed_if_missing()
inv_df, freight_df, logs_df = load_tables()

# --- Header ---
st.title("🏪 Walmart Store Stock & Freight Tracking System")
st.caption("CIS 3400 – Advanced Programming | Real-Time Inventory Status, Overstock Alerts & Movement Entry")

# --- Top KPI Summary ---
in_stock_cnt = int((inv_df["stock_status"] == "In Stock").sum())
low_stock_cnt = int((inv_df["stock_status"] == "Low Stock").sum())
overstock_cnt = int((inv_df["stock_status"] == "Overstock").sum())
out_of_stock_cnt = int((inv_df["stock_status"] == "Out of Stock").sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Store SKUs", len(inv_df))
k2.metric("✅ In Stock", in_stock_cnt)
k3.metric("⚠️ Low Stock", low_stock_cnt)
k4.metric("📦 Overstock", overstock_cnt)
k5.metric("🚨 Out of Stock", out_of_stock_cnt)

st.divider()

# --- Sidebar: Enter a Movement Record ---
with st.sidebar:
    st.header("➕ Enter Movement Record")
    st.write("Log incoming freight, backroom-to-shelf restocks, or POS sales.")

    sku_options = [f"{r.sku} — {r.item_name}" for r in inv_df.itertuples()]
    selected_sku_label = st.selectbox("Select Product (SKU)", sku_options)
    selected_sku = selected_sku_label.split(" — ")[0]

    prod_row = inv_df[inv_df["sku"] == selected_sku].iloc[0]
    st.info(
        f"**Current Balances ({selected_sku})**\n"
        f"- Sales Floor ({prod_row['aisle_location']}): **{prod_row['floor_qty']}**\n"
        f"- Backroom ({prod_row['backroom_bin']}): **{prod_row['backroom_qty']}**\n"
        f"- Status: **{prod_row['stock_status']}**"
    )

    action_type = st.selectbox(
        "Movement Action",
        ["FLOOR_REPLENISH", "POS_SALE", "FREIGHT_UNLOAD"],
        format_func=lambda x: {
            "FLOOR_REPLENISH": "FLOOR_REPLENISH (Backroom → Shelf)",
            "POS_SALE": "POS_SALE (Shelf → Customer)",
            "FREIGHT_UNLOAD": "FREIGHT_UNLOAD (Dock → Backroom)"
        }[x]
    )

    pending_shipments = freight_df[
        (freight_df["sku"] == selected_sku) & (freight_df["status"].isin(["At Dock", "In Transit"]))
    ]
    selected_shipment = None

    if action_type == "FREIGHT_UNLOAD" and not pending_shipments.empty:
        ship_choices = ["Manual Dock Entry"] + [
            f"{r.shipment_id} ({r.quantity} units - {r.status})" for r in pending_shipments.itertuples()
        ]
        chosen_ship = st.selectbox("Link Pending Freight Shipment (Optional)", ship_choices)
        if chosen_ship != "Manual Dock Entry":
            selected_shipment = chosen_ship.split(" ")[0]
            ship_qty = int(pending_shipments[pending_shipments["shipment_id"] == selected_shipment]["quantity"].iloc[0])
            quantity = st.number_input("Quantity", min_value=1, value=ship_qty, disabled=True)
        else:
            quantity = st.number_input("Quantity to Unload", min_value=1, max_value=5000, value=20)
    else:
        default_qty = 10
        if action_type == "FLOOR_REPLENISH" and prod_row["backroom_qty"] > 0:
            default_qty = min(10, int(prod_row["backroom_qty"]))
        elif action_type == "POS_SALE" and prod_row["floor_qty"] > 0:
            default_qty = min(5, int(prod_row["floor_qty"]))
        quantity = st.number_input("Quantity", min_value=1, max_value=5000, value=max(1, default_qty))

    notes = st.text_input("Notes (Optional)", placeholder="e.g., Morning zone restock")

    if st.button("Submit Movement Record", type="primary", use_container_width=True):
        ok, msg = record_movement(
            sku=selected_sku,
            action_type=action_type,
            quantity=int(quantity),
            shipment_id=selected_shipment,
            notes=notes
        )
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

# --- Main Tabs ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Stock Status Overview",
    "🚨 Out of Stock & Overstock Alerts",
    "📜 Movement Logs",
    "🚚 Freight Pipeline"
])

with tab1:
    st.subheader("Live Store Inventory Status")
    col_f1, col_f2 = st.columns(2)
    dept_filter = col_f1.multiselect(
        "Filter by Department",
        options=sorted(inv_df["department"].unique()),
        default=sorted(inv_df["department"].unique())
    )
    status_filter = col_f2.multiselect(
        "Filter by Stock Status",
        options=["In Stock", "Low Stock", "Overstock", "Out of Stock"],
        default=["In Stock", "Low Stock", "Overstock", "Out of Stock"]
    )

    filtered_inv = inv_df[
        (inv_df["department"].isin(dept_filter)) & (inv_df["stock_status"].isin(status_filter))
    ].copy()

    def style_status(val):
        colors = {
            "Out of Stock": "background-color: #f8d7da; color: #721c24; font-weight: bold;",
            "Overstock": "background-color: #fff3cd; color: #856404; font-weight: bold;",
            "Low Stock": "background-color: #ffe5d0; color: #984c0c; font-weight: bold;",
            "In Stock": "background-color: #d4edda; color: #155724; font-weight: bold;"
        }
        return colors.get(val, "")

    display_cols = [
        "sku", "item_name", "department", "aisle_location", "backroom_bin",
        "floor_qty", "backroom_qty", "total_on_hand", "reorder_point",
        "overstock_threshold", "days_of_supply", "stock_status"
    ]
    st.dataframe(
        filtered_inv[display_cols].style.map(style_status, subset=["stock_status"]),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Floor vs. Backroom Units by SKU")
    chart_df = filtered_inv.set_index("sku")[["floor_qty", "backroom_qty"]]
    st.bar_chart(chart_df)

with tab2:
    c_left, c_right = st.columns(2)

    with c_left:
        st.subheader("🚨 Out of Stock / Empty Shelf Items")
        oos_df = inv_df[inv_df["stock_status"] == "Out of Stock"]
        if oos_df.empty:
            st.success("No items are currently Out of Stock!")
        else:
            st.error(f"{len(oos_df)} item(s) have 0 units on the sales floor or storewide.")
            st.dataframe(
                oos_df[["sku", "item_name", "department", "aisle_location", "floor_qty", "backroom_qty"]],
                use_container_width=True,
                hide_index=True
            )

        st.subheader("⚠️ Low Stock (Needs Shelf Replenishment)")
        low_df = inv_df[inv_df["stock_status"] == "Low Stock"]
        if low_df.empty:
            st.success("All active shelves are above reorder points.")
        else:
            st.dataframe(
                low_df[["sku", "item_name", "floor_qty", "backroom_qty", "reorder_point"]],
                use_container_width=True,
                hide_index=True
            )

    with c_right:
        st.subheader("📦 Overstock Items (> 3x Reorder Point)")
        over_df = inv_df[inv_df["stock_status"] == "Overstock"]
        if over_df.empty:
            st.info("No items are currently classified as Overstock.")
        else:
            st.warning(f"{len(over_df)} item(s) exceed the store overstock threshold (3x reorder point).")
            st.dataframe(
                over_df[["sku", "item_name", "department", "floor_qty", "backroom_qty", "total_on_hand", "overstock_threshold", "days_of_supply"]],
                use_container_width=True,
                hide_index=True
            )

with tab3:
    st.subheader(f"Audit Movement History ({len(logs_df)} Records)")
    if logs_df.empty:
        st.info("No movement records logged yet. Use the sidebar to enter a movement record.")
    else:
        st.dataframe(logs_df, use_container_width=True, hide_index=True)

with tab4:
    st.subheader(f"Incoming & Processed Freight Shipments ({len(freight_df)} Records)")
    st.dataframe(freight_df, use_container_width=True, hide_index=True)
