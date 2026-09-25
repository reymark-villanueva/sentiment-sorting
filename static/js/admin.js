/**
 * Isabela State University - Cauayan Campus Library
 * Admin Sentiment Monitoring Console Controller (Vanilla JS)
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile & Tablet Sidebar Toggle
  const btnToggleSidebar = document.getElementById('btnToggleSidebar');
  const sidebar = document.getElementById('adminSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  if (btnToggleSidebar && sidebar) {
    btnToggleSidebar.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (backdrop) backdrop.classList.toggle('open');
    });
  }

  if (backdrop && sidebar) {
    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('open');
      backdrop.classList.remove('open');
    });
  }

  // The date-range tabs and Export Report button are plain server-rendered
  // links (see admin/dashboard.html) and need no JS.

  // 2. Sidebar scrollspy — Sentiment Dashboard / Service Insights / Feedback Logs
  // all point into sections of this one page, so the "active" highlight (normally
  // server-rendered per-page) has to be kept in sync client-side as the user
  // scrolls or clicks between them.
  const spyLinks = Array.from(document.querySelectorAll('.isu-nav-item[data-section-target]'));
  if (spyLinks.length) {
    const sections = spyLinks
      .map((link) => document.getElementById(link.dataset.sectionTarget))
      .filter(Boolean);

    function setActive(targetId) {
      spyLinks.forEach((link) => {
        link.classList.toggle('active', link.dataset.sectionTarget === targetId);
      });
    }

    // Instant feedback on click — don't wait for the scroll/observer to catch up.
    spyLinks.forEach((link) => {
      link.addEventListener('click', () => setActive(link.dataset.sectionTarget));
    });

    if (sections.length && 'IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          // Prefer the topmost section currently intersecting the "active" band,
          // so scrolling past a short section doesn't skip its highlight.
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
          if (visible.length) setActive(visible[0].target.id);
        },
        { rootMargin: '-96px 0px -70% 0px', threshold: 0 }
      );
      sections.forEach((section) => observer.observe(section));
    }
  }
});
