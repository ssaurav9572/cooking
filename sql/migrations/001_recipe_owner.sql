-- Apply once to an existing CookAI database to support private user imports.
ALTER TABLE recipes
  ADD COLUMN owner_user_id BIGINT UNSIGNED NULL AFTER id,
  ADD COLUMN servings INT NOT NULL DEFAULT 2 AFTER difficulty,
  ADD KEY idx_recipe_owner (owner_user_id),
  ADD CONSTRAINT fk_recipe_owner FOREIGN KEY (owner_user_id) REFERENCES users(id);
