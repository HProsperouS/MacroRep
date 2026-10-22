"""The built-in food catalogue.

Common foods every user can search, so a new account isn't left to create each one. Basic
foods follow USDA FoodData Central (public domain); Singapore hawker dishes and drinks
follow the Health Promotion Board's Energy & Nutrient Composition of Food. Values are
typical servings, rounded, and estimates like any food database's: a dish varies by stall.

Ids are permanent because food-log entries refer to them. Add new rows with a new additive
Alembic migration; never reuse an old id for another food.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.validation import MAX_NAME_LENGTH, ensure_plausible_calories

from .models import SERVING_UNITS, Food

Source = Literal["USDA", "HPB"]


@dataclass(frozen=True)
class CatalogFood:
    id: str
    name: str
    serving_size: float
    serving_unit: str
    serving_weight_g: float
    calories: int
    protein: float
    carbs: float
    fat: float
    # Where the values come from (docs only; not stored).
    source: Source

    def row(self) -> dict[str, object]:
        return {
            "id": self.id,
            "owner_id": None,
            "name": self.name,
            "serving_size": self.serving_size,
            "serving_unit": self.serving_unit,
            "serving_weight_g": self.serving_weight_g,
            "calories": self.calories,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
        }


def _usda(
    id: str, name: str, size: float, unit: str, grams: float, kcal: int, p: float, c: float, f: float
) -> CatalogFood:
    return CatalogFood(id, name, size, unit, grams, kcal, p, c, f, "USDA")


def _hpb(
    id: str, name: str, size: float, unit: str, grams: float, kcal: int, p: float, c: float, f: float
) -> CatalogFood:
    return CatalogFood(id, name, size, unit, grams, kcal, p, c, f, "HPB")


# Columns: id, name, serving size, serving unit, serving weight (g), kcal, protein, carbs, fat (g).
SYSTEM_FOODS: tuple[CatalogFood, ...] = (
    # Rice, noodles, bread and other staples
    _usda("food-white-rice", "White rice, cooked", 1, "bowl", 150, 195, 4, 42, 0.4),
    _usda("food-brown-rice", "Brown rice, cooked", 1, "bowl", 150, 185, 4.1, 38.4, 1.5),
    _usda("food-oats", "Rolled oats, dry", 40, "g", 40, 152, 5.3, 27.1, 2.6),
    _usda("food-oatmeal", "Oatmeal, cooked with water", 1, "cup", 234, 166, 5.9, 28.1, 3.6),
    _usda("food-wholemeal-bread", "Wholemeal bread", 1, "slice", 32, 81, 4, 13.8, 1.1),
    _usda("food-white-bread", "White bread", 1, "slice", 25, 66, 1.9, 12.3, 0.8),
    _usda("food-pasta", "Pasta, cooked", 1, "cup", 140, 221, 8.1, 43.3, 1.3),
    _usda("food-egg-noodles", "Egg noodles, cooked", 1, "cup", 160, 221, 7.3, 40.3, 3.3),
    _usda("food-rice-noodles", "Rice noodles (bee hoon), cooked", 1, "cup", 176, 190, 1.6, 42.3, 0.4),
    _usda("food-instant-noodles", "Instant noodles, with seasoning", 1, "piece", 85, 380, 8, 52, 15),
    _usda("food-quinoa", "Quinoa, cooked", 1, "cup", 185, 222, 8.1, 39.4, 3.6),
    _usda("food-potato", "Potato, baked", 1, "piece", 173, 161, 4.3, 36.6, 0.2),
    _usda("food-sweet-potato", "Sweet potato, baked", 1, "piece", 114, 103, 2.3, 23.6, 0.2),
    _usda("food-sweet-corn", "Sweet corn, cooked", 100, "g", 100, 96, 3.4, 21, 1.5),
    _usda("food-bagel", "Bagel, plain", 1, "piece", 98, 246, 10, 48, 1.5),
    _usda("food-cornflakes", "Cornflakes", 1, "cup", 28, 100, 2, 24, 0.2),
    _usda("food-tortilla", "Flour tortilla", 1, "piece", 45, 140, 3.7, 23, 3.6),
    # Meat, fish, eggs and plant protein
    _usda("food-chicken-breast", "Chicken breast, grilled", 100, "g", 100, 165, 31, 0, 3.6),
    _usda("food-chicken-thigh", "Chicken thigh, roasted, skinless", 100, "g", 100, 179, 24.8, 0, 8.2),
    _usda("food-beef-sirloin", "Beef sirloin, grilled", 100, "g", 100, 201, 29, 0, 8.8),
    _usda("food-ground-beef", "Minced beef (85% lean), cooked", 100, "g", 100, 250, 26, 0, 15),
    _usda("food-pork-loin", "Pork loin, roasted", 100, "g", 100, 196, 27, 0, 9),
    _usda("food-pork-belly", "Pork belly, roasted", 100, "g", 100, 518, 9.3, 0, 53),
    _usda("food-turkey-breast", "Turkey breast, roasted", 100, "g", 100, 147, 30, 0, 2),
    _usda("food-salmon", "Salmon, cooked", 100, "g", 100, 206, 22.1, 0, 12.4),
    _usda("food-tuna-canned", "Tuna, canned in water, drained", 100, "g", 100, 116, 25.5, 0, 0.8),
    _usda("food-tilapia", "Tilapia, cooked", 100, "g", 100, 128, 26.2, 0, 2.7),
    _usda("food-prawns", "Prawns, cooked", 100, "g", 100, 99, 24, 0.2, 0.3),
    _usda("food-sardines", "Sardines, canned in oil, drained", 100, "g", 100, 208, 24.6, 0, 11.5),
    _usda("food-egg", "Egg, whole", 1, "piece", 50, 78, 6.3, 0.6, 5.3),
    _usda("food-egg-white", "Egg white", 1, "piece", 33, 17, 3.6, 0.2, 0.1),
    _usda("food-fried-egg", "Egg, fried", 1, "piece", 46, 90, 6.3, 0.4, 6.8),
    _usda("food-firm-tofu", "Tofu, firm", 100, "g", 100, 144, 17.3, 2.8, 8.7),
    _usda("food-silken-tofu", "Tofu, silken", 100, "g", 100, 55, 4.8, 2.9, 2.7),
    _usda("food-tempeh", "Tempeh", 100, "g", 100, 192, 20.3, 7.6, 10.8),
    _usda("food-lentils", "Lentils, cooked", 1, "cup", 198, 230, 17.9, 39.9, 0.8),
    _usda("food-chickpeas", "Chickpeas, cooked", 1, "cup", 164, 269, 14.5, 45, 4.2),
    _usda("food-black-beans", "Black beans, cooked", 1, "cup", 172, 227, 15.2, 40.8, 0.9),
    _usda("food-edamame", "Edamame", 1, "cup", 155, 188, 18.4, 13.8, 8.1),
    _usda("food-whey-protein", "Whey protein powder", 1, "scoop", 30, 120, 24, 3, 1.5),
    # Milk, yoghurt and cheese
    _usda("food-whole-milk", "Milk, full cream", 1, "cup", 244, 149, 7.7, 11.7, 7.9),
    _usda("food-low-fat-milk", "Milk, low fat (1%)", 1, "cup", 244, 102, 8.2, 12.2, 2.4),
    _usda("food-skim-milk", "Milk, skim", 1, "cup", 245, 83, 8.3, 12.2, 0.2),
    _usda("food-soy-milk-plain", "Soy milk, unsweetened", 1, "cup", 243, 80, 7, 4, 4),
    _usda("food-greek-yogurt-nonfat", "Greek yoghurt, plain, non-fat", 170, "g", 170, 100, 17.3, 6.1, 0.7),
    _usda("food-greek-yogurt", "Greek yoghurt, plain, full fat", 170, "g", 170, 165, 15.3, 6.8, 8.5),
    _usda("food-yogurt-low-fat", "Yoghurt, plain, low fat", 1, "cup", 245, 154, 12.9, 17.2, 3.8),
    _usda("food-cheddar", "Cheddar cheese", 1, "slice", 28, 113, 7, 0.4, 9.3),
    _usda("food-mozzarella", "Mozzarella, part skim", 28, "g", 28, 72, 6.9, 0.8, 4.5),
    _usda("food-cottage-cheese", "Cottage cheese, low fat", 113, "g", 113, 92, 11.9, 5.4, 2.6),
    # Fruit
    _usda("food-banana", "Banana", 1, "piece", 118, 105, 1.3, 27, 0.4),
    _usda("food-apple", "Apple", 1, "piece", 182, 95, 0.5, 25.1, 0.3),
    _usda("food-orange", "Orange", 1, "piece", 131, 62, 1.2, 15.4, 0.2),
    _usda("food-pear", "Pear", 1, "piece", 178, 101, 0.6, 27.1, 0.2),
    _usda("food-kiwi", "Kiwi fruit", 1, "piece", 69, 42, 0.8, 10.1, 0.4),
    _usda("food-guava", "Guava", 1, "piece", 55, 37, 1.4, 7.9, 0.5),
    _usda("food-papaya", "Papaya", 1, "cup", 145, 62, 0.7, 15.7, 0.4),
    _usda("food-watermelon", "Watermelon", 1, "cup", 152, 46, 0.9, 11.5, 0.2),
    _usda("food-mango", "Mango", 1, "cup", 165, 99, 1.4, 24.7, 0.6),
    _usda("food-pineapple", "Pineapple", 1, "cup", 165, 82, 0.9, 21.6, 0.2),
    _usda("food-grapes", "Grapes", 1, "cup", 151, 104, 1.1, 27.3, 0.2),
    _usda("food-strawberries", "Strawberries", 1, "cup", 152, 49, 1, 11.7, 0.5),
    _usda("food-blueberries", "Blueberries", 1, "cup", 148, 84, 1.1, 21.4, 0.5),
    _usda("food-durian", "Durian", 100, "g", 100, 147, 1.5, 27.1, 5.3),
    _usda("food-avocado", "Avocado", 100, "g", 100, 160, 2, 8.5, 14.7),
    _usda("food-dates", "Dates, medjool", 1, "piece", 24, 66, 0.4, 18, 0),
    # Vegetables
    _usda("food-broccoli", "Broccoli, cooked", 1, "cup", 156, 55, 3.7, 11.2, 0.6),
    _usda("food-spinach", "Spinach, cooked", 1, "cup", 180, 41, 5.3, 6.8, 0.5),
    _usda("food-bok-choy", "Bok choy (chye sim), cooked", 1, "cup", 170, 20, 2.7, 3, 0.3),
    _usda("food-carrot", "Carrot", 1, "piece", 61, 25, 0.6, 5.8, 0.1),
    _usda("food-cucumber", "Cucumber", 1, "cup", 104, 16, 0.7, 3.8, 0.1),
    _usda("food-tomato", "Tomato", 1, "piece", 123, 22, 1.1, 4.8, 0.2),
    _usda("food-lettuce", "Lettuce, romaine", 1, "cup", 47, 8, 0.6, 1.5, 0.1),
    _usda("food-green-beans", "Green beans, cooked", 1, "cup", 125, 44, 2.4, 9.9, 0.4),
    _usda("food-mixed-vegetables", "Mixed vegetables, cooked", 1, "cup", 182, 118, 5.2, 23.8, 0.3),
    _usda("food-mushrooms", "Mushrooms, cooked", 1, "cup", 156, 44, 3.4, 8.3, 0.7),
    _usda("food-eggplant", "Eggplant (brinjal), cooked", 1, "cup", 99, 35, 0.8, 8.6, 0.2),
    # Nuts, oils and spreads
    _usda("food-peanut-butter", "Peanut butter", 1, "tbsp", 16, 94, 4, 3.2, 8),
    _usda("food-almonds", "Almonds", 28, "g", 28, 164, 6, 6.1, 14.2),
    _usda("food-peanuts", "Peanuts, roasted", 28, "g", 28, 166, 6.7, 6, 14.1),
    _usda("food-cashews", "Cashews", 28, "g", 28, 157, 5.2, 8.6, 12.4),
    _usda("food-walnuts", "Walnuts", 28, "g", 28, 185, 4.3, 3.9, 18.5),
    _usda("food-chia-seeds", "Chia seeds", 1, "tbsp", 12, 58, 2, 5, 3.7),
    _usda("food-olive-oil", "Olive oil", 1, "tbsp", 13.5, 119, 0, 0, 13.5),
    _usda("food-vegetable-oil", "Vegetable oil", 1, "tbsp", 13.6, 120, 0, 0, 13.6),
    _usda("food-butter", "Butter", 1, "tbsp", 14, 102, 0.1, 0, 11.5),
    _usda("food-mayonnaise", "Mayonnaise", 1, "tbsp", 13.8, 94, 0.1, 0.1, 10.3),
    _usda("food-honey", "Honey", 1, "tbsp", 21, 64, 0.1, 17.3, 0),
    _usda("food-sugar", "Sugar", 1, "tbsp", 12.5, 48, 0, 12.5, 0),
    _usda("food-soy-sauce", "Soy sauce", 1, "tbsp", 16, 9, 1.3, 0.8, 0.1),
    _usda("food-ketchup", "Tomato ketchup", 1, "tbsp", 17, 17, 0.2, 4.7, 0),
    _usda("food-hummus", "Hummus", 30, "g", 30, 50, 2.4, 4.3, 2.9),
    # Snacks and fast food
    _usda("food-dark-chocolate", "Dark chocolate (70-85%)", 28, "g", 28, 170, 2.2, 13, 12.1),
    _usda("food-potato-chips", "Potato chips", 28, "g", 28, 150, 2, 14.8, 9.8),
    _usda("food-popcorn", "Popcorn, air-popped", 1, "cup", 8, 31, 1, 6.2, 0.4),
    _usda("food-cheeseburger", "Cheeseburger", 1, "piece", 113, 303, 15, 33, 12),
    _usda("food-french-fries", "French fries, medium", 1, "piece", 117, 365, 4, 48, 17),
    _usda("food-cheese-pizza", "Pizza, cheese", 1, "slice", 107, 285, 12.2, 35.7, 10.4),
    # Drinks
    _usda("food-orange-juice", "Orange juice", 1, "cup", 248, 112, 1.7, 25.8, 0.5),
    _usda("food-cola", "Cola", 330, "ml", 330, 139, 0, 35, 0),
    _usda("food-beer", "Beer", 330, "ml", 330, 142, 1.5, 11.7, 0),
    _usda("food-black-coffee", "Coffee, black", 1, "cup", 240, 2, 0.3, 0, 0),
    _usda("food-latte", "Caffe latte, full cream milk", 1, "cup", 360, 180, 10, 15, 9),
    _usda("food-coconut-water", "Coconut water", 1, "cup", 240, 46, 1.7, 8.9, 0.5),
    # Hawker rice and noodle dishes
    _hpb("food-chicken-rice", "Chicken rice, steamed", 1, "plate", 380, 607, 25, 75, 23),
    _hpb("food-roast-chicken-rice", "Chicken rice, roasted", 1, "plate", 380, 650, 28, 75, 26),
    _hpb("food-duck-rice", "Duck rice", 1, "plate", 380, 640, 27, 80, 23),
    _hpb("food-economy-rice", "Economy rice, 1 meat 2 veg", 1, "plate", 400, 600, 25, 80, 20),
    _hpb("food-nasi-lemak", "Nasi lemak", 1, "plate", 300, 494, 14, 58, 22),
    _hpb("food-nasi-briyani", "Nasi briyani, chicken", 1, "plate", 450, 800, 35, 95, 31),
    _hpb("food-fried-rice", "Fried rice with egg", 1, "plate", 300, 520, 14, 75, 18),
    _hpb("food-laksa", "Laksa", 1, "bowl", 500, 589, 23, 52, 32),
    _hpb("food-char-kway-teow", "Char kway teow", 1, "plate", 380, 744, 23, 76, 38),
    _hpb("food-hokkien-mee", "Hokkien prawn mee", 1, "plate", 400, 522, 18, 69, 19),
    _hpb("food-mee-goreng", "Mee goreng", 1, "plate", 380, 660, 18, 80, 30),
    _hpb("food-wanton-mee", "Wanton mee, dry", 1, "plate", 300, 409, 15, 58, 13),
    _hpb("food-bak-chor-mee", "Bak chor mee, dry", 1, "bowl", 300, 511, 22, 60, 20),
    _hpb("food-fishball-noodles", "Fishball noodle soup", 1, "bowl", 500, 350, 16, 55, 7),
    _hpb("food-ban-mian", "Ban mian, soup", 1, "bowl", 550, 475, 22, 58, 17),
    _hpb("food-prawn-noodle-soup", "Prawn noodle soup", 1, "bowl", 500, 300, 17, 45, 6),
    _hpb("food-lor-mee", "Lor mee", 1, "bowl", 500, 450, 17, 62, 15),
    _hpb("food-mee-rebus", "Mee rebus", 1, "bowl", 500, 556, 20, 82, 16),
    _hpb("food-mee-siam", "Mee siam", 1, "plate", 400, 520, 17, 72, 18),
    _hpb("food-beef-hor-fun", "Beef hor fun", 1, "plate", 450, 700, 30, 85, 26),
    _hpb("food-fried-bee-hoon", "Fried bee hoon, plain", 1, "plate", 200, 360, 8, 56, 12),
    _hpb("food-sliced-fish-soup", "Sliced fish soup with bee hoon", 1, "bowl", 550, 330, 25, 45, 5),
    _hpb("food-yong-tau-foo", "Yong tau foo soup, 6 pieces with bee hoon", 1, "bowl", 550, 450, 25, 55, 14),
    _hpb("food-carrot-cake", "Fried carrot cake (chai tow kway), white", 1, "plate", 300, 550, 10, 60, 30),
    # Hawker breakfast, snacks and sides
    _hpb("food-roti-prata", "Roti prata, plain", 1, "piece", 60, 209, 4, 26, 10),
    _hpb("food-roti-prata-egg", "Roti prata, egg", 1, "piece", 90, 263, 8, 26, 14),
    _hpb("food-thosai", "Thosai, plain", 1, "piece", 100, 150, 4, 26, 3.5),
    _hpb("food-chapati", "Chapati", 1, "piece", 50, 140, 4, 24, 3.5),
    _hpb("food-kaya-toast", "Kaya toast with butter", 2, "slice", 70, 302, 6, 38, 14),
    _hpb("food-kaya", "Kaya", 1, "tbsp", 20, 60, 0.6, 11, 1.6),
    _hpb("food-chicken-satay", "Satay, chicken", 1, "piece", 15, 43, 4, 1.5, 2.3),
    _hpb("food-chicken-wing", "Fried chicken wing", 1, "piece", 60, 170, 12, 5, 11),
    _hpb("food-char-siew", "Char siew (barbecued pork)", 100, "g", 100, 270, 22, 12, 15),
    _hpb("food-popiah", "Popiah", 1, "piece", 130, 190, 6, 26, 7),
    _hpb("food-curry-puff", "Curry puff, chicken", 1, "piece", 70, 246, 5, 25, 14),
    _hpb("food-otah", "Otah", 1, "piece", 40, 70, 5, 2, 4.7),
    _hpb("food-siew-mai", "Siew mai", 1, "piece", 20, 50, 3, 2, 3.3),
    _hpb("food-har-gow", "Har gow", 1, "piece", 20, 40, 2, 5, 1.3),
    _hpb("food-char-siew-pau", "Char siew pau", 1, "piece", 60, 160, 5, 25, 4.5),
    _hpb("food-kang-kong", "Kang kong belacan", 1, "plate", 150, 147, 4, 8, 11),
    _hpb("food-kai-lan", "Kai lan, stir-fried", 1, "plate", 100, 91, 3, 5, 6.5),
    _hpb("food-tau-huay", "Tau huay (soya beancurd), sweetened", 1, "bowl", 250, 151, 6, 25, 3),
    _hpb("food-chendol", "Chendol", 1, "bowl", 300, 402, 4, 65, 14),
    # Hawker drinks
    _hpb("food-kopi", "Kopi (with condensed milk)", 1, "cup", 240, 119, 2, 20, 3.5),
    _hpb("food-kopi-o", "Kopi-O (with sugar)", 1, "cup", 240, 58, 0.3, 14, 0.2),
    _hpb("food-kopi-c", "Kopi-C (with evaporated milk, sugar)", 1, "cup", 240, 90, 2, 15, 2.5),
    _hpb("food-teh", "Teh (with condensed milk)", 1, "cup", 240, 119, 2, 20, 3.5),
    _hpb("food-teh-tarik", "Teh tarik", 1, "cup", 250, 132, 3, 21, 4),
    _hpb("food-milo", "Milo, kopitiam", 1, "cup", 250, 160, 4, 27, 4),
    _hpb("food-soy-milk-sweet", "Soya bean milk, sweetened", 1, "cup", 250, 131, 7, 18, 3.5),
    _hpb("food-bubble-tea", "Bubble tea, milk tea with pearls", 1, "cup", 500, 351, 3, 60, 11),
    _hpb("food-isotonic-drink", "Isotonic drink", 325, "ml", 325, 85, 0, 21, 0),
)


# What a user is offered before searching, after what they ate lately, most likely first:
# common local meals and staples. As many as the most suggestions asked for (20).
POPULAR_FOOD_IDS: tuple[str, ...] = (
    "food-chicken-rice",
    "food-white-rice",
    "food-egg",
    "food-chicken-breast",
    "food-kopi",
    "food-banana",
    "food-nasi-lemak",
    "food-oatmeal",
    "food-economy-rice",
    "food-wholemeal-bread",
    "food-greek-yogurt-nonfat",
    "food-fishball-noodles",
    "food-teh",
    "food-apple",
    "food-salmon",
    "food-roti-prata",
    "food-whole-milk",
    "food-firm-tofu",
    "food-wanton-mee",
    "food-whey-protein",
)


def validate_catalogue() -> None:
    """Fail at import on a malformed row, so a bad entry never reaches a database."""

    ids: set[str] = set()
    names: set[str] = set()
    for food in SYSTEM_FOODS:
        if not re.fullmatch(r"[a-z0-9-]+", food.id) or len(food.id) > 40:
            raise ValueError(f"Invalid food catalogue id: {food.id!r}")
        if food.id in ids:
            raise ValueError(f"Duplicate food catalogue id: {food.id}")
        ids.add(food.id)

        normalized_name = food.name.casefold()
        if not food.name.strip() or len(food.name) > MAX_NAME_LENGTH or normalized_name in names:
            raise ValueError(f"Duplicate, empty or too long food catalogue name: {food.name!r}")
        names.add(normalized_name)

        if food.serving_unit not in SERVING_UNITS:
            raise ValueError(f"Unknown serving unit for {food.id}: {food.serving_unit}")
        if food.serving_unit == "g" and food.serving_weight_g != food.serving_size:
            raise ValueError(f"A serving in grams must weigh its size: {food.id}")
        if min(food.serving_size, food.serving_weight_g, food.calories) <= 0:
            raise ValueError(f"Serving and calories must be positive: {food.id}")
        if min(food.protein, food.carbs, food.fat) < 0:
            raise ValueError(f"Macros can't be negative: {food.id}")
        # The rule a user's own food is held to.
        ensure_plausible_calories(food.calories, food.protein, food.carbs, food.fat)
    unknown = set(POPULAR_FOOD_IDS) - ids
    if unknown or len(set(POPULAR_FOOD_IDS)) != len(POPULAR_FOOD_IDS):
        raise ValueError(f"Popular foods must be distinct catalogue ids: {sorted(unknown)}")


validate_catalogue()


async def ensure_system_foods(session: AsyncSession) -> int:
    """Install missing built-in foods without changing existing rows.

    The caller owns the transaction. Returns the number added.
    """

    catalogue_ids = [food.id for food in SYSTEM_FOODS]
    existing_ids = set(await session.scalars(select(Food.id).where(Food.id.in_(catalogue_ids))))
    missing = [Food(**food.row()) for food in SYSTEM_FOODS if food.id not in existing_ids]
    if missing:
        session.add_all(missing)
        await session.flush()
    return len(missing)
