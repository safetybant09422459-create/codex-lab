var screens = [
  { id: "jarvis-screen", hash: "jarvis" },
  { id: "travel-screen", hash: "travel" },
  { id: "photo-screen", hash: "photo" },
  { id: "garden-screen", hash: "garden" },
  { id: "calendar-screen", hash: "calendar" },
  { id: "home-screen", hash: "home" },
  { id: "developer-screen", hash: "developer" },
];

var screenHashMap = {};
var hashScreenMap = {};
var shellNavigationBound = false;

screens.forEach(function (screen) {
  screenHashMap[screen.id] = screen.hash;
  hashScreenMap[screen.hash] = screen.id;
  hashScreenMap[screen.id] = screen.id;
});

function resolveScreenId() {
  var hash = window.location.hash.replace("#", "");
  var queryIndex = hash.indexOf("?");

  if (queryIndex !== -1) {
    hash = hash.slice(0, queryIndex);
  }
  return hashScreenMap[hash] || "jarvis-screen";
}

function showScreen(screenId, shouldUpdateHash) {
  var screen = document.getElementById(screenId);
  var buttons;
  var screenItems;
  var index;
  var button;
  var item;
  var isActive;

  if (!screen) {
    return;
  }

  buttons = document.querySelectorAll(".shell-nav-button");
  for (index = 0; index < buttons.length; index += 1) {
    button = buttons[index];
    isActive = button.getAttribute("data-screen") === screenId;
    if (isActive) {
      button.classList.add("active");
      button.setAttribute("aria-current", "page");
    } else {
      button.classList.remove("active");
      button.removeAttribute("aria-current");
    }
  }

  screenItems = document.querySelectorAll(".shell-screen");
  for (index = 0; index < screenItems.length; index += 1) {
    item = screenItems[index];
    isActive = item.id === screenId;
    if (isActive) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
    item.hidden = !isActive;
  }

  if (shouldUpdateHash !== false) {
    var screenHash = screenHashMap[screenId];
    if (screenHash) {
      window.history.replaceState(null, "", "#" + screenHash);
    }
  }
}

export function bindShellNavigation() {
  var buttons;
  var index;
  var button;

  if (shellNavigationBound) {
    return;
  }
  shellNavigationBound = true;

  buttons = document.querySelectorAll(".shell-nav-button");
  for (index = 0; index < buttons.length; index += 1) {
    button = buttons[index];
    button.addEventListener("click", function () {
      showScreen(this.getAttribute("data-screen"));
    });
  }

  showScreen(resolveScreenId(), false);
  window.addEventListener("hashchange", function () {
    showScreen(resolveScreenId(), false);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindShellNavigation);
} else {
  bindShellNavigation();
}
