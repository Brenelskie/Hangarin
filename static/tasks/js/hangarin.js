(() => {
    const toggle = document.querySelector("#nav-toggle");
    const navigation = document.querySelector("#primary-navigation");
    const close = document.querySelector("#nav-close");
    const scrim = document.querySelector("#nav-scrim");
    const workspace = document.querySelector(".workspace");
    const mobile = window.matchMedia("(max-width: 900px)");

    if (toggle && navigation && workspace) {
        let isOpen = false;

        const focusableSelector = [
            "a[href]",
            "button:not([disabled])",
            "input:not([disabled])",
            "select:not([disabled])",
            "textarea:not([disabled])",
            "[tabindex]:not([tabindex='-1'])",
        ].join(",");

        const focusableItems = () => [...navigation.querySelectorAll(focusableSelector)]
            .filter((item) => !item.closest("[inert]") && item.getClientRects().length > 0);

        const setOpen = (open, returnFocus = false) => {
            isOpen = mobile.matches && open;
            navigation.classList.toggle("is-open", isOpen);
            document.body.classList.toggle("nav-open", isOpen);
            toggle.setAttribute("aria-expanded", String(isOpen));
            navigation.inert = mobile.matches && !isOpen;
            workspace.inert = isOpen;

            if (isOpen) {
                navigation.setAttribute("role", "dialog");
                navigation.setAttribute("aria-modal", "true");
            } else {
                navigation.removeAttribute("role");
                navigation.removeAttribute("aria-modal");
            }

            if (returnFocus) toggle.focus();
        };

        const syncViewport = () => {
            const activeElement = document.activeElement;
            const focusWasInNavigation = navigation.contains(activeElement);
            const focusWasOnClose = activeElement === close;

            setOpen(false);

            if (mobile.matches && focusWasInNavigation) {
                toggle.focus();
            } else if (!mobile.matches && focusWasOnClose) {
                navigation.querySelector("a[href]")?.focus();
            }
        };

        toggle.addEventListener("click", () => {
            setOpen(!isOpen);
            if (isOpen) (close || focusableItems()[0] || navigation).focus();
        });

        close?.addEventListener("click", () => setOpen(false, true));
        scrim?.addEventListener("click", () => setOpen(false, true));

        document.addEventListener("keydown", (event) => {
            if (!isOpen) return;

            if (event.key === "Escape") {
                event.preventDefault();
                setOpen(false, true);
                return;
            }

            if (event.key !== "Tab") return;

            const items = focusableItems();
            if (!items.length) {
                event.preventDefault();
                navigation.setAttribute("tabindex", "-1");
                navigation.focus();
                return;
            }

            const first = items[0];
            const last = items[items.length - 1];
            const activeElement = document.activeElement;

            if (!navigation.contains(activeElement)) {
                event.preventDefault();
                (event.shiftKey ? last : first).focus();
            } else if (event.shiftKey && activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        });

        navigation.addEventListener("click", (event) => {
            if (mobile.matches && event.target.closest("a")) setOpen(false);
        });
        mobile.addEventListener("change", syncViewport);
        syncViewport();
    }

    const errorSummary = document.querySelector("[data-error-summary]");
    if (errorSummary) errorSummary.focus();
})();
