/* ISU Cauayan Library Feedback System — landing page interactions. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  /* ---------- Header: scrolled state + mobile menu ---------- */
  var header = document.querySelector('[data-header]');
  var menuBtn = document.querySelector('[data-menu-toggle]');

  if (header) {
    var onScroll = function () {
      header.classList.toggle('is-scrolled', window.scrollY > 8);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  if (header && menuBtn) {
    var setMenu = function (open) {
      header.classList.toggle('is-open', open);
      menuBtn.setAttribute('aria-expanded', String(open));
    };

    menuBtn.addEventListener('click', function () {
      setMenu(menuBtn.getAttribute('aria-expanded') !== 'true');
    });

    // Close after choosing a link, on Escape, or when resizing up to desktop.
    document.getElementById('lp-menu').addEventListener('click', function (e) {
      if (e.target.closest('a')) setMenu(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && header.classList.contains('is-open')) {
        setMenu(false);
        menuBtn.focus();
      }
    });
    window.matchMedia('(min-width: 768px)').addEventListener('change', function (e) {
      if (e.matches) setMenu(false);
    });
  }

  /* ---------- FAQ accordion: one item open at a time ---------- */
  var accordion = document.querySelector('[data-accordion]');
  if (accordion) {
    var faqBtns = accordion.querySelectorAll('.lp-faq-btn');

    var setItem = function (btn, open) {
      btn.setAttribute('aria-expanded', String(open));
      document.getElementById(btn.getAttribute('aria-controls')).hidden = !open;
    };

    faqBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var willOpen = btn.getAttribute('aria-expanded') !== 'true';
        faqBtns.forEach(function (other) { setItem(other, false); });
        if (willOpen) setItem(btn, true);
      });
    });
  }

  /* ---------- Scroll reveal ----------
     Only elements that start below the fold are hidden, so nothing that is
     already on screen flashes, and content stays visible without JS. */
  if (!reduceMotion.matches && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        el.classList.add('lp-reveal-in');
        el.classList.remove('lp-reveal-pending');
        observer.unobserve(el);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.08 });

    document.querySelectorAll('[data-reveal]').forEach(function (el) {
      if (el.getBoundingClientRect().top > window.innerHeight) {
        el.classList.add('lp-reveal-pending');
        observer.observe(el);
      }
    });
  }
})();
