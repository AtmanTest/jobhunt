/* ==========================================================================
   Comportements du site : apparition au défilement, jauge de lecture,
   coloration Gherkin, compteurs animés, boutons de copie.
   Aucune dépendance externe.
   ========================================================================= */
(function () {
  "use strict";

  // 1. Apparition progressive des blocs
  var cibles = document.querySelectorAll(".vu, .sec, .carte, .chiffre, .cas, .anomalie");
  cibles.forEach(function (el) { el.classList.add("vu"); });
  if ("IntersectionObserver" in window) {
    var obs = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("on"); obs.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
    cibles.forEach(function (el) { obs.observe(el); });
  } else {
    cibles.forEach(function (el) { el.classList.add("on"); });
  }

  // 2. Jauge de lecture dans l'en-tête
  var jauge = document.querySelector(".jauge");
  if (jauge) {
    var maj = function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      jauge.style.width = (h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0) + "%";
    };
    window.addEventListener("scroll", maj, { passive: true });
    window.addEventListener("resize", maj);
    maj();
  }

  // 3. Coloration des scénarios Gherkin
  var MOTS = {
    "Fonctionnalité": "bal", "Fonctionnalite": "bal", "Feature": "bal", "Règle": "bal", "Regle": "bal",
    "Contexte": "fct", "Scénario": "fct", "Scenario": "fct", "Plan du scénario": "fct",
    "Exemples": "fct", "Examples": "fct", "Et": "att", "Mais": "att",
    "Soit": "don", "Étant donné": "don", "Etant donne": "don", "Etant donné": "don",
    "Quand": "don", "Lorsque": "don", "Alors": "att", "Then": "att", "When": "don", "Given": "don", "And": "att"
  };
  var cles = Object.keys(MOTS).sort(function (a, b) { return b.length - a.length; });
  var motif = new RegExp("^\\s*(?:" + cles.map(function (k) { return k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")\\b");
  document.querySelectorAll("pre.gherkin").forEach(function (bloc) {
    var brut = bloc.textContent;
    var sortie = brut.split("\n").map(function (ligne) {
      var t = ligne.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (/^\s*#/.test(ligne)) { return '<span class="bal">' + t + "</span>"; }
      var m = ligne.match(motif);
      if (!m) { return '<span class="txt">' + t + "</span>"; }
      var cle = m[0];
      var classe = MOTS[cle.trim()] || "fct";
      var suite = t.slice(cle.length);
      return '<span class="cle"><span class="' + classe + '">' + cle +
             '</span></span><span class="txt">' + suite + "</span>";
    }).join("\n");
    bloc.innerHTML = sortie;
  });

  // 4. Compteurs animés sur les chiffres clés
  document.querySelectorAll(".chiffre .valeur").forEach(function (el) {
    var texte = el.textContent.trim();
    var nombre = parseFloat(texte.replace(",", ".").replace(/[^\d.]/g, ""));
    if (!isFinite(nombre) || nombre === 0) { return; }
    var suffixe = texte.replace(/[\d.,\s]/g, "");
    var depart = performance.now();
    var duree = 900;
    var pas = function (t) {
      var p = Math.min(1, (t - depart) / duree);
      var v = nombre * (1 - Math.pow(1 - p, 3));
      el.textContent = (nombre % 1 === 0 ? Math.round(v) : v.toFixed(1)).toLocaleString("fr-FR") + suffixe;
      if (p < 1) { requestAnimationFrame(pas); } else { el.textContent = texte; }
    };
    requestAnimationFrame(pas);
  });

  // 5. Boutons de copie dans les blocs de code
  document.querySelectorAll(".bloc-code .barre").forEach(function (barre) {
    var pre = barre.parentElement.querySelector("pre");
    if (!pre) { return; }
    var zone = barre.querySelector(".droite") || barre;
    var bouton = document.createElement("button");
    bouton.className = "copier";
    bouton.type = "button";
    bouton.textContent = "copier";
    bouton.addEventListener("click", function () {
      navigator.clipboard.writeText(pre.innerText).then(function () {
        bouton.textContent = "copié ✓";
        setTimeout(function () { bouton.textContent = "copier"; }, 1600);
      });
    });
    zone.appendChild(bouton);
  });

  // 6. Coloration Python / diff / shell, sans dépendance : mots-clés et chaînes
  var MOTS_PY = /\b(def|return|class|import|from|for|in|if|elif|else|while|try|except|finally|with|as|and|or|not|None|True|False|lambda|raise|assert|yield|pass|continue|break|global|await|async)\b/g;
  document.querySelectorAll("pre.python").forEach(function (bloc) {
    var t = bloc.textContent.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    t = t.replace(/(&quot;|")([^"\n]*)(&quot;|")/g, '<span class="fct">"$2"</span>');
    t = t.replace(/(#[^\n]*)/g, '<span class="bal">$1</span>');
    t = t.replace(MOTS_PY, '<span class="cle">$1</span>');
    t = t.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="don">$1</span>');
    bloc.innerHTML = t;
  });
})();
