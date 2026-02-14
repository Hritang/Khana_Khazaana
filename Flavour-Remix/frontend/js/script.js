/* ================================
   SCROLL FUNCTION
================================ */

function scrollToProblem() {

  const section = document.getElementById("problem");

  if(section) {
    section.scrollIntoView({
      behavior: "smooth"
    });
  }

}


/* ================================
   PAGE LOAD EVENTS
================================ */

window.addEventListener("load", function() {

  /* Hero image pop-up animation */

  const heroImage = document.getElementById("heroImage");

  if(heroImage) {

    setTimeout(function() {

      heroImage.classList.add("show");

    }, 300);

  }


  /* Reveal animations */

  revealCards(".problem-card");

  revealCards(".solution-card");

  revealCards(".how-step");

  const startBtn = document.querySelector(".start-btn");
  if (startBtn) {
    startBtn.addEventListener("click", function() {
      window.location.href = "dashboard.html";
    });
  }

});


/* ================================
   REVEAL ANIMATION FUNCTION
================================ */

function revealCards(selector) {

  const elements = document.querySelectorAll(selector);

  if(elements.length === 0) return;


  const observer = new IntersectionObserver(function(entries) {

    entries.forEach(function(entry) {

      if(entry.isIntersecting) {

        entry.target.classList.add("show");

      }

    });

  }, {
    threshold: 0.2
  });


  elements.forEach(function(element) {

    observer.observe(element);

  });

}


/* ================================
   OPTIONAL: NAVBAR SCROLL ACTIVE
================================ */

window.addEventListener("scroll", function() {

  const navbar = document.querySelector(".navbar");

  if(!navbar) return;

  if(window.scrollY > 50) {

    navbar.style.background = "rgba(255,255,255,0.4)";
    navbar.style.backdropFilter = "blur(10px)";

  }
  else {

    navbar.style.background = "transparent";

  }

});
