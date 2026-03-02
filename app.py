from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
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
			"image": self.image,
			"total_time": self.total_time,
			"yields": self.yields,
			"created_at": self.created_at.isoformat(),
		}


with app.app_context():
	db.create_all()


def scrape_recipe(url: str) -> Dict[str, Any]:
	scraper = scrape_me(url, wild_mode=True)
	return {
		"title": scraper.title() or "Untitled Recipe",
		"ingredients": scraper.ingredients() or [],
		"instructions": scraper.instructions() or "",
		"image": scraper.image() or "",
		"total_time": scraper.total_time() or None,
		"yields": scraper.yields() or "",
	}


@app.get("/health")
def health() -> Any:
	return jsonify({"status": "ok"})


@app.post("/recipes/import")
def import_recipe() -> Any:
	payload = request.get_json(silent=True) or {}
	url = (payload.get("url") or "").strip()
	user_id = (payload.get("user_id") or "").strip()

	if not url or not user_id:
		return (
			jsonify({"error": "url and user_id are required"}),
			400,
		)

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
	app.run(debug=True)
