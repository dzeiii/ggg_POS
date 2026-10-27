# Small Business POS — Python + Streamlit + SQLite

A local POS prototype with persistent SQLite storage and manually implemented data structures:

- **LinkedListCart**: singly linked list for cart additions, quantity changes, removals, and totals.
- **AVLTree**: self-balancing binary search tree keyed by normalized product names. Used for exact product search and in-order product listing.
- **MinHeap**: binary min-heap for pending pickup orders. Priority 1 is highest; ties are resolved by creation time and order ID.
- **SQLite**: persistent products, transaction headers, transaction line items, and pickup-order statuses.

## Requirements

- Python 3.10 or newer
- pip
- Internet connection for the initial package installation

## Run on Windows

1. Extract the project folder.
2. Open Command Prompt or PowerShell in that folder.
3. (Recommended) Create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use `\.venv\Scripts\activate.bat` in Command Prompt.
4. Install dependencies:

   ```powershell
   py -m pip install -r requirements.txt
   ```
5. Start the app:

   ```powershell
   py -m streamlit run app.py
   ```
6. Streamlit opens a local browser page, normally at `http://localhost:8501`.

## Run on macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The `pos.db` database file is created automatically in the same folder as `app.py`. Keep this file to retain records. Do not delete it unless you intentionally want to reset the database.

## Quick acceptance test

1. Open **Products**, add `Iced Coffee`, category `Drinks`, price `75`, stock `10`.
2. Add `Bottled Water`, category `Drinks`, price `20`, stock `5`.
3. Open **Checkout**, add two Iced Coffees and one Bottled Water. Verify the total is ₱170.00.
4. Complete a regular sale. Verify stock becomes 8 and 4 respectively.
5. Make another cart and place a pickup order at priority 4; then create another at priority 1. Open **Pickup Orders**. Priority 1 should be processed first.
6. Open **Transaction History**, inspect transaction line items, and download the CSV.
7. Stop and restart Streamlit. Confirm product, inventory, transaction, and order history remain.
8. Try a duplicate product name, blank name, quantity larger than stock, and an empty checkout. The app should reject invalid input or show a clear message.

## Data structure test (without opening the UI)

```bash
python -m unittest test_data_structures.py
```

## Notes / limitations

- This is a local educational prototype, not a production payment terminal. It has no payment gateway, authentication, role management, tax configuration, receipt printer, or remote multi-user deployment controls.
- Pickup orders are recorded as sales and inventory is deducted when the order is placed; the queue status tracks fulfillment. Cancelling/refunding orders is not implemented.
- Product deactivation is used instead of hard deletion so historical transaction lines remain meaningful.
- Product names are unique without regard to letter case, which makes name-keyed AVL Tree operations unambiguous.
- SQLite transactions make checkout atomic: if an exception occurs before commit, the sale and stock updates roll back together.
