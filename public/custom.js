(function () {
  // The welcome screen: logo and name side by side, with a handwritten line
  // under them saying what the data is, in the landing page's voice.
  function decorateWelcome() {
    var logo = document.querySelector(".welcome-screen .logo");
    if (!logo || logo.dataset.labeled) return;
    logo.dataset.labeled = "true";

    var wrapper = document.createElement("div");
    wrapper.className = "brand-lockup";
    logo.parentNode.insertBefore(wrapper, logo);
    wrapper.appendChild(logo);

    var name = document.createElement("h1");
    name.className = "brand-lockup-text";
    name.textContent = "Ask Cortex Analyst";
    wrapper.appendChild(name);

    var sub = document.createElement("p");
    sub.className = "brand-sub";
    sub.textContent = "ask about a made-up SaaS company's MRR, churn and cohorts. it shows you the SQL.";
    wrapper.parentNode.insertBefore(sub, wrapper.nextSibling);
  }

  // Chainlit renders on the client and remounts the welcome screen on every
  // new chat, so keep watching instead of running once on load.
  var observer = new MutationObserver(decorateWelcome);
  observer.observe(document.body, { childList: true, subtree: true });
  decorateWelcome();
})();
