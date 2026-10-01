-- CookAI canonical schema. MySQL 8. ~15 tables.
-- JSON columns hold flexible preferences, recipe payloads, and event data.
-- Large media lives in object storage; media_assets stores keys only.

CREATE DATABASE IF NOT EXISTS cookai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cookai;

CREATE TABLE users (
  id            BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  email         VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  name          VARCHAR(120) NOT NULL,
  country       CHAR(2) NOT NULL DEFAULT 'IN',
  language      VARCHAR(12) NOT NULL DEFAULT 'en',
  timezone      VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
  currency      CHAR(3) NOT NULL DEFAULT 'INR',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE households (
  id            BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  name          VARCHAR(120) NOT NULL,
  country       CHAR(2) NOT NULL DEFAULT 'IN',
  currency      CHAR(3) NOT NULL DEFAULT 'INR',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_household_owner FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE household_members (
  id            BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  household_id  BIGINT UNSIGNED NOT NULL,
  name          VARCHAR(120) NOT NULL,
  role          VARCHAR(40) NOT NULL DEFAULT 'member',
  age_group     VARCHAR(20) NOT NULL DEFAULT 'adult',
  diet_profile  VARCHAR(40) NOT NULL DEFAULT 'none',
  allergies     JSON NULL,
  preferences   JSON NULL,
  spice_level   DECIMAL(3,2) NULL,
  notes         VARCHAR(500) NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_member_household FOREIGN KEY (household_id) REFERENCES households(id)
);

CREATE TABLE profiles (
  user_id               BIGINT UNSIGNED PRIMARY KEY,
  favorite_cuisines     JSON NULL,
  favorite_dishes       JSON NULL,
  liked_ingredients     JSON NULL,
  disliked_ingredients  JSON NULL,
  frequent_dishes       JSON NULL,
  recent_dishes         JSON NULL,
  spice_level           DECIMAL(3,2) NOT NULL DEFAULT 0.50,
  oil_preference        VARCHAR(40) NULL,
  salt_preference       VARCHAR(40) NULL,
  nutrition_targets     JSON NULL,
  budget_preferences    JSON NULL,
  exploration_level     DECIMAL(3,2) NOT NULL DEFAULT 0.40,
  cooking_skill         VARCHAR(20) NOT NULL DEFAULT 'intermediate',
  equipment             JSON NULL,
  food_preferences      JSON NULL,
  recommendation_memory JSON NULL,
  updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE ingredients (
  id               BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  canonical_name   VARCHAR(160) NOT NULL,
  scientific_name  VARCHAR(160) NULL,
  category         VARCHAR(80) NULL,
  sub_category     VARCHAR(80) NULL,
  aliases          JSON NULL,
  translations     JSON NULL,
  vegetarian       TINYINT(1) NOT NULL DEFAULT 1,
  vegan            TINYINT(1) NOT NULL DEFAULT 1,
  contains_egg     TINYINT(1) NOT NULL DEFAULT 0,
  contains_dairy   TINYINT(1) NOT NULL DEFAULT 0,
  contains_gluten  TINYINT(1) NOT NULL DEFAULT 0,
  contains_alcohol TINYINT(1) NOT NULL DEFAULT 0,
  contains_nuts    TINYINT(1) NOT NULL DEFAULT 0,
  animal_derived   TINYINT(1) NOT NULL DEFAULT 0,
  halal_status     VARCHAR(24) NOT NULL DEFAULT 'unknown',
  kosher_status    VARCHAR(24) NOT NULL DEFAULT 'unknown',
  jain_status      VARCHAR(24) NOT NULL DEFAULT 'unknown',
  satvik_status    VARCHAR(24) NOT NULL DEFAULT 'unknown',
  allergens        JSON NULL,
  nutrition_data   JSON NULL,
  source           VARCHAR(40) NULL,
  source_id        VARCHAR(80) NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_ingredient_name (canonical_name)
);

CREATE TABLE recipes (
  id                  BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  owner_user_id       BIGINT UNSIGNED NULL,
  canonical_name      VARCHAR(200) NOT NULL,
  country             VARCHAR(80) NULL,
  region              VARCHAR(80) NULL,
  cuisine             VARCHAR(80) NULL,
  dish_type           VARCHAR(40) NULL,
  ingredients_json    JSON NOT NULL,
  steps_json          JSON NOT NULL,
  nutrition_json      JSON NULL,
  equipment_json      JSON NULL,
  substitutions_json  JSON NULL,
  diet_tags           JSON NULL,
  allergens           JSON NULL,
  difficulty          VARCHAR(20) NOT NULL DEFAULT 'easy',
  servings            INT NOT NULL DEFAULT 2,
  prep_minutes        INT NOT NULL DEFAULT 10,
  cook_minutes        INT NOT NULL DEFAULT 20,
  source_type         VARCHAR(40) NOT NULL DEFAULT 'canonical',
  source_id           VARCHAR(80) NULL,
  source_url          VARCHAR(500) NULL,
  confidence          DECIMAL(4,3) NOT NULL DEFAULT 0.800,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_cuisine (cuisine),
  KEY idx_country (country),
  KEY idx_recipe_owner (owner_user_id),
  CONSTRAINT fk_recipe_owner FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE pantry (
  id             BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id        BIGINT UNSIGNED NOT NULL,
  household_id   BIGINT UNSIGNED NULL,
  ingredient_id  BIGINT UNSIGNED NOT NULL,
  quantity       DECIMAL(12,3) NOT NULL DEFAULT 0,
  unit           VARCHAR(20) NOT NULL DEFAULT 'g',
  expires_at     DATE NULL,
  estimated_cost DECIMAL(12,2) NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_pantry_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_pantry_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
);

CREATE TABLE food_events (
  id            BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id       BIGINT UNSIGNED NOT NULL,
  household_id  BIGINT UNSIGNED NULL,
  event_type    VARCHAR(32) NOT NULL,
  occurred_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reference_id  BIGINT UNSIGNED NULL,
  calories      DECIMAL(10,2) NULL,
  protein_g     DECIMAL(10,2) NULL,
  carbs_g       DECIMAL(10,2) NULL,
  fat_g         DECIMAL(10,2) NULL,
  amount        DECIMAL(12,2) NULL,
  currency      CHAR(3) NULL,
  data_json     JSON NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_events_user_time (user_id, occurred_at),
  CONSTRAINT fk_event_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE conversations (
  id            BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id       BIGINT UNSIGNED NOT NULL,
  household_id  BIGINT UNSIGNED NULL,
  type          VARCHAR(40) NOT NULL DEFAULT 'chat',
  title         VARCHAR(200) NULL,
  messages_json JSON NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_conv_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE cooking_sessions (
  id           BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id      BIGINT UNSIGNED NOT NULL,
  recipe_id    BIGINT UNSIGNED NOT NULL,
  current_step INT NOT NULL DEFAULT 1,
  status       VARCHAR(24) NOT NULL DEFAULT 'active',
  started_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  state_json   JSON NULL,
  CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_session_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(id)
);

CREATE TABLE shopping_lists (
  id              BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id         BIGINT UNSIGNED NOT NULL,
  household_id    BIGINT UNSIGNED NULL,
  recipe_id       BIGINT UNSIGNED NULL,
  items_json      JSON NOT NULL,
  estimated_total DECIMAL(12,2) NULL,
  actual_total    DECIMAL(12,2) NULL,
  status          VARCHAR(24) NOT NULL DEFAULT 'open',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at    DATETIME NULL,
  CONSTRAINT fk_shop_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE merchants (
  id         BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  name       VARCHAR(160) NOT NULL,
  country    CHAR(2) NOT NULL DEFAULT 'IN',
  city       VARCHAR(80) NULL,
  latitude   DECIMAL(9,6) NULL,
  longitude  DECIMAL(9,6) NULL,
  website    VARCHAR(255) NULL,
  type       VARCHAR(40) NOT NULL DEFAULT 'grocery',
  verified   TINYINT(1) NOT NULL DEFAULT 0
);

CREATE TABLE merchant_offers (
  id                 BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  merchant_id        BIGINT UNSIGNED NOT NULL,
  ingredient_id      BIGINT UNSIGNED NULL,
  product_name       VARCHAR(200) NOT NULL,
  price              DECIMAL(12,2) NOT NULL,
  currency           CHAR(3) NOT NULL DEFAULT 'INR',
  stock_status       VARCHAR(24) NOT NULL DEFAULT 'in_stock',
  delivery_available TINYINT(1) NOT NULL DEFAULT 1,
  campaign_id        VARCHAR(64) NULL,
  bid_amount         DECIMAL(12,2) NULL,
  start_at           DATETIME NULL,
  end_at             DATETIME NULL,
  sponsored          TINYINT(1) NOT NULL DEFAULT 0,
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_offer_merchant FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);

CREATE TABLE media_assets (
  id               BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id          BIGINT UNSIGNED NOT NULL,
  type             VARCHAR(20) NOT NULL,
  storage_key      VARCHAR(255) NOT NULL,
  mime_type        VARCHAR(80) NULL,
  purpose          VARCHAR(40) NULL,
  consent          TINYINT(1) NOT NULL DEFAULT 0,
  retention_policy VARCHAR(40) NOT NULL DEFAULT 'explicit',
  expires_at       DATETIME NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_media_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE ai_usage (
  id             BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id        BIGINT UNSIGNED NULL,
  provider       VARCHAR(40) NOT NULL,
  model          VARCHAR(80) NOT NULL,
  task           VARCHAR(80) NOT NULL,
  input_tokens   INT NOT NULL DEFAULT 0,
  output_tokens  INT NOT NULL DEFAULT 0,
  duration_ms    INT NOT NULL DEFAULT 0,
  estimated_cost DECIMAL(12,6) NOT NULL DEFAULT 0,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_usage_user (user_id, created_at)
);
