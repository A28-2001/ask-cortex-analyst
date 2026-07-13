(function () {
  function addBrandLabel() {
    var logo = document.querySelector(".welcome-screen .logo");
    if (!logo || logo.dataset.labeled) return;
    logo.dataset.labeled = "true";

    var wrapper = document.createElement("div");
    wrapper.className = "brand-lockup";
    logo.parentNode.insertBefore(wrapper, logo);
    wrapper.appendChild(logo);

    var label = document.createElement("div");
    label.className = "brand-lockup-text";
    label.textContent = "Ask Cortex Analyst";
    wrapper.appendChild(label);
  }

  // Chainlit is a client-rendered SPA -- the welcome screen mounts async,
  // so watch for it rather than relying on a single DOMContentLoaded pass.
  var observer = new MutationObserver(addBrandLabel);
  observer.observe(document.body, { childList: true, subtree: true });
  addBrandLabel();
})();
