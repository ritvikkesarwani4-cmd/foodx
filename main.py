from fastapi import FastAPI, Request
import os
import mysql.connector

app = FastAPI()

# 🔥 session-based carts (fix for Railway issue)
ongoing_orders = {}

# 🔥 DB connection (replace with Railway creds)
conn = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT")),  
)
cursor = conn.cursor()

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    session = data["session"]
    intent = data["queryResult"]["intent"]["displayName"]
    params = data["queryResult"]["parameters"]

    # ✅ create cart per user session
    if session not in ongoing_orders:
        ongoing_orders[session] = {}

    cart = ongoing_orders[session]

    # ---------------- ADD ORDER ----------------
    if intent == "add_order":
        items = params.get("food-item", [])
        numbers = params.get("number", [])

        if not numbers:
            numbers = [1] * len(items)

        if len(numbers) != len(items):
            numbers = [numbers[0]] * len(items)

        for item, qty in zip(items, numbers):
            item = item.title()
            qty = int(qty)

            if item in cart:
                cart[item] += qty
            else:
                cart[item] = qty

        return {
            "fulfillmentText": f"Current order: {cart}"
        }

    # ---------------- REMOVE ORDER ----------------
    elif intent == "remove_order":
        items = params.get("food-item", [])
        numbers = params.get("number", [])

        # remove ALL if no number
        if not numbers:
            for item in items:
                item = item.title()
                if item in cart:
                    del cart[item]

        else:
            if len(numbers) != len(items):
                numbers = [numbers[0]] * len(items)

            for item, qty in zip(items, numbers):
                item = item.title()
                qty = int(qty)

                if item in cart:
                    cart[item] -= qty
                    if cart[item] <= 0:
                        del cart[item]

        return {
            "fulfillmentText": f"Updated order: {cart}"
        }

    # ---------------- COMPLETE ORDER ----------------
    elif intent == "order_complete":

        if not cart:
            return {"fulfillmentText": "Your cart is empty"}

        # create new order
        cursor.execute("INSERT INTO orders () VALUES ()")
        conn.commit()

        order_id = cursor.lastrowid  # 🔥 simple numeric ID

        # save items
        for item, qty in cart.items():
            cursor.execute(
                "INSERT INTO order_items (order_id, item, qty) VALUES (%s, %s, %s)",
                (order_id, item, qty)
            )

        conn.commit()

        # clear only this user's cart
        ongoing_orders[session] = {}

        return {
            "fulfillmentText": f"Order placed! Your order id is {order_id}"
        }

    # ---------------- TRACK ORDER ----------------
    elif intent == "track_order":
        raw_id = params.get("order_id")

        try:
            if isinstance(raw_id, list):
                order_id = int(raw_id[0])
            else:
                order_id = int(raw_id)
        except:
            return {"fulfillmentText": "Invalid order id"}

        cursor.execute(
            "SELECT item, qty FROM order_items WHERE order_id=%s",
            (order_id,)
        )
        rows = cursor.fetchall()

        if not rows:
            return {"fulfillmentText": "Order not found"}

        result = ", ".join([f"{qty} {item}" for item, qty in rows])

        return {
            "fulfillmentText": f"Your order: {result}"
        }

    # ---------------- DEFAULT ----------------
    return {"fulfillmentText": "I didn’t understand"}