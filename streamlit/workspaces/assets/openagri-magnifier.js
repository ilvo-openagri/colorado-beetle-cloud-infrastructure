(() => {
    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function initializeMagnifier(root) {
        if (root.dataset.magnifierReady === "1") {
            return;
        }

        const stage = root.querySelector(".openagri-magnifier-stage");
        const image = root.querySelector(".openagri-magnifier-image");
        const result = root.querySelector(".openagri-magnifier-result");
        if (!stage || !image || !result) {
            return;
        }

        root.dataset.magnifierReady = "1";

        const zoom = Number.parseFloat(root.dataset.zoom || "2.5");
        const lensSize = Number.parseInt(root.dataset.lensSize || "180", 10);
        const resultSize = Number.parseInt(root.dataset.resultSize || "280", 10);

        const lens = document.createElement("div");
        lens.className = "openagri-magnifier-lens";
        stage.appendChild(lens);

        result.style.width = `${resultSize}px`;
        result.style.height = `${resultSize}px`;

        function refreshResultBackground() {
            const width = image.getBoundingClientRect().width;
            const height = image.getBoundingClientRect().height;
            result.style.backgroundImage = `url("${image.src}")`;
            result.style.backgroundSize = `${width * zoom}px ${height * zoom}px`;
        }

        function hideLens() {
            lens.style.display = "none";
            result.style.opacity = "0";
        }

        function showLens() {
            lens.style.display = "block";
            result.style.opacity = "1";
        }

        function updateLens(event) {
            const rect = image.getBoundingClientRect();
            const width = rect.width;
            const height = rect.height;
            const pointerX = event.clientX - rect.left;
            const pointerY = event.clientY - rect.top;

            if (
                pointerX < 0 ||
                pointerY < 0 ||
                pointerX > width ||
                pointerY > height
            ) {
                hideLens();
                return;
            }

            showLens();

            const halfLens = lensSize / 2;
            const lensLeft = clamp(pointerX - halfLens, 0, Math.max(0, width - lensSize));
            const lensTop = clamp(pointerY - halfLens, 0, Math.max(0, height - lensSize));

            lens.style.width = `${lensSize}px`;
            lens.style.height = `${lensSize}px`;
            lens.style.left = `${lensLeft}px`;
            lens.style.top = `${lensTop}px`;

            const offsetX = pointerX * zoom - resultSize / 2;
            const offsetY = pointerY * zoom - resultSize / 2;
            result.style.backgroundPosition = `${-offsetX}px ${-offsetY}px`;
        }

        image.addEventListener("load", refreshResultBackground);
        stage.addEventListener("mouseenter", showLens);
        stage.addEventListener("mouseleave", hideLens);
        stage.addEventListener("mousemove", updateLens);
        window.addEventListener("resize", refreshResultBackground);

        if (image.complete) {
            refreshResultBackground();
        } else {
            image.addEventListener("load", refreshResultBackground, { once: true });
        }
    }

    function scan() {
        document.querySelectorAll(".openagri-magnifier").forEach(initializeMagnifier);
    }

    document.addEventListener("DOMContentLoaded", scan);
    window.addEventListener("load", scan);

    const observer = new MutationObserver(scan);
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
})();
