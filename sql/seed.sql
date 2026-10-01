-- Seed: canonical ingredients (per 100g nutrition unless noted) and a small Indian + global dish set.
-- Nutrition numbers are approximate USDA-style references for the vertical slice, not clinical claims.
USE cookai;

INSERT INTO ingredients
  (canonical_name, category, aliases, translations, vegetarian, vegan, contains_egg, contains_dairy, contains_gluten, contains_nuts, animal_derived, jain_status, allergens, nutrition_data, source)
VALUES
('Chicken', 'protein', JSON_ARRAY('murgh','chicken breast'), JSON_OBJECT('hi','मुर्गा','en','chicken'), 0, 0, 0, 0, 0, 0, 1, 'not_allowed', JSON_ARRAY(), JSON_OBJECT('calories',165,'protein_g',31,'carbs_g',0,'fat_g',3.6,'per','100g'), 'seed'),
('Paneer', 'protein', JSON_ARRAY('cottage cheese','paneer'), JSON_OBJECT('hi','पनीर'), 1, 0, 0, 1, 0, 0, 1, 'allowed', JSON_ARRAY('dairy'), JSON_OBJECT('calories',265,'protein_g',18,'carbs_g',1.2,'fat_g',20.8,'per','100g'), 'seed'),
('Chickpea', 'legume', JSON_ARRAY('chana','kabuli chana','garbanzo'), JSON_OBJECT('hi','चना'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',164,'protein_g',8.9,'carbs_g',27,'fat_g',2.6,'per','100g'), 'seed'),
('Rice', 'grain', JSON_ARRAY('chawal','basmati'), JSON_OBJECT('hi','चावल'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',130,'protein_g',2.7,'carbs_g',28,'fat_g',0.3,'per','100g'), 'seed'),
('Tomato', 'vegetable', JSON_ARRAY('tamatar'), JSON_OBJECT('hi','टमाटर'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',18,'protein_g',0.9,'carbs_g',3.9,'fat_g',0.2,'per','100g'), 'seed'),
('Onion', 'vegetable', JSON_ARRAY('pyaaz'), JSON_OBJECT('hi','प्याज'), 1, 1, 0, 0, 0, 0, 0, 'not_allowed', JSON_ARRAY(), JSON_OBJECT('calories',40,'protein_g',1.1,'carbs_g',9.3,'fat_g',0.1,'per','100g'), 'seed'),
('Garlic', 'vegetable', JSON_ARRAY('lehsun'), JSON_OBJECT('hi','लहसुन'), 1, 1, 0, 0, 0, 0, 0, 'not_allowed', JSON_ARRAY(), JSON_OBJECT('calories',149,'protein_g',6.4,'carbs_g',33,'fat_g',0.5,'per','100g'), 'seed'),
('Ginger', 'vegetable', JSON_ARRAY('adrak'), JSON_OBJECT('hi','अदरक'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',80,'protein_g',1.8,'carbs_g',18,'fat_g',0.8,'per','100g'), 'seed'),
('Basil', 'herb', JSON_ARRAY('thai basil','tulsi'), JSON_OBJECT('hi','तुलसी'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',23,'protein_g',3.2,'carbs_g',2.6,'fat_g',0.6,'per','100g'), 'seed'),
('Soy sauce', 'condiment', JSON_ARRAY('soya sauce'), JSON_OBJECT('hi','सोया सॉस'), 1, 1, 0, 0, 1, 0, 0, 'not_allowed', JSON_ARRAY('gluten','soy'), JSON_OBJECT('calories',53,'protein_g',8,'carbs_g',5,'fat_g',0.1,'per','100ml'), 'seed'),
('Mustard oil', 'fat', JSON_ARRAY('sarson tel'), JSON_OBJECT('hi','सरसों का तेल'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',884,'protein_g',0,'carbs_g',0,'fat_g',100,'per','100ml'), 'seed'),
('Wheat flour', 'grain', JSON_ARRAY('atta','gehun'), JSON_OBJECT('hi','गेहूं का आटा'), 1, 1, 0, 0, 1, 0, 0, 'allowed', JSON_ARRAY('gluten'), JSON_OBJECT('calories',340,'protein_g',12,'carbs_g',72,'fat_g',1.7,'per','100g'), 'seed'),
('Sattu', 'legume', JSON_ARRAY('roasted gram flour'), JSON_OBJECT('hi','सत्तू'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',390,'protein_g',22,'carbs_g',58,'fat_g',6,'per','100g'), 'seed'),
('Eggplant', 'vegetable', JSON_ARRAY('baingan','brinjal'), JSON_OBJECT('hi','बैंगन'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',25,'protein_g',1,'carbs_g',6,'fat_g',0.2,'per','100g'), 'seed'),
('Potato', 'vegetable', JSON_ARRAY('aloo'), JSON_OBJECT('hi','आलू'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',77,'protein_g',2,'carbs_g',17,'fat_g',0.1,'per','100g'), 'seed'),
('Lentil', 'legume', JSON_ARRAY('dal','masoor','toor'), JSON_OBJECT('hi','दाल'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',116,'protein_g',9,'carbs_g',20,'fat_g',0.4,'per','100g'), 'seed'),
('Butter', 'fat', JSON_ARRAY('makhan'), JSON_OBJECT('hi','मक्खन'), 1, 0, 0, 1, 0, 0, 1, 'allowed', JSON_ARRAY('dairy'), JSON_OBJECT('calories',717,'protein_g',0.9,'carbs_g',0.1,'fat_g',81,'per','100g'), 'seed'),
('Yogurt', 'dairy', JSON_ARRAY('dahi','curd'), JSON_OBJECT('hi','दही'), 1, 0, 0, 1, 0, 0, 1, 'allowed', JSON_ARRAY('dairy'), JSON_OBJECT('calories',61,'protein_g',3.5,'carbs_g',4.7,'fat_g',3.3,'per','100g'), 'seed'),
('Fish', 'protein', JSON_ARRAY('machli'), JSON_OBJECT('hi','मछली'), 0, 0, 0, 0, 0, 0, 1, 'not_allowed', JSON_ARRAY('fish'), JSON_OBJECT('calories',120,'protein_g',22,'carbs_g',0,'fat_g',3,'per','100g'), 'seed'),
('Banana', 'fruit', JSON_ARRAY('kela'), JSON_OBJECT('hi','केला'), 1, 1, 0, 0, 0, 0, 0, 'allowed', JSON_ARRAY(), JSON_OBJECT('calories',89,'protein_g',1.1,'carbs_g',23,'fat_g',0.3,'per','100g'), 'seed');

-- Demo user. Password is not used by the slice; auth is a header user id.
INSERT INTO users (email, password_hash, name, country, language, timezone, currency)
VALUES ('shailendra@cookai.local', 'not-a-real-hash', 'Shailendra', 'IN', 'en', 'Asia/Kolkata', 'INR');

INSERT INTO households (owner_user_id, name, country, currency)
VALUES (1, 'Shailendra Household', 'IN', 'INR');

INSERT INTO household_members (household_id, name, role, age_group, diet_profile, allergies, spice_level)
VALUES
(1, 'Shailendra', 'owner', 'adult', 'none', JSON_ARRAY(), 0.75),
(1, 'Member', 'adult', 'adult', 'vegetarian', JSON_ARRAY(), 0.50);

INSERT INTO profiles (
  user_id, favorite_cuisines, favorite_dishes, disliked_ingredients, recent_dishes,
  spice_level, exploration_level, cooking_skill, budget_preferences, nutrition_targets, recommendation_memory
) VALUES (
  1,
  JSON_ARRAY('Indian','Thai'),
  JSON_ARRAY('Paneer Butter Masala','Chicken Biryani','Dal Tadka'),
  JSON_ARRAY('raw_onion'),
  JSON_ARRAY('Paneer Butter Masala','Chicken Biryani','Dal Tadka'),
  0.75, 0.72, 'intermediate',
  JSON_OBJECT('meal_budget_inr', 280, 'dinner_budget_inr', 700),
  JSON_OBJECT('calories', 2000, 'protein_g', 90),
  JSON_OBJECT(
    'cuisines', JSON_OBJECT('Indian', 0.92, 'Thai', 0.40, 'Korean', 0.10),
    'proteins', JSON_OBJECT('chicken', 0.83, 'paneer', 0.71),
    'newness_needed', 0.70
  )
);

INSERT INTO recipes (
  canonical_name, country, region, cuisine, dish_type, ingredients_json, steps_json,
  diet_tags, difficulty, prep_minutes, cook_minutes, source_type, confidence
) VALUES
(
  'Dal Tadka', 'India', 'North', 'Indian', 'dinner',
  JSON_ARRAY(
    JSON_OBJECT('name','Lentil','quantity',200,'unit','g'),
    JSON_OBJECT('name','Tomato','quantity',150,'unit','g'),
    JSON_OBJECT('name','Onion','quantity',80,'unit','g'),
    JSON_OBJECT('name','Garlic','quantity',10,'unit','g'),
    JSON_OBJECT('name','Mustard oil','quantity',15,'unit','ml')
  ),
  JSON_ARRAY(
    JSON_OBJECT('step',1,'instruction','Rinse lentils and simmer with turmeric until soft.','duration_seconds',900),
    JSON_OBJECT('step',2,'instruction','Heat mustard oil, crackle cumin, add onion, garlic and tomato.','duration_seconds',300),
    JSON_OBJECT('step',3,'instruction','Pour tadka over dal, salt, simmer 2 minutes.','duration_seconds',120)
  ),
  JSON_ARRAY('vegetarian'), 'easy', 10, 25, 'canonical', 0.9
),
(
  'Litti Chokha', 'India', 'Bihar / Jharkhand', 'Eastern Indian', 'dinner',
  JSON_ARRAY(
    JSON_OBJECT('name','Wheat flour','quantity',200,'unit','g'),
    JSON_OBJECT('name','Sattu','quantity',120,'unit','g'),
    JSON_OBJECT('name','Mustard oil','quantity',20,'unit','ml'),
    JSON_OBJECT('name','Eggplant','quantity',250,'unit','g'),
    JSON_OBJECT('name','Tomato','quantity',150,'unit','g'),
    JSON_OBJECT('name','Potato','quantity',150,'unit','g')
  ),
  JSON_ARRAY(
    JSON_OBJECT('step',1,'instruction','Knead wheat flour with water and salt into a firm dough.','duration_seconds',300),
    JSON_OBJECT('step',2,'instruction','Mix sattu with mustard oil, salt, ginger and spices.','duration_seconds',180),
    JSON_OBJECT('step',3,'instruction','Stuff dough balls and roast until crusted.','duration_seconds',1200),
    JSON_OBJECT('step',4,'instruction','Roast eggplant, mash with tomato, potato and mustard oil for chokha.','duration_seconds',900)
  ),
  JSON_ARRAY('vegetarian'), 'medium', 20, 40, 'canonical', 0.92
),
(
  'Thai Basil Chicken', 'Thailand', 'Central', 'Thai', 'dinner',
  JSON_ARRAY(
    JSON_OBJECT('name','Chicken','quantity',500,'unit','g'),
    JSON_OBJECT('name','Basil','quantity',20,'unit','g'),
    JSON_OBJECT('name','Tomato','quantity',100,'unit','g'),
    JSON_OBJECT('name','Soy sauce','quantity',30,'unit','ml'),
    JSON_OBJECT('name','Rice','quantity',300,'unit','g'),
    JSON_OBJECT('name','Garlic','quantity',10,'unit','g')
  ),
  JSON_ARRAY(
    JSON_OBJECT('step',1,'instruction','Heat oil until shimmering.','duration_seconds',60),
    JSON_OBJECT('step',2,'instruction','Add garlic, then chicken. Stir until no longer pink.','duration_seconds',360),
    JSON_OBJECT('step',3,'instruction','Add soy sauce and tomato. Cook until light golden.','duration_seconds',180),
    JSON_OBJECT('step',4,'instruction','Fold in basil off heat. Serve with rice.','duration_seconds',60)
  ),
  JSON_ARRAY('non_vegetarian'), 'easy', 10, 20, 'canonical', 0.88
),
(
  'Paneer Butter Masala', 'India', 'North', 'Indian', 'dinner',
  JSON_ARRAY(
    JSON_OBJECT('name','Paneer','quantity',300,'unit','g'),
    JSON_OBJECT('name','Tomato','quantity',300,'unit','g'),
    JSON_OBJECT('name','Butter','quantity',30,'unit','g'),
    JSON_OBJECT('name','Onion','quantity',100,'unit','g'),
    JSON_OBJECT('name','Yogurt','quantity',50,'unit','g')
  ),
  JSON_ARRAY(
    JSON_OBJECT('step',1,'instruction','Blend tomato, ginger and spices into a gravy base.','duration_seconds',180),
    JSON_OBJECT('step',2,'instruction','Cook gravy in butter until oil separates.','duration_seconds',600),
    JSON_OBJECT('step',3,'instruction','Add paneer and a spoon of yogurt. Simmer gently.','duration_seconds',300)
  ),
  JSON_ARRAY('vegetarian'), 'easy', 15, 25, 'canonical', 0.9
);
