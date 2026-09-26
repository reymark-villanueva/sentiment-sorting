/**
 * Isabela State University - Cauayan Campus Library
 * Multi-Step Feedback Form Controller (Vanilla JS)
 *
 * Text-only by design: this system classifies sentiment purely from the
 * written comment, so there's no star rating or demographic step here.
 */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('isuFeedbackForm');
  if (!form) return;

  // State — nothing is pre-selected; the user must actively choose each field.
  let currentStep = 1;
  const totalSteps = 3;
  let selectedServiceId = '';
  let selectedServiceName = '';

  // Elements
  const stepPanels = document.querySelectorAll('.isu-form-step-panel');
  const stepItems = document.querySelectorAll('.isu-step-item');
  const stepLines = document.querySelectorAll('.isu-step-line');
  const btnNext = document.getElementById('btnNextStep');
  const btnPrev = document.getElementById('btnPrevStep');
  const btnSubmit = document.getElementById('btnSubmitFeedback');
  const cancelLink = document.getElementById('btnCancelFeedback');

  // Hidden inputs for Django POST
  const inputService = document.getElementById('inputService');
  const inputComments = document.getElementById('inputComments');

  // Summary Elements
  const summaryService = document.getElementById('summaryService');
  const summaryComments = document.getElementById('summaryComments');
  const step2Subtitle = document.getElementById('step2Subtitle');

  // Quick Aspects data — 7 negative / 7 neutral / 7 positive phrases per
  // service (see feedback/aspects.py), keyed by service pk as a string.
  const aspectsDataEl = document.getElementById('service-aspects-data');
  let serviceAspects = {};
  if (aspectsDataEl) {
    try {
      serviceAspects = JSON.parse(aspectsDataEl.textContent) || {};
    } catch (err) {
      serviceAspects = {};
    }
  }

  const quickAspectsContainer = document.getElementById('quickAspectsContainer');

  function shuffle(array) {
    const result = array.slice();
    for (let i = result.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
  }

  function renderQuickAspects(serviceId) {
    if (!quickAspectsContainer) return;
    quickAspectsContainer.innerHTML = '';
    // Already a flat, server-shuffled list of {phrase, sentiment} objects
    // (see feedback/aspects.py) — shuffled again here so re-selecting the
    // same service mid-session doesn't always show the same order twice.
    const entries = serviceAspects[serviceId];
    if (!entries || !entries.length) return;

    shuffle(entries).forEach(({ phrase, sentiment }) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'isu-chip';
      chip.dataset.sentiment = sentiment;
      chip.textContent = phrase;
      quickAspectsContainer.appendChild(chip);
    });
  }

  // 1. Service Selection Handling
  const serviceCards = document.querySelectorAll('.isu-service-card');
  serviceCards.forEach(card => {
    card.addEventListener('click', () => {
      serviceCards.forEach(c => {
        c.classList.remove('selected');
        c.setAttribute('aria-pressed', 'false');
      });
      card.classList.add('selected');
      card.setAttribute('aria-pressed', 'true');
      selectedServiceId = card.getAttribute('data-service-id') || '';
      selectedServiceName = card.getAttribute('data-service-name') || '';
      if (inputService) inputService.value = selectedServiceId;
      renderQuickAspects(selectedServiceId);
      if (step2Subtitle) {
        step2Subtitle.textContent = selectedServiceName
          ? `Tell us about your experience with ${selectedServiceName}.`
          : 'Tell us about your experience.';
      }
      updateSummary();
    });
  });

  // 2. Quick Feedback Chips / Tags — delegated, since chips are re-rendered
  // per selected service rather than being fixed elements in the DOM.
  if (quickAspectsContainer) {
    quickAspectsContainer.addEventListener('click', (e) => {
      const chip = e.target.closest('.isu-chip');
      if (!chip) return;
      chip.classList.toggle('selected');
      const tagText = chip.innerText.trim();
      const textarea = document.getElementById('feedbackCommentsText');
      if (textarea && chip.classList.contains('selected') && !textarea.value.includes(tagText)) {
        textarea.value = textarea.value ? `${textarea.value.trim()}, ${tagText}` : tagText;
      }
      if (inputComments && textarea) inputComments.value = textarea.value;
      updateSummary();
    });
  }

  // Feedback textarea — the sole signal the sentiment model classifies
  const textarea = document.getElementById('feedbackCommentsText');
  if (textarea) {
    textarea.addEventListener('input', () => {
      if (inputComments) inputComments.value = textarea.value;
      updateSummary();
    });
  }

  function updateSummary() {
    if (summaryService) summaryService.innerText = selectedServiceName || 'Not selected';
    if (summaryComments) {
      const text = textarea ? textarea.value.trim() : '';
      summaryComments.innerText = text ? `"${text}"` : 'Not written yet.';
    }
  }

  // 3. Stepper Navigation
  function goToStep(step, { scroll = true } = {}) {
    if (step < 1 || step > totalSteps + 1) return;
    currentStep = step;

    stepPanels.forEach(panel => {
      const panelStep = parseInt(panel.getAttribute('data-step'), 10);
      panel.style.display = panelStep === currentStep ? 'block' : 'none';
    });

    stepItems.forEach(item => {
      const itemStep = parseInt(item.getAttribute('data-step'), 10);
      item.classList.remove('active', 'completed');
      if (itemStep < currentStep) {
        item.classList.add('completed');
      } else if (itemStep === currentStep) {
        item.classList.add('active');
      }
    });

    stepLines.forEach((line, index) => {
      line.classList.toggle('completed', index + 1 < currentStep);
    });

    if (btnPrev) {
      btnPrev.style.display = currentStep > 1 && currentStep <= totalSteps ? 'inline-flex' : 'none';
    }
    if (btnNext) {
      btnNext.style.display = currentStep < totalSteps ? 'inline-flex' : 'none';
    }
    if (btnSubmit) {
      btnSubmit.style.display = currentStep === totalSteps ? 'inline-flex' : 'none';
    }
    if (cancelLink) {
      cancelLink.style.display = currentStep <= totalSteps ? 'inline-flex' : 'none';
    }

    // Scroll all the way to the document top (not a fixed mid-page offset)
    // so the new step's own heading — "Give Us Your Feedback" / "Share Your
    // Thoughts" / "Review & Submit" — is what the user actually sees, on
    // every step, instead of landing mid-scroll with only the stepper
    // corner visible above the fold. Skipped on the very first render
    // (page just loaded at the top already; forcing another scroll there
    // was itself the bug).
    if (scroll) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  if (btnNext) {
    btnNext.addEventListener('click', (e) => {
      e.preventDefault();
      if (currentStep === 1 && !selectedServiceId) {
        alert('Please select a library service before proceeding.');
        return;
      }
      if (currentStep === 2 && !(textarea && textarea.value.trim().length >= 3)) {
        alert('Please share your feedback before proceeding — this is what gets classified.');
        return;
      }
      goToStep(currentStep + 1);
    });
  }

  if (btnPrev) {
    btnPrev.addEventListener('click', (e) => {
      e.preventDefault();
      goToStep(currentStep - 1);
    });
  }

  if (cancelLink) {
    cancelLink.addEventListener('click', () => {
      const proceed = currentStep > 1
        ? confirm('Are you sure you want to cancel? Your feedback entries will be cleared.')
        : true;
      if (proceed) window.location.href = form.dataset.homeUrl || '/';
    });
  }

  // Form Submit Handler — real AJAX round-trip, no fabricated success/reference code.
  form.addEventListener('submit', (e) => {
    e.preventDefault();

    if (!selectedServiceId || !(textarea && textarea.value.trim().length >= 3)) {
      alert('Please complete the service selection and write your feedback before submitting.');
      return;
    }

    if (inputService) inputService.value = selectedServiceId;
    if (inputComments && textarea) inputComments.value = textarea.value;

    const formData = new FormData(form);

    if (btnSubmit) {
      btnSubmit.disabled = true;
      btnSubmit.innerText = 'Submitting...';
    }

    fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(async (res) => {
        const data = await res.json().catch(() => null);
        if (res.ok && data && data.status === 'success') {
          showConfirmation(data);
        } else {
          const firstError = data && data.errors
            ? Object.values(data.errors)[0][0].message
            : 'Please check your responses and try again.';
          alert(`We couldn't submit your feedback: ${firstError}`);
        }
      })
      .catch(() => {
        alert('A network error occurred while submitting your feedback. Please try again.');
      })
      .finally(() => {
        if (btnSubmit) {
          btnSubmit.disabled = false;
          btnSubmit.innerHTML = 'Submit Feedback &check;';
        }
      });
  });

  function showConfirmation(data) {
    stepPanels.forEach(panel => panel.style.display = 'none');
    const confirmPanel = document.getElementById('confirmationStep');
    if (confirmPanel) confirmPanel.style.display = 'block';

    const progressBar = document.querySelector('.isu-progress-bar-card');
    if (progressBar) progressBar.style.opacity = '0.7';

    const footer = document.querySelector('.isu-form-footer');
    if (footer) footer.style.display = 'none';

    const message = document.getElementById('confirmationMessage');
    if (message && data && data.message) message.innerText = data.message;

    const refCode = document.getElementById('confirmationRefCode');
    if (refCode) refCode.innerText = (data && data.reference_code) || '—';
  }

  // Initialize
  updateSummary();
  goToStep(1, { scroll: false });
});
