# Activate your venv (if not already active):
# & "C:\Users\Ginod\OneDrive\Desktop\Personal Projects\Recipe Sorter\.venv\Scripts\Activate.ps1"

# Start the server:
# python app.py

# Test import (grabs ingredients + steps)
# $body = @{ url = "https://www.bbcgoodfood.com/recipes/easy-pancakes"; user_id = "test-user" } | ConvertTo-Json
# Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/recipes/import" -ContentType "application/json" -Body $body
# Where ingredients/steps go

# Ingredients are stored in SQLite in recipes.db, column ingredients_json.
# Instructions are stored in instructions.
# Steps are generated from instructions and returned as steps in the API response. See app.py:41-154.
# How to view them

# Immediate response: the POST response includes ingredients, instructions, and steps.
# Saved recipes for a user:
# Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:5000/users/test-user/recipes"

# Single recipe by ID:
# Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:5000/recipes/1"
from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from recipe_scrapers import scrape_me

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recipes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CORS(app)
db = SQLAlchemy(app)


class Recipe(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.String(128), nullable=False, index=True)
	url = db.Column(db.String(2048), nullable=False)
	title = db.Column(db.String(512), nullable=False)
	ingredients_json = db.Column(db.Text, nullable=True)
	instructions = db.Column(db.Text, nullable=True)
	tools_json = db.Column(db.Text, nullable=True)
	image = db.Column(db.String(2048), nullable=True)
	total_time = db.Column(db.Integer, nullable=True)
	yields = db.Column(db.String(256), nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"id": self.id,
			"user_id": self.user_id,
			"url": self.url,
			"title": self.title,
			"ingredients": json.loads(self.ingredients_json)
			if self.ingredients_json
			else [],
			"instructions": self.instructions,
			"steps": split_steps(self.instructions),
			"tools": json.loads(self.tools_json) if self.tools_json else [],
			"image": self.image,
			"total_time": self.total_time,
			"yields": self.yields,
			"created_at": self.created_at.isoformat(),
		}


with app.app_context():
	db.create_all()
	result = db.session.execute(text("PRAGMA table_info(recipe)"))
	columns = {row[1] for row in result.fetchall()}
	if "tools_json" not in columns:
		db.session.execute(text("ALTER TABLE recipe ADD COLUMN tools_json TEXT"))
		db.session.commit()



def split_steps(instructions: str | None) -> List[str]:
	if not instructions:
		return []
	lines = [line.strip() for line in instructions.splitlines()]
	steps = [line for line in lines if line]
	return steps


def extract_tools(instructions: str, ingredients: List[str]) -> List[str]:
	text = " ".join([instructions or "", " ".join(ingredients)]).lower()
	known_tools = [
		"oven",
		"stovetop",
		"microwave",
		"air fryer",
		"slow cooker",
		"pressure cooker",
		"grill",
		"skillet",
		"frying pan",
		"saucepan",
		"pot",
		"baking sheet",
		"baking pan",
		"casserole dish",
		"mixing bowl",
		"whisk",
		"spatula",
		"tongs",
		"ladle",
		"cutting board",
		"chef's knife",
		"paring knife",
		"peeler",
		"grater",
		"colander",
		"strainer",
		"measuring cups",
		"measuring spoons",
		"food processor",
		"blender",
		"stand mixer",
		"hand mixer",
		"thermometer",
	]
	found = []
	for tool in known_tools:
		if tool in text:
			found.append(tool)
	return sorted(set(found))


def scrape_recipe(url: str) -> Dict[str, Any]:
	try:
		scraper = scrape_me(url, wild_mode=True)
	except AttributeError as exc:
		message = str(exc)
		if "list" in message and "get" in message:
			scraper = scrape_me(url, wild_mode=False)
		else:
			raise
	ingredients = scraper.ingredients() or []
	instructions = scraper.instructions() or ""
	return {
		"title": scraper.title() or "Untitled Recipe",
		"ingredients": ingredients,
		"instructions": instructions,
		"steps": split_steps(instructions),
		"tools": extract_tools(instructions, ingredients),
		"image": scraper.image() or "",
		"total_time": scraper.total_time() or None,
		"yields": scraper.yields() or "",
	}


@app.get("/health")
def health() -> Any:
	return jsonify({"status": "ok"})


@app.get("/")
def login_page() -> Any:
	return render_template("index.html")


@app.get("/dashboard")
def dashboard_page() -> Any:
	return render_template("dashboard.html")


@app.post("/recipes/import")
def import_recipe() -> Any:
	payload = request.get_json(silent=True)
	if isinstance(payload, list):
		payload = payload[0] if payload else {}
	if not isinstance(payload, dict):
		payload = {}
	url = (payload.get("url") or "").strip().rstrip("/")
	user_id = (payload.get("user_id") or "").strip()

	if not url or not user_id:
		return (
			jsonify({"error": "url and user_id are required"}),
			400,
		)

	existing = Recipe.query.filter_by(user_id=user_id, url=url).first()
	if existing:
		response = existing.to_dict()
		response["duplicate"] = True
		return jsonify(response), 200

	try:
		recipe_data = scrape_recipe(url)
	except Exception as exc:  # pragma: no cover - error passthrough
		return (
			jsonify({"error": "failed to scrape recipe", "details": str(exc)}),
			400,
		)

	recipe = Recipe(
		user_id=user_id,
		url=url,
		title=recipe_data["title"],
		ingredients_json=json.dumps(recipe_data["ingredients"]),
		instructions=recipe_data["instructions"],
		tools_json=json.dumps(recipe_data["tools"]),
		image=recipe_data["image"],
		total_time=recipe_data["total_time"],
		yields=recipe_data["yields"],
	)
	db.session.add(recipe)
	db.session.commit()

	return jsonify(recipe.to_dict()), 201


@app.get("/users/<user_id>/recipes")
def list_user_recipes(user_id: str) -> Any:
	recipes = (
		Recipe.query.filter_by(user_id=user_id)
		.order_by(Recipe.created_at.desc())
		.all()
	)
	return jsonify([recipe.to_dict() for recipe in recipes])


@app.get("/recipes/<int:recipe_id>")
def get_recipe(recipe_id: int) -> Any:
	recipe = Recipe.query.get_or_404(recipe_id)
	return jsonify(recipe.to_dict())


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Recipe Sorter")
	parser.add_argument(
		"--scan",
		help="Scan a recipe URL and print parsed data as JSON",
	)
	args = parser.parse_args()

	if args.scan:
		try:
			print(json.dumps(scrape_recipe(args.scan), indent=2))
		except Exception as exc:  # pragma: no cover - CLI passthrough
			raise SystemExit(f"Scan failed: {exc}")
	else:
		app.run(debug=True)
