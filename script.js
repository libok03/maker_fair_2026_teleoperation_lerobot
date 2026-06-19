const counters = document.querySelectorAll("[data-target]");

const animateCounter = (counter) => {
  const target = Number(counter.dataset.target);
  let current = 0;
  const step = Math.max(1, Math.round(target / 36));

  const tick = () => {
    current = Math.min(target, current + step);
    counter.textContent = current;
    if (current < target) {
      requestAnimationFrame(tick);
    }
  };

  tick();
};

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.5 }
);

counters.forEach((counter) => observer.observe(counter));
