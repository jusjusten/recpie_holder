// set environment
// & "C:\Users\Ginod\OneDrive\Desktop\Personal Projects\Recipe Sorter\.venv\Scripts\Activate.ps1"
// run app
// python app.py

// test import (get ingredient and steps)
// $body = @{ url = "https://www.bbcgoodfood.com/recipes/easy-pancakes"; user_id = "test-user" } | ConvertTo-Json
// Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/recipes/import" -ContentType "application/json" -Body $body

// works for bbc good food


const storageKey = "recipe-sorter-user";

const loginForm = document.getElementById("login-form");
const userIdInput = document.getElementById("user-id");
const currentUser = document.getElementById("current-user");
const signOutButton = document.getElementById("sign-out");
const importForm = document.getElementById("import-form");
const recipeUrlInput = document.getElementById("recipe-url");
const importStatus = document.getElementById("import-status");
const recipesContainer = document.getElementById("recipes");

function getUserId() {
  return window.localStorage.getItem(storageKey) || "";
}

function setUserId(userId) {
  window.localStorage.setItem(storageKey, userId);
}

function clearUserId() {
  window.localStorage.removeItem(storageKey);
}

function redirectTo(path) {
  window.location.href = path;
}

async function fetchRecipes(userId) {
  const response = await fetch(`/users/${encodeURIComponent(userId)}/recipes`);
  if (!response.ok) {
    throw new Error("Failed to load recipes");
  }
  return response.json();
}

function renderRecipes(recipes) {
  recipesContainer.innerHTML = "";
  if (!recipes.length) {
    recipesContainer.innerHTML = "<p class=\"muted\">No recipes yet. Import one above.</p>";
    return;
  }
  recipes.forEach((recipe) => {
    const card = document.createElement("article");
    card.className = "recipe-card";
    card.innerHTML = `
      <h3>${recipe.title}</h3>
      <p class="muted">${recipe.total_time ? `${recipe.total_time} min` : "Time not listed"}</p>
      <div class="columns">
        <div>
          <h4>Ingredients</h4>
          <ul>
            ${(recipe.ingredients || []).map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </div>
        <div>
          <h4>Steps</h4>
          <ol>
            ${(recipe.steps || []).map((step) => `<li>${step}</li>`).join("")}
          </ol>
        </div>
      </div>
    `;
    recipesContainer.appendChild(card);
  });
}

async function loadDashboard() {
  const userId = getUserId();
  if (!userId) {
    redirectTo("/");
    return;
  }
  currentUser.textContent = `Signed in as ${userId}`;
  try {
    const recipes = await fetchRecipes(userId);
    renderRecipes(recipes);
  } catch (error) {
    recipesContainer.innerHTML = "<p class=\"error\">Unable to load recipes.</p>";
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const userId = userIdInput.value.trim();
    if (!userId) {
      return;
    }
    setUserId(userId);
    redirectTo("/dashboard");
  });
}

if (signOutButton) {
  signOutButton.addEventListener("click", () => {
    clearUserId();
    redirectTo("/");
  });
}

if (importForm) {
  importForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    importStatus.textContent = "";
    importStatus.classList.remove("error");
    const userId = getUserId();
    const url = recipeUrlInput.value.trim();
    if (!userId || !url) {
      return;
    }
    importStatus.textContent = "Importing...";
    try {
      const response = await fetch("/recipes/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, user_id: userId }),
      });
      const data = await response.json();
      if (!response.ok) {
        const message = data.details
          ? `${data.error || "Failed to import recipe"}: ${data.details}`
          : data.error || "Failed to import recipe";
        throw new Error(message);
      }
      importStatus.textContent = "Recipe imported.";
      recipeUrlInput.value = "";
      const recipes = await fetchRecipes(userId);
      renderRecipes(recipes);
    } catch (error) {
      importStatus.textContent = error.message;
      importStatus.classList.add("error");
    }
  });
}

if (currentUser) {
  loadDashboard();
}
