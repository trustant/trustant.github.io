// Mobile navigation. The menu is a plain anchor list, so the page stays
// usable without JavaScript; this only adds the collapsible behaviour.
function handleMobileNav() {
  const mobileToggle = document.querySelector("[data-mobile-toggle]");
  const navigation = document.querySelector("[data-navigation]");

  if (!mobileToggle || !navigation) return;

  const setOpen = (open) => {
    navigation.classList.toggle("open", open);
    mobileToggle.classList.toggle("active", open);
    mobileToggle.setAttribute("aria-expanded", String(open));
    mobileToggle.setAttribute("aria-label", open ? "Hide menu" : "Show menu");
  };

  setOpen(false);

  mobileToggle.addEventListener("click", () => {
    setOpen(!navigation.classList.contains("open"));
  });

  // Close once a section is selected.
  navigation.addEventListener("click", (event) => {
    if (event.target.closest("a")) setOpen(false);
  });

  // Close on Escape, returning focus to the toggle.
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navigation.classList.contains("open")) {
      setOpen(false);
      mobileToggle.focus();
    }
  });

  document.documentElement.addEventListener("click", (event) => {
    if (!mobileToggle.contains(event.target) && !navigation.contains(event.target)) {
      setOpen(false);
    }
  });
}

// The motto composes one message at a time: type it, hold it, erase it, move
// on. The messages come out of the markup rather than being repeated here, so
// the no-JS list stays the single source of the copy.
function handleMotto() {
  const TYPE = 45;
  const ERASE = 25;
  const HOLD = 2200;
  const GAP = 400;

  const motto = document.getElementById("motto");
  const list = document.getElementById("motto-list");
  if (!motto || !list) return;

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const messages = [...list.children].map((item) => item.textContent.trim());
  if (!messages.length) return;

  // The animated line is hidden from assistive tech — a half-composed string is
  // noise to a screen reader — and the full list stays in the DOM, visually
  // hidden, as the accessible copy.
  list.classList.remove("motto-list");
  list.classList.add("visually-hidden");

  const line = document.createElement("span");
  line.className = "motto-line";
  line.setAttribute("aria-hidden", "true");

  const text = document.createTextNode("");
  const caret = document.createElement("span");
  caret.className = "motto-caret";
  line.append(text, caret);
  motto.insertBefore(line, list);

  let index = 0;
  let count = 0;
  let erasing = false;
  let timer = null;

  const step = () => {
    const message = messages[index];
    let wait;

    if (!erasing) {
      count += 1;
      text.nodeValue = message.slice(0, count);
      if (count === message.length) {
        erasing = true;
        wait = HOLD;
      } else {
        wait = TYPE;
      }
    } else {
      count -= 1;
      text.nodeValue = message.slice(0, count);
      if (count === 0) {
        erasing = false;
        index = (index + 1) % messages.length;
        wait = GAP;
      } else {
        wait = ERASE;
      }
    }

    timer = setTimeout(step, wait);
  };

  const play = () => {
    if (timer === null) timer = setTimeout(step, GAP);
  };

  const pause = () => {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
  };

  // Don't type into a backgrounded tab.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause();
    else play();
  });

  play();
}

// Every template sits in one horizontal rail. The strip above it is a
// convenience: clicking an entry scrolls the rail to that group's first card,
// and the entry for whichever group is currently in view is marked.
function handleTemplateNav() {
  const rail = document.getElementById("template-rail");
  const links = [...document.querySelectorAll(".template-tab")];
  const anchors = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if (!rail || links.length !== anchors.length || !anchors.length) return;

  const mark = (index) => {
    links.forEach((link, i) => {
      link.classList.toggle("is-current", i === index);
      if (i === index) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
  };

  // Scroll the rail itself rather than letting the browser jump the page to
  // an element inside a horizontally scrolling container.
  links.forEach((link, i) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      rail.scrollTo({
        left: anchors[i].offsetLeft - rail.offsetLeft,
        behavior: "smooth",
      });
      mark(i);
    });
  });

  // Track which group the rail is showing as it is scrolled by hand. The
  // leading edge is measured a little into the view so a group counts as
  // current once its first card is properly on screen, not as it grazes it.
  const current = () => {
    const edge = rail.scrollLeft + 24;
    let index = 0;
    anchors.forEach((anchor, i) => {
      if (anchor.offsetLeft - rail.offsetLeft <= edge) index = i;
    });

    // At the far end the rail cannot scroll any further, so the last group
    // would never become current on its own.
    if (rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 8) {
      index = anchors.length - 1;
    }
    return index;
  };

  let pending = false;
  rail.addEventListener("scroll", () => {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(() => {
      pending = false;
      mark(current());
    });
  });

  mark(0);
}

