from fastapi import FastAPI, Request
import mysql.connector
import os 
import pymysql

app = FastAPI()

# temporary cart (in memory)
ongoing_order = {}

conn = pymysql.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT"))
)
cursor = conn.cursor()

@app.post("/webhook")
async def webhook(req: Request):
    global ongoing_order

    data = await req.json()

    intent = data["queryResult"]["intent"]["displayName"]
    params = data["queryResult"]["parameters"]

    # ADD ORDER
    if intent == "add_order":
        items = params.get("food-item", [])
        numbers = params.get("number", [])

    # fallback if number missing
        if not numbers:
            numbers = [1] * len(items)

        # fix mismatch length (very common)
        if len(numbers) != len(items):
            numbers = [numbers[0]] * len(items)

        for item, qty in zip(items, numbers):
            qty = int(qty)
            if item in ongoing_order:
                ongoing_order[item] += qty
            else:
                ongoing_order[item] = qty

        print("CART:", ongoing_order)

        return {
            "fulfillmentText": f"Added items. Current order: {ongoing_order}. Anything else? or anything need to remove ?"
        }
    # REMOVE ORDER
    elif intent == "remove_order":
        items = params.get("food-item", [])
        numbers = params.get("number", [])

        # if no number → remove ALL
        if not numbers:
            for item in items:
                if item in ongoing_order:
                    del ongoing_order[item]

            return {
                "fulfillmentText": f"Updated order: {ongoing_order}.Anything else?"
            }

        # if number exists → remove specific qty
        for item, qty in zip(items, numbers):
            qty = int(qty)

            if item in ongoing_order:
                ongoing_order[item] -= qty

                if ongoing_order[item] <= 0:
                    del ongoing_order[item]

        return {
            "fulfillmentText": f"Updated order: {ongoing_order}.Anything else?"
}
    # COMPLETE ORDER
    elif intent == "order_complete":

        # create order
        cursor.execute("INSERT INTO orders () VALUES ()")
        conn.commit()

        order_id = cursor.lastrowid  # 🔥 THIS IS YOUR SIMPLE ID

        # insert items
        for item, qty in ongoing_order.items():
            cursor.execute(
                "INSERT INTO order_items (order_id, item, qty) VALUES (%s, %s, %s)",
                (order_id, item, qty)
            )

        conn.commit()

        ongoing_order = {}

        return {
            "fulfillmentText": f"Order placed! Your order id is {order_id} , you can track it with that id."
        }

    # TRACK ORDER
    elif intent == "track_order":
        order_id = params.get("order_id")

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

    return {"fulfillmentText": "Unknown request"}