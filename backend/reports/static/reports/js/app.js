// Minimal, progressive-enhancement-only JS. No framework, no build step.

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
});