// The pricing buttons each open a panel: the download chooser, the buy form
// and the sales enquiry. <dialog> brings the focus trap, Escape and the inert
// backdrop, so this only wires up opening, closing and the form submits.
function handlePanelDialogs() {
  const open = (dialog) => {
    if (!dialog || typeof dialog.showModal !== "function") return;

    // The framed page is only fetched when it is actually wanted, so the
    // external request is not made on every page load.
    const frame = dialog.querySelector("iframe[data-src]");
    if (frame && !frame.src) frame.src = frame.dataset.src;

    dialog.showModal();
  };

  document.querySelectorAll("[data-open-dialog]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      open(document.getElementById(trigger.dataset.openDialog));
    });
  });

  document.querySelectorAll(".panel-dialog").forEach((dialog) => {
    dialog.querySelectorAll("[data-close-dialog]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });

    // A click on the backdrop lands on the dialog itself, never its contents.
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  // Payment is not connected yet. Say so plainly rather than collecting
  // details that go nowhere.
  document.querySelector("[data-buy-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    window.alert("stripe integration to be implemented");
    document.getElementById("buy-dialog").close();
  });

  document.querySelector("[data-contact-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    window.alert("Thank you. Sales contact handling is not connected yet.");
    document.getElementById("contact-dialog").close();
  });
}

// A deliberately slow glide to a section, for the nav links marked
// [data-slow-scroll]. Native smooth scrolling is both faster than we want here
// and not tunable, so the travel is animated by hand over a fixed duration.
//
// Only in-page targets are handled: a link pointing at another page keeps its
// normal behaviour and the browser navigates, arriving at the fragment as
// usual.
function handleSlowScroll() {
  const DURATION = 2400;

  // The bar floats over the content 24px from the top, so a section scrolled
  // to y=0 would sit underneath it.
  const OFFSET = 104;

  // A gentle ease in and out: no lurch at either end of a long travel.
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

  document.querySelectorAll("[data-slow-scroll]").forEach((link) => {
    link.addEventListener("click", (event) => {
      // The href is absolute (/#credits) so it works from any page; only take
      // it over when the fragment names something on this one.
      const hash = link.hash;
      if (!hash) return;

      const target = document.getElementById(hash.slice(1));
      if (!target) return;

      // Same-page only: let a link from /documentation/ navigate home.
      if (link.pathname !== window.location.pathname) return;

      event.preventDefault();

      const start = window.scrollY;
      const end = Math.max(
        0,
        Math.min(
          target.getBoundingClientRect().top + start - OFFSET,
          document.documentElement.scrollHeight - window.innerHeight,
        ),
      );
      const distance = end - start;

      // Put the fragment in the address bar either way, so the position is
      // shareable and Back behaves as it would have.
      const settle = () => {
        if (history.replaceState) history.replaceState(null, "", hash);
        else window.location.hash = hash;
      };

      if (reduced.matches || !distance) {
        window.scrollTo(0, end);
        settle();
        return;
      }

      const began = performance.now();

      const step = (now) => {
        const progress = Math.min((now - began) / DURATION, 1);
        window.scrollTo(0, start + distance * ease(progress));
        if (progress < 1) window.requestAnimationFrame(step);
        else settle();
      };

      window.requestAnimationFrame(step);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  handleMobileNav();
  handleMotto();
  handleTemplateNav();
  handlePanelDialogs();
  handleSlowScroll();
});
