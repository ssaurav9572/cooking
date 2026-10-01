# Decision architecture

The import flow uses Jev's typed-decision pattern while leaving data parsing and actions under CookAI's control.

1. **Build small state:** the optional Jev request receives a maximum 4,500-character excerpt and parser facts: title presence, ingredient and step counts, and missing-quantity count. It does not receive profile, pantry, household or conversation data.
2. **Ask independent typed questions in one request:** `content_kind` is a choice (`recipe`, `not_a_recipe`, `unclear`), `completeness` is a 0–3 ordered score, and `needs_review` is a yes/no probability.
3. **Apply app policy:** parsing and minimum-field validation run locally. A high-confidence `not_a_recipe` signal can only add a warning; it cannot discard a structurally valid recipe. Missing title, ingredients or steps blocks saving.
4. **Require review:** every import preview must be reviewed and explicitly confirmed before commit. Jev never writes to the recipe collection.
5. **Degrade locally:** without `JEV_API_KEY`, or if the service call fails, a deterministic checker returns the same typed answer shape. Its choice confidence is deliberately capped below the Jev review-warning threshold; its values are rule signals, not calibrated Jev confidence. Jev is never used for diet, allergy, nutrition, cost or authorization decisions.

The 0.75 threshold applies only to adding a stronger “this may not be a recipe” review warning. It is not an acceptance threshold. Confidence is a signal, not a correctness guarantee.
