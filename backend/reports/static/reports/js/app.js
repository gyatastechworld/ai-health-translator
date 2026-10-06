// Minimal, progressive-enhancement-only JS. No framework, no build step.

var pollingActive = false;

document.addEventListener("DOMContentLoaded", function () {
    // Mobile navigation toggle
    var toggle = document.getElementById("mobile-menu-toggle");
    var menu = document.getElementById("mobile-menu");

    if (toggle && menu) {
        toggle.addEventListener("click", function () {
            var isOpen = !menu.hidden;
            menu.hidden = isOpen;
            toggle.setAttribute("aria-expanded", String(!isOpen));
        });
    }

    // File input name preview
    document.querySelectorAll("[data-file-input]").forEach(function (input) {
        var previewEl = document.querySelector(
            '[data-file-preview="' + input.id + '"]'
        );
        if (!previewEl) return;

        var defaultText = previewEl.textContent;

        input.addEventListener("change", function () {
            if (input.files && input.files.length > 0) {
                previewEl.textContent = input.files[0].name;
            } else {
                previewEl.textContent = defaultText;
            }
        });
    });

    // Auto-dismiss flash messages
    document.querySelectorAll("[data-alert-dismiss]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var alertEl = btn.closest("[data-alert]");
            if (alertEl) alertEl.remove();
        });
    });

    // Show a loading state on submit, so a request that takes a few
    // seconds (e.g. the upload form running text extraction) doesn't
    // look like the click did nothing.
    document.querySelectorAll("[data-loading-submit]").forEach(function (form) {
        form.addEventListener("submit", function () {
            var submitBtn = form.querySelector('button[type="submit"]');
            if (!submitBtn) return;

            submitBtn.disabled = true;
            submitBtn.dataset.originalText = submitBtn.textContent;
            submitBtn.innerHTML =
                '<span class="inline-flex items-center gap-2">' +
                '<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" ' +
                'fill="none" viewBox="0 0 24 24" aria-hidden="true">' +
                '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>' +
                '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>' +
                '</svg>' +
                (form.dataset.loadingText || "Processing...") +
                '</span>';
        });
    });

    var pollTarget = document.querySelector("[data-translation-poll]");
    if (pollTarget && !pollingActive) {
        pollingActive = true;

        var statusUrl = pollTarget.dataset.statusUrl;
        var messageEl = document.querySelector("[data-processing-message]");

        var PROCESSING_MESSAGES = [
            "Reading your report…",
            "Looking at the values…",
            "Putting it in plain language…",
            "Almost done…",
        ];
        var MAX_POLL_ATTEMPTS = 60;
        var POLL_INTERVAL_MS = 3000;

        var attemptCount = 0;
        var messageIndex = 0;

        var pollTimer = setInterval(function () {
            attemptCount += 1;

            if (messageEl && messageIndex < PROCESSING_MESSAGES.length - 1) {
                messageIndex += 1;
                messageEl.textContent = PROCESSING_MESSAGES[messageIndex];
            }

            if (attemptCount > MAX_POLL_ATTEMPTS) {
                clearInterval(pollTimer);
                pollingActive = false;

                if (messageEl) {
                    messageEl.textContent =
                        "This is taking longer than expected. Please try again.";
                }

                return;
            }

            fetch(statusUrl, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (response) {
                    return response.json();
                })
                .then(function (data) {
                    if (
                        data.processing_status === "done" ||
                        data.processing_status === "failed"
                    ) {
                        clearInterval(pollTimer);
                        pollingActive = false;
                        window.location.reload();
                    }
                })
                .catch(function () {});
        }, POLL_INTERVAL_MS);
    }
});
