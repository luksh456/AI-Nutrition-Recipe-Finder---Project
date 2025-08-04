from flask import Flask, render_template, request, redirect, url_for
import requests
import os
import base64
import random
import json

app = Flask(__name__)

# 🔑 Your API Keys
CLARIFAI_API_KEY = "3ee36c32547d42269e30f003fdbca067"
SPOONACULAR_API_KEY = "4e84da9d03214f5fa696d5d5627d9fd3"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Local data file
DATA_FILE = "fridge_data.json"

# Clarifai Model Info
MODEL_ID = "food-item-recognition"
MODEL_VERSION = "1d5fd481e0cf4826aa72ec3ff049e044"
CLARIFAI_URL = f"https://api.clarifai.com/v2/models/{MODEL_ID}/versions/{MODEL_VERSION}/outputs"

# 🍎 Function: Get Nutrition Facts
def get_nutrition(ingredient):
    try:
        search_url = f"https://api.spoonacular.com/food/ingredients/search?query={ingredient}&apiKey={SPOONACULAR_API_KEY}"
        search_resp = requests.get(search_url).json()

        if search_resp.get("results"):
            ing_id = search_resp["results"][0]["id"]
            info_url = f"https://api.spoonacular.com/food/ingredients/{ing_id}/information?amount=100&unit=gram&apiKey={SPOONACULAR_API_KEY}"
            info_resp = requests.get(info_url).json()

            nutrients = info_resp.get("nutrition", {}).get("nutrients", [])
            data = {"name": ingredient, "calories": "N/A", "protein": "N/A", "fat": "N/A", "carbs": "N/A"}

            for n in nutrients:
                if n["name"] == "Calories":
                    data["calories"] = round(n["amount"], 2)
                elif n["name"] == "Protein":
                    data["protein"] = round(n["amount"], 2)
                elif n["name"] == "Fat":
                    data["fat"] = round(n["amount"], 2)
                elif n["name"] == "Carbohydrates":
                    data["carbs"] = round(n["amount"], 2)
            return data
        else:
            return {"name": ingredient, "calories": "Unknown", "protein": "-", "fat": "-", "carbs": "-"}
    except Exception as e:
        print(f"[Nutrition Error] {e}")
        return {"name": ingredient, "calories": "Error", "protein": "-", "fat": "-", "carbs": "-"}

# ⏰ Function: Generate Expiry Reminders
def generate_expiry(ingredients):
    reminders = {"expired": [], "soon": [], "upcoming": [], "safe": []}
    for ing in ingredients:
        days = random.randint(1, 14)
        if days <= 2:
            reminders["expired"].append(f"{ing} may expire very soon ({days} days left)")
        elif days <= 5:
            reminders["soon"].append(f"{ing} expires in {days} days")
        elif days <= 10:
            reminders["upcoming"].append(f"{ing} expires in {days} days")
        else:
            reminders["safe"].append(f"{ing} is safe for {days} days")
    return reminders

# 📌 Function: Save data to JSON
def save_to_json(ingredients, nutrition_data, reminders):
    data_entry = {
        "ingredients": ingredients,
        "nutrition_data": nutrition_data,
        "reminders": reminders
    }
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(data_entry)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# 📌 Function: Load history from JSON
def load_history():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

# 📌 Function: Clear history
def clear_history():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)

@app.route("/", methods=["GET", "POST"])
def index():
    ingredients = []
    recipes = []
    nutrition_data = []
    uploaded_image = None
    reminders = {}
    error_message = None

    if request.method == "POST":
        if "clear_history" in request.form:   # ✅ Clear history button pressed
            clear_history()
            return redirect(url_for("index"))

        elif "food_image" not in request.files:
            error_message = "No file uploaded!"
        else:
            file = request.files["food_image"]
            if file.filename == "":
                error_message = "No file selected!"
            else:
                filepath = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(filepath)
                uploaded_image = filepath

                try:
                    headers = {"Authorization": f"Key {CLARIFAI_API_KEY}"}
                    with open(filepath, "rb") as f:
                        img_bytes = f.read()
                    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

                    response = requests.post(
                        CLARIFAI_URL,
                        headers=headers,
                        json={"inputs": [{"data": {"image": {"base64": img_base64}}}]}
                    )

                    response_json = response.json()
                    print("Clarifai Response:", response_json)

                    if "outputs" in response_json and len(response_json["outputs"]) > 0:
                        concepts = response_json['outputs'][0]['data'].get('concepts', [])
                        if concepts:
                            ingredients = [c['name'] for c in concepts[:5]]
                            nutrition_data = [get_nutrition(ing) for ing in ingredients]
                            reminders = generate_expiry(ingredients)

                            save_to_json(ingredients, nutrition_data, reminders)

                            # Recipes
                            query = ",".join(ingredients)
                            recipe_url = f"https://api.spoonacular.com/recipes/findByIngredients?ingredients={query}&number=3&apiKey={SPOONACULAR_API_KEY}"
                            recipe_response = requests.get(recipe_url)
                            recipes = recipe_response.json()
                        else:
                            error_message = "No ingredients detected in this image."
                    else:
                        error_message = f"Clarifai Error: {response_json}"
                except Exception as e:
                    error_message = f"Error: {str(e)}"

    history = load_history()

    return render_template("index.html",
                           ingredients=ingredients,
                           recipes=recipes,
                           nutrition_data=nutrition_data,
                           uploaded_image=uploaded_image,
                           reminders=reminders,
                           error_message=error_message,
                           history=history)

if __name__ == "__main__":
    app.run(debug=True)
